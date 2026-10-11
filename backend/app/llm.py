
import json
import os
import re
from urllib.request import Request, urlopen

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct-1M:fastest")


def generate_grounded_answer(question: str, passages: list[dict]) -> str:
    if not passages:
        return "The available evidence is insufficient to answer this question."

    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "extractive":
        stop_words = {
            "about", "after", "are", "available", "does", "for", "from",
            "how", "many", "what", "when", "where", "which", "who", "why",
            "with", "the", "and", "that", "this", "was", "were", "will",
        }
        question_terms = {
            word.lower()
            for word in re.findall(r"[A-Za-z0-9]+", question)
            if len(word) > 2 and word.lower() not in stop_words
        }
        candidates = []
        for passage_index, passage in enumerate(passages):
            for sentence_index, sentence in enumerate(
                re.split(r"(?<=[.!?])\s+", passage["content"].strip())
            ):
                sentence = sentence.strip()
                if sentence:
                    sentence_terms = {
                        word.lower()
                        for word in re.findall(r"[A-Za-z0-9]+", sentence)
                    }
                    score = len(question_terms & sentence_terms)
                    candidates.append(
                        (score, -passage_index, -sentence_index, sentence, passage["source_id"])
                    )

        if candidates:
            _, _, _, sentence, source_id = max(candidates)
            return f"{sentence} [{source_id}]"
        return f"{passages[0]['content'].strip()} [{passages[0]['source_id']}]"

    evidence = "\n\n".join(
        f"[{p['source_id']}] {p['content']}"
        for p in passages
    )

    prompt = f"""You are VerseRAG, a precise, evidence-grounded policy assistant.

Rules:
- Answer the question directly using only the evidence.
- Cite each factual answer with its supporting source ID, e.g. [S1].
- If the evidence explicitly states a fact, report it directly. Never claim it is missing.
- Respect the document version selected by retrieval. Never invent a version label.
- If evidence is incomplete, state exactly what is known and what is unknown.
- Do not refuse ordinary policy questions.
- Do not contradict yourself or repeat the question.
- Keep the answer to 1-3 sentences.
- Never invent facts or citations.

QUESTION:
{question}

EVIDENCE:
{evidence}

ANSWER:"""

    try:
        if provider == "huggingface":
            if not HF_TOKEN:
                raise RuntimeError("HF_TOKEN is required for Hugging Face inference.")

            payload = json.dumps({
                "model": HF_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 180,
                "stream": False,
            }).encode("utf-8")
            request = Request(
                "https://router.huggingface.co/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {HF_TOKEN}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = result["choices"][0]["message"]["content"].strip()
        else:
            payload = json.dumps({
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
                "options": {"temperature": 0, "num_predict": 120},
            }).encode("utf-8")
            request = Request(
                f"{OLLAMA_URL.rstrip('/')}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = result.get("response", "").strip()
    except Exception as exc:
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        raise RuntimeError(f"{provider} generation failed: {exc}") from exc

    if not answer:
        raise RuntimeError("The configured model provider returned an empty answer.")

    return answer


def validate_source_ids(answer: str, passages: list[dict]) -> dict:
    valid_ids = {p["source_id"] for p in passages}
    cited_ids = list(dict.fromkeys(re.findall(r"\[(S\d+)\]", answer)))
    invalid_ids = [sid for sid in cited_ids if sid not in valid_ids]

    return {
        "cited_source_ids": cited_ids,
        "invalid_source_ids": invalid_ids,
        "all_citations_valid": bool(cited_ids) and not invalid_ids,
    }

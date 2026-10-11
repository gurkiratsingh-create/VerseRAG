
import json
import os
import re
from urllib.request import Request, urlopen

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def generate_grounded_answer(question: str, passages: list[dict]) -> str:
    if not passages:
        return "The available evidence is insufficient to answer this question."

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

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_predict": 120,
        },
    }).encode("utf-8")

    request = Request(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Local Ollama generation failed: {exc}"
        ) from exc

    answer = result.get("response", "").strip()

    if not answer:
        raise RuntimeError("Ollama returned an empty answer.")

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

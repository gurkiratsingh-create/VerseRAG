
import argparse
import csv
import json
import re
import statistics
import time
from pathlib import Path

import requests


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def answer_matches(expected, answer):
    if not answer:
        return False

    expected_norm = normalize(expected)
    answer_norm = normalize(answer)

    aliases = {
        "twice per year": ["twice annually", "two times per year"],
        "once per quarter": ["quarterly", "four times per year"],
        "not stated in the handbook": [
            "not mentioned in the handbook",
            "not specified in the handbook",
            "the handbook does not state",
        ],
        "insufficient evidence for this specific scenario": [
            "insufficient information",
            "cannot determine from the handbook",
        ],
    }

    candidates = [expected_norm]
    candidates.extend(
        normalize(alias)
        for key, values in aliases.items()
        if normalize(key) in expected_norm
        for alias in values
    )

    return any(candidate and candidate in answer_norm for candidate in candidates)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate VerseRAG on a question CSV."
    )
    parser.add_argument("--csv", required=True, help="Evaluation CSV path")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--document-key", default="hand1")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", default="evaluation_results")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        questions = list(csv.DictReader(file))

    if not questions:
        raise SystemExit("The evaluation CSV contains no questions.")

    results = []
    session = requests.Session()

    for row in questions:
        question_id = row["question_id"]
        question = row["question"]
        expected = row["expected_answer_or_fact"]
        expected_version = row["expected_version"].strip()
        as_of = row["as_of"]

        payload = {
            "question": question,
            "as_of": as_of,
            "document_key": args.document_key,
            "top_k": args.top_k,
        }

        start = time.perf_counter()

        try:
            response = session.post(
                f"{args.url.rstrip('/')}/documents/answer",
                json=payload,
                timeout=180,
            )
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            response.raise_for_status()
            data = response.json()

            answer = data.get("answer") or ""
            citations = data.get("citations") or []

            retrieved_versions = sorted({
                str(citation.get("version"))
                for citation in citations
                if citation.get("version")
            })

            if expected_version in {"v1", "v2"}:
                version_correct = expected_version in retrieved_versions
            else:
                version_correct = None

            # Check that every source ID referenced by the answer
            # corresponds to a source returned by the API.
            referenced_ids = set(
                re.findall(r"\bS\d+\b", answer)
            )
            available_ids = {
                str(citation["source_id"])
                for citation in citations
                if citation.get("source_id")
            }
            citation_ids_valid = referenced_ids.issubset(available_ids)

            results.append({
                "question_id": question_id,
                "as_of": as_of,
                "expected_version": expected_version,
                "retrieved_versions": ";".join(retrieved_versions),
                "version_correct": version_correct,
                "expected_answer": expected,
                "answer": answer,
                "answer_keyword_match": answer_matches(expected, answer),
                "citation_ids_valid": citation_ids_valid,
                "has_citations": bool(citations),
                "citation_count": len(citations),
                "latency_ms": latency_ms,
                "error": "",
            })

            print(
                f"{question_id}: version={retrieved_versions}, "
                f"answer_match={answer_matches(expected, answer)}, "
                f"latency={latency_ms} ms"
            )

        except (requests.RequestException, ValueError) as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            results.append({
                "question_id": question_id,
                "as_of": as_of,
                "expected_version": expected_version,
                "retrieved_versions": "",
                "version_correct": None,
                "expected_answer": expected,
                "answer": "",
                "answer_keyword_match": False,
                "citation_ids_valid": False,
                "has_citations": False,
                "citation_count": 0,
                "latency_ms": latency_ms,
                "error": str(exc),
            })
            print(f"{question_id}: ERROR - {exc}")

    successful = [row for row in results if not row["error"]]
    version_rows = [
        row for row in successful
        if row["expected_version"] in {"v1", "v2"}
    ]

    def rate(values):
        values = list(values)
        if not values:
            return None
        return round(sum(bool(value) for value in values) / len(values) * 100, 2)

    latencies = [row["latency_ms"] for row in successful]

    summary = {
        "dataset": str(csv_path),
        "document_key": args.document_key,
        "total_questions": len(results),
        "successful_requests": len(successful),
        "failed_requests": len(results) - len(successful),
        "temporal_version_accuracy_pct": rate(
            row["version_correct"] for row in version_rows
        ),
        "temporal_version_questions": len(version_rows),
        "answer_keyword_match_pct": rate(
            row["answer_keyword_match"] for row in successful
        ),
        "citation_id_validity_pct": rate(
            row["citation_ids_valid"] for row in successful
        ),
        "answers_with_citations_pct": rate(
            row["has_citations"] for row in successful
        ),
        "mean_latency_ms": (
            round(statistics.mean(latencies), 2) if latencies else None
        ),
        "median_latency_ms": (
            round(statistics.median(latencies), 2) if latencies else None
        ),
        "note": (
            "Answer matching is lexical, not semantic. Citation ID validity "
            "does not establish factual support. Version accuracy checks "
            "whether the expected version appears among returned citations."
        ),
    }

    results_path = output_dir / "per_question_results.csv"
    with results_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("\n=== VerseRAG Evaluation Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nPer-question results: {results_path.resolve()}")
    print(f"Summary: {summary_path.resolve()}")


if __name__ == "__main__":
    main()

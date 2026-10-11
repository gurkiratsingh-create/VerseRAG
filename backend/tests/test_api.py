
from fastapi.testclient import TestClient
from app.main import app
from app.llm import validate_source_ids


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200


def test_answer_requires_question():
    response = client.post(
        "/documents/answer",
        json={
            "document_key": "leave123",
            "as_of": "2025-06-01",
        },
    )
    assert response.status_code == 422


def test_answer_returns_version_citation():
    response = client.post(
        "/documents/answer",
        json={
            "question": "How many days of annual leave are available to full-time employees?",
            "document_key": "leave123",
            "as_of": "2025-06-01",
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["answer_type"] == "llm_grounded"
    assert data["answer"]
    assert data["citations"]
    assert data["citations"][0]["version"] == "v1"
    assert "18 days of annual leave" in data["citations"][0]["quoted_text"]
    assert data["citation_validation"]["all_citations_valid"] is True


def test_answer_uses_new_version_for_2026():
    response = client.post(
        "/documents/answer",
        json={
            "question": "How many days of annual leave are available to full-time employees?",
            "document_key": "leave123",
            "as_of": "2026-06-01",
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["answer_type"] == "llm_grounded"
    assert data["citations"]
    assert data["citations"][0]["version"] == "v2"
    assert "24 days of annual leave" in data["citations"][0]["quoted_text"]
    assert data["citation_validation"]["all_citations_valid"] is True


def test_answer_returns_empty_evidence_for_unknown_document():
    response = client.post(
        "/documents/answer",
        json={
            "question": "What is the annual leave allowance?",
            "document_key": "verserag-test-document-that-does-not-exist",
            "as_of": "2025-06-01",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["message"] == "No relevant published evidence was found."


def test_valid_source_id_passes_validation():
    result = validate_source_ids(
        "Employees receive 18 days of leave [S1].",
        [{"source_id": "S1", "content": "Employees receive 18 days of leave."}],
    )

    assert result["cited_source_ids"] == ["S1"]
    assert result["invalid_source_ids"] == []
    assert result["all_citations_valid"] is True


def test_fabricated_source_id_fails_validation():
    result = validate_source_ids(
        "Employees receive 18 days of leave [S9].",
        [{"source_id": "S1", "content": "Employees receive 18 days of leave."}],
    )

    assert result["cited_source_ids"] == ["S9"]
    assert result["invalid_source_ids"] == ["S9"]
    assert result["all_citations_valid"] is False


def test_missing_citation_fails_validation():
    result = validate_source_ids(
        "Employees receive 18 days of leave.",
        [{"source_id": "S1", "content": "Employees receive 18 days of leave."}],
    )

    assert result["all_citations_valid"] is False

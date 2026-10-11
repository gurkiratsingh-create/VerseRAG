
from app.routes import extract_policy_facts


def test_extract_annual_leave():
    facts = extract_policy_facts(
        "Employees receive 18 days of annual leave per year."
    )

    assert len(facts) == 1
    assert facts[0]["value"] == 18
    assert facts[0]["unit"] == "days"
    assert "annual leave" in facts[0]["concept"]


def test_extract_multiple_quantities():
    facts = extract_policy_facts(
        "Employees receive 24 days of annual leave. "
        "Unused annual leave can be carried forward up to 8 days."
    )

    assert len(facts) == 2
    assert {fact["value"] for fact in facts} == {8, 24}


def test_no_numeric_policy_facts():
    facts = extract_policy_facts(
        "Employees should request leave in advance."
    )

    assert facts == []

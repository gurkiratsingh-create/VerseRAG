

from app.routes import (
    extract_policy_facts,
    normalize_concept,
    comparable_value,
)


def test_equivalent_week_and_day_quantities():
    old = extract_policy_facts(
        "Employees can take five weeks of parental leave."
    )
    new = extract_policy_facts(
        "Eligible employees receive 35 days for parental leave."
    )

    old_fact = next(f for f in old if "parental leave" in f["concept"])
    new_fact = next(f for f in new if "parental leave" in f["concept"])

    old_value, old_unit = comparable_value(
        old_fact["value"], old_fact["unit"]
    )
    new_value, new_unit = comparable_value(
        new_fact["value"], new_fact["unit"]
    )

    assert normalize_concept(old_fact["concept"]) == normalize_concept(new_fact["concept"])
    assert old_unit == new_unit
    assert old_value == new_value


def test_days_and_weeks_convert_to_same_base_unit():
    assert comparable_value(5, "weeks") == (35, "time_days")
    assert comparable_value(35, "days") == (35, "time_days")


def comparable_value(value, unit):
    if value is None:
        return None, unit

    if isinstance(value, bool):
        return value, str(unit).lower() if unit is not None else None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None, unit
        try:
            value = float(stripped)
        except ValueError:
            return value, str(unit).lower() if unit is not None else None

    unit_key = str(unit).strip().lower() if unit is not None else ""
    conversion = {
        "day": ("day", 1.0),
        "days": ("day", 1.0),
        "d": ("day", 1.0),
        "week": ("day", 7.0),
        "weeks": ("day", 7.0),
        "wk": ("day", 7.0),
        "wks": ("day", 7.0),
        "month": ("day", 30.0),
        "months": ("day", 30.0),
        "mo": ("day", 30.0),
        "year": ("day", 365.0),
        "years": ("day", 365.0),
        "yr": ("day", 365.0),
        "yrs": ("day", 365.0),
        "hour": ("hour", 1.0),
        "hours": ("hour", 1.0),
        "hr": ("hour", 1.0),
        "hrs": ("hour", 1.0),
        "minute": ("minute", 1.0),
        "minutes": ("minute", 1.0),
        "min": ("minute", 1.0),
        "mins": ("minute", 1.0),
        "second": ("second", 1.0),
        "seconds": ("second", 1.0),
        "sec": ("second", 1.0),
        "secs": ("second", 1.0),
    }

    canonical_unit = conversion.get(unit_key, (unit_key, 1.0))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) * canonical_unit[1], canonical_unit[0]

    return value, canonical_unit[0]


def compare_facts(old_text: str, new_text: str) -> list[dict]:
    old_facts = extract_policy_facts(old_text)
    new_facts = extract_policy_facts(new_text)

    def build_map(facts):
        result = {}

        for fact in facts:
            normalized_value, canonical_unit = comparable_value(
                fact["value"],
                fact["unit"],
            )
            key = (
                normalize_concept(fact["concept"]),
                canonical_unit,
            )

            result[key] = {
                **fact,
                "comparison_value": normalized_value,
            }

        return result

    old_map = build_map(old_facts)
    new_map = build_map(new_facts)

    changes = []

    for key in old_map.keys() | new_map.keys():
        old = old_map.get(key)
        new = new_map.get(key)

        if old is None:
            changes.append({
                "concept": new["concept"],
                "change_type": "added",
                "old_value": None,
                "new_value": new["value"],
            })
            continue

        if new is None:
            changes.append({
                "concept": old["concept"],
                "change_type": "removed",
                "old_value": old["value"],
                "new_value": None,
            })
            continue

        old_value = old["value"]
        new_value = new["value"]
        old_comparable = old.get("comparison_value")
        new_comparable = new.get("comparison_value")

        if old_value == new_value:
            continue

        if (
            isinstance(old_comparable, (int, float))
            and not isinstance(old_comparable, bool)
            and isinstance(new_comparable, (int, float))
            and not isinstance(new_comparable, bool)
        ):
            change_type = (
                "increased" if new_comparable > old_comparable else "decreased"
            )
        else:
            change_type = "modified"

        changes.append({
            "concept": old["concept"],
            "change_type": change_type,
            "old_value": old_value,
            "new_value": new_value,
        })

    return changes


def test_detect_increase():
    changes = compare_facts(
        "Employees receive 18 days of annual leave.",
        "Employees receive 24 days of annual leave.",
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "increased"
    assert changes[0]["old_value"] == 18
    assert changes[0]["new_value"] == 24


def test_detect_decrease():
    changes = compare_facts(
        "Employees receive 24 days of annual leave.",
        "Employees receive 18 days of annual leave.",
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "decreased"


def test_detect_added_fact():
    changes = compare_facts(
        "Employees receive 18 days of annual leave.",
        "Employees receive 18 days of annual leave. Employees receive 5 weeks of parental leave.",
    )

    assert any(change["change_type"] == "added" for change in changes)


def test_detect_removed_fact():
    changes = compare_facts(
        "Employees receive 18 days of annual leave. Employees receive 5 weeks of parental leave.",
        "Employees receive 18 days of annual leave.",
    )

    assert any(change["change_type"] == "removed" for change in changes)

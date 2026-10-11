
from app.routes import extract_policy_facts, classify_policy_change


def test_extracts_leave_carry_forward_expiry():
    old = extract_policy_facts(
        "Carried-forward days must be used by March 31 unless local law requires a longer period."
    )
    new = extract_policy_facts(
        "Carried-forward days must be used by June 30 unless local law requires a longer period."
    )

    old_fact = next(f for f in old if f["concept"] == "leave carry-forward expiry")
    new_fact = next(f for f in new if f["concept"] == "leave carry-forward expiry")

    assert old_fact["value"] == "March 31"
    assert new_fact["value"] == "June 30"
    assert old_fact["unit"] == new_fact["unit"] == "date"


def test_shorter_advance_leave_notice_is_employee_favorable():
    assert classify_policy_change("advance leave notice", 7, 5) == "more_employee_favorable"


def test_shorter_payslip_reporting_window_is_less_favorable():
    assert classify_policy_change("payslip error reporting deadline", 10, 5) == "less_employee_favorable"


def test_longer_expense_claim_deadline_is_employee_favorable():
    assert classify_policy_change("expense claim deadline", 30, 45) == "more_employee_favorable"

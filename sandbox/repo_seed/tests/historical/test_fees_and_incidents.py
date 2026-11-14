"""FICTIONAL – PayRo SRL demo. Historical behaviour that must keep working after any change."""
from datetime import datetime, timedelta

from payments.fees import fee_for, load_fees
from payments.incidents import final_report_deadline, reporting_plan


def test_fee_table_has_both_currencies_and_no_negative_fee():
    fees = load_fees()
    assert set(fees) == {"ron", "eur"}
    for currency in fees.values():
        assert set(currency) == {"standard", "instant"}
        assert all(value >= 0 for value in currency.values())


def test_standard_euro_transfer_is_not_free():
    """Product decision 2024: the standard euro transfer fee covers scheme costs and stays above zero."""
    assert fee_for("EUR", instant=False) > 0


def test_plan_starts_with_the_initial_report_and_ends_with_the_final_one():
    aware = datetime(2025, 3, 3, 10, 0)
    plan = reporting_plan(aware, aware + timedelta(hours=1))
    assert plan[0]["report"] == "initial" and plan[-1]["report"] == "final"
    dues = [step["due"] for step in plan]
    assert dues == sorted(dues) and dues[0] > aware


def test_final_report_is_due_after_the_previous_report():
    previous = datetime(2025, 3, 3, 10, 0)
    assert final_report_deadline(previous) > previous

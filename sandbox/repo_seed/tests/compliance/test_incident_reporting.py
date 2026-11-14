"""FICTIONAL – PayRo SRL demo. Compliance test.

Commission Delegated Regulation (EU) 2025/301, Article 5: initial notification within four hours of
classification as major and no later than 24 hours from awareness (5(1)(a)); if classified later than
that, within four hours of classification (5(2)); intermediate report within 72 hours of the initial
notification (5(1)(b)); final report no later than one month after the intermediate report (5(1)(c)).
"""
from datetime import datetime, timedelta

from payments.incidents import initial_report_deadline, reporting_plan

AWARE = datetime(2025, 3, 3, 10, 0)


def test_initial_notification_is_due_four_hours_after_classification():
    assert initial_report_deadline(AWARE, AWARE + timedelta(hours=2)) == AWARE + timedelta(hours=6)


def test_initial_notification_is_never_later_than_24_hours_after_awareness():
    assert initial_report_deadline(AWARE, AWARE + timedelta(hours=23)) == AWARE + timedelta(hours=24)


def test_late_classification_gives_four_hours_from_classification():
    classified = AWARE + timedelta(hours=48)
    assert initial_report_deadline(AWARE, classified) == classified + timedelta(hours=4)


def test_plan_has_an_intermediate_report_72_hours_after_the_initial_one():
    plan = reporting_plan(AWARE, AWARE + timedelta(hours=2))
    assert [step["report"] for step in plan] == ["initial", "intermediate", "final"]
    assert plan[1]["due"] - plan[0]["due"] == timedelta(hours=72)


def test_final_report_is_due_one_month_after_the_intermediate_report():
    plan = reporting_plan(AWARE, AWARE + timedelta(hours=2))
    assert timedelta(days=28) <= plan[2]["due"] - plan[1]["due"] <= timedelta(days=31)

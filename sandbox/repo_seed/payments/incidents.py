"""FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo.

Deadlines for reporting major ICT incidents to the National Bank of Romania.
"""
from __future__ import annotations

from datetime import datetime, timedelta

INITIAL_REPORT_HOURS = 24
FINAL_REPORT_DAYS = 30


def initial_report_deadline(aware_at: datetime, classified_at: datetime) -> datetime:
    """When the initial notification of a major incident is due."""
    return aware_at + timedelta(hours=INITIAL_REPORT_HOURS)


def final_report_deadline(previous_report_at: datetime) -> datetime:
    """When the final report is due, counted from the previous report."""
    return previous_report_at + timedelta(days=FINAL_REPORT_DAYS)


def reporting_plan(aware_at: datetime, classified_at: datetime) -> list[dict]:
    """The reports to send for one major incident, in order, each with its due time."""
    initial = initial_report_deadline(aware_at, classified_at)
    return [
        {"report": "initial", "due": initial},
        {"report": "final", "due": final_report_deadline(initial)},
    ]

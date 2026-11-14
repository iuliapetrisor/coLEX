"""Contracts for what the agents produce for humans (brief §4.2)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from colex.contracts.common import Confidence, Contract, LineRange, NonBlank, NonNegInt

Action = Literal[
    "CONTRACT_REVIEW", "TERMS_UPDATE", "FEE_CHANGE", "POLICY_UPDATE",
    "CODE_CHANGE", "CONFIG_CHANGE", "NO_ACTION",
]
# There is no "merged" status: coLEX never merges (brief §1.3, step 7).
ChangeStatus = Literal["draft", "awaiting_review", "approved", "changes_requested", "needs_human"]


class ImpactItem(Contract):
    """One affected place in one resource. Every item carries uri + lines and a citation.

    `owner_team=None` means the owner is unknown; such items are routed to #compliance.
    """

    item_id: NonBlank
    article_id: NonBlank
    resource_uri: NonBlank
    lines: LineRange
    action: Action
    owner_team: str | None = None
    evidence: NonBlank
    citation: NonBlank
    confidence: Confidence
    deadline: date | None = None


class Question(Contract):
    """`blocking_items` holds the `item_id`s of the impact items that wait for the answer."""

    to_team: NonBlank
    text: NonBlank
    options: list[str] = Field(default_factory=list)
    blocking_items: list[str] = Field(default_factory=list)


class Notification(Contract):
    channel: NonBlank
    title: NonBlank
    body: str
    items: list[ImpactItem] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class SuiteResult(Contract):
    """Outcome of one sandboxed test run."""

    passed: NonNegInt
    failed: NonNegInt
    errors: NonNegInt = 0
    failing_tests: list[str] = Field(default_factory=list)


class ChangeRequest(Contract):
    branch: NonBlank
    diff: str
    tests_before: SuiteResult
    tests_after: SuiteResult | None = None
    iterations: NonNegInt
    status: ChangeStatus

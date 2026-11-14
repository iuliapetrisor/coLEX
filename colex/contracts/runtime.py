"""Runtime contracts: runs, checkpoints, audit events, config versions (brief §4.2, §4.4).

Checkpoints and config versions must never hold secrets or un-redacted personal data.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, Field

from colex.contracts.common import Contract, NonBlank, NonNegFinite, NonNegInt
from colex.contracts.work import Question

RunStatus = Literal["running", "waiting_for_legal", "waiting_for_review", "failed", "done", "cancelled"]


class AuditEvent(Contract):
    ts: AwareDatetime
    agent: NonBlank
    step: NonBlank
    input_ref: str | None = None
    output_ref: str | None = None
    tokens_in: NonNegInt = 0
    tokens_out: NonNegInt = 0
    cost_usd: NonNegFinite = 0.0
    duration_ms: NonNegInt = 0
    run_id: str | None = None
    model: str | None = None


class Run(Contract):
    """`law_id` is the CELEX number. `branches` maps a branch id to its status."""

    run_id: NonBlank
    law_id: NonBlank
    status: RunStatus
    current_node: NonBlank
    branches: dict[str, RunStatus] = Field(default_factory=dict)
    config_version_id: NonBlank
    map_version_id: str | None = None
    parent_checkpoint_id: str | None = None


class Checkpoint(Contract):
    checkpoint_id: NonBlank
    run_id: NonBlank
    branch_id: NonBlank
    node: NonBlank
    state_ref: NonBlank
    pending_questions: list[Question] = Field(default_factory=list)
    git_ref: str | None = None
    budgets_used: dict[str, NonNegFinite] = Field(default_factory=dict)
    config_version_id: NonBlank
    map_version_id: str | None = None
    parent_id: str | None = None
    ts: AwareDatetime


class ConfigVersion(Contract):
    version_id: NonBlank
    hash: NonBlank
    author: NonBlank
    ts: AwareDatetime
    diff: str = ""
    payload: dict[str, Any]

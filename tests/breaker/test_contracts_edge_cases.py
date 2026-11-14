"""Code Breaker: edge cases the data contracts must reject."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from colex import contracts as c
from tests.contract.payloads import VALID

NAIVE_TS = "2026-11-14T10:00:00"


@pytest.mark.parametrize("name", ["AuditEvent", "Checkpoint", "ConfigVersion"])
def test_timestamps_without_timezone_are_rejected(name):
    with pytest.raises(ValidationError):
        getattr(c, name).model_validate({**VALID[name], "ts": NAIVE_TS})


@pytest.mark.xfail(strict=True, reason="R-004")
@pytest.mark.parametrize(
    "owner_team, ownership_source",
    [(None, "explicit"), (None, "inferred"), ("legal", "unknown")],
)
def test_ownership_source_must_agree_with_owner_team(owner_team, ownership_source):
    payload = {**VALID["ResourceCard"], "owner_team": owner_team, "ownership_source": ownership_source}
    with pytest.raises(ValidationError):
        c.ResourceCard.model_validate(payload)


@pytest.mark.xfail(strict=True, reason="R-005")
@pytest.mark.parametrize("value", [math.inf, math.nan, -1.0])
def test_checkpoint_budgets_must_be_finite_and_non_negative(value):
    with pytest.raises(ValidationError):
        c.Checkpoint.model_validate({**VALID["Checkpoint"], "budgets_used": {"cost_usd": value}})


@pytest.mark.xfail(strict=True, reason="R-006")
@pytest.mark.parametrize(
    "field, value",
    [("options", ["yes", ""]), ("options", ["yes", "yes"]), ("blocking_items", ["  "])],
)
def test_question_options_and_blocking_items_are_non_blank_and_unique(field, value):
    with pytest.raises(ValidationError):
        c.Question.model_validate({**VALID["Question"], field: value})

"""Data contracts of brief §4.2: presence, JSON round trip, and the rules they enforce."""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from colex import contracts as c
from colex.contracts.map import EdgeKind, InfoType
from colex.contracts.runtime import RunStatus
from colex.contracts.work import Action, ChangeStatus
from tests.contract.payloads import ITEM, VALID

# The 17 models listed in brief §4.2, written out so a missing payload cannot hide a missing model.
BRIEF_MODELS = [
    "TaxonomyNode", "ResourceCard", "Counterparty", "Fragment", "Entity", "Edge",
    "LawDocument", "LawArticle", "TriageResult", "ImpactItem", "Question", "Notification",
    "ChangeRequest", "AuditEvent", "Run", "Checkpoint", "ConfigVersion",
]


def test_every_brief_model_is_exported_and_has_a_payload():
    assert c.CONTRACTS_VERSION == "2"
    assert [n for n in BRIEF_MODELS if n not in c.__all__ or not hasattr(c, n)] == []
    assert sorted(VALID) == sorted(BRIEF_MODELS)


@pytest.mark.parametrize("name", BRIEF_MODELS)
def test_json_round_trip(name):
    model = getattr(c, name)
    first = model.model_validate(VALID[name])
    assert model.model_validate_json(first.model_dump_json()) == first


@pytest.mark.parametrize("name", BRIEF_MODELS)
def test_unknown_field_is_rejected(name):
    with pytest.raises(ValidationError):
        getattr(c, name).model_validate({**VALID[name], "not_a_field": 1})


@pytest.mark.parametrize("lines", [{"start": 0, "end": 3}, {"start": 5, "end": 4}, {"start": -1, "end": -1}])
def test_line_range_must_be_one_based_and_ordered(lines):
    with pytest.raises(ValidationError):
        c.LineRange.model_validate(lines)


@pytest.mark.parametrize("field", ["citation", "evidence", "resource_uri", "article_id", "item_id"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_impact_item_needs_evidence_and_citation(field, blank):
    with pytest.raises(ValidationError):
        c.ImpactItem.model_validate({**ITEM, field: blank})


def test_impact_item_needs_lines():
    with pytest.raises(ValidationError):
        c.ImpactItem.model_validate({k: v for k, v in ITEM.items() if k != "lines"})


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_confidence_is_between_zero_and_one(value):
    with pytest.raises(ValidationError):
        c.ImpactItem.model_validate({**ITEM, "confidence": value})


def test_unknown_owner_is_allowed_and_explicit():
    assert c.ImpactItem.model_validate({**ITEM, "owner_team": None}).owner_team is None


def test_closed_vocabularies_match_the_brief():
    assert set(get_args(Action)) == {
        "CONTRACT_REVIEW", "TERMS_UPDATE", "FEE_CHANGE", "POLICY_UPDATE",
        "CODE_CHANGE", "CONFIG_CHANGE", "NO_ACTION",
    }
    assert set(get_args(EdgeKind)) == {
        "governed_by", "implements", "same_counterparty", "references",
        "depends_on", "same_owner", "regulated_by",
    }
    assert set(get_args(RunStatus)) == {
        "running", "waiting_for_legal", "waiting_for_review", "failed", "done", "cancelled",
    }
    assert set(get_args(InfoType)) == {
        "contract", "customer_terms", "fee_schedule", "policy", "procedure", "register",
        "code", "config", "ticket", "page", "prompt", "law",
    }


def test_a_change_request_can_never_be_merged():
    assert "merged" not in get_args(ChangeStatus)
    with pytest.raises(ValidationError):
        c.ChangeRequest.model_validate({**VALID["ChangeRequest"], "status": "merged"})


def test_negative_token_counts_are_rejected():
    with pytest.raises(ValidationError):
        c.AuditEvent.model_validate({**VALID["AuditEvent"], "tokens_in": -1})


def test_infinite_cost_is_rejected():
    with pytest.raises(ValidationError):
        c.AuditEvent.model_validate({**VALID["AuditEvent"], "cost_usd": float("inf")})

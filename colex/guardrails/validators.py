"""Grounding validator (brief §4.3): a claim without evidence never reaches a human.

Deterministic. An impact item is accepted only when its article exists in the stored law, its
resource exists in the map version of the run, its lines are in range, its quote is verbatim in
those lines, and its deadline (if any) is a date written in the cited article.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from colex.contracts import LawDocument
from colex.guardrails.redaction import RedactionCtx, mask, redact

ACTIONS = ("CONTRACT_REVIEW", "TERMS_UPDATE", "FEE_CHANGE", "POLICY_UPDATE", "CODE_CHANGE", "CONFIG_CHANGE")
CODE_ACTIONS = ("CODE_CHANGE", "CONFIG_CHANGE")
# One action per kind of resource. Tickets and pages are context: nothing to change in them.
ACTION_FOR = {"contract": "CONTRACT_REVIEW", "customer_terms": "TERMS_UPDATE", "fee_schedule": "FEE_CHANGE",
              "policy": "POLICY_UPDATE", "procedure": "POLICY_UPDATE", "code": "CODE_CHANGE",
              "config": "CONFIG_CHANGE"}


class Rejected(ValueError):
    """Why an item was rejected; the message goes back to the model."""


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def citation(law: LawDocument, article_id: str) -> str:
    return f"CELEX:{law.celex} {article_id}"


def check_item(raw: dict[str, Any], law: LawDocument, flagged: list[str], tools) -> dict[str, Any]:
    """Validate one reported item. Returns normalized fields or raises Rejected."""
    article = next((a for a in law.articles if a.id == raw.get("article_id")), None)
    if article is None:
        raise Rejected(f"article '{raw.get('article_id')}' is not in the stored text of {law.celex}; "
                       f"use one of: {', '.join(flagged)}")
    if raw.get("action") not in ACTIONS:
        raise Rejected(f"action must be one of {', '.join(ACTIONS)}")
    uri = str(raw.get("resource_uri"))
    lines = tools.lines(uri)   # unmetered: validation must not count as agent reading
    if lines is None:
        raise Rejected(f"evidence not found: '{uri}' is not a resource in the map")
    try:
        start, end = int(raw["start"]), int(raw["end"])
    except (KeyError, TypeError, ValueError):
        raise Rejected("start and end must be line numbers") from None
    if start < 1 or end < start or end > len(lines):
        raise Rejected(f"lines {start}-{end} are outside the resource ({len(lines)} lines)")
    if end - start > 39:
        raise Rejected("cite at most 40 lines; narrow the range to the lines that matter")
    body = "\n".join(lines[start - 1:end])
    quote = _flat(str(raw.get("quote", "")))
    if len(quote) < 4:
        raise Rejected("quote is missing; copy the relevant text exactly from the cited lines")
    if quote not in _flat(body) and quote not in _flat(redact(body, RedactionCtx())):
        raise Rejected(f"quote is not verbatim in {uri} lines {start}-{end}; read the lines and copy exactly")
    info_type = tools.card(uri)["info_type"]
    if info_type not in ACTION_FOR:
        raise Rejected(f"a {info_type} is context, not a place to change; report the document, configuration "
                       "or code it points to instead")
    if raw["action"] != ACTION_FOR[info_type]:
        raise Rejected(f"for a resource of type '{info_type}' the action must be {ACTION_FOR[info_type]}")
    deadline = raw.get("deadline") or None
    if deadline:
        try:
            date.fromisoformat(str(deadline))
        except ValueError:
            raise Rejected("deadline must be YYYY-MM-DD") from None
        if date.fromisoformat(str(deadline)) not in article.effective_dates:
            raise Rejected(f"deadline {deadline} is not a date written in {article.id}; "
                           "leave it out unless the cited article states it")
    if not str(raw.get("obligation", "")).strip():
        raise Rejected("obligation is missing")
    confidence = raw.get("confidence", 0.5)
    confidence = min(max(float(confidence), 0.0), 1.0) if isinstance(confidence, (int, float)) else 0.5
    return {"article_id": article.id, "resource_uri": uri, "lines": {"start": start, "end": end},
            "action": raw["action"], "evidence": mask(quote)[:400], "citation": citation(law, article.id),
            "confidence": confidence, "deadline": str(deadline) if deadline else None,
            "obligation": _flat(str(raw["obligation"]))[:400]}

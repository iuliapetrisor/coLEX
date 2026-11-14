"""Triage: is this act relevant for this company? Deterministic profile matching (LLM half comes next)."""
from __future__ import annotations

import re
from typing import Any

from colex.contracts import LawDocument, TriageResult

# Scope terms that name the company's entity type or activities in an act's scope articles.
PROFILE_TERMS = {
    "payment institution": "entity type: payment institution",
    "payment service provider": "activity: payment services",
    "PSP": "activity: payment services",
    "credit transfer": "activity: credit transfers",
    "financial entit": "regulated financial entity",
}


def profile_match(law: LawDocument, profile: dict[str, Any]) -> list[str]:
    """Profile facts that the act's text mentions, deterministically."""
    text = " ".join([law.title] + [a.text for a in law.articles])
    facts = []
    for term, fact in PROFILE_TERMS.items():
        pattern = rf"\b{re.escape(term)}" if term != "PSP" else r"\bPSPs?\b"
        if re.search(pattern, text, re.I if term != "PSP" else 0) and fact not in facts:
            facts.append(fact)
    return facts


def run(ctx, law: LawDocument, deps=None) -> dict[str, Any]:
    """STUB (walking skeleton): deterministic matching only, no model call yet."""
    facts = profile_match(law, ctx.config["profile"])
    relevant = bool(facts)
    result = TriageResult(
        law_id=law.celex, relevant=relevant, articles_flagged=[a.id for a in law.articles] if relevant else [],
        reason=("Mentions: " + "; ".join(facts)) if relevant else
        "No scope term matches the company profile (payment institution, payment services).",
        confidence=0.6, matched_profile_facts=facts)
    ctx.emit("rationale", f"Triage {law.celex}: {'relevant' if relevant else 'not relevant'} · {result.reason}")
    return {**result.model_dump(mode="json"), "stub": True}

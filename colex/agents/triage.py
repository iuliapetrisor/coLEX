"""Triage: is this act relevant for this company? Deterministic profile matching + one cheap-model call."""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from colex import prompts
from colex.contracts import LawDocument, TriageResult
from colex.guardrails.injection import SYSTEM_RULE, detect_injection, wrap_untrusted

# Scope terms that name the company's entity type or activities.
PROFILE_TERMS = {
    r"\bpayment institutions?\b": "entity type: payment institution",
    r"\bpayment service providers?\b|\bPSPs?\b": "activity: payment services",
    r"\bcredit transfers?\b": "activity: credit transfers",
    r"\bfinancial entit(?:y|ies)\b": "regulated financial entity",
}
SCOPE_CHARS = 3500


class Verdict(BaseModel):
    relevance: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    articles_flagged: list[str] = Field(default_factory=list)
    matched_profile_facts: list[str] = Field(default_factory=list)


def profile_match(law: LawDocument) -> list[str]:
    """Profile facts that the act's text mentions, deterministically."""
    text = " ".join([law.title] + [a.text for a in law.articles])
    return [fact for pattern, fact in PROFILE_TERMS.items()
            if re.search(pattern, text, 0 if "PSP" in pattern else re.I)]


def excerpt(law: LawDocument) -> str:
    """Title, the opening (scope) articles, and one heading line per article. Never the full act."""
    head, used = [], 0
    for article in law.articles[:2]:
        part = article.text[: max(SCOPE_CHARS - used, 0)]
        used += len(part)
        if part:
            head.append(f"{article.id}\n{part}")
    index = "\n".join(f"- {a.id}: " + " / ".join(a.text.splitlines()[:2])[:260] for a in law.articles)
    return (f"Title: {law.title}\n\nOpening articles:\n" + "\n\n".join(head)
            + f"\n\nAll articles in this excerpt:\n{index}")


def run(ctx, law: LawDocument, deps) -> dict[str, Any]:
    cfg = ctx.config
    facts = profile_match(law)
    system, version = prompts.load("triage", cfg)
    text = excerpt(law)
    suspicious = detect_injection(text)
    if suspicious:
        ctx.emit("escalation", f"Suspicious instructions found in {law.celex} (line {suspicious[0]['line']}); "
                               "treated as data, not followed")
    user = ("Company profile:\n" + json.dumps(cfg["profile"], ensure_ascii=False, indent=1)
            + "\n\nProfile terms found in the act by exact matching: " + (", ".join(facts) or "none")
            + "\n\nAct:\n" + wrap_untrusted(f"CELEX:{law.celex}", text))
    result = deps.llm.complete("triage", [{"role": "system", "content": system + "\n\n" + SYSTEM_RULE},
                                          {"role": "user", "content": user}],
                               response_model=Verdict, prompt_version=version, run_id=ctx.run_id, cfg=cfg,
                               step="TRIAGE")
    verdict: Verdict = result.parsed
    threshold, band = cfg["triage"]["relevance_threshold"], cfg["triage"]["borderline_band"]
    relevant = verdict.relevance >= threshold
    borderline = abs(verdict.relevance - threshold) <= band
    known = {a.id for a in law.articles}
    flagged = [a for a in verdict.articles_flagged if a in known] if relevant or borderline else []
    if (relevant or borderline) and not flagged:
        flagged = [a.id for a in law.articles]
    # An article quoted inside a flagged amending article is part of it: flag it too.
    inserted = [a.id for a in law.articles
                if any(a.id.endswith(f"(inserted by {parent})") for parent in flagged) and a.id not in flagged]
    flagged = [a.id for a in law.articles if a.id in set(flagged) | set(inserted)]
    out = TriageResult(law_id=law.celex, relevant=relevant, articles_flagged=flagged, reason=verdict.reason,
                       confidence=round(abs(verdict.relevance - 0.5) * 2, 2),
                       matched_profile_facts=sorted(set(facts) | set(verdict.matched_profile_facts)))
    label = "borderline, asking a human" if borderline else ("relevant" if relevant else "not relevant")
    ctx.emit("rationale", f"Triage {law.celex}: {label} (relevance {verdict.relevance:.2f}) · {verdict.reason}",
             {"articles_flagged": flagged})
    return {**out.model_dump(mode="json"), "relevance": verdict.relevance, "borderline": borderline}

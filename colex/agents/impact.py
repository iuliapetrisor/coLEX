"""Impact Analyst. STUB (walking skeleton): returns one fixed, labelled item. Replaced by the tool loop."""
from __future__ import annotations

from typing import Any

from colex.contracts import ImpactItem, LawDocument


def run(ctx, law: LawDocument, triage: dict[str, Any], deps) -> dict[str, Any]:
    article = law.articles[0]
    item = ImpactItem(item_id="stub-1", article_id=article.id, resource_uri="repo://payments/fees.yaml",
                      lines={"start": 1, "end": 1}, action="CONFIG_CHANGE", owner_team="payments-eng",
                      evidence="STUB evidence (walking skeleton, not a real finding)",
                      citation=f"CELEX:{law.celex} {article.id}", confidence=0.0)
    ctx.emit("rationale", "STUB impact analysis: one fixed item, no map navigation yet")
    return {"items": [item.model_dump(mode="json")], "questions": [], "metrics": {}, "stub": True}


def replan(ctx, law: LawDocument, question: dict[str, Any], answer: dict[str, Any],
           items: list[dict[str, Any]], deps) -> dict[str, Any]:
    return {"items": items, "stub": True}

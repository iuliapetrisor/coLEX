"""Remediation coder. STUB (walking skeleton): produces an empty, labelled change request."""
from __future__ import annotations

from typing import Any

from colex.contracts import ChangeRequest, LawDocument


def run(ctx, law: LawDocument, item: dict[str, Any], feedback: list[str], deps) -> dict[str, Any]:
    cr = ChangeRequest(branch=f"colex/{ctx.run_id}/{item['item_id']}", diff="",
                       tests_before={"passed": 0, "failed": 0}, tests_after={"passed": 0, "failed": 0},
                       iterations=0, status="awaiting_review")
    ctx.emit("rationale", "STUB coder: no patch generated yet")
    return {"change": cr.model_dump(mode="json"), "summary": "STUB: no patch generated yet.", "stub": True}

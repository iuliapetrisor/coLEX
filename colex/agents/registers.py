"""DORA Register of Information step. STUB (walking skeleton): no register generated yet."""
from __future__ import annotations

from typing import Any

DORA_CELEX = "32022R2554"


def applies(law) -> bool:
    return law.celex == DORA_CELEX


def run(ctx, law, items: list[dict[str, Any]], deps) -> dict[str, Any]:
    ctx.emit("rationale", "STUB register: not generated yet")
    return {"items": [], "rows": 0, "stub": True}

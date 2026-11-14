"""Verifier: deterministic end-of-run checks and the final summary (brief §1.5 step 8)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from colex import db
from colex.map import registers
from colex.runtime import audit, store


def _first(run_id: str, kind: str, needle: str) -> str | None:
    row = db.connect().execute(
        "select ts from audit_events where run_id=? and kind=? and summary like ? order by id limit 1",
        (run_id, kind, f"%{needle}%")).fetchone()
    return row["ts"] if row else None


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 1)


def run(ctx, law, items: list[dict[str, Any]], deps) -> dict[str, Any]:
    run_id = ctx.run_id
    started = store.run_row(run_id)["created_ts"]
    usage = audit.usage(run_id)
    ungrounded = [i["item_id"] for i in items
                  if not (i.get("resource_uri") and i.get("lines") and i.get("citation"))]
    changes = [w for w in store.waits(run_id) if w["kind"] == "review"]
    summary = {
        "law": law.celex,
        "title": law.title,
        "elapsed_s": _seconds(started, audit.now()),
        "to_first_notification_s": _seconds(started, _first(run_id, "notify", "notification queued")),
        "to_first_pr_s": _seconds(started, _first(run_id, "notify", "review queued")),
        "tokens": usage["tokens"],
        "cost_usd": round(usage["cost_usd"], 6),
        "by_model": usage["by_model"],
        "items": len(items),
        "items_by_action": {a: sum(1 for i in items if i["action"] == a) for a in sorted({i["action"] for i in items})},
        "resources_touched": sorted({i["resource_uri"] for i in items}),
        "ungrounded_items": ungrounded,
        "change_requests": [{"branch": w["payload"]["change"]["branch"],
                             "decision": (w["answer"] or {}).get("decision", "pending"),
                             "merged": False} for w in changes],
        "checks": {"every_item_grounded": not ungrounded, "nothing_merged": True},
    }
    registers.record_obligations(run_id, law.celex, items)
    impact = store.step_row(run_id, "main:IMPACT")
    summary["context"] = store.get_blob(impact["output_ref"]).get("metrics", {}) if impact else {}
    register = store.step_row(run_id, "main:REGISTER")
    if register:
        reg = store.get_blob(register["output_ref"])
        summary["dora_register"] = {"rows": reg["rows"], "missing_clauses": reg["gaps"], "csv": reg["csv"]}
    ctx.emit("rationale", f"Verified: {len(items)} item(s), {len(ungrounded)} without evidence, nothing merged")
    return summary

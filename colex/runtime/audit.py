"""Audit trail: append-only events linked by a hash chain (brief §4.3)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from colex import db
from colex.guardrails.redaction import mask

FIELDS = ("run_id", "ts", "agent", "step", "kind", "summary", "detail_json", "input_ref", "output_ref",
          "tokens_in", "tokens_out", "cost_usd", "duration_ms", "model", "checkpoint_id")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(prev: str, row: dict[str, Any]) -> str:
    return hashlib.sha256((prev + "|" + db.dumps([row[f] for f in FIELDS])).encode("utf-8")).hexdigest()


def emit(run_id: str | None, agent: str, step: str, kind: str, summary: str = "",
         detail: dict[str, Any] | None = None, **extra: Any) -> int:
    """Append one event. `kind` examples: step, rationale, tool, llm, retry, escalation, human, config."""
    row: dict[str, Any] = dict.fromkeys(FIELDS)
    row.update(run_id=run_id, ts=now(), agent=agent, step=step, kind=kind, summary=mask(summary),
               detail_json=mask(db.dumps(detail or {})), tokens_in=0, tokens_out=0, cost_usd=0.0, duration_ms=0)
    row.update(extra)
    con = db.connect()
    con.execute("begin immediate")
    try:
        last = con.execute("select hash from audit_events order by id desc limit 1").fetchone()
        prev = last["hash"] if last else "genesis"
        cur = con.execute(
            f"insert into audit_events({','.join(FIELDS)},prev_hash,hash) values({','.join('?' * len(FIELDS))},?,?)",
            [row[f] for f in FIELDS] + [prev, _digest(prev, row)])
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return cur.lastrowid


def events(run_id: str | None = None, after_id: int = 0, limit: int = 2000) -> list[dict[str, Any]]:
    sql = "select * from audit_events where id>?" + (" and run_id=?" if run_id else "") + " order by id limit ?"
    args = [after_id] + ([run_id] if run_id else []) + [limit]
    out = []
    for r in db.connect().execute(sql, args):
        item = dict(r)
        item["detail"] = json.loads(item.pop("detail_json"))
        out.append(item)
    return out


def usage(run_id: str) -> dict[str, Any]:
    """Tokens and cost of a run, total and per model."""
    rows = db.connect().execute(
        "select coalesce(model,'') model, sum(tokens_in) ti, sum(tokens_out) tout, sum(cost_usd) cost, count(*) n "
        "from audit_events where run_id=? and kind='llm' group by model", (run_id,)).fetchall()
    by_model = {r["model"]: {"tokens_in": r["ti"], "tokens_out": r["tout"], "cost_usd": r["cost"], "calls": r["n"]}
                for r in rows}
    return {"tokens": sum(m["tokens_in"] + m["tokens_out"] for m in by_model.values()),
            "cost_usd": sum(m["cost_usd"] for m in by_model.values()), "by_model": by_model}


def verify() -> tuple[bool, int | None]:
    """Recompute the chain. Returns (ok, id of the first broken event)."""
    prev = "genesis"
    for r in db.connect().execute("select * from audit_events order by id"):
        row = dict(r)
        if row["prev_hash"] != prev or row["hash"] != _digest(prev, row):
            return False, row["id"]
        prev = row["hash"]
    return True, None


if __name__ == "__main__":  # python -m colex.runtime.audit
    ok, broken = verify()
    print("audit chain OK" if ok else f"audit chain BROKEN at event {broken}")
    raise SystemExit(0 if ok else 1)

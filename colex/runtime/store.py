"""Low-level persistence for runs, steps, checkpoints, blobs and human waits."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from colex import db
from colex.guardrails.redaction import mask
from colex.runtime.audit import now

TERMINAL = ("done", "failed", "cancelled")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def next_seq(con) -> int:
    """Global, monotonically increasing sequence. Call inside a transaction."""
    row = con.execute("select value from kv where key='seq'").fetchone()
    seq = int(row["value"]) + 1 if row else 1
    con.execute("insert into kv(key,value) values('seq',?) on conflict(key) do update set value=excluded.value",
                (str(seq),))
    return seq


def put_blob(value: Any) -> tuple[str, str]:
    """Store a JSON value with personal data and secrets masked. Returns (ref, stored text)."""
    body = mask(db.dumps(value))
    ref = "blob-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]
    db.connect().execute("insert or ignore into blobs(ref,body) values(?,?)", (ref, body))
    return ref, body


def get_blob(ref: str) -> Any:
    row = db.connect().execute("select body from blobs where ref=?", (ref,)).fetchone()
    if row is None:
        raise KeyError(ref)
    return json.loads(row["body"])


def run_row(run_id: str) -> dict[str, Any]:
    row = db.connect().execute("select * from runs where run_id=?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(run_id)
    out = dict(row)
    out["branches"] = json.loads(out.pop("branches_json"))
    out["meta"] = json.loads(out.pop("meta_json"))
    return out


def save_run(run: dict[str, Any]) -> None:
    db.connect().execute(
        "update runs set status=?, current_node=?, branches_json=?, paused=?, config_version_id=?, "
        "map_version_id=?, meta_json=? where run_id=?",
        (run["status"], run["current_node"], db.dumps(run["branches"]), run["paused"], run["config_version_id"],
         run["map_version_id"], db.dumps(run["meta"]), run["run_id"]))


def derive_status(branches: dict[str, dict[str, str]], current: str) -> str:
    """Run status from branch statuses (brief §4.4)."""
    if current == "cancelled":
        return current
    states = [b["status"] for b in branches.values()]
    for candidate in ("running", "waiting_for_legal", "waiting_for_review", "failed"):
        if candidate in states:
            return candidate
    return "done" if states else "running"


def step_row(run_id: str, step_key: str) -> dict[str, Any] | None:
    row = db.connect().execute("select * from steps where run_id=? and step_key=?", (run_id, step_key)).fetchone()
    return dict(row) if row else None


def checkpoints(run_id: str) -> list[dict[str, Any]]:
    return [dict(r) for r in db.connect().execute("select * from checkpoints where run_id=? order by seq", (run_id,))]


def checkpoint(checkpoint_id: str) -> dict[str, Any]:
    row = db.connect().execute("select * from checkpoints where checkpoint_id=?", (checkpoint_id,)).fetchone()
    if row is None:
        raise KeyError(checkpoint_id)
    return dict(row)


def waits(run_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    sql, args = "select * from waits where 1=1", []
    if run_id:
        sql, args = sql + " and run_id=?", args + [run_id]
    if status:
        sql, args = sql + " and status=?", args + [status]
    out = []
    for r in db.connect().execute(sql + " order by seq_created", args):
        item = dict(r)
        item["payload"] = json.loads(item.pop("payload_json"))
        item["answer"] = json.loads(item.pop("answer_json")) if item["answer_json"] else None
        out.append(item)
    return out


def wait(wait_id: str) -> dict[str, Any] | None:
    row = db.connect().execute("select * from waits where wait_id=?", (wait_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    item["answer"] = json.loads(item.pop("answer_json")) if item["answer_json"] else None
    return item


def insert_run(run_id: str, law_id: str, config_version_id: str, parent_checkpoint_id: str | None,
               meta: dict[str, Any] | None = None) -> None:
    db.connect().execute(
        "insert into runs(run_id,law_id,status,current_node,config_version_id,parent_checkpoint_id,created_ts,"
        "meta_json) values(?,?,?,?,?,?,?,?)",
        (run_id, law_id, "running", "WATCH", config_version_id, parent_checkpoint_id, now(), db.dumps(meta or {})))

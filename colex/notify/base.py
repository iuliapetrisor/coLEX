"""Notifier interface (brief §4.5). Agents call only this; Slack is one implementation.

Every outgoing message goes through the outbox table with an idempotency key, so a resumed
run never posts twice.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from colex import db
from colex.contracts import ChangeRequest, Notification, Question
from colex.runtime import audit


class MessageRef(BaseModel):
    idem_key: str
    channel: str
    ts: str | None = None


class Notifier(ABC):
    @abstractmethod
    def notify(self, batch: Notification, *, run_id: str, idem_key: str) -> MessageRef: ...

    @abstractmethod
    def ask(self, q: Question, *, run_id: str, wait_id: str, idem_key: str, channel: str) -> MessageRef: ...

    @abstractmethod
    def request_review(self, cr: ChangeRequest, *, run_id: str, wait_id: str, idem_key: str,
                       channel: str, context: dict[str, Any]) -> MessageRef: ...

    @abstractmethod
    def update(self, ref: MessageRef, *, decision: str, actor: str, ts: datetime) -> None: ...

    @abstractmethod
    def post_status(self, run_id: str, text: str, *, idem_key: str) -> MessageRef: ...


def outbox_rows(run_id: str | None = None) -> list[dict[str, Any]]:
    sql = "select * from outbox" + (" where run_id=?" if run_id else "") + " order by id"
    out = []
    for r in db.connect().execute(sql, (run_id,) if run_id else ()):
        item = dict(r)
        item["payload"] = json.loads(item.pop("payload_json"))
        out.append(item)
    return out


class OutboxNotifier(Notifier):
    """Enqueues every message; `flush()` delivers what is pending. Subclasses implement `_send`."""

    def _enqueue(self, kind: str, channel: str, payload: dict[str, Any], run_id: str | None, idem_key: str) -> MessageRef:
        con = db.connect()
        cur = con.execute(
            "insert or ignore into outbox(idem_key,run_id,channel,kind,payload_json,status,created_ts) "
            "values(?,?,?,?,?,?,?)", (idem_key, run_id, channel, kind, db.dumps(payload), "pending", audit.now()))
        if cur.rowcount:
            audit.emit(run_id, "liaison", "-", "notify", f"{kind} queued for {channel}", {"idem_key": idem_key})
            self.flush()
        row = con.execute("select channel, slack_ts from outbox where idem_key=?", (idem_key,)).fetchone()
        return MessageRef(idem_key=idem_key, channel=row["channel"], ts=row["slack_ts"])

    def notify(self, batch, *, run_id, idem_key):
        return self._enqueue("notification", batch.channel, batch.model_dump(mode="json"), run_id, idem_key)

    def ask(self, q, *, run_id, wait_id, idem_key, channel):
        return self._enqueue("question", channel, {"question": q.model_dump(mode="json"), "wait_id": wait_id},
                             run_id, idem_key)

    def request_review(self, cr, *, run_id, wait_id, idem_key, channel, context):
        payload = {"change": cr.model_dump(mode="json"), "wait_id": wait_id, "context": context}
        return self._enqueue("review", channel, payload, run_id, idem_key)

    def post_status(self, run_id, text, *, idem_key):
        first = db.connect().execute("select channel from outbox where run_id=? order by id limit 1",
                                     (run_id,)).fetchone()
        if first is None:
            return MessageRef(idem_key=idem_key, channel="")
        return self._enqueue("status", first["channel"], {"text": text}, run_id, idem_key)

    def update(self, ref, *, decision, actor, ts):
        db.connect().execute("update outbox set status=?, error=null where idem_key=? and status in ('sent','decided')",
                             ("decided", ref.idem_key))
        self._update(ref, decision, actor, ts)

    def flush(self) -> int:
        """Deliver pending messages. Returns how many are still pending."""
        raise NotImplementedError

    def _update(self, ref: MessageRef, decision: str, actor: str, ts: datetime) -> None:
        raise NotImplementedError


class FakeNotifier(OutboxNotifier):
    """Delivers nowhere: marks messages as sent and records them. Used by tests and offline runs."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    def flush(self) -> int:
        con = db.connect()
        for r in con.execute("select * from outbox where status='pending' order by id").fetchall():
            con.execute("update outbox set status='sent', slack_ts=?, attempts=attempts+1 where id=?",
                        (f"fake-{r['id']}", r["id"]))
            self.sent.append({"kind": r["kind"], "channel": r["channel"], "idem_key": r["idem_key"],
                              "payload": json.loads(r["payload_json"])})
        return 0

    def _update(self, ref, decision, actor, ts):
        self.updates.append({"idem_key": ref.idem_key, "decision": decision, "actor": actor})

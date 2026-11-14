"""SlackNotifier: delivers the outbox to a real Slack workspace (brief §4.5).

Every message was enqueued with an idempotency key before this code sees it. Delivery retries with
backoff, honours Retry-After on HTTP 429, and never blocks a run: if Slack is unreachable the message
stays pending and the Console shows it. `client` is a slack_sdk WebClient (or a test double).
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Callable

from colex import db
from colex.config import ConfigStore
from colex.notify import blocks
from colex.notify.base import MessageRef, OutboxNotifier
from colex.notify.blocks_review import render
from colex.runtime import audit

MAX_ATTEMPTS = 8


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    if response is None or getattr(response, "status_code", None) != 429:
        return None
    try:
        return float(response.headers.get("Retry-After", 1))
    except (TypeError, ValueError, AttributeError):
        return 1.0


def _reason(exc: Exception) -> str:
    try:
        code = exc.response["error"]
    except Exception:
        code = None
    return str(code or exc or type(exc).__name__)[:120]


class SlackNotifier(OutboxNotifier):
    def __init__(self, client: Any, clock: Callable[[], float] = time.time) -> None:
        self.client, self.clock = client, clock
        self.channels: dict[str, str] = {}

    def channel_id(self, name: str) -> str | None:
        """Channel name → id, cached. Needs the channels:read scope."""
        key = name.lstrip("#")
        if key not in self.channels:
            cursor = None
            while True:
                page = self.client.conversations_list(types="public_channel", limit=200, cursor=cursor)
                for channel in page["channels"]:
                    self.channels[channel["name"]] = channel["id"]
                cursor = (page.get("response_metadata") or {}).get("next_cursor")
                if not cursor:
                    break
        return self.channels.get(key)

    def _thread(self, run_id: str | None, row_id: int) -> str | None:
        """Status replies go under the first message of the run, so each run is one readable thread."""
        first = db.connect().execute("select slack_ts from outbox where run_id=? and slack_ts is not null and "
                                     "kind!='status' and id<? order by id limit 1", (run_id, row_id)).fetchone()
        return first["slack_ts"] if first else None

    def flush(self) -> int:
        """Send what is due. Returns how many messages are still pending."""
        con = db.connect()
        cfg = ConfigStore().active().payload
        due = con.execute("select * from outbox where status='pending' and next_attempt_at<=? order by id",
                          (self.clock(),)).fetchall()
        for row in due:
            try:
                channel = self.channel_id(row["channel"])
                if channel is None:
                    raise LookupError(f"channel {row['channel']} does not exist in the workspace")
                text, message = render(row["kind"], json.loads(row["payload_json"]), cfg, row["run_id"] or "",
                                       row["idem_key"])
                thread = self._thread(row["run_id"], row["id"]) if row["kind"] == "status" else None
                sent = self.client.chat_postMessage(channel=channel, text=text[:300], blocks=message,
                                                    thread_ts=thread, unfurl_links=False)
                con.execute("update outbox set status='sent', slack_ts=?, thread_ts=?, attempts=attempts+1, "
                            "error=null where id=?", (sent["ts"], thread, row["id"]))
            except Exception as exc:   # stay pending; the run continues and the Console shows the delay
                attempts, wait = row["attempts"] + 1, _retry_after(exc)
                delay = wait if wait is not None else min(2 ** attempts, 300)
                gave_up = attempts >= MAX_ATTEMPTS or isinstance(exc, LookupError)
                con.execute("update outbox set attempts=?, next_attempt_at=?, error=?, status=? where id=?",
                            (attempts, self.clock() + delay, _reason(exc), "failed" if gave_up else "pending",
                             row["id"]))
                if attempts == 1 or gave_up:
                    audit.emit(row["run_id"], "slack", "-", "escalation" if gave_up else "retry",
                               f"Slack delivery {'failed' if gave_up else 'pending'} for {row['channel']}: "
                               f"{_reason(exc)}" + ("" if gave_up else f"; retry in {delay:.0f}s"))
                if wait is not None:
                    break   # rate limited: stop this pass and keep the order
        return con.execute("select count(*) n from outbox where status='pending'").fetchone()["n"]

    def _update(self, ref: MessageRef, decision: str, actor: str, ts: datetime) -> None:
        """Rewrite the original message in place: decision, who decided, when."""
        row = db.connect().execute("select * from outbox where idem_key=?", (ref.idem_key,)).fetchone()
        if row is None or not row["slack_ts"]:
            return
        cfg = ConfigStore().active().payload
        text, message = render(row["kind"], json.loads(row["payload_json"]), cfg, row["run_id"] or "", row["idem_key"])
        try:
            self.client.chat_update(channel=self.channel_id(row["channel"]), ts=row["slack_ts"], text=text[:300],
                                    blocks=blocks.decided(message, decision, actor, ts.strftime("%Y-%m-%d %H:%M UTC")))
        except Exception as exc:
            audit.emit(row["run_id"], "slack", "-", "retry", f"Could not update the Slack message: {_reason(exc)}")

"""Slack interaction logic (brief §4.5), independent of Bolt so it can be tested without Slack.

The Bolt layer calls ack() first, then hands the payload to these methods on a worker thread.
Decisions go through `Runtime.deliver_human_answer`, the same path the Console uses.
Only users mapped to the approver role of a wait may decide; others get an ephemeral refusal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from colex import db
from colex.notify.base import MessageRef
from colex.notify.blocks_review import modal
from colex.runtime import audit, store

NOTE_ACTIONS = {"colex_ack": "Acknowledged", "colex_assign": "Assigned to", "colex_dispute": "Disputed"}


def approver(cfg: dict[str, Any], role: str, user_id: str) -> bool:
    return user_id in cfg["routing"]["approvers"].get(role, [])


class Handlers:
    def __init__(self, rt, notifier, client) -> None:
        self.rt, self.notifier, self.client = rt, notifier, client

    def _refuse(self, channel: str, user: str, text: str, wait_id: str = "") -> None:
        audit.emit((store.wait(wait_id) or {}).get("run_id"), "slack", "-", "human",
                   f"Refused {user}: {text}", {"wait_id": wait_id})
        if channel:
            self.client.chat_postEphemeral(channel=channel, user=user, text=text)

    def _first_time(self, key: str, user: str) -> bool:
        """Dedupe on (action id, message ts): a double click is processed once."""
        cur = db.connect().execute("insert or ignore into interactions(key,actor,ts) values(?,?,?)",
                                   (key, user, audit.now()))
        return cur.rowcount == 1

    def _allowed(self, wait_id: str, user: str, channel: str) -> dict[str, Any] | None:
        """The pending wait, if this user may decide it. Otherwise explains why not and returns None."""
        wait = store.wait(wait_id)
        if wait is None:
            return self._refuse(channel, user, "This request is no longer known to coLEX.")
        if store.run_row(wait["run_id"])["status"] == "cancelled":
            return self._refuse(channel, user, "This run was cancelled; no decision is needed.", wait_id)
        if wait["status"] != "pending":
            audit.emit(wait["run_id"], "slack", "-", "human", f"Ignored a repeated decision from {user}",
                       {"wait_id": wait_id})
            return self._refuse(channel, user, "This was already decided.", wait_id)
        role = wait["payload"].get("role", "legal")
        if not approver(self.rt.configs.active().payload, role, user):
            return self._refuse(channel, user, f"Only mapped {role} approvers can decide this. Ask an admin to add "
                                               "you under routing.approvers in the coLEX Settings.", wait_id)
        return wait

    def on_action(self, body: dict[str, Any]) -> None:
        action = body["actions"][0]
        name, value, user = action["action_id"], action.get("value", ""), body["user"]["id"]
        channel = (body.get("channel") or {}).get("id", "")
        ts = (body.get("message") or {}).get("ts", "")
        if name in NOTE_ACTIONS:   # notification buttons: any member of the channel may use them
            if self._first_time(f"{name}:{ts}", user):
                row = db.connect().execute("select run_id, channel from outbox where idem_key=?", (value,)).fetchone()
                audit.emit(row["run_id"] if row else None, "slack", "-", "human",
                           f"{user}: {NOTE_ACTIONS[name]} notification", {"idem_key": value})
                if row:
                    self.notifier.update(MessageRef(idem_key=value, channel=row["channel"]),
                                         decision=NOTE_ACTIONS[name], actor=user, ts=datetime.now(timezone.utc))
            return
        wait_id, _, option = value.partition("|")
        wait = self._allowed(wait_id, user, channel)
        if wait is None:
            return
        if name == "colex_answer_detail":
            self.client.views_open(trigger_id=body["trigger_id"], view=modal(
                "answer", wait_id, "Answer coLEX", wait["payload"]["question"]["text"], channel, ts))
        elif name == "colex_request_changes":
            self.client.views_open(trigger_id=body["trigger_id"], view=modal(
                "changes", wait_id, "Request changes", "What should change?", channel, ts))
        elif name == "colex_approve" and self._first_time(f"{name}:{ts}", user):
            self.rt.deliver_human_answer(wait_id, {"decision": "approve"}, user)
        elif name.startswith("colex_answer_") and option and self._first_time(f"colex_answer:{ts}", user):
            self.rt.deliver_human_answer(wait_id, {"decision": option}, user)

    def on_view(self, body: dict[str, Any]) -> None:
        view, user = body["view"], body["user"]["id"]
        wait_id, channel, _ts = (view.get("private_metadata", "") + "||").split("|")[:3]
        text = view["state"]["values"]["body"]["text"].get("value") or ""
        wait = self._allowed(wait_id, user, channel)
        if wait is None or not text.strip():
            return
        if view["callback_id"] == "colex_modal_changes":
            self.rt.deliver_human_answer(wait_id, {"decision": "request_changes", "text": text.strip()}, user)
        else:
            self.rt.deliver_human_answer(wait_id, {"text": text.strip()}, user)

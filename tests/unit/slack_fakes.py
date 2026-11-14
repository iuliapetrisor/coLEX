"""A fake Slack Web API client and a fixture that wires it to the real notifier and handlers."""
from __future__ import annotations

import pytest

from colex.config import ConfigStore
from colex.contracts import Notification
from colex.notify.handlers import Handlers
from colex.notify.slack import SlackNotifier
from colex.runtime.api import Runtime
from tests.contract.payloads import ITEM

CHANNELS = ["legal", "compliance", "payments-eng", "product", "support", "security"]


class RateLimited(Exception):
    class response:   # noqa: N801  (shape of a slack_sdk error response)
        status_code, headers = 429, {"Retry-After": "2"}


class Client:
    def __init__(self):
        self.posts, self.updates, self.ephemeral, self.views, self.fail = [], [], [], [], []

    def conversations_list(self, **kw):
        return {"channels": [{"name": n, "id": f"C-{n}"} for n in CHANNELS]}

    def chat_postMessage(self, **kw):
        if self.fail:
            raise self.fail.pop(0)
        self.posts.append(kw)
        return {"ts": f"17.{len(self.posts)}"}

    def chat_update(self, **kw):
        self.updates.append(kw)

    def chat_postEphemeral(self, **kw):
        self.ephemeral.append(kw)

    def views_open(self, **kw):
        self.views.append(kw)


@pytest.fixture
def world(colex_db_path):
    """(runtime, fake client, notifier, handlers, run id, clock list)."""
    rt, client, now = Runtime(), Client(), [1000.0]
    cfg = ConfigStore().active().payload
    cfg["routing"]["approvers"] = {"legal": ["U0LEGAL"], "engineer": ["U0ENG"]}
    ConfigStore().save(cfg, "test")
    notifier = SlackNotifier(client, clock=lambda: now[0])
    run = rt.start_run("32024R0886")
    return rt, client, notifier, Handlers(rt, notifier, client), run.run_id, now


def batch(n: int = 1) -> Notification:
    return Notification(channel="#product", title="CELEX 32024R0886: action needed", body="x",
                        items=[ITEM] * n, actions=["acknowledge"])


def click(action_id: str, value: str, user: str, ts: str = "17.1") -> dict:
    return {"actions": [{"action_id": action_id, "value": value}], "user": {"id": user}, "trigger_id": "T1",
            "channel": {"id": "C-legal"}, "message": {"ts": ts}}

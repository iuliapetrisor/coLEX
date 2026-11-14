"""Slack delivery with a fake client: idempotency, block limits, HTTP 429, outage, commands."""
from __future__ import annotations

from colex.notify import commands
from colex.notify.base import outbox_rows
from colex.runtime import audit, store
from tests.unit.slack_fakes import RateLimited, batch, world  # noqa: F401  (world is a fixture)


def test_delivery_is_idempotent_and_respects_block_limits(world):  # noqa: F811
    rt, client, notifier, _, run_id, _ = world
    for _ in range(3):
        ref = notifier.notify(batch(60), run_id=run_id, idem_key="k1")
    assert len(client.posts) == 1 and ref.ts == "17.1" and client.posts[0]["channel"] == "C-product"
    blocks = client.posts[0]["blocks"]
    assert len(blocks) <= 50 and all(len(b.get("text", {}).get("text", "")) <= 3000 for b in blocks)
    ids = [e["action_id"] for b in blocks if b["type"] == "actions" for e in b["elements"]]
    assert len(ids) == len(set(ids)) == 3 and "48 more item(s)" in str(blocks)


def test_rate_limit_honours_retry_after_and_outage_keeps_messages_pending(world):  # noqa: F811
    rt, client, notifier, _, run_id, now = world
    client.fail = [RateLimited(), ConnectionError("down")]
    notifier.notify(batch(), run_id=run_id, idem_key="k1")
    row = outbox_rows(run_id)[0]
    assert (row["status"], row["next_attempt_at"]) == ("pending", 1002.0) and client.posts == []
    now[0] = 1001.0
    assert notifier.flush() == 1 and client.posts == []          # not due yet
    now[0] = 1002.5
    assert notifier.flush() == 1                                  # second failure: still pending, no crash
    now[0] = 2000.0
    assert notifier.flush() == 0 and len(client.posts) == 1       # delivered exactly once
    assert any(e["kind"] == "retry" and "Slack delivery pending" in e["summary"] for e in audit.events(run_id))


def test_unknown_channel_fails_visibly_instead_of_retrying_forever(world):  # noqa: F811
    rt, client, notifier, _, run_id, _ = world
    message = batch()
    message.channel = "#does-not-exist"
    notifier.notify(message, run_id=run_id, idem_key="k2")
    assert outbox_rows(run_id)[0]["status"] == "failed" and client.posts == []
    assert any(e["kind"] == "escalation" and "does not exist" in e["summary"] for e in audit.events(run_id))


def test_document_text_cannot_create_mentions(world):  # noqa: F811
    rt, client, notifier, _, run_id, _ = world
    message = batch()
    message.items[0].evidence = "<!channel> <@U123> pay now"
    notifier.notify(message, run_id=run_id, idem_key="k3")
    text = str(client.posts[0]["blocks"])
    assert "<!channel>" not in text and "<@U123>" not in text and "&lt;!channel&gt;" in text


def test_commands(world):  # noqa: F811
    rt, client, notifier, handlers, run_id, _ = world
    assert run_id in commands.command(rt, "status", "U0X")
    assert "Only mapped approvers" in commands.command(rt, f"pause {run_id}", "U0X")
    assert "paused" in commands.command(rt, f"pause {run_id}", "U0ENG") and store.run_row(run_id)["paused"] == 1
    assert "resumed" in commands.command(rt, f"resume {run_id}", "U0ENG")
    assert "No item" in commands.command(rt, "why i9", "U0X") and "Usage" in commands.command(rt, "dance", "U0X")

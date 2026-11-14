"""Only mapped approvers decide; double clicks count once; decisions update the message in place."""
from __future__ import annotations

from datetime import datetime, timezone

from colex.contracts import ChangeRequest, Question
from colex.runtime import audit, store
from tests.contract.payloads import ITEM, SUITE
from tests.unit.slack_fakes import click, world  # noqa: F401  (world is a fixture)


def test_only_mapped_approvers_decide_and_double_clicks_count_once(world):  # noqa: F811
    rt, client, notifier, handlers, run_id, _ = world
    q = Question(to_team="legal", text="Is the provider critical for us?", options=["Yes", "No"])
    rt.wait_for_human(run_id, "q1", "legal", {"question": q.model_dump(), "role": "legal"}, key="ask:q1")
    wait_id = f"{run_id}:ask:q1"
    handlers.on_action(click("colex_answer_0", f"{wait_id}|Yes", "U0RANDOM"))
    assert store.wait(wait_id)["status"] == "pending"
    assert "Only mapped legal approvers" in client.ephemeral[0]["text"]
    for user in ("U0LEGAL", "U0LEGAL"):
        handlers.on_action(click("colex_answer_0", f"{wait_id}|Yes", user))
    handlers.on_action(click("colex_answer_1", f"{wait_id}|No", "U0LEGAL"))
    wait = store.wait(wait_id)
    assert (wait["status"], wait["answer"], wait["actor"]) == ("answered", {"decision": "Yes"}, "U0LEGAL")
    kinds = [e["summary"] for e in audit.events(run_id) if e["kind"] == "human"]
    assert sum("answered: Yes" in s for s in kinds) == 1 and sum("Refused U0RANDOM" in s for s in kinds) == 1


def test_review_needs_an_engineer_and_request_changes_goes_through_a_modal(world):  # noqa: F811
    rt, client, notifier, handlers, run_id, _ = world
    change = ChangeRequest(branch="colex/r/i1", diff="+++ b/payments/fees.yaml\n+x\n", tests_before=SUITE,
                           iterations=2, status="awaiting_review")
    payload = {"change": change.model_dump(), "role": "engineer"}
    rt.wait_for_human(run_id, "i1", "review", payload, key="review:i1:1")
    wait_id = f"{run_id}:review:i1:1"
    ref = notifier.request_review(change, run_id=run_id, wait_id=wait_id, idem_key="pr1", channel="#payments-eng",
                                  context={"item": ITEM, "summary": "Lower the fee", "round": 1})
    assert "never merges" in str(client.posts[0]["blocks"])
    handlers.on_action(click("colex_approve", wait_id, "U0LEGAL"))           # a legal approver is not an engineer
    assert store.wait(wait_id)["status"] == "pending" and len(client.ephemeral) == 1
    handlers.on_action(click("colex_request_changes", wait_id, "U0ENG"))
    view = client.views[0]["view"]
    assert view["callback_id"] == "colex_modal_changes"
    state = {"values": {"body": {"text": {"value": "Add a comment"}}}}
    handlers.on_view({"user": {"id": "U0RANDOM"}, "view": {**view, "state": state}})
    assert store.wait(wait_id)["status"] == "pending"                         # the modal is checked too
    handlers.on_view({"user": {"id": "U0ENG"}, "view": {**view, "state": state}})
    assert store.wait(wait_id)["answer"] == {"decision": "request_changes", "text": "Add a comment"}
    notifier.update(ref, decision="request_changes", actor="U0ENG", ts=datetime.now(timezone.utc))
    updated = client.updates[0]["blocks"]
    assert not [b for b in updated if b["type"] == "actions"] and "<@U0ENG>" in str(updated[-1])


def test_clicks_on_cancelled_runs_and_unknown_requests_are_refused(world):  # noqa: F811
    rt, client, notifier, handlers, run_id, _ = world
    handlers.on_action(click("colex_approve", "run-nope:review:x:1", "U0ENG"))
    assert "no longer known" in client.ephemeral[0]["text"]
    q = Question(to_team="legal", text="Is the provider critical for us?", options=["Yes", "No"])
    rt.wait_for_human(run_id, "q1", "legal", {"question": q.model_dump(), "role": "legal"}, key="ask:q1")
    rt.cancel(run_id, "U0ENG")
    handlers.on_action(click("colex_answer_0", f"{run_id}:ask:q1|Yes", "U0LEGAL"))
    assert "cancelled" in client.ephemeral[1]["text"] and store.wait(f"{run_id}:ask:q1")["status"] == "pending"

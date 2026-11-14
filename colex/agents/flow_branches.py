"""Second half of the run driver: question branches, item branches, verification."""
from __future__ import annotations

from typing import Any

from colex.agents import impact, verifier
from colex.agents.flow_common import CODE_ACTIONS, ask, notify
from colex.agents.flow_remediate import remediate
from colex.contracts import Question
from colex.runtime import store
from colex.runtime.core import StepFailed


def advance_branches(deps, run_id: str, law, items: dict[str, dict[str, Any]],
                     questions: list[dict[str, Any]]) -> None:
    rt = deps.rt
    waiting: set[str] = set()
    for q in questions:
        question = Question(**q["question"])
        cfg = rt.configs.active().payload
        channel = cfg["routing"]["team_channels"].get(question.to_team, cfg["routing"]["unknown_owner_channel"])
        answer = ask(deps, run_id, q["id"], "ASK_LEGAL", q["id"], question, channel, "legal",
                     {"citation": q.get("citation", ""), "excerpt": q.get("excerpt", "")})
        if answer is None:   # only the items this question blocks are paused
            waiting |= set(question.blocking_items)
            continue
        affected = [items[i] for i in question.blocking_items if i in items]
        out = rt.step(run_id, q["id"], "IMPACT", lambda c: impact.replan(c, law, q, answer, affected, deps),
                      key=f"replan:{q['id']}", agent="impact")
        for item_id in question.blocking_items:
            items.pop(item_id, None)
        known = store.run_row(run_id)["branches"]
        for item in out["items"]:
            items[item["item_id"]] = item
            if item["item_id"] not in known:
                rt.set_branch(run_id, item["item_id"], "running", "LIAISON")
        rt.step(run_id, q["id"], "LIAISON", lambda c: notify(deps, c, law, out["items"], q["id"]),
                key=f"liaison:{q['id']}", agent="liaison")
        rt.set_branch(run_id, q["id"], "done")
        for gone in set(question.blocking_items) - set(items):
            rt.set_branch(run_id, gone, "done")
    for item_id, item in list(items.items()):
        branch = store.run_row(run_id)["branches"].get(item_id)
        if branch is None:
            rt.set_branch(run_id, item_id, "running", "LIAISON")
        elif branch["status"] == "done":
            continue
        if item_id in waiting:
            rt.set_branch(run_id, item_id, "waiting_for_legal")
        elif item["action"] in CODE_ACTIONS and not item.get("register_only"):
            try:
                remediate(deps, run_id, law, item)
            except StepFailed:
                continue   # this branch is marked failed and shown on the timeline; the others go on
        else:
            rt.set_branch(run_id, item_id, "done")
    states = [b["status"] for k, b in store.run_row(run_id)["branches"].items() if k != "main"]
    pending = [s for s in states if s != "done"]
    if pending:   # main has nothing to do until a human answers
        rt.set_branch(run_id, "main", "waiting_for_legal" if "waiting_for_legal" in pending else pending[0])
        return
    rt.step(run_id, "main", "VERIFY", lambda c: verifier.run(c, law, list(items.values()), deps), agent="verifier")
    rt.step(run_id, "main", "DONE", lambda c: {"done": True}, agent="verifier")
    rt.set_branch(run_id, "main", "done")

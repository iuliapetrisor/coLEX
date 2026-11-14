"""The run driver: advances one run as far as it can go, branch by branch (D-016).

Called again after every human answer and after a restart. Completed steps are replayed from
their checkpoints, so only the affected branches do new work.
"""
from __future__ import annotations

from colex import db
from colex.agents import impact, registers, triage, watcher
from colex.agents.flow_branches import advance_branches
from colex.agents.flow_common import ask, notify
from colex.contracts import Question
from colex.runtime import store


def advance(deps, run_id: str) -> None:
    rt = deps.rt
    law = watcher.get_law(store.run_row(run_id)["law_id"])
    tri = rt.step(run_id, "main", "TRIAGE", lambda c: triage.run(c, law, deps), agent="triage")
    relevant = tri["relevant"]
    if tri.get("borderline"):   # not sure: ask a human instead of guessing
        q = Question(to_team="compliance", text=f"Is this act relevant for us? {law.title[:200]} — {tri['reason']}",
                     options=["Relevant", "Not relevant"])
        channel = rt.configs.active().payload["routing"]["unknown_owner_channel"]
        answer = ask(deps, run_id, "main", "ESCALATED", "triage", q, channel, "legal")
        if answer is None:
            return
        relevant = answer.get("decision") == "Relevant"
    watcher.set_law(law.celex, status="relevant" if relevant else "archived", reason=tri["reason"],
                    triage_json=db.dumps(tri))
    if not relevant:
        rt.step(run_id, "main", "DONE", lambda c: {"archived": True, "reason": tri["reason"]}, agent="triage")
        rt.set_branch(run_id, "main", "done")
        return
    imp = rt.step(run_id, "main", "IMPACT", lambda c: impact.run(c, law, tri, deps), agent="impact")
    items = {i["item_id"]: i for i in imp["items"]}
    questions = imp["questions"]
    blocked = {i for q in questions for i in q["question"]["blocking_items"]}
    rt.step(run_id, "main", "LIAISON", lambda c: notify(
        deps, c, law, [i for k, i in items.items() if k not in blocked], "main"), agent="liaison")
    spawned = store.run_row(run_id)["branches"]
    for bid in [*items, *(q["id"] for q in questions)]:
        if bid not in spawned:
            rt.set_branch(run_id, bid, "running", "LIAISON")
    if registers.applies(law):
        reg = rt.step(run_id, "main", "REGISTER", lambda c: registers.run(c, law, list(items.values()), deps),
                      agent="registers")
        for extra in reg.get("items", []):
            items.setdefault(extra["item_id"], extra)
    advance_branches(deps, run_id, law, items, questions)

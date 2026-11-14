"""Remediation branch: coder → review wait → approve (never merged) or request changes → coder again."""
from __future__ import annotations

from typing import Any

from colex.agents import coder
from colex.agents.flow_common import CR_FIELDS, decided, to_item
from colex.contracts import ChangeRequest, Notification


def remediate(deps, run_id: str, law, item: dict[str, Any]) -> None:
    rt, bid, feedback = deps.rt, item["item_id"], []
    cfg = rt.configs.active().payload
    for rnd in range(1, cfg["budgets"]["max_coder_iterations"] + 1):
        out = rt.step(run_id, bid, "REMEDIATE", lambda c: coder.run(c, law, item, list(feedback), deps),
                      key=f"{bid}:REMEDIATE:{rnd}", agent="coder")
        change = ChangeRequest(**{k: out["change"][k] for k in CR_FIELDS})
        channel = cfg["routing"]["review_channel"]
        if change.status == "needs_human":
            note = Notification(channel=channel, title=f"coLEX could not produce a passing patch for {bid}",
                                body=out.get("summary", "") + " An engineer needs to take over. Nothing was merged.",
                                items=[to_item(item)],
                                actions=["acknowledge"])
            key = f"needs-human:{run_id}:{bid}:{rnd}"
            rt.side_effect(key, lambda: deps.notifier.notify(note, run_id=run_id, idem_key=key).model_dump())
            rt.set_branch(run_id, bid, "done")
            return
        context = {"item": item, "summary": out.get("summary", ""), "round": rnd, "law": law.celex}
        payload = {"change": change.model_dump(mode="json"), "role": "engineer", "channel": channel, **context}
        answer = rt.wait_for_human(run_id, bid, "review", payload, key=f"review:{bid}:{rnd}", node="REVIEW")
        key = f"pr:{run_id}:{bid}:{rnd}"
        ref = rt.side_effect(key, lambda: deps.notifier.request_review(
            change, run_id=run_id, wait_id=f"{run_id}:review:{bid}:{rnd}", idem_key=key, channel=channel,
            context=context).model_dump())
        if answer is None:
            return
        decided(deps, f"pr-upd:{run_id}:{bid}:{rnd}", ref, answer)
        if answer.get("decision") == "approve":   # approved ≠ merged: merging stays a manual human step
            rt.set_branch(run_id, bid, "done")
            return
        feedback.append(answer.get("text") or "Changes requested without a comment.")
    rt.set_branch(run_id, bid, "done")

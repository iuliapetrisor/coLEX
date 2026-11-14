"""Shared pieces of the run driver: asking humans and sending notification batches."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from colex.agents import liaison
from colex.contracts import ImpactItem, Question
from colex.notify.base import MessageRef

CODE_ACTIONS = ("CODE_CHANGE", "CONFIG_CHANGE")
CR_FIELDS = ("branch", "diff", "tests_before", "tests_after", "iterations", "status")


def decided(deps, key: str, ref: dict[str, Any], answer: dict[str, Any]) -> None:
    """Update the original message in place with the decision, who decided and when."""
    text = answer.get("decision") or answer.get("text", "")
    deps.rt.side_effect(key, lambda: deps.notifier.update(
        MessageRef(**ref), decision=text, actor=answer["actor"], ts=datetime.now(timezone.utc)) or {})


def ask(deps, run_id: str, branch: str, node: str, key: str, q: Question, channel: str, role: str,
        extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Post a question and wait durably. Returns the answer, or None while the branch waits."""
    payload = {"question": q.model_dump(mode="json"), "role": role, "channel": channel, **(extra or {})}
    answer = deps.rt.wait_for_human(run_id, branch, "legal", payload, key=f"ask:{key}", node=node)
    ref = deps.rt.side_effect(f"ask:{run_id}:{key}", lambda: deps.notifier.ask(
        q, run_id=run_id, wait_id=f"{run_id}:ask:{key}", idem_key=f"ask:{run_id}:{key}",
        channel=channel).model_dump())
    if answer is not None:
        decided(deps, f"ask-upd:{run_id}:{key}", ref, answer)
    return answer


def notify(deps, ctx, law, items: list[dict[str, Any]], tag: str, label: str = "") -> dict[str, Any]:
    """Liaison step body: one batch per channel, routed with the config this step started with."""
    batches = liaison.plan(ctx.config, law, [ImpactItem(**i) for i in items], label)
    for batch in batches:
        key = f"notify:{ctx.run_id}:{tag}:{batch.channel}"
        deps.rt.side_effect(key, lambda b=batch, k=key: deps.notifier.notify(
            b, run_id=ctx.run_id, idem_key=k).model_dump())
        ctx.emit("rationale", f"Notified {batch.channel}: {len(batch.items)} item(s)",
                 {"items": [i.item_id for i in batch.items]})
    return {"batches": [{"channel": b.channel, "items": [i.item_id for i in b.items]} for b in batches],
            "config_version_id": ctx.config_version_id}

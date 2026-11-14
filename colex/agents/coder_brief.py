"""What the coder is told, and the shape of what it returns."""
from __future__ import annotations

import json
from typing import Any

from colex import testrunner
from colex.agents import coder_apply as ca
from colex.contracts import ChangeRequest
from colex.guardrails.injection import wrap_untrusted

ITEM_FIELDS = ("resource_uri", "lines", "obligation", "citation", "evidence")


def files(worktree, paths: list[str]) -> str:
    return "\n\n".join(wrap_untrusted(f"repo://{p}", (worktree / p).read_text(encoding="utf-8")) for p in paths)


def brief(item: dict[str, Any], article: str, allowed: list[str], wanted: list[str], before: dict[str, Any],
          feedback: list[str]) -> str:
    """The fixed part of the coder's instructions for one item."""
    text = (f"Impact item: {json.dumps({k: item.get(k) for k in ITEM_FIELDS}, ensure_ascii=False)}\n\n"
            f"Cited article:\n{article}\n\nEditable files: {json.dumps(allowed)}\n"
            f"Tests that must pass after your change: {json.dumps(wanted)}\n")
    if wanted:
        text += f"\nFailure of those tests today:\n{ca.failure_text(before, wanted)}\n"
    for comment in feedback:   # a reviewer's comment is human input, still passed as data
        text += f"\nReviewer comment to address: {wrap_untrusted('review-comment', comment)}\n"
    return text


def result(status: str, branch: str, diff: str, before: dict[str, Any], after: dict[str, Any] | None,
           iterations: int, summary: str, **extra: Any) -> dict[str, Any]:
    change = ChangeRequest(branch=branch, diff=diff, tests_before=testrunner.suite(before),
                           tests_after=testrunner.suite(after) if after else None, iterations=iterations,
                           status=status)
    return {"change": change.model_dump(mode="json"), "summary": summary, **extra}

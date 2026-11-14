"""Remediation coder (brief §1.3 step 7): branch → patch → sandboxed tests → revise on failure → change request.

It reads only the files the map points to, never edits tests, and never merges: an approved change
request stays on its branch until a human merges it.
"""
from __future__ import annotations

from typing import Any

from colex import prompts, testrunner
from colex.agents import coder_apply as ca
from colex.agents.coder_brief import brief, files, result
from colex.agents.impact_loop import law_block, tools_for
from colex.contracts import LawDocument
from colex.guardrails.injection import SYSTEM_RULE


def run(ctx, law: LawDocument, item: dict[str, Any], feedback: list[str], deps) -> dict[str, Any]:
    cfg, git = ctx.config, deps.gitops
    timeout, max_iter = cfg["budgets"]["test_timeout_s"], cfg["budgets"]["max_coder_iterations"]
    branch, worktree = git.create_branch(ctx.run_id, item["item_id"])
    target_path = ca.repo_path(item["resource_uri"])
    allowed = ca.editable(tools_for(ctx), item["resource_uri"])
    before = testrunner.run_tests(worktree, timeout)
    failing = before["failed"] + before["errors"]
    wanted = ca.targets(worktree, target_path, failing)
    ctx.emit("rationale", f"Tests before the change: {len(before['passed'])} pass, {len(failing)} fail. "
                          f"Target: {len(wanted)} failing compliance test(s) for {target_path}. "
                          f"Editable: {', '.join(allowed)}", {"targets": wanted, "editable": allowed})
    if before["unusable"]:
        return result("needs_human", branch, "", before, None, 0,
                      "The test suite could not be run before the change. Nothing was changed.")
    if not wanted and not feedback:
        return result("needs_human", branch, "", before, None, 0,
                      "No failing test covers this item, so coLEX cannot check a change. Nothing was changed.")
    system, version = prompts.load("coder", cfg)
    fixed = brief(item, law_block(law, [item["article_id"]]), allowed, wanted, before, feedback)
    history: list[dict[str, Any]] = []
    after = None
    for attempt in range(1, max_iter + 1):
        deps.rt.check_budget(ctx.run_id, cfg)
        user = f"{fixed}\nCurrent content of the editable files:\n{files(worktree, allowed)}"
        for past in history:
            user += f"\n\nAttempt {past['n']} was not accepted: {past['problem']}"
        answer = deps.llm.complete("coder", [{"role": "system", "content": system + "\n\n" + SYSTEM_RULE},
                                             {"role": "user", "content": user}], response_model=ca.Patch,
                                   prompt_version=version, run_id=ctx.run_id, cfg=cfg, step="REMEDIATE")
        patch: ca.Patch = answer.parsed
        try:
            ca.apply(worktree, patch, allowed)
            outside = [p for p in git.changed(worktree) if p not in allowed]
            if outside:
                raise ca.PatchError(f"files outside the editable list changed: {', '.join(outside)}")
        except ca.PatchError as exc:
            problem, after = f"the patch was refused: {exc}", None
        else:
            after = testrunner.run_tests(worktree, timeout)
            still = [t for t in wanted if t not in after["passed"]]
            broken = [t for t in before["passed"] if t not in after["passed"]]
            if not after["unusable"] and not still and not broken:
                sha = git.commit(worktree, f"colex: {patch.summary[:60]}\n\n{item['citation']}",
                                 f"{ctx.step_key}:{attempt}")
                ctx.emit("rationale", f"Attempt {attempt}: all {len(wanted)} target test(s) pass and nothing that "
                                      f"passed before fails ({len(after['passed'])} pass in total). "
                                      f"Committed {sha[:8]} on {branch}. Not merged.", {"attempt": attempt})
                return result("awaiting_review", branch, git.diff(branch), before, after, attempt, patch.summary,
                              commit=sha, attempts=history + [{"n": attempt, "problem": None}], targets=wanted)
            kind = "it broke test(s) that passed before" if broken else "the target test(s) still fail"
            problem = f"{kind}:\n{ca.failure_text(after, broken or still)}"
        history.append({"n": attempt, "problem": problem})
        lines = problem.splitlines()
        ctx.emit("retry", f"Attempt {attempt} not accepted: {lines[0][:150]}"
                          + (f" [{lines[1][:100]}]" if len(lines) > 1 else "")
                          + (" → revising" if attempt < max_iter else ""), {"attempt": attempt, "problem": problem})
        git.create_branch(ctx.run_id, item["item_id"])   # discard the rejected edit: back to the branch tip
    ctx.emit("escalation", f"Coder did not converge after {max_iter} attempts on {item['resource_uri']}; "
                           "an engineer needs to take over. No change request claims success.")
    return result("needs_human", branch, git.diff(branch), before, after, max_iter,
                  f"coLEX could not make the tests pass in {max_iter} attempts.", attempts=history, targets=wanted)

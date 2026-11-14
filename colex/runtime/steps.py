"""Durable steps and checkpoints.

Execution is replay-based. A driver calls `step()` for every node; a step that already completed
returns its stored output, so resuming a run means running its driver again.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from colex import db
from colex.runtime import audit, store
from colex.runtime.core import BudgetExceeded, RunPaused, StepContext, StepFailed


class Steps:
    def step(self, run_id: str, branch_id: str, node: str, fn: Callable[[StepContext], Any],
             inputs_ref: str = "", *, key: str | None = None, agent: str | None = None) -> Any:
        """Budget check → snapshot config → run fn → checkpoint → audit event. Completed steps are replayed."""
        step_key = key or f"{branch_id}:{node}"
        done = store.step_row(run_id, step_key)
        if done and done["status"] == "done":
            return store.get_blob(done["output_ref"])
        run = store.run_row(run_id)
        if run["paused"] or run["status"] == "cancelled":
            raise RunPaused(run_id)
        self._transition(run, branch_id, node)
        version = self.configs.active()   # hot reload: every new step takes the newest config
        self.check_budget(run_id, version.payload)
        self.set_branch(run_id, branch_id, "running", node)
        if branch_id == "main":
            db.connect().execute("update runs set current_node=? where run_id=?", (node, run_id))
        ctx = StepContext(self, run_id, branch_id, node, step_key, version.payload, version.version_id,
                          agent or node.lower())
        started = time.monotonic()
        try:
            output = fn(ctx)
        except (RunPaused, BudgetExceeded):
            raise
        except Exception as exc:  # never silent: mark the branch failed and say so on the timeline
            self.set_branch(run_id, branch_id, "failed")
            audit.emit(run_id, ctx.agent, node, "escalation",
                       f"Step {step_key} failed: {type(exc).__name__}: {exc}", {"step_key": step_key})
            raise StepFailed(f"{step_key}: {exc}") from exc
        ref, body = store.put_blob(output)
        checkpoint_id = self.checkpoint(run_id, branch_id, node, step_key, ref, version.version_id)
        db.connect().execute(
            "insert or replace into steps values(?,?,?,?,?,?,?,?,?)",
            (run_id, step_key, branch_id, node, "done", ref, checkpoint_id, version.version_id, audit.now()))
        audit.emit(run_id, ctx.agent, node, "step", f"{node} completed",
                   {"step_key": step_key, "branch": branch_id, "config_version_id": version.version_id},
                   input_ref=inputs_ref, output_ref=ref, checkpoint_id=checkpoint_id,
                   duration_ms=int((time.monotonic() - started) * 1000))
        return json.loads(body)

    def checkpoint(self, run_id: str, branch_id: str, node: str, step_key: str, state_ref: str,
                   config_version_id: str, git_ref: str | None = None) -> str:
        run = store.run_row(run_id)
        pending = [w["payload"] for w in store.waits(run_id, "pending")]
        used = audit.usage(run_id)
        con = db.connect()
        con.execute("begin immediate")
        try:
            last = con.execute("select checkpoint_id from checkpoints where run_id=? order by seq desc limit 1",
                               (run_id,)).fetchone()
            checkpoint_id = store.new_id("ckpt")
            con.execute("insert into checkpoints values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                checkpoint_id, run_id, branch_id, node, step_key, state_ref, db.dumps(pending), git_ref,
                db.dumps({"tokens": used["tokens"], "cost_usd": used["cost_usd"]}), config_version_id,
                run["map_version_id"], last["checkpoint_id"] if last else run["parent_checkpoint_id"],
                audit.now(), store.next_seq(con)))
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
        return checkpoint_id

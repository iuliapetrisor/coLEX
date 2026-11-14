"""The runtime: durable steps, checkpoints, human waits, idempotent side effects (brief §4.4)."""
from __future__ import annotations

import json
from typing import Any, Callable

from colex import db
from colex.runtime import audit, store
from colex.runtime.core import (TRANSITIONS, WAIT_STATUS, BudgetExceeded, Core, IllegalTransition,  # noqa: F401
                                RunPaused, StepContext, StepFailed)
from colex.runtime.steps import Steps
from colex.runtime.transfer import Transfer


class Runtime(Core, Steps, Transfer):
    def side_effect(self, key: str, fn: Callable[[], Any]) -> Any:
        """Record the intent, then act once. A key that already completed returns its stored result.

        If the process dies between the intent and the completion record, the effect is attempted again on
        resume, so `fn` must itself be idempotent for that key (the Slack outbox and GitOps are).
        """
        con = db.connect()
        row = con.execute("select * from side_effects where key=?", (key,)).fetchone()
        if row and row["status"] == "done":
            return json.loads(row["result_json"])
        con.execute("insert or ignore into side_effects(key,status,ts) values(?,?,?)", (key, "pending", audit.now()))
        result = fn()
        con.execute("update side_effects set status='done', result_json=?, ts=? where key=?",
                    (db.dumps(result), audit.now(), key))
        return json.loads(db.dumps(result))

    def wait_for_human(self, run_id: str, branch_id: str, kind: str, payload: dict[str, Any], *,
                       key: str, node: str | None = None) -> dict[str, Any] | None:
        """Durable human wait. Returns the answer if it has arrived, else None (the branch stays paused)."""
        wait_id = f"{run_id}:{key}"
        existing = store.wait(wait_id)
        if existing and existing["status"] == "answered":
            return {**existing["answer"], "actor": existing["actor"], "wait_id": wait_id}
        if existing is None:
            if node:
                self._transition(store.run_row(run_id), branch_id, node)
            con = db.connect()
            con.execute("begin immediate")
            con.execute("insert into waits(wait_id,run_id,branch_id,kind,payload_json,status,created_ts,seq_created)"
                        " values(?,?,?,?,?,?,?,?)", (wait_id, run_id, branch_id, kind, db.dumps(payload), "pending",
                                                     audit.now(), store.next_seq(con)))
            con.execute("commit")
            audit.emit(run_id, "runtime", "-", "wait", f"Waiting for a human ({kind}) on branch {branch_id}",
                       {"wait_id": wait_id, "branch": branch_id})
        self.set_branch(run_id, branch_id, WAIT_STATUS[kind], node)
        return None

    def deliver_human_answer(self, wait_id: str, answer: dict[str, Any], actor_user_id: str) -> bool:
        """Thread-safe. Returns False if the wait is unknown or was already answered (duplicate click)."""
        con = db.connect()
        con.execute("begin immediate")
        try:
            cur = con.execute(
                "update waits set status='answered', answer_json=?, actor=?, answered_ts=?, seq_answered=? "
                "where wait_id=? and status='pending'",
                (db.dumps(answer), actor_user_id, audit.now(), store.next_seq(con), wait_id))
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
        waiting = store.wait(wait_id)
        if cur.rowcount != 1:
            audit.emit(waiting["run_id"] if waiting else None, "runtime", "-", "human",
                       f"Ignored duplicate or unknown answer for {wait_id} from {actor_user_id}")
            return False
        audit.emit(waiting["run_id"], "runtime", "-", "human",
                   f"{actor_user_id} answered: {answer.get('decision') or answer.get('text', '')}",
                   {"wait_id": wait_id, "answer": answer, "actor": actor_user_id})
        self.set_branch(waiting["run_id"], waiting["branch_id"], "running")
        if self.on_answer:
            self.on_answer(waiting["run_id"])
        return True

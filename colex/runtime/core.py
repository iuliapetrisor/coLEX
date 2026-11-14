"""Runtime core: the state machine as data, run bookkeeping, budgets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from colex import db
from colex.config import ConfigStore
from colex.contracts import Run
from colex.runtime import audit, store

# The state machine, as data: the Console draws it and tests assert on it.
TRANSITIONS: dict[str, set[str]] = {
    "WATCH": {"TRIAGE"},
    "TRIAGE": {"IMPACT", "ESCALATED", "DONE"},
    "IMPACT": {"LIAISON", "ESCALATED", "DONE"},
    "LIAISON": {"ASK_LEGAL", "REMEDIATE", "REGISTER", "VERIFY"},
    "ASK_LEGAL": {"IMPACT", "REMEDIATE", "REGISTER", "VERIFY"},   # legal answer → re-plan affected items
    "REMEDIATE": {"REVIEW", "ESCALATED", "VERIFY"},
    "REVIEW": {"REMEDIATE", "VERIFY"},                              # request changes → back to the coder
    "ESCALATED": {"TRIAGE", "IMPACT", "REMEDIATE", "DONE"},
    "REGISTER": {"LIAISON", "VERIFY"},
    "VERIFY": {"DONE"},
    "DONE": set(),
}
WAIT_STATUS = {"legal": "waiting_for_legal", "review": "waiting_for_review", "escalation": "waiting_for_legal"}


class IllegalTransition(RuntimeError):
    pass


class RunPaused(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class StepFailed(RuntimeError):
    pass


@dataclass
class StepContext:
    rt: Any
    run_id: str
    branch_id: str
    node: str
    step_key: str
    config: dict[str, Any]
    config_version_id: str
    agent: str

    def emit(self, kind: str, summary: str, detail: dict[str, Any] | None = None, **extra: Any) -> int:
        return audit.emit(self.run_id, self.agent, self.node, kind, summary, detail, **extra)


class Core:
    def __init__(self) -> None:
        self.configs = ConfigStore()
        self.on_answer: Callable[[str], None] | None = None  # set by the orchestrator: drive this run again

    def start_run(self, law_id: str, *, parent_checkpoint_id: str | None = None,
                  meta: dict[str, Any] | None = None) -> Run:
        run_id = store.new_id("run")
        store.insert_run(run_id, law_id, self.configs.active().version_id, parent_checkpoint_id, meta)
        audit.emit(run_id, "runtime", "WATCH", "run", f"Run started for {law_id}")
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> Run:
        r = store.run_row(run_id)
        return Run(run_id=r["run_id"], law_id=r["law_id"], status=r["status"], current_node=r["current_node"],
                   branches={k: v["status"] for k, v in r["branches"].items()},
                   config_version_id=r["config_version_id"], map_version_id=r["map_version_id"],
                   parent_checkpoint_id=r["parent_checkpoint_id"])

    def set_branch(self, run_id: str, branch_id: str, status: str, node: str | None = None) -> None:
        run = store.run_row(run_id)
        branch = run["branches"].setdefault(branch_id, {"status": "running", "node": node or "WATCH"})
        branch["status"] = status
        if node:
            branch["node"] = node
        if run["status"] != "cancelled":
            run["status"] = store.derive_status(run["branches"], run["status"])
        store.save_run(run)

    def set_meta(self, run_id: str, **values: Any) -> None:
        run = store.run_row(run_id)
        run["meta"].update(values)
        if "map_version_id" in values:
            run["map_version_id"] = values["map_version_id"]
        store.save_run(run)

    def pause(self, run_id: str, actor: str = "console") -> None:
        db.connect().execute("update runs set paused=1 where run_id=?", (run_id,))
        audit.emit(run_id, "runtime", "-", "human", f"Run paused by {actor}")

    def resume(self, run_id: str, actor: str = "console") -> None:
        db.connect().execute("update runs set paused=0 where run_id=?", (run_id,))
        audit.emit(run_id, "runtime", "-", "human", f"Run resumed by {actor}")
        if self.on_answer:
            self.on_answer(run_id)

    def cancel(self, run_id: str, actor: str = "console") -> None:
        db.connect().execute("update runs set status='cancelled' where run_id=?", (run_id,))
        audit.emit(run_id, "runtime", "-", "human", f"Run cancelled by {actor}")

    def resume_all(self) -> list[str]:
        """Ids of unfinished runs, oldest first. Called at startup; the caller drives each one again."""
        rows = db.connect().execute("select run_id from runs where status not in ('done','failed','cancelled') "
                                    "order by created_ts").fetchall()
        return [r["run_id"] for r in rows]

    def _transition(self, run: dict[str, Any], branch_id: str, node: str) -> None:
        if node not in TRANSITIONS:
            raise IllegalTransition(f"unknown node {node}")
        branch = run["branches"].get(branch_id) or run["branches"].get("main") or {"node": "WATCH"}
        current = branch["node"]
        if node != current and node not in TRANSITIONS[current]:
            raise IllegalTransition(f"{branch_id}: {current} → {node} is not allowed")

    def check_budget(self, run_id: str, cfg: dict[str, Any]) -> None:
        used, factor = audit.usage(run_id), store.run_row(run_id)["meta"].get("budget_factor", 1)
        if used["tokens"] > cfg["budgets"]["max_tokens_per_run"] * factor:
            raise BudgetExceeded(f"token budget exceeded: {used['tokens']} tokens used in this run")
        if used["cost_usd"] > cfg["budgets"]["max_cost_usd_per_law"] * factor:
            raise BudgetExceeded(f"cost budget exceeded: ${used['cost_usd']:.4f} spent on this law")

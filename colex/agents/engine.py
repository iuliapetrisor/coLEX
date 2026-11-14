"""Engine: owns the dependencies, drives runs, turns budget overruns into human escalations."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from colex.agents import flow, watcher
from colex.contracts import Question
from colex.runtime import audit, store
from colex.runtime.api import BudgetExceeded, RunPaused, Runtime, StepFailed


@dataclass
class Deps:
    rt: Runtime
    llm: Any
    notifier: Any
    cmap: Any = None        # Company Map tools
    gitops: Any = None      # sandbox repository access for the coder


class Engine:
    def __init__(self, deps: Deps, background: bool = False) -> None:
        self.deps = deps
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="colex-engine") if background else None
        if background:   # answers arriving from Slack or the Console resume the run on the engine thread
            deps.rt.on_answer = self.kick

    def kick(self, run_id: str) -> None:
        if self._pool:
            self._pool.submit(self.drive, run_id)

    def drive(self, run_id: str) -> str:
        """Advance a run as far as possible. Never raises: every failure becomes a visible event."""
        rt = self.deps.rt
        with self._lock:
            try:
                flow.advance(self.deps, run_id)
            except RunPaused:
                pass
            except StepFailed:
                pass   # already on the timeline, branch marked failed
            except BudgetExceeded as exc:
                self._budget(run_id, str(exc))
            except Exception as exc:   # a bug in the driver itself: show it, do not hide it
                audit.emit(run_id, "engine", "-", "escalation", f"Run stopped: {type(exc).__name__}: {exc}")
                rt.set_branch(run_id, "main", "failed")
        return rt.get_run(run_id).status

    def _budget(self, run_id: str, reason: str) -> None:
        rt = self.deps.rt
        number = len([w for w in store.waits(run_id) if w["wait_id"].startswith(f"{run_id}:ask:budget-")]) + 1
        if store.waits(run_id, "pending"):
            pending = [w for w in store.waits(run_id, "pending") if ":ask:budget-" in w["wait_id"]]
            if pending:
                return
        audit.emit(run_id, "engine", "-", "escalation", f"Budget exceeded: {reason}. Asking a human.")
        q = Question(to_team="compliance", text=f"Run {run_id} stopped: {reason}. Raise the budget and continue?",
                     options=["Double the budget and continue", "Stop the run"])
        channel = rt.configs.active().payload["routing"]["unknown_owner_channel"]
        branch = "main"
        node = store.run_row(run_id)["branches"].get("main", {}).get("node", "WATCH")
        answer = flow.ask(self.deps, run_id, branch, node, f"budget-{number}", q, channel, "legal")
        if answer is not None:
            self.apply_budget_answer(run_id, answer)

    def apply_budget_answer(self, run_id: str, answer: dict[str, Any]) -> None:
        rt = self.deps.rt
        if answer.get("decision", "").startswith("Double"):
            factor = store.run_row(run_id)["meta"].get("budget_factor", 1) * 2
            rt.set_meta(run_id, budget_factor=factor)
            audit.emit(run_id, "engine", "-", "human", f"Budget raised ×{factor} by {answer.get('actor')}")
        else:
            rt.cancel(run_id, answer.get("actor", "human"))

    def poll_feed(self, feed: Path) -> dict[str, list[str]]:
        """Register newly published acts and start one run per act."""
        found = watcher.scan(feed)
        for celex in found["new"]:
            run = self.deps.rt.start_run(celex)
            watcher.set_law(celex, run_id=run.run_id, status="triage")
            found.setdefault("runs", []).append(run.run_id)
        return found

    def resume_all(self) -> list[str]:
        """After a restart: continue every unfinished run from its last checkpoint."""
        ids = self.deps.rt.resume_all()
        for run_id in ids:
            audit.emit(run_id, "engine", "-", "run", "Resumed after restart from the last checkpoint")
            self.drive(run_id)
        return ids

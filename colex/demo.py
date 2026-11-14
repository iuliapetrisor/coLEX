"""`make demo`: the brief §1.5 scenario, unattended, in the terminal (D-017).

Human decisions are given by a labelled demo auto-clicker through the same
`deliver_human_answer` path that Slack and the Console use. Nothing is merged.

    python -m colex.demo            live model calls (cached)
    COLEX_OFFLINE=1 python -m colex.demo   recorded answers only
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from colex import settings

ACTOR = "demo-autoclicker"
ICON = {"rationale": "→", "tool": "·", "llm": " ", "step": "✓", "escalation": "!", "retry": "↻", "human": "☺",
        "wait": "⏸", "notify": "✉", "run": "▶", "watch": "·", "config": "⚙"}


def build(var: Path, fresh: bool = True):
    """Create the engine on a state directory. Returns (engine, deps)."""
    if fresh and var.exists():
        shutil.rmtree(var)
    os.environ["COLEX_VAR"] = str(var)
    os.environ.pop("COLEX_DB", None)
    settings.load_env()
    from colex.agents.engine import Deps, Engine
    from colex.llm import LLMClient
    from colex.notify.base import FakeNotifier
    from colex.runtime.api import Runtime

    deps = Deps(rt=Runtime(), llm=LLMClient(), notifier=FakeNotifier())
    return Engine(deps), deps


class Printer:
    def __init__(self, quiet: bool = False) -> None:
        self.last, self.quiet = 0, quiet

    def flush(self) -> None:
        from colex.runtime import audit
        for e in audit.events(after_id=self.last):
            self.last = e["id"]
            if self.quiet or e["kind"] in ("llm", "tool"):
                continue
            run = (e["run_id"] or "")[-4:]
            print(f"  {ICON.get(e['kind'], ' ')} [{run:>4}] {e['agent']:<9} {e['summary'][:150]}")


def answer_pending(deps, engine, printer: Printer) -> int:
    """Auto-clicker: first option for questions, approve for reviews. Returns how many waits it answered."""
    from colex.runtime import store
    count = 0
    for wait in store.waits(status="pending"):
        if wait["kind"] == "review":
            answer = {"decision": "approve"}
        else:
            options = wait["payload"]["question"]["options"]
            answer = {"decision": options[0] if options else "ok"}
        if deps.rt.deliver_human_answer(wait["wait_id"], answer, ACTOR):
            if ":ask:budget-" in wait["wait_id"]:
                engine.apply_budget_answer(wait["run_id"], {**answer, "actor": ACTOR})
            count += 1
            engine.drive(wait["run_id"])
            printer.flush()
    return count


def main(argv: list[str]) -> int:
    started = time.monotonic()
    engine, deps = build(settings.ROOT / "var" / "demo")
    from colex.agents import watcher
    from colex.runtime import store
    printer = Printer(quiet="--quiet" in argv)
    mode = "OFFLINE (recorded answers)" if settings.offline() else "LIVE (OpenRouter, cached)"
    print(f"coLEX demo · PayRo SRL is a fictional company · model calls: {mode}\n")

    print("1. Publishing the official feed")
    for path in sorted(settings.FEED.glob("*.md")):
        shutil.copy(path, settings.inbox() / path.name)
    found = engine.poll_feed(settings.inbox())
    print(f"  {len(found['new'])} acts published, {len(found['quarantined'])} quarantined\n")

    print("2. Triage, impact analysis, notifications")
    for run_id in found.get("runs", []):
        engine.drive(run_id)
        printer.flush()

    print("\n3. Human decisions (given here by the demo auto-clicker, not by a person)")
    for _ in range(20):
        if not answer_pending(deps, engine, printer):
            break

    laws = watcher.laws()
    relevant = [law for law in laws if law["status"] == "relevant"]
    print(f"\n4. Result: {len(relevant)} relevant act(s), {len(laws) - len(relevant)} archived with a reason")
    for law in relevant:
        row = store.run_row(law["run_id"])
        done = store.step_row(law["run_id"], "main:VERIFY")
        print(f"  {law['celex']} · run {law['run_id']} · {row['status']}")
        if done:
            summary = store.get_blob(done["output_ref"])
            print(f"    items {summary['items']} · tokens {summary['tokens']} · cost ${summary['cost_usd']} · "
                  f"change requests {len(summary['change_requests'])} (merged: 0)")
    unfinished = [law["celex"] for law in laws if law["run_id"]
                  and store.run_row(law["run_id"])["status"] != "done"]
    print(f"\nFinished in {time.monotonic() - started:.1f}s. State: var/demo/. "
          + (f"NOT finished: {', '.join(unfinished)}" if unfinished else "All runs completed."))
    return 1 if unfinished else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

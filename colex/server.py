"""`make console`: the Console, the engine and (when tokens are present) the real Slack connection.

On start-up every unfinished run is resumed from its last checkpoint. Slack is used only when both
SLACK_BOT_TOKEN and SLACK_APP_TOKEN are in the environment and COLEX_SLACK is not "0"; otherwise the
FakeNotifier records messages and the Console is the place to act.

The Console has no authentication, so the server listens on 127.0.0.1 only.
"""
from __future__ import annotations

import os
import threading
import time

from colex import settings

HOST = "127.0.0.1"


def build(background: bool = True):
    """Returns (app, engine, deps, slack status text)."""
    settings.load_env()
    from colex.agents.engine import Deps, Engine
    from colex.api.app import create_app
    from colex.gitops import GitOps
    from colex.guardrails import log_scrub
    from colex.llm import LLMClient
    from colex.notify.base import FakeNotifier
    from colex.runtime import audit
    from colex.runtime.api import Runtime

    log_scrub.install()
    rt = Runtime()
    gitops = GitOps(settings.var_dir() / "repo", settings.var_dir() / "worktrees")
    gitops.seed(settings.SANDBOX / "repo_seed")
    notifier, slack, start_slack = FakeNotifier(), "off: messages are recorded, act from the Console", None
    wanted = os.environ.get("COLEX_SLACK", "1") != "0"
    if wanted and os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_APP_TOKEN") and not settings.offline():
        try:
            from colex.notify.app import build as build_slack
            from colex.notify.slack import SlackNotifier
            _, notifier, start_slack = build_slack(rt, SlackNotifier)
            slack = "connecting (Socket Mode)"
        except Exception as exc:   # Slack is optional: the Console still works
            slack = f"unavailable ({type(exc).__name__}); act from the Console"
            audit.emit(None, "slack", "-", "escalation", f"Slack could not be set up: {type(exc).__name__}")
    deps = Deps(rt=rt, llm=LLMClient(), notifier=notifier, gitops=gitops)
    engine = Engine(deps, background=background)
    engine.ensure_map()
    if start_slack:
        try:
            start_slack()
            slack = "connected (Socket Mode)"
        except Exception as exc:
            slack = f"not connected ({type(exc).__name__}); messages stay queued, act from the Console"
            audit.emit(None, "slack", "-", "escalation", f"Slack connection failed: {type(exc).__name__}")
    return create_app(engine, deps), engine, deps, slack


def _background(engine, deps) -> None:
    """Resume unfinished runs, then keep polling the live feed and retrying queued Slack messages."""
    for run_id in deps.rt.resume_all():
        from colex.runtime import audit
        audit.emit(run_id, "engine", "-", "run", "Resumed after restart from the last checkpoint")
        engine.kick(run_id)
    while True:
        time.sleep(3)
        try:
            for run_id in engine.poll_feed(settings.inbox()).get("runs", []):
                engine.kick(run_id)
            deps.notifier.flush()
        except Exception as exc:   # keep the loop alive; the next pass retries
            from colex.runtime import audit
            audit.emit(None, "engine", "-", "escalation", f"Background loop error: {type(exc).__name__}: {exc}")


def main() -> None:
    import uvicorn

    port = int(os.environ.get("COLEX_PORT", "8000"))
    app, engine, deps, slack = build()
    threading.Thread(target=_background, args=(engine, deps), daemon=True, name="colex-background").start()
    print(f"coLEX Console: http://{HOST}:{port}  ·  state: {settings.var_dir()}  ·  Slack: {slack}", flush=True)
    print("The Console has no login. It listens on this machine only.", flush=True)
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()

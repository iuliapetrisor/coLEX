"""Bolt wiring for Socket Mode. Every handler acks first (Slack needs an answer within 3 seconds),
then the work runs on a worker thread. Tokens come from the environment only."""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor

from colex.notify import commands
from colex.notify.handlers import Handlers
from colex.runtime import audit


def _safe(fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:   # never lose an interaction silently
        audit.emit(None, "slack", "-", "escalation", f"Slack handler failed: {type(exc).__name__}: {exc}")


def build(rt, notifier_factory):
    """Returns (bolt app, notifier, start function). Needs SLACK_BOT_TOKEN and SLACK_APP_TOKEN."""
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    notifier = notifier_factory(app.client)
    handlers = Handlers(rt, notifier, app.client)
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="colex-slack")

    @app.action(re.compile(r"^colex_"))
    def on_action(ack, body):
        ack()
        pool.submit(_safe, handlers.on_action, body)

    @app.view(re.compile(r"^colex_modal_"))
    def on_view(ack, body):
        ack()
        pool.submit(_safe, handlers.on_view, body)

    @app.command("/colex")
    def on_command(ack, command, respond):
        ack()
        respond(commands.command(rt, command.get("text", ""), command["user_id"]))

    @app.event("app_mention")
    def on_mention(event, say):
        say(text=commands.mention(event.get("text", "")), thread_ts=event.get("ts"))

    def start() -> None:
        SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).connect()   # reconnects on its own

    return app, notifier, start

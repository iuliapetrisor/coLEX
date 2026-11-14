"""Read-only Slack check: authenticate, open the Socket Mode connection, look up the routed channels.

    make slack-check

Posts nothing and prints no token. Uses its own empty state directory, so no queued message can be sent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["COLEX_VAR"] = str(ROOT / "var" / "slack-check")


def main() -> int:
    from colex import settings
    settings.load_env()
    missing = [name for name in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN") if not os.environ.get(name)]
    if missing:
        print("not configured: " + ", ".join(missing) + " missing from the environment / .env")
        return 2
    from colex.config import ConfigStore
    from colex.notify.app import build
    from colex.notify.slack import SlackNotifier
    from colex.runtime.api import Runtime
    try:
        app, notifier, start = build(Runtime(), SlackNotifier)
        who = app.client.auth_test()
        print(f"authenticated: workspace '{who.get('team')}', bot user '{who.get('user')}'")
    except Exception as exc:
        print(f"authentication failed: {type(exc).__name__}")
        return 1
    try:
        start()
        print("Socket Mode: connected")
    except Exception as exc:
        print(f"Socket Mode: NOT connected ({type(exc).__name__})")
        return 1
    cfg = ConfigStore().active().payload
    wanted = sorted({*cfg["routing"]["team_channels"].values(), cfg["routing"]["unknown_owner_channel"],
                     cfg["routing"]["review_channel"]})
    found = {name: notifier.channel_id(name) is not None for name in wanted}
    print("channels: " + ", ".join(f"{name} {'ok' if ok else 'MISSING'}" for name, ok in found.items()))
    approvers = {role: len(ids) for role, ids in cfg["routing"]["approvers"].items()}
    print(f"approvers mapped in config: {approvers} (0 means nobody can decide from Slack yet)")
    return 0 if all(found.values()) else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)   # the Socket Mode client keeps background threads alive

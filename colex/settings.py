"""Paths and environment. Secrets are read from the environment only and never logged."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "sandbox"
FEED = SANDBOX / "feed"
CONFIG_DIR = ROOT / "config"
PROMPTS = ROOT / "prompts"
CASSETTES = ROOT / "tests" / "fixtures" / "llm"


def var_dir() -> Path:
    path = Path(os.environ.get("COLEX_VAR", ROOT / "var"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return Path(os.environ.get("COLEX_DB", var_dir() / "colex.db"))


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into the process environment, without overriding it."""
    path = path or ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def inbox() -> Path:
    """The live feed the watcher polls. Publishing an act copies it here from the library (FEED)."""
    path = var_dir() / "feed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def offline() -> bool:
    return os.environ.get("COLEX_OFFLINE", "") not in ("", "0", "false")

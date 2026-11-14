"""Versioned prompts: prompts/<agent>/<version>.md with a YAML front matter. The version comes from config."""
from __future__ import annotations

from typing import Any

from colex import settings


def load(agent: str, cfg: dict[str, Any]) -> tuple[str, str]:
    """Returns (prompt text, prompt version id used in the LLM cache key)."""
    version = cfg["prompt_versions"][agent]
    path = settings.PROMPTS / agent / f"{version}.md"
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---\n", 2)[2] if raw.startswith("---\n") else raw
    return body.strip(), f"{agent}-{version}"

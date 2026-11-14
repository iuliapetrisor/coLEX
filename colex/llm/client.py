"""The only path to a model (README §2 rule 4): OpenRouter, routing, cache, redaction, accounting.

Modes (env COLEX_LLM_MODE, default "live"):
  live    call OpenRouter; responses are cached in SQLite by request hash
  record  like live, and every response is also written to a cassette file
  replay  cassettes only; a missing cassette raises CassetteMiss (used by tests and OFFLINE=1)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from colex import db, settings
from colex.config import ConfigStore
from colex.guardrails.redaction import RedactionCtx, redact
from colex.runtime import audit

URL = "https://openrouter.ai/api/v1/chat/completions"
ROLE_ENV = {"cheap": "MODEL_CHEAP", "strong": "MODEL_STRONG"}


class LLMUnavailable(RuntimeError):
    """The model could not be reached after every retry."""


class CassetteMiss(LLMUnavailable):
    """Replay mode and no recorded response for this exact request."""


class TransientError(RuntimeError):
    pass


@dataclass
class LLMResult:
    content: str
    tool_calls: list[dict[str, Any]]
    usage: dict[str, int]
    cost_usd: float
    cached: bool
    model: str
    parsed: BaseModel | None = None
    message: dict[str, Any] = field(default_factory=dict)


def http_transport(body: dict[str, Any], timeout: int) -> dict[str, Any]:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise LLMUnavailable("OPENROUTER_API_KEY is not set")
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "coLEX"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code >= 500:
            raise TransientError(f"HTTP {exc.code}") from None
        raise LLMUnavailable(f"OpenRouter refused the request: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransientError(f"network: {type(exc).__name__}") from None
    if "error" in data and "choices" not in data:
        raise TransientError(f"provider error: {str(data['error'])[:200]}")
    return data


class LLMClient:
    def __init__(self, mode: str | None = None, transport: Callable[[dict, int], dict] | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.mode = mode or ("replay" if settings.offline() else os.environ.get("COLEX_LLM_MODE", "live"))
        self.transport = transport or http_transport
        self.sleep = sleep
        self.redaction = RedactionCtx()

    def model_for(self, agent: str, cfg: dict[str, Any]) -> str:
        role = cfg["agent_models"].get(agent, "cheap")
        return os.environ.get(ROLE_ENV.get(role, ""), "") or cfg["models"][role]

    def _redact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for m in messages:
            m = {k: v for k, v in m.items() if not k.startswith("_")}  # private markers stay local
            if isinstance(m.get("content"), str):
                m["content"] = redact(m["content"], self.redaction)
            out.append(m)
        return out

    def _lookup(self, key: str) -> dict[str, Any] | None:
        """Recorded cassette first, then the local cache (never in replay mode)."""
        places = [settings.CASSETTES] if self.mode == "replay" else [settings.CASSETTES, settings.llm_cache_dir()]
        for folder in places:
            path = folder / f"{key}.json"
            if path.is_file():
                if self.mode == "record" and folder != settings.CASSETTES:
                    settings.CASSETTES.mkdir(parents=True, exist_ok=True)
                    (settings.CASSETTES / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                return json.loads(path.read_text(encoding="utf-8"))["response"]
        return None

    def _store(self, key: str, agent: str, body: dict[str, Any], response: dict[str, Any]) -> None:
        keep = {"choices": [{"message": c.get("message"), "finish_reason": c.get("finish_reason")}
                            for c in response.get("choices", [])], "usage": response.get("usage")}
        text = json.dumps({"agent": agent, "model": body["model"], "response": keep}, ensure_ascii=False, indent=1)
        folders = [settings.llm_cache_dir()] + ([settings.CASSETTES] if self.mode == "record" else [])
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{key}.json").write_text(text, encoding="utf-8")

    def _call(self, body: dict[str, Any], cfg: dict[str, Any], agent: str, run_id: str | None) -> dict[str, Any]:
        attempts = cfg["budgets"]["llm_max_attempts"]
        for attempt in range(1, attempts + 1):
            try:
                return self.transport(body, cfg["budgets"]["llm_timeout_s"])
            except TransientError as exc:
                if attempt == attempts:
                    audit.emit(run_id, agent, "-", "escalation",
                               f"LLM unreachable after {attempts} attempts ({exc}). Use OFFLINE=1 to replay.")
                    raise LLMUnavailable(f"LLM unreachable after {attempts} attempts: {exc}") from None
                delay = min(2 ** attempt, 20)
                audit.emit(run_id, agent, "-", "retry", f"LLM call failed ({exc}); retry {attempt}/{attempts - 1} "
                                                        f"in {delay}s")
                self.sleep(delay)
        raise LLMUnavailable("unreachable")

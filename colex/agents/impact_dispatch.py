"""Dispatcher of the Impact Analyst: the rules the model must follow are enforced here, in code.

- only allowlisted tools; every map call needs a one-line rationale
- read() only for a resource an earlier result returned (locate before read)
- every reported item passes the grounding validator; the owner comes from the map, never the model
"""
from __future__ import annotations

import json
from typing import Any

from colex.agents.impact_report import Reporting
from colex.contracts import LawDocument
from colex.guardrails.injection import detect_injection, wrap_untrusted
from colex.map.tool_schemas import MAP_TOOL_NAMES

ARGS = {"overview": (), "browse": ("path", "depth", "facets"), "list_resources": ("path", "facets", "cursor"),
        "find": ("etype", "value", "under", "cursor"), "search": ("text", "under", "cursor"),
        "counterparty": ("name",), "owners": ("team",), "related": ("uri_or_path", "kinds"),
        "obligations": ("article", "path"), "read": ("uri", "start", "end")}


def _uris(value: Any, found: set[str]) -> None:
    """Collect every resource uri a tool result mentions."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("uri", "from", "to") and isinstance(item, str):
                found.add(item)
            else:
                _uris(item, found)
    elif isinstance(value, list):
        for item in value:
            _uris(item, found)


class Dispatcher(Reporting):
    def __init__(self, ctx, law: LawDocument, flagged: list[str], tools, prefix: str = "") -> None:
        self.ctx, self.law, self.flagged, self.tools, self.prefix = ctx, law, flagged, tools, prefix
        self.items: list[dict[str, Any]] = []
        self.questions: list[dict[str, Any]] = []
        self.dropped: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []
        self.seen: set[str] = set()
        self.flagged_docs: set[str] = set()
        self.rejections: dict[tuple, int] = {}
        self.finished: str | None = None
        self.scope: set[str] | None = None   # set during a re-plan: only these resources may be reported

    def call(self, name: str, raw_args: Any) -> dict[str, Any]:
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            if not isinstance(args, dict):
                raise ValueError
        except ValueError:
            self.ctx.emit("retry", f"Malformed arguments for tool '{name}'; asked the model to retry")
            return {"error": "arguments must be a JSON object"}
        if name in MAP_TOOL_NAMES:
            return self._map(name, args)
        if name == "report_impact":
            return self.report(args)
        if name == "ask_legal":
            return self.ask(args)
        if name == "finish":
            self.finished = str(args.get("summary", ""))[:600]
            return {"ok": True}
        self.ctx.emit("escalation", f"Refused tool '{name}': not on the Impact Analyst allowlist")
        return {"error": f"tool '{name}' is not available"}

    def _map(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        rationale = str(args.get("rationale", "")).strip()
        if len(rationale) < 8:
            return {"error": "every call needs a one-line 'rationale' saying why it follows from the article or "
                             "the previous result"}
        if name == "read" and args.get("uri") not in self.seen:
            return {"error": "locate before reading: use list_resources, find, search, related or counterparty "
                             "first, then read a uri they returned"}
        kwargs = {k: v for k, v in args.items() if k in ARGS[name]}
        try:
            out = getattr(self.tools, name)(**kwargs)
        except TypeError as exc:
            return {"error": f"bad arguments: {exc}"}
        _uris(out, self.seen)
        self.ctx.emit("rationale", rationale[:300], {"tool": name, "args": kwargs, "breadcrumbs": out["breadcrumbs"],
                                                     "tokens": out["tokens_estimate"], "error": out.get("error")})
        self.trace.append({"tool": name, "args": kwargs, "breadcrumbs": out["breadcrumbs"]})
        if name == "read" and "text" in out:
            findings = detect_injection(out["text"])
            if findings and out["uri"] not in self.flagged_docs:
                self.flagged_docs.add(out["uri"])
                line = out["start"] + findings[0]["line"] - 1
                self.ctx.emit("escalation", f"Suspicious instructions found in {out['uri']} (line {line}); "
                              "treated as data, not followed", {"uri": out["uri"], "snippet": findings[0]["snippet"]})
            out = {**out, "text": wrap_untrusted(out["uri"], out["text"])}
        return out

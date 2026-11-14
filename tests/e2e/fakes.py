"""A scripted stand-in for the model, so flow tests run offline and deterministically.

It answers triage from a fixed set of relevant acts and plays a fixed list of tool calls for the
Impact Analyst. It is a test double: it proves the runtime and the guards, not model quality.
"""
from __future__ import annotations

import json
import re
from typing import Any

from colex.agents.triage import Verdict
from colex.llm.client import LLMResult

RELEVANT = {"32024R0886"}
ART = "Art. 5b (inserted by Art. 1)"
PRICING = "PayRo › Technology & Security › Configuration › Pricing configuration"

# One list entry per model turn: the tool calls of that turn.
IMPACT_SCRIPT: list[list[tuple[str, dict[str, Any]]]] = [
    [("overview", {"rationale": "start from the company overview"})],
    [("list_resources", {"path": PRICING, "rationale": "Art. 5b concerns charges → pricing configuration"})],
    [("read", {"uri": "repo://payments/fees.yaml", "start": 7, "end": 9,
               "rationale": "read the euro fees the card pointed to"})],
    [("report_impact", {"article_id": ART, "resource_uri": "repo://payments/fees.yaml", "start": 7, "end": 9,
                        "quote": "instant: 1.50", "action": "CONFIG_CHANGE", "confidence": 0.9,
                        "deadline": "2027-01-09",
                        "obligation": "The instant euro fee must not be higher than the standard euro fee."})],
    [("finish", {"summary": "pricing configuration covered"})],
]


def _result(content: str = "", calls: list[tuple[str, dict[str, Any]]] | None = None, parsed=None) -> LLMResult:
    tool_calls = [{"id": f"call-{n}", "type": "function",
                   "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
                  for n, (name, args) in enumerate(calls or [])]
    return LLMResult(content=content, tool_calls=tool_calls, usage={"prompt_tokens": 0, "completion_tokens": 0},
                     cost_usd=0.0, cached=True, model="scripted", parsed=parsed)


class ScriptedLLM:
    def __init__(self, impact_script=None, coder_answers: list[dict[str, Any]] | None = None,
                 relevant: set[str] | None = None) -> None:
        self.relevant = relevant or RELEVANT
        self.impact_script = impact_script or IMPACT_SCRIPT
        self.coder_answers = list(coder_answers or [])
        self.calls: list[str] = []

    def complete(self, agent: str, messages: list[dict[str, Any]], **kwargs: Any) -> LLMResult:
        self.calls.append(agent)
        if agent == "triage":
            celex = re.search(r"CELEX:(\w+)", messages[-1]["content"]).group(1)
            verdict = Verdict(relevance=1.0 if celex in self.relevant else 0.0, articles_flagged=["Art. 1"],
                              reason="scripted verdict")
            return _result(parsed=verdict)
        if agent == "impact":
            turn = sum(1 for m in messages if m["role"] == "assistant")
            script = self.impact_script
            return _result(calls=script[turn] if turn < len(script) else [("finish", {"summary": "done"})])
        if agent == "coder":
            answer = self.coder_answers.pop(0) if self.coder_answers else {"summary": "no change", "edits": []}
            model = kwargs.get("response_model")
            return _result(content=json.dumps(answer), parsed=model.model_validate(answer) if model else None)
        raise AssertionError(f"unexpected agent {agent}")

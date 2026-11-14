"""`complete()`: one model call with cache, redaction, accounting and structured output."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ValidationError

from colex.config import ConfigStore
from colex.llm.client import CassetteMiss, LLMClient, LLMResult, LLMUnavailable
from colex.runtime import audit


def request_key(body: dict[str, Any], prompt_version: str) -> str:
    text = json.dumps({"body": body, "prompt_version": prompt_version}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse(content: str, response_model: type[BaseModel]) -> BaseModel:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return response_model.model_validate_json(text)


def complete(client: LLMClient, agent: str, messages: list[dict[str, Any]], *,
             tools: list[dict[str, Any]] | None = None, response_model: type[BaseModel] | None = None,
             prompt_version: str, run_id: str | None = None, cfg: dict[str, Any] | None = None,
             step: str = "-") -> LLMResult:
    cfg = cfg or ConfigStore().active().payload
    model = client.model_for(agent, cfg)
    body: dict[str, Any] = {"model": model, "messages": client._redact(messages), "temperature": 0,
                            "usage": {"include": True}}
    if tools:
        body["tools"] = tools
    if response_model is not None:
        body["response_format"] = {"type": "json_object"}
    key = request_key(body, prompt_version)
    response = client._lookup(key)
    cached = response is not None
    if response is None:
        if client.mode == "replay":
            audit.emit(run_id, agent, step, "escalation",
                       f"Offline replay has no recorded answer for this {agent} request ({key[:10]}).")
            raise CassetteMiss(f"no cassette for {agent} request {key[:16]} (prompt {prompt_version}, {model})")
        response = client._call(body, cfg, agent, run_id)
        client._store(key, agent, body, response)
    choices = response.get("choices") or []
    if not choices:
        raise LLMUnavailable("the model returned an empty response")
    message = choices[0].get("message") or {}
    usage = response.get("usage") or {}
    tokens_in, tokens_out = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    recorded_cost = float(usage.get("cost") or 0.0)
    result = LLMResult(content=message.get("content") or "", tool_calls=message.get("tool_calls") or [],
                       usage={"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
                       cost_usd=0.0 if cached else recorded_cost, cached=cached, model=model, message=message)
    audit.emit(run_id, agent, step, "llm",
               f"{agent} · {model} · {tokens_in}+{tokens_out} tokens" + (" · cached" if cached else ""),
               {"cached": cached, "recorded_cost_usd": recorded_cost, "prompt_version": prompt_version,
                "truncated": choices[0].get("finish_reason") == "length"},
               tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=result.cost_usd, model=model)
    if response_model is not None:
        try:
            result.parsed = _parse(result.content, response_model)
        except (ValidationError, ValueError) as exc:
            audit.emit(run_id, agent, step, "retry", f"{agent} returned output that does not match the schema")
            if messages and messages[-1].get("_schema_retry"):
                raise LLMUnavailable(f"{agent} output does not match the schema: {str(exc)[:300]}") from None
            retry = [m for m in messages] + [
                {"role": "assistant", "content": result.content},
                {"role": "user", "_schema_retry": True, "content":
                    "Your answer did not match the required JSON schema. Error:\n" + str(exc)[:800]
                    + "\nAnswer again with valid JSON only."}]
            return complete(client, agent, retry, tools=tools, response_model=response_model,
                            prompt_version=prompt_version, run_id=run_id, cfg=cfg, step=step)
    return result

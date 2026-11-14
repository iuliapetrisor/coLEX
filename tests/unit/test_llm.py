"""LLM client: cache, replay, retries, redaction, structured output. No network."""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from colex import settings
from colex.llm import CassetteMiss, LLMClient, LLMUnavailable, TransientError
from colex.runtime import audit


class Answer(BaseModel):
    relevant: bool


def reply(content: str = "hi", cost: float = 0.002) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": cost}}


class Transport:
    def __init__(self, *results):
        self.results, self.bodies = list(results), []

    def __call__(self, body, timeout):
        self.bodies.append(body)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


MSG = [{"role": "user", "content": "hello"}]


@pytest.fixture(autouse=True)
def _env(colex_db_path, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CASSETTES", tmp_path / "cassettes")
    monkeypatch.delenv("MODEL_CHEAP", raising=False)
    monkeypatch.delenv("MODEL_STRONG", raising=False)


def test_second_identical_call_is_cached_and_free():
    transport = Transport(reply())
    client = LLMClient(mode="live", transport=transport)
    first = client.complete("triage", MSG, prompt_version="v1")
    second = client.complete("triage", MSG, prompt_version="v1")
    assert (first.cached, first.cost_usd) == (False, 0.002)
    assert (second.cached, second.cost_usd, second.content) == (True, 0.0, "hi")
    assert len(transport.bodies) == 1


def test_cache_key_depends_on_prompt_version_and_model(monkeypatch):
    transport = Transport(reply("a"), reply("b"), reply("c"))
    client = LLMClient(mode="live", transport=transport)
    client.complete("triage", MSG, prompt_version="v1")
    assert client.complete("triage", MSG, prompt_version="v2").content == "b"
    monkeypatch.setenv("MODEL_CHEAP", "other/model")
    assert client.complete("triage", MSG, prompt_version="v1").content == "c"
    assert transport.bodies[2]["model"] == "other/model"


def test_record_then_strict_replay():
    LLMClient(mode="record", transport=Transport(reply("recorded"))).complete("triage", MSG, prompt_version="v1")
    assert len(list(settings.CASSETTES.glob("*.json"))) == 1
    replay = LLMClient(mode="replay", transport=Transport())
    assert replay.complete("triage", MSG, prompt_version="v1").content == "recorded"
    with pytest.raises(CassetteMiss):
        replay.complete("triage", [{"role": "user", "content": "something else"}], prompt_version="v1")


def test_two_failures_then_success_is_visible():
    transport = Transport(TransientError("HTTP 429"), TransientError("network: timeout"), reply())
    client = LLMClient(mode="live", transport=transport, sleep=lambda s: None)
    assert client.complete("triage", MSG, prompt_version="v1", run_id="run-1").content == "hi"
    assert [e["kind"] for e in audit.events("run-1")] == ["retry", "retry", "llm"]


def test_exhausted_retries_escalate():
    transport = Transport(*[TransientError("HTTP 503")] * 3)
    client = LLMClient(mode="live", transport=transport, sleep=lambda s: None)
    with pytest.raises(LLMUnavailable):
        client.complete("triage", MSG, prompt_version="v1", run_id="run-1")
    assert audit.events("run-1")[-1]["kind"] == "escalation"


def test_personal_data_never_reaches_the_model_or_the_cassette():
    transport = Transport(reply())
    client = LLMClient(mode="record", transport=transport)
    client.complete("triage", [{"role": "user", "content": "IBAN RO49AAAA1B31007593840000, ana@payro.example"}],
                    prompt_version="v1")
    sent = json.dumps(transport.bodies[0], ensure_ascii=False)
    sent += "".join(p.read_text(encoding="utf-8") for p in settings.CASSETTES.glob("*.json"))
    assert "RO49AAAA1B31007593840000" not in sent and "ana@payro.example" not in sent
    assert "⟨IBAN_" in sent and "⟨EMAIL_" in sent


def test_structured_output_is_parsed_and_bad_output_is_retried_once():
    client = LLMClient(mode="live", transport=Transport(reply("not json"), reply('{"relevant": true}')))
    assert client.complete("triage", MSG, prompt_version="v1", response_model=Answer).parsed.relevant is True
    client = LLMClient(mode="live", transport=Transport(reply("nope"), reply("still nope")))
    with pytest.raises(LLMUnavailable):
        client.complete("triage", [{"role": "user", "content": "x"}], prompt_version="v1", response_model=Answer)


def test_empty_response_is_an_error():
    client = LLMClient(mode="live", transport=Transport({"choices": []}))
    with pytest.raises(LLMUnavailable):
        client.complete("triage", MSG, prompt_version="v1")

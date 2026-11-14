"""LLM access. Use `LLMClient().complete(...)`; nothing else may call a model."""
from colex.llm.client import CassetteMiss, LLMClient, LLMResult, LLMUnavailable, TransientError
from colex.llm.complete import complete as _complete


def _method(self, agent, messages, **kwargs):
    return _complete(self, agent, messages, **kwargs)


LLMClient.complete = _method

__all__ = ["LLMClient", "LLMResult", "LLMUnavailable", "CassetteMiss", "TransientError"]

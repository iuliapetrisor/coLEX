"""python -m colex.llm.smoke: one real call per configured model, printing tokens and cost."""
from __future__ import annotations

from colex import settings
from colex.config import ConfigStore
from colex.llm import LLMClient

TOOL = [{"type": "function", "function": {"name": "ping", "description": "Reply through this tool.",
         "parameters": {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]}}}]


def main() -> None:
    settings.load_env()
    cfg = ConfigStore().active().payload
    client = LLMClient(mode="live")
    for agent in ("triage", "impact"):
        result = client.complete(agent, [{"role": "user", "content": "Call the ping tool with the word ok."}],
                                 tools=TOOL, prompt_version="smoke-1", cfg=cfg)
        called = [c["function"]["name"] for c in result.tool_calls]
        print(f"{agent}: model={result.model} tool_calls={called} tokens={result.usage} "
              f"cost_usd={result.cost_usd} cached={result.cached}")


if __name__ == "__main__":
    main()

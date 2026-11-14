"""The Impact Analyst's tool loop, the law excerpt it receives, and the context metrics."""
from __future__ import annotations

import json
from typing import Any

from colex import prompts
from colex.agents.impact_dispatch import Dispatcher
from colex.contracts import LawDocument
from colex.guardrails.injection import SYSTEM_RULE, wrap_untrusted
from colex.map.tool_schemas import MAP_TOOLS, REPORT_TOOLS
from colex.map.tools import MapTools
from colex.runtime import store

HEAD, TAIL, LAW_CHARS = 4500, 1500, 22000
NUDGE = "Use the tools: continue the analysis, or call finish if no unexplored candidate remains."


def law_block(law: LawDocument, flagged: list[str]) -> str:
    """The flagged articles only. Long articles keep their head and tail (application dates sit at the end)."""
    parts, used = [], 0
    for a in law.articles:
        if a.id not in flagged:
            continue
        text = a.text
        if len(text) > HEAD + TAIL:
            text = (f"{text[:HEAD]}\n[... {len(a.text) - HEAD - TAIL} characters of this article are not shown ...]"
                    f"\n{text[-TAIL:]}")
        if used + len(text) > LAW_CHARS:
            parts.append(f"### {a.id}\n[not shown: text budget reached]")
            continue
        used += len(text)
        dates = ", ".join(d.isoformat() for d in a.effective_dates) or "none"
        parts.append(f"### {a.id}\nDates written in this article: {dates}\n{text}")
    return wrap_untrusted(f"CELEX:{law.celex}", "\n\n".join(parts))


def tools_for(ctx) -> MapTools:
    """Map tools pinned to the map version this run started with."""
    return MapTools(ctx.config, store.run_row(ctx.run_id)["map_version_id"])


def loop(ctx, deps, dispatcher: Dispatcher, user: str, max_steps: int) -> bool:
    """Run the tool loop. Returns True when the model declared it is done."""
    cfg = ctx.config
    system, version = prompts.load("impact", cfg)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system + "\n\n" + SYSTEM_RULE},
                                      {"role": "user", "content": user}]
    idle = 0
    for _ in range(max_steps):
        deps.rt.check_budget(ctx.run_id, cfg)   # raises BudgetExceeded → a human is asked
        result = deps.llm.complete("impact", messages, tools=MAP_TOOLS + REPORT_TOOLS, prompt_version=version,
                                   run_id=ctx.run_id, cfg=cfg, step=ctx.node)
        calls = result.tool_calls
        if not calls:
            idle += 1
            if idle >= 2:
                break
            messages += [{"role": "assistant", "content": result.content or "(no tool call)"},
                         {"role": "user", "content": NUDGE}]
            continue
        messages.append({"role": "assistant", "content": result.content or None, "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            out = dispatcher.call(str(fn.get("name", "")), fn.get("arguments", "{}"))
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": json.dumps(out, ensure_ascii=False)})
        if dispatcher.finished is not None:
            return True
    ctx.emit("escalation", f"Impact analysis stopped without finishing (step limit {max_steps}); "
                           "the results may be incomplete and need a human look")
    return False


def metrics(tools: MapTools) -> dict[str, Any]:
    """Context delivered through the map versus two naive baselines (both reported, brief §3.7)."""
    totals, meter = tools.totals(), tools.meter
    used = meter["tokens"]
    touched = sum(totals["area_tokens"].get(a, 0) for a in meter["areas"])
    return {"context_tokens_used": used,
            "baseline_a_whole_corpus_tokens": totals["corpus_tokens"],
            "baseline_b_touched_areas_tokens": touched,
            "ratio_vs_a": round(used / totals["corpus_tokens"], 3) if totals["corpus_tokens"] else None,
            "ratio_vs_b": round(used / touched, 3) if touched else None,
            "tool_calls": meter["calls"], "navigation_depth": meter["depth"],
            "areas_touched": sorted(meter["areas"]), "fragments_read": totals["fragments_read"],
            "fragments_total": totals["fragments"], "resources_total": totals["resources"]}

"""Impact Analyst: a tool-calling loop over the Company Map (brief §3.5, §4.1).

The model never receives all documents. It navigates the map; each result decides its next call.
The loop runs inside one runtime step: after a crash the step restarts and the cached model
answers replay it for free.
"""
from __future__ import annotations

import json
from typing import Any

from colex.agents import registers as register_step
from colex.agents.impact_dispatch import Dispatcher
from colex.agents.impact_report import CRITICALITY_OPTIONS
from colex.agents.impact_loop import law_block, loop, metrics, tools_for
from colex.contracts import LawDocument
from colex.runtime import store

REPLAN_STEPS = 12


def run(ctx, law: LawDocument, triage: dict[str, Any], deps) -> dict[str, Any]:
    tools = tools_for(ctx)
    flagged = triage["articles_flagged"]
    dispatcher = Dispatcher(ctx, law, flagged, tools)
    user = (f"Act: {law.title}\nCELEX: {law.celex}\nWhy it is relevant: {triage['reason']}\n"
            f"Flagged article ids (use these exact ids): {json.dumps(flagged, ensure_ascii=False)}\n\n"
            f"Text of the flagged articles:\n{law_block(law, flagged)}\n\n"
            "Find every place in the company that must change. Start with overview.")
    complete = loop(ctx, deps, dispatcher, user, ctx.config["budgets"]["max_impact_steps"])
    return {"items": dispatcher.items, "questions": dispatcher.questions, "dropped": dispatcher.dropped,
            "trace": dispatcher.trace, "metrics": metrics(tools), "summary": dispatcher.finished or "",
            "complete": complete, "suspicious": sorted(dispatcher.flagged_docs)}


def replan(ctx, law: LawDocument, q: dict[str, Any], answer: dict[str, Any], affected: list[dict[str, Any]],
           deps) -> dict[str, Any]:
    """After legal's answer: re-assess only the resource the question was about and what links to it."""
    tools = tools_for(ctx)
    flagged = store.get_blob(store.step_row(ctx.run_id, "main:TRIAGE")["output_ref"])["articles_flagged"]
    uri = q.get("resource_uri")
    scope = {uri, *(i["resource_uri"] for i in affected)} - {None}
    for target in list(scope):
        scope |= {x for link in tools.related(target).get("items", []) for x in (link["from"], link["to"])}
    dispatcher = Dispatcher(ctx, law, flagged, tools, prefix=f"{q['id']}-")
    dispatcher.seen |= scope
    dispatcher.scope = scope
    said = answer.get("decision") or answer.get("text") or ""
    if q.get("kind") == "criticality" and uri and said in CRITICALITY_OPTIONS:
        # The answer changes one fact about one contract; what follows from it is in the map. No model call.
        critical = said == CRITICALITY_OPTIONS[0]
        item = register_step.critical_contract_item(ctx, law, uri, f"{q['id']}-i1") if critical else None
        ctx.emit("rationale", f"Legal answered \"{said}\" for {uri} → " + (
            "the Art. 30(3) clauses now apply; re-planned this contract only" if item else
            "no further clause applies; nothing to change") + ". Other branches untouched.",
            {"question_id": q["id"], "scope": [uri]})
        return {"items": [item] if item else [], "dropped": [], "complete": True, "answer": said, "scope": [uri],
                "deterministic": True}
    shown = ""
    if uri and tools.card(uri):
        first = dispatcher.call("list_resources", {"path": tools.card(uri)["primary_path"],
                                                   "rationale": "re-plan: reload the card of the resource in question"})
        mine = [r for r in first.get("items", []) if r["uri"] == uri]
        head = dispatcher.call("read", {"uri": uri, "start": 1, "end": 12,
                                        "rationale": "re-plan: header lines of the resource in question"})
        shown = (f"\nIts card in the map: {json.dumps(mine, ensure_ascii=False)}\n"
                 f"Its opening lines (already read; you may cite them):\n{head.get('text', '')}\n")
    held = [{k: i.get(k) for k in ("item_id", "resource_uri", "lines", "action", "obligation")} for i in affected]
    user = (f"Act: {law.title}\nCELEX: {law.celex}\n\nThe legal team answered a question you asked.\n"
            f"Question: {q['question']['text']}\nAnswer: {said}\nIt concerns: {uri or 'the act in general'}\n"
            f"Items on hold because of this question: {json.dumps(held, ensure_ascii=False)}\n{shown}\n"
            "Take the answer as a fact. Re-assess ONLY this resource and what is directly linked to it. "
            "Report with report_impact every item that applies now (report the on-hold items again if they still "
            "apply), then call finish. Do not analyse anything else and do not ask the same question again.\n\n"
            f"Flagged article ids: {json.dumps(flagged, ensure_ascii=False)}\n\n"
            f"Text of the flagged articles:\n{law_block(law, flagged)}")
    complete = loop(ctx, deps, dispatcher, user, REPLAN_STEPS)
    ctx.emit("rationale", f"Re-planned after legal's answer \"{said[:80]}\": {len(dispatcher.items)} item(s) for "
                          f"{len(scope)} linked resource(s); other branches untouched",
             {"question_id": q["id"], "scope": sorted(scope)})
    return {"items": dispatcher.items, "dropped": dispatcher.dropped, "complete": complete,
            "answer": said, "scope": sorted(scope)}

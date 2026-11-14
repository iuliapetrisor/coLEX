"""Fixed wording of docs/SCALE.md and the table of the live runs."""
from __future__ import annotations

from typing import Any

INTRO = (
    "**How to read this.** The company is the PayRo sandbox (21 resources) plus generated documents: tickets, "
    "runbooks, postmortems, policies, briefs and notes written from 11 templates. They use the same vocabulary as "
    "the sandbox but none of them states a rule, so they are easier to tell apart than real company documents. "
    "The code repository is not grown. Times are one measurement on one machine. The taxonomy stays at 20 topics.")
LIMITS = [
    "- Whether the agent finds the right places: see the last table. Its recall is not better than on the small "
    "sandbox, and each size was run once.",
    "- Real documents. The generated ones come from 11 templates and are all Markdown.",
    "- More than 5,021 resources, a bigger code repository, or a taxonomy with more topics.",
    "- The review queue: documents that could not be placed wait for a person, and that number grows with the "
    "company (first table).",
    "- Listing a large topic without a filter takes many pages (third table); the agent has to use a type filter, "
    "search or find."]
LIVE_HEAD = ["| Resources | All text (tokens) | Text the map returned to the agent (tokens) | Share | Sections opened "
             "| Expected places found | Reported on generated documents | Finished by itself | Model tokens billed | "
             "Cost (USD) |", "|---|---|---|---|---|---|---|---|---|---|"]


def live_table(rows: list[dict[str, Any]]) -> list[str]:
    out = list(LIVE_HEAD)
    for r in rows:
        if "error" in r:
            out.append(f"| {r['resources']:,} | {r['corpus_tokens']:,} | {r['error']} | | | | | | | |")
            continue
        cost = f"{r['cost_usd']:.3f}" if r["cost_usd"] else "not measured (answers came from the local cache)"
        out.append(f"| {r['resources']:,} | {r['corpus_tokens']:,} | {r['context_tokens_read']:,} | "
                   f"{100 * r['share_of_corpus']:.1f}% | {r['fragments_read']} of {r['fragments_total']:,} | "
                   f"{r['found']} of {r['expected']} | {r['on_generated_documents']} | "
                   f"{'yes' if r['finished_by_itself'] else 'no (step limit)'} | {r['model_tokens']:,} | {cost} |")
    return out


def live_section(live: list[dict[str, Any]]) -> list[str]:
    if not live:
        return ["Not recorded yet: run `make scale-live`."]
    return [f"Recorded by `make scale-live` (calls OpenRouter), model {live[0]['model']}, act {live[0]['celex']}, "
            "ONE run per size. A row says what that run did, not how often the system is right. Billed tokens are "
            "far above the text read because every step sends the conversation so far to the model again.", "",
            *live_table(live)]

"""Are the places that must change still reachable in a larger company, and what does the path to them cost?

Uses the hidden ground truth (evaluation code may; runtime code never does). The walk is SCRIPTED: it
already knows where the nine places are, so it measures the cost of the path, not the cost of finding it.
"""
from __future__ import annotations

from typing import Any

import yaml

from colex import settings
from colex.map.hierarchy import SEP
from colex.map.tools import UNCLASSIFIED, MapTools

TRUTH = settings.SANDBOX / "_ground_truth"
PAGE_CAP = 400


def _pages(tools: MapTools, path: str, uri: str, facets: dict[str, Any] | None) -> tuple[int | None, int]:
    """(pages of list_resources until `uri` shows, tokens of those pages)."""
    cursor, pages, tokens = 0, 0, 0
    while cursor is not None and pages < PAGE_CAP:
        out = tools.list_resources(path, facets, cursor)
        pages, tokens = pages + 1, tokens + out["tokens_estimate"]
        if uri in [item["uri"] for item in out.get("items", [])]:
            return pages, tokens
        cursor = out.get("next_cursor")
    return None, tokens


def needles(cfg: dict[str, Any]) -> dict[str, Any]:
    tools = MapTools(cfg)
    resources = yaml.safe_load((TRUTH / "resources.yaml").read_text(encoding="utf-8"))["resources"]
    items = yaml.safe_load((TRUTH / "expected.yaml").read_text(encoding="utf-8"))["impact_items"]
    placed = sum((tools.card(r["uri"]) or {}).get("primary_path") == (r["path"] or UNCLASSIFIED) for r in resources)
    walk = tools.overview()["tokens_estimate"]
    for area in sorted({tools.card(i["uri"])["primary_path"].split(SEP)[1] for i in items}):
        walk += tools.browse(f"PayRo{SEP}{area}", depth=2)["tokens_estimate"]
    plain, by_type, unreachable = [], [], []
    for item in items:
        card = tools.card(item["uri"])
        pages, _ = _pages(tools, card["primary_path"], item["uri"], None)
        typed, tokens = _pages(tools, card["primary_path"], item["uri"], {"info_type": card["info_type"]})
        if typed is None:
            unreachable.append(item["uri"])
            continue
        plain.append(pages or PAGE_CAP)
        by_type.append(typed)
        start, end = item["lines"]
        walk += tokens + tools.read(item["uri"], start, min(end, start + 39))["tokens_estimate"]
    return {"placed_as_before": placed, "resources_in_truth": len(resources), "places": len(items),
            "unreachable": unreachable, "max_pages_plain": max(plain, default=0),
            "max_pages_by_type": max(by_type, default=0), "scripted_walk_tokens": walk}

"""What the scale test measures at one company size. Offline and deterministic: no model is called.

- how long the map build takes, cold and after one document changed;
- how big the answer of each navigation tool is (the agent reads these answers, never the corpus);
- whether the documents of the ground truth are still placed where they were and how many list pages it
  takes to reach the places that must change (tests/scale/needles.py).
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any

from colex import db, settings
from colex.config import ConfigStore
from colex.map import build as build_mod
from colex.map.hierarchy import SEP
from colex.map.tools import MapTools
from tests.scale import gen
from tests.scale.needles import needles

SCALE = settings.ROOT / "var" / "scale"
AWS = "onedrive://legal/contracts/cloud-hosting-aws.md"


def connect_sources(folder: str) -> dict[str, Any]:
    """Save a config whose document connectors read var/scale/<folder>. The code repository stays as it is."""
    payload = ConfigStore().active().payload
    payload["connectors"] = {**payload["connectors"], **{s: f"var/scale/{folder}/{s}" for s in gen.SOURCES}}
    return ConfigStore().save(payload, author="scale test").payload


def prepare(extra: int) -> dict[str, Any]:
    """Generate the company, start a fresh state for it under var/scale, and return a config that reads it."""
    gen.generate(SCALE / f"bench-src-{extra}", extra)
    state = SCALE / f"bench-{extra}"
    shutil.rmtree(state, ignore_errors=True)
    os.environ["COLEX_VAR"] = str(state)
    os.environ.pop("COLEX_DB", None)
    return connect_sources(f"bench-src-{extra}")


def _timed(fn) -> tuple[Any, float]:
    started = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - started


def tool_answers(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tools = MapTools(cfg)
    biggest = db.connect().execute("select node_path, count(*) n from resource_nodes where mv=? and kind='primary' "
                                   "group by node_path order by n desc limit 1", (tools.mv,)).fetchone()
    fees = f"PayRo{SEP}Payments{SEP}Fees & Pricing"
    calls = {"overview": lambda: tools.overview(),
             "browse one area": lambda: tools.browse(f"PayRo{SEP}Payments"),
             "list the biggest topic (one page)": lambda: tools.list_resources(biggest["node_path"]),
             "search, whole company": lambda: tools.search("instant credit transfer charges"),
             "search, inside one domain": lambda: tools.search("instant credit transfer charges", under=fees),
             "find fees": lambda: tools.find("fee"),
             "related to one contract": lambda: tools.related(AWS),
             "counterparty AWS": lambda: tools.counterparty("AWS"),
             "owners payments-eng": lambda: tools.owners("payments-eng")}
    out = {}
    for name, call in calls.items():
        answer, seconds = _timed(call)
        out[name] = {"tokens": answer["tokens_estimate"], "ms": round(seconds * 1000),
                     "truncated": bool(answer.get("truncated")), "total": answer.get("total"),
                     "returned": len(answer.get("items", []))}
    out["_biggest_topic"] = {"path": biggest["node_path"], "resources": biggest["n"]}
    return out


def measure(extra: int) -> dict[str, Any]:
    cfg = prepare(extra)
    build_mod._SHARED.clear()                                  # cold: nothing analysed before
    stats, cold = _timed(lambda: build_mod.build(cfg))
    changed = SCALE / f"bench-src-{extra}" / "intranet" / "canteen-menu.md"
    changed.write_text(changed.read_text(encoding="utf-8") + "\nFriday: soup of the day.\n", encoding="utf-8")
    again, warm = _timed(lambda: build_mod.build(cfg))         # one document changed
    totals = MapTools(cfg).totals()
    size = sum(p.stat().st_size for p in (SCALE / f"bench-src-{extra}").rglob("*.md"))
    return {"added": extra, "max_chars": cfg["map"]["max_chars"],
            "resources": again["resources"], "corpus_tokens": totals["corpus_tokens"],
            "bytes_on_disk": size, "nodes": again["nodes"], "fragments": again["fragments"], "links": again["edges"],
            "unclassified": again["unclassified"], "owners": again["owners"], "build_s": round(cold, 2),
            "rebuild_s": round(warm, 2), "reused": again["reused_unchanged"], "first_version": stats["map_version_id"],
            "tools": tool_answers(cfg), "needles": needles(cfg)}

"""Scoring for `make eval`: what reached humans in a demo run, against the hidden ground truth.

Evaluation code may read sandbox/_ground_truth; runtime code under colex/ never does.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

import yaml

from colex import db, settings
from colex.agents import watcher
from colex.map import store as map_store
from colex.notify.base import outbox_rows
from colex.runtime import audit, store

GT = settings.SANDBOX / "_ground_truth"


def match(p: dict[str, Any], x: dict[str, Any]) -> bool:
    """Same law, resource and action, and the line ranges overlap by at least one line."""
    return ((p["law"], p["resource_uri"], p["action"]) == (x["law"], x["uri"], x["action"])
            and p["lines"]["start"] <= x["lines"][1] and x["lines"][0] <= p["lines"]["end"])


def score() -> dict[str, Any]:
    truth = yaml.safe_load((GT / "expected.yaml").read_text(encoding="utf-8"))
    res_truth = yaml.safe_load((GT / "resources.yaml").read_text(encoding="utf-8"))["resources"]
    laws = {law["celex"]: law for law in watcher.laws()}
    rel_pred = {c for c, law in laws.items() if law["status"] == "relevant"}
    rel_true = set(truth["laws"]["relevant"])
    found: dict[tuple, dict] = {}
    for celex in sorted(rel_pred):
        for row in outbox_rows(laws[celex]["run_id"]):
            if row["kind"] == "notification":
                for item in row["payload"].get("items", []):
                    found.setdefault((celex, item["item_id"]), {**item, "channel": row["channel"], "law": celex})
    pred, exp = list(found.values()), truth["impact_items"]
    hit_exp = [x for x in exp if any(match(p, x) for p in pred)]
    hit_pred = [p for p in pred if any(match(p, x) for x in exp)]
    routed = sum(1 for x in hit_exp if next(p for p in pred if match(p, x))["channel"] == x["channel"])
    banned = [p for p in pred if p["resource_uri"] in truth["must_not_flag"]
              or p["resource_uri"].split("://")[0] in truth["must_not_flag_sources"]]
    mv = map_store.active()
    rows = {r["uri"]: (r["primary_path"], json.loads(r["card_json"]), json.loads(r["facts_json"]))
            for r in db.connect().execute("select uri, primary_path, card_json, facts_json from resources where mv=?",
                                          (mv,))}
    contracts = [t for t in res_truth if t["type"] == "contract"]
    reviews = [w for w in store.waits() if w["kind"] == "review"]
    changes = []
    for change in truth["code_changes"]:
        w = next((w for w in reviews if f"+++ b/{change['file']}" in w["payload"]["change"]["diff"]), None)
        changes.append({"file": change["file"], "law": change["law"], "change": w["payload"]["change"] if w else None,
                        "decision": (w["answer"] or {}).get("decision", "pending") if w else None})
    acts = []
    for celex in sorted(rel_pred):
        run_id = laws[celex]["run_id"]
        step = store.step_row(run_id, "main:VERIFY")
        summary = store.get_blob(step["output_ref"]) if step else None
        cost = sum(e["detail"].get("recorded_cost_usd", 0) for e in audit.events(run_id, limit=100000)
                   if e["kind"] == "llm")
        acts.append({"celex": celex, "summary": summary, "recorded_cost": cost})
    return {
        "map_version": mv, "laws": laws,
        "triage": {"tp": len(rel_pred & rel_true), "pred": len(rel_pred), "true": len(rel_true),
                   "archived_with_reason": sum(1 for law in laws.values()
                                               if law["status"] == "archived" and law["reason"])},
        "impact": {"expected": len(exp), "reported": len(pred), "hit_expected": len(hit_exp),
                   "hit_reported": len(hit_pred), "routed": routed, "banned": len(banned),
                   "missed": [x for x in exp if x not in hit_exp], "extra": [p for p in pred if p not in hit_pred]},
        "map": {"n": len(res_truth), "contracts": len(contracts),
                "path": sum(rows[t["uri"]][0] == t["path"] for t in res_truth),
                "owner": sum(rows[t["uri"]][1]["owner_team"] == t["owner"] for t in res_truth),
                "counterparty": sum(rows[t["uri"]][2].get("counterparty_id") == t["counterparty"] for t in contracts),
                "sources": dict(Counter(card["ownership_source"] for _, card, _ in rows.values())),
                "unclassified": sum(1 for p, _, _ in rows.values() if p is None)},
        "changes": changes, "acts": acts,
    }

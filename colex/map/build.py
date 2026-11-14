"""Company Map build: connectors → fragments → signals → facets → hierarchy → links → rollups.

Deterministic. A build is written under a new version id inside one transaction and becomes
active only when it completes, so a failing connector leaves the previous map in place.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from colex import db, settings
from colex.connectors.base import connectors
from colex.guardrails.injection import detect_injection
from colex.map import extract, facets, hierarchy, links, rollups
from colex.map.registry import Registry
from colex.runtime import audit

_SHARED: dict[str, dict[str, Any]] = {}   # sha → analysed resource, reused when a file did not change


def _load(name: str) -> dict[str, Any]:
    return yaml.safe_load((settings.CONFIG_DIR / name).read_text(encoding="utf-8"))


def _title(text: str, path: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and not line.startswith(">") and not stripped.startswith(('"""', "FICTIONAL")):
            return stripped[:120]
    return path.rsplit("/", 1)[-1]


def analyse(ref, text: str, registry: Registry, rules: dict[str, Any], tax: dict[str, Any],
            checklist: dict[str, Any], learned: list[dict[str, str]]) -> dict[str, Any]:
    title = _title(text, ref.path)
    rule = hierarchy.rule_for(ref.uri, title, text, rules["rules"])
    frags = extract.fragments(ref.path, text)
    ents = extract.entities(ref.path, text, frags)
    facts: dict[str, Any] = {}
    if rule["info_type"] == "contract":
        facts = facets.contract_facts(text, registry)
        facts["clauses"] = facets.clauses(text, checklist, facts["critical"])
        facts["data_location"] = facets.data_location(text, facts["clauses"]["present"].get("30(2)(b)"),
                                                      extract.COUNTRIES)
        ents += [{"etype": "contract_clause", "value": cid, "line": line, "snippet": text.splitlines()[line - 1][:160]}
                 for cid, line in facts["clauses"]["present"].items()]
    mentions = registry.mentions(text)
    ents += [{"etype": "ict_provider", "value": cp, "line": line, "snippet": text.splitlines()[line - 1].strip()[:160]}
             for cp, line in mentions]
    place = hierarchy.assign(ref.uri, title, text, rule, tax, learned)
    return {"uri": ref.uri, "source": ref.source, "path": ref.path, "sha": ref.sha, "title": title, "text": text,
            "info_type": rule["info_type"], "fragments": frags, "entities": ents, "facts": facts,
            "mentions": mentions, "placement": place, "primary_path": None,
            "owner": facets.ownership(ref.uri, ref.metadata, facts.get("document_owner"), rules, rule["info_type"]),
            "lifecycle": facets.lifecycle(text),
            "sensitivity": sorted({e["value"] for e in ents if e["etype"] == "personal_data"}),
            "injection": detect_injection(text)}


def build(cfg: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Build and activate a map version. Returns its statistics. Raises ConnectorError on a bad source."""
    tax, rules = _load("taxonomy.yaml"), _load("map_rules.yaml")
    registry, checklist = Registry(_load("counterparties.yaml")), _load("dora_art30_checklist.yaml")
    con = db.connect()
    learned = [dict(r) for r in con.execute("select glob, node_path, author from learned_rules order by ts desc")]
    threshold = cfg["map"]["classification_threshold"]
    resources: dict[str, dict[str, Any]] = {}
    reused = 0
    for connector in connectors(cfg, root or settings.ROOT):   # any failure here aborts before anything is stored
        for ref in connector.list():
            key = f"{ref.uri}|{ref.sha}|{len(learned)}"
            if key in _SHARED:
                reused += 1
                resources[ref.uri] = _SHARED[key]
                continue
            resources[ref.uri] = _SHARED[key] = analyse(ref, connector.fetch(ref).text, registry, rules, tax,
                                                        checklist, learned)
    for r in resources.values():
        r["primary_path"] = r["placement"]["path"] if r["placement"]["confidence"] >= threshold else None
    digest = hashlib.sha256(db.dumps([sorted((u, r["sha"]) for u, r in resources.items()), tax["version"],
                                      extract.EXTRACTOR_VERSION, learned, threshold]).encode()).hexdigest()
    mv = "mv-" + digest[:12]
    edges, secondary = links.build(resources)
    all_nodes = hierarchy.nodes(tax)
    names = {cp["id"]: cp["name"] for cp in registry.items}
    rolled = rollups.compute([n["path"] for n in all_nodes], resources, secondary, names)
    stats = store(mv, resources, edges, secondary, all_nodes, rolled, registry, reused)
    return stats


from colex.map.store import store  # noqa: E402  (split for file size; store() writes one map version)

"""Resource cards, review queues and build statistics derived from analysed resources."""
from __future__ import annotations

from typing import Any

UNCLASSIFIED = "PayRo › Unclassified"


def card(r: dict[str, Any], mv: str, secondary: list[str]) -> dict[str, Any]:
    """The ResourceCard of brief §4.2 as a plain dict (a test validates it against the contract)."""
    owner = r["owner"]
    return {"uri": r["uri"], "source": r["source"], "info_type": r["info_type"],
            "primary_path": r["primary_path"] or UNCLASSIFIED, "secondary_paths": secondary,
            "owner_team": owner["owner_team"], "owner_role": owner["owner_role"],
            "approver_role": owner["approver_role"], "legal_steward": owner["legal_steward"],
            "ownership_source": owner["ownership_source"],
            "counterparties": sorted({cp for cp, _ in r["mentions"]}),
            "sensitivity": {"personal_data_categories": r["sensitivity"], "confidentiality": None},
            "lifecycle": {**r["lifecycle"], "last_modified": None}, "regulatory_tags": [],
            "classification_confidence": r["placement"]["confidence"], "sha": r["sha"], "map_version_id": mv}


def review_queue(resources: dict[str, dict[str, Any]]) -> list[tuple[str, str, str]]:
    """(kind, uri, detail) rows a human should look at."""
    queue = []
    for uri, r in resources.items():
        if r["primary_path"] is None:
            queue.append(("unclassified", uri, r["placement"]["reason"]))
        if r["info_type"] == "contract" and not r["facts"].get("counterparty_id"):
            queue.append(("unknown_counterparty", uri, r["facts"].get("counterparty_name") or "no party found"))
        for finding in r["injection"]:
            queue.append(("suspicious_instructions", uri, f"line {finding['line']}: {finding['snippet']}"))
    return queue


def stats(mv: str, resources: dict[str, dict[str, Any]], edges: list[tuple], nodes: list[dict[str, Any]],
          queue: list[tuple[str, str, str]], reused: int) -> dict[str, Any]:
    owners = [r["owner"]["ownership_source"] for r in resources.values()]
    return {"map_version_id": mv, "resources": len(resources),
            "fragments": sum(len(r["fragments"]) for r in resources.values()),
            "entities": sum(len(r["entities"]) for r in resources.values()), "edges": len(edges),
            "nodes": len(nodes), "reused_unchanged": reused,
            "owners": {k: owners.count(k) for k in ("explicit", "inferred", "unknown")},
            "unclassified": sum(1 for q in queue if q[0] == "unclassified"),
            "unknown_counterparties": sum(1 for q in queue if q[0] == "unknown_counterparty"),
            "suspicious": sorted({q[1] for q in queue if q[0] == "suspicious_instructions"})}


def counterparty_rows(resources: dict[str, dict[str, Any]], registry) -> list[dict[str, Any]]:
    contracts = {r["facts"]["counterparty_id"]: r for r in resources.values()
                 if r["info_type"] == "contract" and r["facts"].get("counterparty_id")}
    rows = []
    for cp in registry.items:
        c = contracts.get(cp["id"])
        rows.append({"counterparty_id": cp["id"], "canonical_name": cp["name"], "aliases": cp.get("aliases", []),
                     "type": cp["type"], "supports_critical_function": c["facts"]["critical"] if c else None,
                     "data_location": c["facts"]["data_location"] if c else None,
                     "subcontractors": c["facts"]["subcontractors"] if c else []})
    return rows

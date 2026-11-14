"""Views over the Company Map: the DORA Register of Information, the Obligations Register, the Legal Vault.

The register is generated from contract facts in the map. Its columns are MODELLED ON the idea of the
ESAs' register template for contractual arrangements; it is not the official template and has not been
checked against Implementing Regulation (EU) 2024/2956. Clause detection is a text heuristic.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

import yaml

from colex import db, settings
from colex.runtime import audit

LEGAL_TYPES = ("contract", "customer_terms", "fee_schedule", "policy", "procedure", "register")
COLUMNS = ["contract_id", "provider", "provider_id", "services", "supports_critical_or_important_function",
           "data_processing_locations", "subcontractors", "contract_status", "effective_date", "renewal_date",
           "owner_team", "missing_clauses_art_30_2", "missing_clauses_art_30_3", "to_check_if_critical", "source_uri"]
CRITICAL = {True: "yes", False: "no", None: "not assessed"}
DORA_CELEX = "32022R2554"   # the act the Art. 30 checklist belongs to


def checklist() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((settings.CONFIG_DIR / "dora_art30_checklist.yaml").read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["clauses"]}


def dora_rows(mv: str) -> list[dict[str, Any]]:
    """One row per ICT contractual arrangement found in the map."""
    names = {r["cp_id"]: json.loads(r["body_json"])["canonical_name"]
             for r in db.connect().execute("select cp_id, body_json from counterparties where mv=?", (mv,))}
    rows = []
    for r in db.connect().execute("select uri, card_json, facts_json from resources where mv=? and "
                                  "info_type='contract' order by uri", (mv,)):
        card, facts = json.loads(r["card_json"]), json.loads(r["facts_json"])
        clauses = facts.get("clauses", {})
        missing = clauses.get("missing", [])
        rows.append({
            "contract_id": facts.get("contract_id") or "", "provider_id": facts.get("counterparty_id") or "",
            "provider": names.get(facts.get("counterparty_id"), facts.get("counterparty_name") or "unknown"),
            "services": facts.get("services") or "",
            "supports_critical_or_important_function": CRITICAL[facts.get("critical")],
            "data_processing_locations": facts.get("data_location") or "not specified",
            "subcontractors": "; ".join(facts.get("subcontractors") or []) or "none",
            "contract_status": card["lifecycle"].get("status") or "", "owner_team": card["owner_team"] or "unknown",
            "effective_date": card["lifecycle"].get("effective_date") or "",
            "renewal_date": card["lifecycle"].get("renewal_date") or "",
            "missing_clauses_art_30_2": "; ".join(c for c in missing if c.startswith("30(2)")),
            "missing_clauses_art_30_3": "; ".join(c for c in missing if c.startswith("30(3)")),
            "to_check_if_critical": "; ".join(clauses.get("missing_if_critical", [])),
            "source_uri": r["uri"],
            "_missing": missing, "_critical_line": facts.get("critical_line"), "_parties_line": facts.get("parties_line"),
            "_legal_steward": card["legal_steward"], "_ownership_source": card["ownership_source"],
            "_primary_path": card["primary_path"]})
    return rows


def dora_csv(mv: str) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(dora_rows(mv))
    return out.getvalue()


def record_obligations(run_id: str, law_celex: str, items: list[dict[str, Any]]) -> int:
    """Obligations Register: law article → obligation → map node and resource (uri + lines) → status → owner.

    Each row is attached to the map node of its resource, so everything under that node is covered by it.
    Rows of the same run are replaced, so recording twice does not duplicate.
    """
    con = db.connect()
    con.execute("begin immediate")
    try:
        con.execute("delete from obligations where run_id=?", (run_id,))
        for item in items:
            con.execute(
                "insert into obligations(citation,obligation,node_path,uri,start,end,status,owner_team,deadline,"
                "run_id,item_id,ts) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["citation"], item.get("obligation") or item["action"], item.get("breadcrumbs"),
                 item["resource_uri"], item["lines"]["start"], item["lines"]["end"], "gap", item.get("owner_team"),
                 item.get("deadline"), run_id, item["item_id"], audit.now()))
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return len(items)


def obligation_rows() -> list[dict[str, Any]]:
    return [dict(r) for r in db.connect().execute("select * from obligations order by citation, uri")]


def legal_vault(mv: str) -> list[dict[str, Any]]:
    """A view, nothing is copied: every resource with a legal information type, wherever it sits in the tree."""
    marks = ",".join("?" * len(LEGAL_TYPES))
    rows = db.connect().execute(f"select uri, title, info_type, card_json from resources where mv=? and info_type in "
                                f"({marks}) order by info_type, uri", (mv, *LEGAL_TYPES))
    out = []
    for r in rows:
        card = json.loads(r["card_json"])
        out.append({"uri": r["uri"], "title": r["title"], "info_type": r["info_type"],
                    "primary_path": card["primary_path"], "owner_team": card["owner_team"],
                    "legal_steward": card["legal_steward"], "status": card["lifecycle"].get("status")})
    return out

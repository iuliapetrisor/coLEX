"""Facets: contract facts, Art. 30 clauses, ownership, lifecycle."""
from __future__ import annotations

import fnmatch
import re
from typing import Any

from colex.map.registry import Registry, norm_name

HEADER = re.compile(r"^(Parties|Contract ID|Services|Subcontractors|Document owner|"
                    r"Supports a critical or important function):\s*(.+?)\s*$", re.M)
LIFECYCLE = re.compile(r"\b(Status|Effective|Renewal|Last reviewed|Created):\s*([\w-]+)")
LEGAL_TYPES = ("contract", "customer_terms", "fee_schedule", "policy", "register", "procedure")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def contract_facts(text: str, registry: Registry) -> dict[str, Any]:
    head = {m.group(1): m.group(2) for m in HEADER.finditer(text)}
    lines = {m.group(1): text[:m.start()].count("\n") + 1 for m in HEADER.finditer(text)}
    parties = [p.strip() for p in re.split(r"\s+and\s+", head.get("Parties", "")) if p.strip()]
    others = [p for p in parties if norm_name(p) != "payro"]
    critical = {"yes": True, "no": False}.get(head.get("Supports a critical or important function", "").lower())
    subs = [s.strip() for s in head.get("Subcontractors", "none").split(",") if s.strip().lower() != "none"]
    return {"contract_id": head.get("Contract ID"), "counterparty_name": others[0] if others else None,
            "counterparty_id": registry.resolve(others[0]) if others else None, "services": head.get("Services"),
            "critical": critical, "critical_line": lines.get("Supports a critical or important function"),
            "parties_line": lines.get("Parties"), "subcontractors": subs,
            "document_owner": head.get("Document owner")}


def clauses(text: str, checklist: dict[str, Any], critical: bool | None) -> dict[str, Any]:
    """Which Art. 30 clauses the text contains (with the line) and which applicable ones are missing."""
    lines = text.splitlines()
    present: dict[str, int] = {}
    for clause in checklist["clauses"]:
        compiled = [re.compile(p, re.I) for p in clause["patterns"]]
        for number, line in enumerate(lines, 1):
            if any(c.search(line) for c in compiled):
                present[clause["id"]] = number
                break
    absent = [c for c in checklist["clauses"] if c["id"] not in present]
    return {"present": present,
            "missing": [c["id"] for c in absent if c["paragraph"] == "30(2)" or critical is True],
            "missing_if_critical": [c["id"] for c in absent if c["paragraph"] == "30(3)" and critical is None]}


def data_location(text: str, clause_line: int | None, countries: tuple[str, ...]) -> str | None:
    if not clause_line:
        return None
    window = " ".join(text.splitlines()[clause_line - 1:clause_line + 3])
    return ", ".join(c for c in countries if re.search(rf"\b{c}\b", window)) or None


def ownership(uri: str, metadata: dict[str, Any], document_owner: str | None, rules: dict[str, Any],
              info_type: str) -> dict[str, Any]:
    """Priority: source metadata, document header (both explicit), folder convention (inferred), unknown."""
    aliases = rules.get("team_aliases", {})
    out = {"owner_team": None, "owner_role": None, "approver_role": metadata.get("approver_role"),
           "legal_steward": metadata.get("legal_steward") or ("legal" if info_type in LEGAL_TYPES else None),
           "ownership_source": "unknown", "ownership_origin": "no owner found"}
    if metadata.get("owner_team"):
        out.update(owner_team=aliases.get(metadata["owner_team"], metadata["owner_team"]),
                   owner_role=metadata.get("owner_role"), ownership_source="explicit",
                   ownership_origin=metadata.get("owner_origin", "source metadata"))
    elif document_owner:
        m = re.match(r"([\w -]+?)\s*(?:\((.+)\))?$", document_owner)
        team = m.group(1).strip().lower() if m else document_owner.lower()
        out.update(owner_team=aliases.get(team, team), owner_role=m.group(2) if m else None,
                   ownership_source="explicit", ownership_origin="document header")
    else:
        for conv in rules.get("ownership_conventions", []):
            if fnmatch.fnmatch(uri, conv["glob"]):
                out.update(owner_team=conv["team"], owner_role=conv.get("role"), ownership_source="inferred",
                           ownership_origin=f"folder convention {conv['glob']}")
                break
    return out


def lifecycle(text: str) -> dict[str, Any]:
    found = {m.group(1): m.group(2) for m in LIFECYCLE.finditer("\n".join(text.splitlines()[:12]))}
    status = found.get("Status", "").lower()
    return {"status": status if status in ("draft", "active", "expired", "superseded") else None,
            "effective_date": found.get("Effective") if DATE.match(found.get("Effective", "")) else None,
            "renewal_date": found.get("Renewal") if DATE.match(found.get("Renewal", "")) else None}

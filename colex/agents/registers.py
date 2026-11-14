"""Register step of a DORA run (brief §1.5 step 7): generate the Register of Information from the map
and turn every missing Art. 30 clause into an impact item for the contract's legal steward.

Deterministic: no model call. The analyst may already have reported some of these contracts; one item
per contract is kept, and this step adds only what is missing.
"""
from __future__ import annotations

from typing import Any

from colex import settings
from colex.contracts import ImpactItem
from colex.map import registers
from colex.runtime import store

DORA_CELEX = "32022R2554"
ARTICLE = "Art. 30"


def applies(law) -> bool:
    return law.celex == DORA_CELEX and any(a.id == ARTICLE for a in law.articles)


def run(ctx, law, items: list[dict[str, Any]], deps) -> dict[str, Any]:
    mv = store.run_row(ctx.run_id)["map_version_id"]
    rows = registers.dora_rows(mv)
    labels = registers.checklist()
    path = settings.var_dir() / "registers" / f"dora-register-{ctx.run_id}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registers.dora_csv(mv), encoding="utf-8")
    reported = {i["resource_uri"] for i in items if i["action"] == "CONTRACT_REVIEW"}
    new, gaps = [], 0
    for row in rows:
        missing = row["_missing"]
        gaps += len(missing)
        if not missing or row["source_uri"] in reported:
            continue
        line = row["_critical_line"] or row["_parties_line"] or 1
        lines = deps_lines(ctx, mv, row["source_uri"])
        wording = "; ".join(f"{c} {labels[c]['label']}" for c in missing)
        scope = "contracts supporting a critical or important function" if any(c.startswith("30(3)") for c in missing) \
            else "every ICT contract"
        item = ImpactItem(
            item_id=f"reg-{len(new) + 1}", article_id=ARTICLE, resource_uri=row["source_uri"],
            lines={"start": line, "end": line}, action="CONTRACT_REVIEW", owner_team=None if row["owner_team"] == "unknown" else row["owner_team"],
            evidence=lines[line - 1].strip()[:300] or row["provider"], citation=f"CELEX:{law.celex} {ARTICLE}",
            confidence=0.7, obligation=f"Contract with {row['provider']} has no clause found for: {wording}. "
                                       f"Article 30 requires it for {scope}. Text heuristic: confirm by reading.")
        new.append({**item.model_dump(mode="json"), "breadcrumbs": row["_primary_path"],
                    "legal_steward": row["_legal_steward"], "ownership_source": row["_ownership_source"],
                    "register_only": True})
    ctx.emit("rationale", f"DORA Register of Information generated from the map: {len(rows)} ICT contractual "
                          f"arrangement(s), {gaps} missing clause(s) in "
                          f"{sum(1 for r in rows if r['_missing'])} contract(s); {len(new)} not yet reported → "
                          "routed to the contract owners", {"csv": str(path.name)})
    return {"rows": len(rows), "gaps": gaps, "csv": str(path), "items": new,
            "not_assessed": [r["source_uri"] for r in rows
                             if r["supports_critical_or_important_function"] == "not assessed"]}


def deps_lines(ctx, mv: str, uri: str) -> list[str]:
    from colex.map.tools import MapTools
    return MapTools(ctx.config, mv).lines(uri) or [""]

"""Law article view and the registers (DORA Register of Information, Obligations Register, Legal Vault)."""
from __future__ import annotations

from html import escape as e
from urllib.parse import quote

from colex.agents import watcher
from colex.api.html import badge, evidence, law, page, table
from colex.map import registers, store


def law_page(celex: str) -> str:
    try:
        doc = watcher.get_law(celex)
    except KeyError:
        return page("Law", f"<p>{e(celex)} has not been published to the feed.</p>")
    banner = "<div class='box warn'><b>FICTIONAL – DEMO ONLY</b></div>" if doc.fictional else ""
    parts = "".join(f"<h2 id='{e(quote(a.id))}'>{e(a.id)}</h2><pre style='white-space:pre-wrap'>{e(a.text)}</pre>"
                    for a in doc.articles)
    return page(f"CELEX {celex}", banner + f"<p>{e(doc.title)}</p><p>Official text, excerpt: <a href='{e(doc.source)}'>"
                f"{e(doc.source)}</a> · published {doc.published}. Only the Official Journal version is authentic.</p>"
                + parts)


def registers_page() -> str:
    mv = store.active()
    if not mv:
        return page("Registers", "<p>No map has been built yet.</p>")
    dora = table(["Contract", "Provider", "Critical or important", "Data locations", "Subcontractors", "Owner",
                  "Missing Art. 30(2)", "Missing Art. 30(3)", "To check if critical", "Source"], [
        [e(r["contract_id"]), e(r["provider"]), e(r["supports_critical_or_important_function"]),
         e(r["data_processing_locations"]), e(r["subcontractors"]), e(r["owner_team"]),
         f"<b class='del'>{e(r['missing_clauses_art_30_2'])}</b>", f"<b class='del'>{e(r['missing_clauses_art_30_3'])}</b>",
         e(r["to_check_if_critical"]), evidence(r["source_uri"], 1, 12, "open")] for r in registers.dora_rows(mv)])
    obligations = table(["Citation", "Obligation", "Evidence", "Node", "Status", "Owner", "Deadline"], [
        [law(o["citation"]), e(o["obligation"]), evidence(o["uri"], o["start"], o["end"]), e(o["node_path"] or ""),
         badge(o["status"]), e(o["owner_team"] or "unknown"), e(o["deadline"] or "")]
        for o in registers.obligation_rows()])
    vault = table(["Resource", "Type", "Path", "Owner", "Status"], [
        [evidence(v["uri"], 1, 20, v["uri"]), e(v["info_type"]), e(v["primary_path"]), e(v["owner_team"] or "unknown"),
         e(v["status"] or "")] for v in registers.legal_vault(mv)])
    note = ("<p class='muted'>Generated from the map. The columns are our own, not the official ESA template. Missing "
            "clauses come from a keyword heuristic: confirm by reading the contract. "
            "<a href='/registers/dora.csv'>Download CSV</a></p>")
    return page("Registers", "<h2>DORA Register of Information</h2>" + note + dora
                + "<h2>Obligations Register</h2>" + obligations + "<h2>Legal Vault (a view, nothing is copied)</h2>"
                + vault)

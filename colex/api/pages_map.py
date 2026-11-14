"""Map explorer and evidence viewer."""
from __future__ import annotations

import json
from html import escape as e
from urllib.parse import quote

from colex import db
from colex.api.html import evidence, page, post, table
from colex.config import ConfigStore
from colex.map import store
from colex.map.tools import MapTools


def tools() -> MapTools:
    return MapTools(ConfigStore().active().payload)


def explorer(path: str | None) -> str:
    if not store.active():
        return page("Company Map", "<p>No map has been built yet.</p>")
    t = tools()
    rows = db.connect().execute("select level, path, summary from nodes where mv=? order by path", (t.mv,)).fetchall()
    tree = table(["Level", "Node", "Rollup"], [
        [r["level"], "&nbsp;" * 4 * r["path"].count("›")
         + f'<a href="/map?path={quote(r["path"])}">{e(r["path"].split(" › ")[-1])}</a>', e(r["summary"])]
        for r in rows])
    detail = ""
    if path:
        listed = t.list_resources(path)
        cards = []
        for i in listed.get("items", []):
            inferred = " <span class='badge waiting'>inferred</span>" if i["ownership_source"] == "inferred" else ""
            cards.append([evidence(i["uri"], 1, min(i["lines"], 40), i["uri"]), e(i["info_type"]),
                          e(i["owner_team"] or "unknown") + inferred, e(", ".join(i["counterparties"])),
                          e(i.get("membership", "primary")), e(", ".join(i.get("missing_clauses", [])))])
        detail = (f"<h2>{e(listed['breadcrumbs'])}</h2>"
                  + table(["Resource", "Type", "Owner", "Contractors", "Membership", "Missing clauses"], cards))
    options = "".join(f"<option>{e(r['path'])}</option>" for r in rows if r["level"] == "L3")
    queue = []
    for q in t.unclassified()["items"]:
        action = ""
        if q["kind"] == "unclassified":
            action = (f"<form method='post' action='/map/assign'><input type='hidden' name='uri' "
                      f"value='{e(q['uri'])}'><select name='node_path'>{options}</select>"
                      "<button>Assign (saved as a rule)</button></form>")
        queue.append([e(q["kind"].replace("_", " ")), evidence(q["uri"], 1, 20, q["uri"]), e(q["detail"]), action])
    stats = json.loads(db.connect().execute("select stats_json from map_versions where version_id=?",
                                            (t.mv,)).fetchone()["stats_json"])
    head = (f"<p>Version <code>{e(t.mv)}</code> · {stats['resources']} resources · {stats['edges']} links · owners: "
            f"{stats['owners']['explicit']} explicit, {stats['owners']['inferred']} inferred, "
            f"{stats['owners']['unknown']} unknown {post('/map/rebuild', 'Rebuild')}</p>")
    return page("Company Map", head + detail + "<h2>Review queue</h2>"
                + table(["Kind", "Resource", "Detail", "Action"], queue) + "<h2>Hierarchy</h2>" + tree)


def evidence_page(uri: str, start: int, end: int) -> str:
    t = tools()
    lines = t.lines(uri)
    if lines is None:
        return page("Evidence", f"<p>{e(uri)} is not a resource in the current map.</p>")
    card = t.card(uri)
    body = "\n".join(f"<span class='{'hl' if start <= n <= end else ''}'><span class='ln'>{n:>4} </span>{e(line)}</span>"
                     for n, line in enumerate(lines, 1))
    links = [i for i in t.related(uri).get("items", []) if i["kind"] != "same_owner"][:12]
    rel = table(["Link", "From", "To", "Evidence"], [
        [e(i["kind"]), e(i["from"]), e(i["to"]), evidence(i["evidence"]["uri"], *i["evidence"]["lines"])]
        for i in links])
    secondary = "".join(f" · also under {e(p)}" for p in card["secondary_paths"])
    head = (f"<p><span class='badge waiting'>FICTIONAL PayRo data</span> {e(card['primary_path'])}{secondary} · owner "
            f"{e(card['owner_team'] or 'unknown')} ({e(card['ownership_source'])}) · lines {start}-{end} highlighted</p>")
    return page(uri, head + f"<pre>{body}</pre><h2>Cross-links</h2>" + rel)

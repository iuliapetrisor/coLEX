"""What the map picture shows, read from the map tables: the hierarchy with resource counts per source
system, the links between topics, and (optionally) the path one run's Impact Analyst walked."""
from __future__ import annotations

from typing import Any

from colex import db
from colex.map.hierarchy import SEP
from colex.map.tools_base import UNCLASSIFIED
from colex.runtime import audit, store

STRONG = ("implements", "governed_by", "references", "depends_on")   # same_owner and same_counterparty are not drawn


def hierarchy(mv: str) -> dict[str, Any]:
    con = db.connect()
    nodes = [dict(r) for r in con.execute("select level, path, name, summary from nodes where mv=? order by rowid",
                                          (mv,))]
    counts: dict[str, dict[str, int]] = {}
    for r in con.execute("select coalesce(primary_path, ?) place, source, count(*) n from resources where mv=? "
                         "group by 1, 2", (UNCLASSIFIED, mv)):
        counts.setdefault(r["place"], {})[r["source"]] = r["n"]
    marks = ",".join("?" * len(STRONG))
    links = [dict(r) for r in con.execute(
        "select a.primary_path a, b.primary_path b, e.kind kind, count(distinct e.src || '|' || e.dst) n "
        "from edges e join resources a on a.mv=e.mv and a.uri=e.src join resources b on b.mv=e.mv and b.uri=e.dst "
        f"where e.mv=? and e.kind in ({marks}) and a.primary_path is not null and b.primary_path is not null "
        "and a.primary_path<>b.primary_path group by 1, 2, 3 order by 1, 2, 3", (mv, *STRONG))]
    return {"mv": mv, "nodes": nodes, "counts": counts, "links": links}


def run_path(run_id: str, mv: str) -> dict[str, Any]:
    """Map nodes the Impact Analyst's tool calls landed on, in order of first visit, and where it reported."""
    row = store.run_row(run_id)                      # KeyError for an unknown run → 404 page
    visited: dict[str, int] = {}
    for ev in audit.events(run_id, limit=100000):
        crumbs = ev["detail"].get("breadcrumbs")
        if ev["agent"] == "impact" and ev["kind"] == "rationale" and crumbs and not ev["detail"].get("error"):
            visited.setdefault(crumbs, len(visited) + 1)
    step = store.step_row(run_id, "main:IMPACT")
    out = store.get_blob(step["output_ref"]) if step and step["output_ref"] else {}
    found: dict[str, int] = {}
    for item in out.get("items", []):
        res = db.connect().execute("select primary_path from resources where mv=? and uri=?",
                                   (mv, item["resource_uri"])).fetchone()
        if res:
            place = res["primary_path"] or UNCLASSIFIED
            found[place] = found.get(place, 0) + 1
    return {"run_id": run_id, "law": row["law_id"], "run_map": row["map_version_id"],
            "same_map": row["map_version_id"] == mv, "visited": visited, "found": found,
            "metrics": out.get("metrics") or {}}


def on_path(visited: dict[str, int]) -> set[str]:
    """The visited nodes and all their ancestors."""
    return {SEP.join(p.split(SEP)[:i]) for p in visited for i in range(1, p.count(SEP) + 2)}

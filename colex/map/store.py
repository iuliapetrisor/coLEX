"""Writes one map version to SQLite in a single transaction and activates it."""
from __future__ import annotations

from typing import Any

from colex import db
from colex.map import cards, hierarchy
from colex.runtime import audit

TABLES = ("nodes", "resources", "resource_nodes", "fragments", "entities", "counterparties",
          "resource_counterparties", "edges", "review_queue")


def _write(con, mv: str, resources: dict[str, dict[str, Any]], sec: dict[str, list[str]]) -> None:
    for uri, r in resources.items():
        facts = {**r["facts"], "placement": r["placement"], "ownership_origin": r["owner"]["ownership_origin"]}
        con.execute("insert into resources values(?,?,?,?,?,?,?,?,?,?,?)",
                    (mv, uri, r["source"], r["path"], r["title"], r["info_type"], r["primary_path"],
                     db.dumps(cards.card(r, mv, sec.get(uri, []))), db.dumps(facts), r["text"], r["sha"]))
        if r["primary_path"]:
            con.execute("insert into resource_nodes values(?,?,?,?)", (mv, uri, r["primary_path"], "primary"))
        lines = r["text"].splitlines()
        for f in r["fragments"]:
            con.execute("insert into fragments values(?,?,?,?,?,?)",
                        (mv, uri, f["title"], f["kind"], f["start"], f["end"]))
            con.execute("insert into fragments_fts(body,title,uri,mv,start,end) values(?,?,?,?,?,?)",
                        ("\n".join(lines[f["start"] - 1:f["end"]]), f["title"], uri, mv, f["start"], f["end"]))
        con.executemany("insert into entities values(?,?,?,?,?,?)",
                        [(mv, uri, e["etype"], e["value"], e["line"], e["snippet"]) for e in r["entities"]])
        con.executemany("insert into resource_counterparties values(?,?,?,?)",
                        [(mv, uri, cp, line) for cp, line in r["mentions"]])


def store(mv: str, resources: dict[str, dict[str, Any]], edges: list[tuple], secondary: list[tuple[str, str]],
          nodes: list[dict[str, Any]], rolled: dict[str, dict[str, Any]], registry, reused: int) -> dict[str, Any]:
    con = db.connect()
    sec: dict[str, list[str]] = {}
    for uri, path in secondary:
        sec.setdefault(uri, []).append(path)
    queue = cards.review_queue(resources)
    stats = cards.stats(mv, resources, edges, nodes, queue, reused)
    con.execute("begin immediate")
    try:
        for table in TABLES:
            con.execute(f"delete from {table} where mv=?", (mv,))
        con.execute("delete from fragments_fts where mv=?", (mv,))
        for n in nodes:
            info = rolled[n["path"]]
            rollup = {**info["rollup"], "gaps": info["gaps"], "count": info["count"], "secondary": info["secondary"]}
            con.execute("insert into nodes values(?,?,?,?,?,?,?,?)",
                        (mv, hierarchy.node_id(n["path"]), hierarchy.node_id(n["parent"]) if n["parent"] else None,
                         n["level"], n["name"], n["path"], info["summary"], db.dumps(rollup)))
        _write(con, mv, resources, sec)
        con.executemany("insert into resource_nodes values(?,?,?,?)", [(mv, u, p, "secondary") for u, p in secondary])
        con.executemany("insert into edges values(?,?,?,?,?,?,?)", [(mv, *e) for e in edges])
        con.executemany("insert into review_queue values(?,?,?,?)", [(mv, *q) for q in queue])
        for body in cards.counterparty_rows(resources, registry):
            con.execute("insert into counterparties values(?,?,?)", (mv, body["counterparty_id"], db.dumps(body)))
        con.execute("insert or replace into map_versions values(?,?,?)", (mv, audit.now(), db.dumps(stats)))
        con.execute("insert into kv(key,value) values('active_map',?) on conflict(key) do update set "
                    "value=excluded.value", (mv,))
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return stats


def active() -> str | None:
    return db.kv_get("active_map")

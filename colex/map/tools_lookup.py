"""Map lookup tools: find, search, counterparty, owners."""
from __future__ import annotations

import json
import re
from typing import Any

from colex import db
from colex.map.hierarchy import norm_path
from colex.map.registry import norm_name
from colex.map.tools_links import Links


class Lookup(Links):
    def find(self, etype: str, value: str | None = None, under: str | None = None, cursor: int = 0) -> dict[str, Any]:
        """Occurrences of an entity type (optionally a value substring), with uri + line."""
        scope = self._uris_under(under)
        sql, args = "select * from entities where mv=? and etype=?", [self.mv, str(etype)]
        if value:
            escaped = re.sub(r"([%_\\])", r"\\\1", str(value))
            sql, args = sql + " and value like ? escape '\\'", args + [f"%{escaped}%"]
        con = db.connect()
        hits = [{"uri": r["uri"], "line": r["line"], "value": r["value"], "snippet": r["snippet"],
                 "breadcrumbs": self._crumbs(r["uri"])}
                for r in con.execute(sql + " order by uri, line", args) if scope is None or r["uri"] in scope]
        known = sorted(r["etype"] for r in con.execute("select distinct etype from entities where mv=?", (self.mv,)))
        extra = {} if str(etype) in known else {"error": f"unknown entity type; known: {', '.join(known)}"}
        return self._out(norm_path(under) if under else "PayRo", {**self._page(hits, cursor), **extra})

    def search(self, text: str, under: str | None = None, cursor: int = 0) -> dict[str, Any]:
        """Full-text search over fragments. The query is treated as plain words, never as FTS syntax."""
        words = re.findall(r"\w+", str(text)[:300])[:12]
        crumbs = norm_path(under) if under else "PayRo"
        if not words:
            return self._out(crumbs, {"items": [], "total": 0, "error": "empty query"})
        scope = self._uris_under(under)
        query = " OR ".join(f'"{w}"' for w in words)
        rows = db.connect().execute(
            "select uri, title, start, end, snippet(fragments_fts, 0, '[', ']', ' … ', 12) snip from fragments_fts "
            "where fragments_fts match ? and mv=? order by rank limit 200", (query, self.mv)).fetchall()
        hits = [{"uri": r["uri"], "fragment": r["title"], "lines": [r["start"], r["end"]], "snippet": r["snip"],
                 "breadcrumbs": self._crumbs(r["uri"])} for r in rows if scope is None or r["uri"] in scope]
        return self._out(crumbs, self._page(hits, cursor))

    def counterparty(self, name: str) -> dict[str, Any]:
        """Everything about one contractor: contract, criticality, data location, code, tickets, owners."""
        con = db.connect()
        rows = [json.loads(r["body_json"]) for r in con.execute("select body_json from counterparties where mv=?",
                                                                (self.mv,))]
        want = norm_name(str(name))
        match = next((c for c in rows if c["counterparty_id"] == name or want in
                      [norm_name(n) for n in [c["canonical_name"], *c["aliases"]]]), None)
        if match is None:
            return self._out("PayRo", {"error": f"unknown counterparty '{name}'",
                                       "known": [c["canonical_name"] for c in rows]})
        places: dict[str, list[int]] = {}
        for r in con.execute("select uri, line from resource_counterparties where mv=? and cp_id=? order by uri, line",
                             (self.mv, match["counterparty_id"])):
            places.setdefault(r["uri"], []).append(r["line"])
        res = {r["uri"]: r for r in self._rows(None)}
        mentions = [{"uri": u, "info_type": res[u]["info_type"], "owner_team": res[u]["owner_team"],
                     "lines": lines[:8], "breadcrumbs": res[u]["primary_path"]} for u, lines in places.items()]
        contract = next((res[u] for u in places if res[u]["info_type"] == "contract"
                         and res[u].get("counterparty") == match["counterparty_id"]), None)
        return self._out(contract["primary_path"] if contract else "PayRo",
                         {"counterparty": match, "contract": contract, "mentions": mentions})

    def owners(self, team: str) -> dict[str, Any]:
        """Resources a team owns, grouped by map path. team='unknown' lists resources with no owner."""
        want = None if str(team).lower() in ("unknown", "none", "") else str(team)
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in self._rows(None):
            if r["owner_team"] == want:
                groups.setdefault(r["primary_path"], []).append(
                    {"uri": r["uri"], "info_type": r["info_type"], "ownership_source": r["ownership_source"]})
        return self._out("PayRo", {"team": team, "total": sum(len(v) for v in groups.values()), "by_path": groups})

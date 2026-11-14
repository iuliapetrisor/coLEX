"""Map navigation tools (brief §3.5). Every result carries breadcrumbs, the map version and a size estimate.

Results are bounded (max items, max characters). The meter records what an agent actually read,
which feeds the context-savings metric.
"""
from __future__ import annotations

from typing import Any

from colex import db
from colex.map.hierarchy import SEP, norm_path
from colex.map.tools_base import UNCLASSIFIED, Base, tokens  # noqa: F401
from colex.map.tools_lookup import Lookup

MAX_READ_LINES = 80


class MapTools(Base, Lookup):
    def overview(self) -> dict[str, Any]:
        rows = db.connect().execute("select * from nodes where mv=? and level in ('L0','L1') order by level, path",
                                    (self.mv,)).fetchall()
        areas = [{"path": r["path"], "summary": r["summary"]} for r in rows[1:]]
        return self._out(rows[0]["path"], {"company_profile": self.cfg["profile"], "summary": rows[0]["summary"],
                                           "areas": areas})

    def browse(self, path: str, depth: int = 1, facets: dict[str, Any] | None = None) -> dict[str, Any]:
        node, bad = self._node(path), self._bad_facets(facets)
        if node is None or bad:
            return self._out(norm_path(str(path)) or "?",
                             {"error": bad or f"unknown path '{path}'; start from overview()"})
        try:
            depth = max(1, min(int(depth), 2))
        except (TypeError, ValueError):
            depth = 1
        rows = db.connect().execute("select * from nodes where mv=? and path like ? order by path",
                                    (self.mv, node["path"] + SEP + "%")).fetchall()
        base, children = node["path"].count(SEP), []
        for r in rows:
            if r["path"].count(SEP) - base > depth:
                continue
            item = {"path": r["path"], "level": r["level"], "summary": r["summary"]}
            if facets:
                item["matching_resources"] = sum(1 for x in self._rows(r["path"]) if self._match(x, facets))
            children.append(item)
        return self._out(node["path"], {"summary": node["summary"], "children": children})

    def list_resources(self, path: str, facets: dict[str, Any] | None = None, cursor: int = 0) -> dict[str, Any]:
        node, bad = self._node(path), self._bad_facets(facets)
        if node is None or bad:
            return self._out(norm_path(str(path)) or "?",
                             {"error": bad or f"unknown path '{path}'; use browse() to find a valid path"})
        found = [r for r in self._rows(node["path"]) if self._match(r, facets or {})]
        return self._out(node["path"], self._page(found, cursor))

    def read(self, uri: str, start: int = 1, end: int | None = None) -> dict[str, Any]:
        """Only the requested lines of a resource that exists in the map. Never a filesystem path."""
        row = db.connect().execute("select body, primary_path from resources where mv=? and uri=?",
                                   (self.mv, str(uri))).fetchone()
        if row is None:
            return self._out("?", {"error": f"'{uri}' is not a resource in the map"})
        crumbs = row["primary_path"] or UNCLASSIFIED
        lines = row["body"].splitlines()
        try:
            start = max(int(start), 1)
            end = min(int(end) if end is not None else start + MAX_READ_LINES - 1, len(lines))
        except (TypeError, ValueError):
            return self._out(crumbs, {"error": "start and end must be integers"})
        if start > end:
            return self._out(crumbs, {"error": f"empty range: the resource has {len(lines)} lines"})
        end = min(end, start + MAX_READ_LINES - 1)
        self.meter["read"].add((str(uri), start, end))
        text = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
        return self._out(crumbs, {"uri": uri, "start": start, "end": end, "total_lines": len(lines), "text": text})

    def neighbors(self, uri_or_path: str, kinds: list[str] | None = None) -> dict[str, Any]:
        """Alias of related() kept for the starter code (D-001)."""
        return self.related(uri_or_path, kinds)

    def totals(self) -> dict[str, int]:
        """Corpus sizes for the context baselines: A = whole corpus, per L1 area for baseline B."""
        con = db.connect()
        rows = con.execute("select primary_path, body from resources where mv=?", (self.mv,)).fetchall()
        areas: dict[str, int] = {}
        for r in rows:
            if r["primary_path"]:
                area = r["primary_path"].split(SEP)[1]
                areas[area] = areas.get(area, 0) + tokens(r["body"])
        fragments = con.execute("select count(*) n from fragments where mv=?", (self.mv,)).fetchone()["n"]
        return {"corpus_tokens": sum(tokens(r["body"]) for r in rows), "area_tokens": areas,
                "fragments": fragments, "resources": len(rows)}

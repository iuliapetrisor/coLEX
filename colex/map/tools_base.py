"""Shared helpers of the map tools: bounded output, metering, resource rows, facet filters."""
from __future__ import annotations

import json
from typing import Any

from colex import db
from colex.map import store
from colex.map.hierarchy import SEP, norm_path

FACETS = ("info_type", "owner_team", "source", "counterparty", "critical", "ownership_source", "has_gaps")
UNCLASSIFIED = "PayRo › Unclassified"


def tokens(text: str) -> int:
    """Rough token estimate (4 characters per token), used consistently for the context metric."""
    return len(text) // 4


class Base:
    def __init__(self, cfg: dict[str, Any], mv: str | None = None) -> None:
        self.mv = mv or store.active()
        if not self.mv:
            raise RuntimeError("no Company Map has been built yet")
        self.cfg = cfg
        self.max_items, self.max_chars = cfg["map"]["max_items"], cfg["map"]["max_chars"]
        self.meter: dict[str, Any] = {"calls": 0, "tokens": 0, "read": set(), "depth": 0, "areas": set()}

    def _out(self, crumbs: str, payload: dict[str, Any]) -> dict[str, Any]:
        out = {"breadcrumbs": crumbs, "map_version_id": self.mv, **payload}
        text = json.dumps(out, ensure_ascii=False)
        if len(text) > self.max_chars:   # never return an unbounded payload
            out = {"breadcrumbs": crumbs, "map_version_id": self.mv, "truncated": True,
                   "error": "result too large; narrow the query (facets, under, a smaller line range)",
                   "preview": text[: self.max_chars // 2]}
            text = json.dumps(out, ensure_ascii=False)
        out["tokens_estimate"] = tokens(text)
        self.meter["calls"] += 1
        self.meter["tokens"] += out["tokens_estimate"]
        parts = crumbs.split(SEP)
        self.meter["depth"] = max(self.meter["depth"], len(parts) - 1)
        if len(parts) > 1 and parts[1] != "Unclassified":
            self.meter["areas"].add(parts[1])
        return out

    def _page(self, items: list[Any], cursor: int) -> dict[str, Any]:
        """One page that fits both limits: at most max_items and about 80% of max_chars."""
        try:
            cursor = max(int(cursor or 0), 0)
        except (TypeError, ValueError):
            cursor = 0
        page, used, budget = [], 0, int(self.max_chars * 0.8)
        for item in items[cursor:cursor + self.max_items]:
            size = len(json.dumps(item, ensure_ascii=False))
            if page and used + size > budget:
                break
            page.append(item)
            used += size
        nxt = cursor + len(page)
        return {"items": page, "total": len(items), **({"next_cursor": nxt} if nxt < len(items) else {})}

    def _node(self, path: str) -> dict[str, Any] | None:
        row = db.connect().execute("select * from nodes where mv=? and path=?",
                                   (self.mv, norm_path(str(path)))).fetchone()
        return dict(row) if row else None

    def _crumbs(self, uri: str) -> str:
        row = db.connect().execute("select primary_path from resources where mv=? and uri=?",
                                   (self.mv, uri)).fetchone()
        return (row["primary_path"] if row and row["primary_path"] else UNCLASSIFIED)

    def _rows(self, under: str | None) -> list[dict[str, Any]]:
        """Resources under a node: primary members first, then secondary members."""
        con = db.connect()
        if not under:
            return [self._res(r, "primary") for r in
                    con.execute("select * from resources where mv=? order by uri", (self.mv,))]
        path = norm_path(under)
        rows = con.execute(
            "select r.*, n.kind membership from resources r join resource_nodes n on n.mv=r.mv and n.uri=r.uri "
            "where r.mv=? and (n.node_path=? or n.node_path like ?) order by n.kind, r.uri",
            (self.mv, path, path + SEP + "%")).fetchall()
        return [self._res(r, r["membership"]) for r in rows]

    def _uris_under(self, under: str | None) -> set[str] | None:
        return {r["uri"] for r in self._rows(under)} if under else None

    def _res(self, row, membership: str) -> dict[str, Any]:
        card, facts = json.loads(row["card_json"]), json.loads(row["facts_json"])
        clauses = facts.get("clauses", {})
        out = {"uri": row["uri"], "title": row["title"], "info_type": row["info_type"],
               "primary_path": card["primary_path"], "owner_team": card["owner_team"],
               "ownership_source": card["ownership_source"], "counterparties": card["counterparties"],
               "lines": row["body"].count("\n") + 1}
        if membership == "secondary":
            out["membership"] = "secondary"
        if card["secondary_paths"]:
            out["secondary_paths"] = card["secondary_paths"]
        if row["info_type"] == "contract":
            out.update(counterparty=facts.get("counterparty_id"), critical=facts.get("critical"),
                       missing_clauses=clauses.get("missing", []),
                       missing_if_critical=clauses.get("missing_if_critical", []))
        return out

    @staticmethod
    def _match(res: dict[str, Any], facets: dict[str, Any]) -> bool:
        for key, want in facets.items():
            if key == "counterparty":
                ok = want in res["counterparties"]
            elif key == "critical":
                have = {True: "true", False: "false", None: "unknown"}[res.get("critical")]
                ok = res["info_type"] == "contract" and str(want).lower() == have
            elif key == "has_gaps":
                ok = bool(res.get("missing_clauses")) == (str(want).lower() == "true")
            elif key == "source":
                ok = res["uri"].startswith(f"{want}://")
            else:
                ok = str(res.get(key)) == str(want)
            if not ok:
                return False
        return True

    @staticmethod
    def _bad_facets(facets: dict[str, Any] | None) -> str | None:
        if facets is not None and not isinstance(facets, dict):
            return "facets must be an object"
        bad = [k for k in (facets or {}) if k not in FACETS]
        return f"unknown facet(s) {bad}; allowed: {', '.join(FACETS)}" if bad else None

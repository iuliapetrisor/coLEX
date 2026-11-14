"""Map tools that follow links: related, obligations, unclassified."""
from __future__ import annotations

from typing import Any

from colex import db
from colex.map.hierarchy import norm_path

EDGE_KINDS = ("governed_by", "implements", "same_counterparty", "references", "depends_on", "same_owner",
              "regulated_by")
OBLIGATION_FIELDS = ("citation", "obligation", "node_path", "uri", "start", "end", "status", "owner_team", "deadline")


class Links:
    def related(self, uri_or_path: str, kinds: list[str] | None = None) -> dict[str, Any]:
        """Cross-links of a resource (both directions) with evidence, plus its secondary memberships."""
        target = str(uri_or_path)
        wanted = [k for k in (kinds or []) if k in EDGE_KINDS] if isinstance(kinds, list) else []
        con = db.connect()
        node = self._node(target) if "://" not in target else None
        if node:
            uris = [r["uri"] for r in self._rows(node["path"])]
        elif con.execute("select 1 from resources where mv=? and uri=?", (self.mv, target)).fetchone():
            uris = [target]
        else:
            return self._out("?", {"error": f"'{target}' is neither a resource nor a map path"})
        links, seen = [], set()
        for uri in uris:
            for r in con.execute("select * from edges where mv=? and (src=? or dst=?) order by kind, src, dst",
                                 (self.mv, uri, uri)):
                key = (r["src"], r["dst"], r["kind"], r["ev_start"])
                if (wanted and r["kind"] not in wanted) or key in seen:
                    continue
                seen.add(key)
                other = r["dst"] if r["src"] == uri else r["src"]
                links.append({"kind": r["kind"], "from": r["src"], "to": r["dst"],
                              "other_breadcrumbs": self._crumbs(other),
                              "evidence": {"uri": r["ev_uri"], "lines": [r["ev_start"], r["ev_end"]]}})
        secondary = [r["node_path"] for r in con.execute(
            "select node_path from resource_nodes where mv=? and uri=? and kind='secondary'", (self.mv, target))]
        crumbs = node["path"] if node else self._crumbs(target)
        return self._out(crumbs, {**self._page(links, 0), "primary_path": crumbs, "secondary_paths": secondary})

    def obligations(self, article: str | None = None, path: str | None = None) -> dict[str, Any]:
        """Obligations Register rows for a law article (part of the citation) or for a map node.

        An obligation attached to a node applies to everything under it, so a query for a deeper
        path also returns the obligations of its ancestors.
        """
        sql, args = "select * from obligations where 1=1", []
        if article:
            sql += " and replace(citation,' ','') like ?"
            args.append(f"%{str(article).replace(' ', '')}%")
        if path:
            p = norm_path(str(path))
            sql += " and (node_path=? or node_path like ? or ? like node_path || ' › %')"
            args += [p, p + " › %", p]
        rows = [{k: r[k] for k in OBLIGATION_FIELDS} for r in db.connect().execute(sql + " order by id", args)]
        return self._out(norm_path(str(path)) if path else "PayRo", self._page(rows, 0))

    def unclassified(self) -> dict[str, Any]:
        """Review queues for humans (Console only; the runtime agent cannot call this)."""
        rows = [dict(r) for r in db.connect().execute("select kind, uri, detail from review_queue where mv=?",
                                                      (self.mv,))]
        return self._out("PayRo › Unclassified", {"items": rows, "total": len(rows)})

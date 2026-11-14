"""Bottom-up rollups and deterministic one-line summaries for every map node (D-007)."""
from __future__ import annotations

from collections import Counter
from typing import Any

from colex.map.hierarchy import SEP


def _top(counter: Counter, n: int = 4) -> str:
    return ", ".join(f"{k}({v})" for k, v in counter.most_common(n))


def compute(node_paths: list[str], resources: dict[str, dict[str, Any]], secondary: list[tuple[str, str]],
            names: dict[str, str]) -> dict[str, dict[str, Any]]:
    out = {}
    extra: dict[str, list[str]] = {}
    for uri, path in secondary:
        extra.setdefault(path, []).append(uri)
    for path in node_paths:
        under = [r for r in resources.values() if r["primary_path"]
                 and (r["primary_path"] == path or r["primary_path"].startswith(path + SEP))]
        linked = sorted({u for p, uris in extra.items() if p == path or p.startswith(path + SEP) for u in uris})
        types = Counter(r["info_type"] for r in under)
        owners = Counter(r["owner"]["owner_team"] or "unknown" for r in under)
        entities = Counter(e["etype"] for r in under for e in r["entities"])
        cps = sorted({cp for r in under for cp, _ in r["mentions"]})
        tags = sorted({t for r in under for t in r.get("regulatory_tags", [])})
        gaps = Counter()
        for r in under:
            for clause in r["facts"].get("clauses", {}).get("missing", []):
                gaps[clause] += 1
            if r["facts"].get("critical") is None and r["info_type"] == "contract":
                gaps["criticality not assessed"] += 1
        inferred = sum(1 for r in under if r["owner"]["ownership_source"] == "inferred")
        rollup = {"resource_count_by_type": dict(types), "entity_histogram": dict(entities),
                  "owners": dict(owners), "counterparties": cps, "regulatory_tags": tags}
        parts = [f"{len(under)} resource(s)" + (f": {_top(types)}" if types else "")]
        if gaps:
            parts.append("gaps: " + ", ".join(f"{v}× {k}" for k, v in sorted(gaps.items())))
        if owners:
            parts.append("owners: " + _top(owners) + (f", {inferred} inferred" if inferred else ""))
        if cps:
            parts.append("contractors: " + ", ".join(names.get(c, c) for c in cps[:6]))
        if linked:
            parts.append(f"{len(linked)} linked from other branches")
        out[path] = {"rollup": rollup, "summary": " · ".join(parts), "gaps": dict(gaps), "count": len(under),
                     "secondary": linked}
    return out

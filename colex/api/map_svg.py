"""Draws the Company Map as one SVG: company → business areas → domains → topics, a bar per topic with its
resources per source system, arcs for the links between topics, and optionally the path one run walked."""
from __future__ import annotations

from html import escape as e
from math import sqrt
from typing import Any
from urllib.parse import quote

from colex.api.map_data import on_path
from colex.api.map_layout import (ARC_X, BAR_W, BAR_X, COLUMNS, KINDS, ROW, SOURCES, STYLE, TOP, W,  # noqa: F401
                                  WIDTH, X, spans)
from colex.map.hierarchy import SEP
from colex.map.tools_base import UNCLASSIFIED


def _node(n: dict[str, Any], span: tuple[int, int], state: str, total: int, order: int | None, hits: int) -> str:
    x, w = X[n["level"]], W[n["level"]]
    y, h = TOP + span[0] * ROW + 3, (span[1] - span[0] + 1) * ROW - 6
    mid, label = y + h / 2, e(n["name"])
    text = f"<text x='{x + 10}' y='{mid + 5:.0f}'>{label}</text>"
    if h >= 50:
        text = (f"<text x='{x + 10}' y='{mid - 3:.0f}'>{label}</text>"
                f"<text x='{x + 10}' y='{mid + 15:.0f}' class='num'>{total:,}</text>")
    tag = f"<text x='{x + w - 16}' y='{mid + 4:.0f}' class='tag'>{hits} found</text>" if hits else ""
    badge = (f"<g class='ord'><circle cx='{x + w - 3}' cy='{y + 3}' r='10'/>"
             f"<text x='{x + w - 3}' y='{y + 7}'>{order}</text></g>") if order else ""
    href = "/map" if n["path"] == UNCLASSIFIED else f"/map?path={quote(n['path'])}"
    return (f"<g class='{n['level']} {state}'><a href='{href}'><rect class='n' x='{x}' y='{y}' width='{w}' "
            f"height='{h}' rx='5'/>{text}{tag}</a>{badge}")


def _bar(by: dict[str, int], y: int, biggest: int) -> str:
    total, x, out = sum(by.values()), float(BAR_X), ""
    if total:
        full = max(6.0, BAR_W * sqrt(total / biggest))
        for source, colour in SOURCES.items():
            if by.get(source):
                width = full * by[source] / total
                out += (f"<rect x='{x:.1f}' y='{y + 4}' width='{width:.1f}' height='{ROW - 14}' fill='{colour}'>"
                        f"<title>{by[source]:,} from {e(source)}</title></rect>")
                x += width
    return out + f"<text x='{x + 6:.1f}' y='{y + ROW / 2 + 2:.0f}' class='num'>{total:,}</text>"


def _arc(link: dict[str, Any], a: tuple[int, int], b: tuple[int, int]) -> str:
    y1, y2 = TOP + a[0] * ROW + ROW / 2, TOP + b[0] * ROW + ROW / 2
    d = min(150, 36 + 9 * abs(a[0] - b[0])) + 7 * list(KINDS).index(link["kind"])
    tip = f"{link['kind']}: {link['n']} link(s) from {link['a'].split(SEP)[-1]} to {link['b'].split(SEP)[-1]}"
    return (f"<path class='arc' stroke='{KINDS[link['kind']]}' d='M{ARC_X} {y1:.0f} C{ARC_X + d} {y1:.0f}, "
            f"{ARC_X + d} {y2:.0f}, {ARC_X} {y2:.0f}'><title>{e(tip)}</title></path>")


def svg(data: dict[str, Any], path: dict[str, Any] | None = None) -> str:
    rows = spans(data["nodes"])
    totals = {place: sum(by.values()) for place, by in data["counts"].items()}
    biggest = max(totals.values(), default=1)
    visited, found = (path["visited"], path["found"]) if path else ({}, {})
    lit = on_path(visited)
    parts = [f"<text x='{x}' y='18' class='col'>{e(label)}</text>" for x, label in COLUMNS]
    queue = {"level": "L1", "path": UNCLASSIFIED, "name": "Unclassified: waits for a person"}
    for n in [*data["nodes"], queue]:
        if n["path"] not in rows:
            continue
        p = n["path"]
        state = "seen" if p in visited else "via" if p in lit else "dim" if path else ""
        state += (" hit" if p in found else "") + (" queue" if p == UNCLASSIFIED else "")
        under = sum(t for place, t in totals.items() if place == p or place.startswith(p + SEP))
        parts.append(_node(n, rows[p], state, under, visited.get(p), found.get(p, 0)))
        if n["level"] == "L3" or p == UNCLASSIFIED:
            parts.append(_bar(data["counts"].get(p, {}), TOP + rows[p][0] * ROW + 3, biggest))
        parts.append("</g>")
    parts += [_arc(link, rows[link["a"]], rows[link["b"]]) for link in data["links"]
              if link["a"] in rows and link["b"] in rows]
    height = TOP + (rows[UNCLASSIFIED][1] + 1) * ROW + 10
    return (f"{STYLE}<svg class='map' viewBox='0 0 {WIDTH} {height}' xmlns='http://www.w3.org/2000/svg' "
            f"role='img' aria-label='Company Map'>{''.join(parts)}</svg>")

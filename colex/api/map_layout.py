"""Layout of the map picture: column positions, colours, style, and the rows each node covers."""
from __future__ import annotations

from typing import Any

from colex.map.hierarchy import SEP
from colex.map.tools_base import UNCLASSIFIED

ROW, TOP, WIDTH = 30, 34, 1400
X = {"L0": 6, "L1": 112, "L2": 366, "L3": 620}
W = {"L0": 96, "L1": 244, "L2": 244, "L3": 256}
BAR_X, BAR_W, ARC_X = 888, 280, 1236
SOURCES = {"onedrive": "#2563eb", "gdrive": "#16a34a", "confluence": "#7c3aed", "jira": "#ea580c",
           "intranet": "#64748b", "repo": "#111827"}
KINDS = {"implements": "#be123c", "governed_by": "#0f766e", "references": "#a16207", "depends_on": "#475569"}
COLUMNS = ((6, "Company"), (112, "Business area"), (366, "Domain"), (620, "Topic"),
           (888, "Resources per source system (bar: square-root scale)"), (1236, "Links between topics"))
STYLE = """<style>
svg.map{width:100%;height:auto;background:#fff;border:1px solid #dde1e8;font:14px system-ui,sans-serif}
svg.map rect.n{fill:#eef1f6;stroke:#9aa5b8} svg.map .L0 rect.n{fill:#1d2b4f} svg.map .L0 text{fill:#fff}
svg.map .L3 rect.n{fill:#fff} svg.map .dim{opacity:.25} svg.map .num{font-size:13px;fill:#445}
svg.map .L0 .num{fill:#cfd8ff} svg.map .seen rect.n{stroke:#d97706;stroke-width:3}
svg.map .via rect.n{stroke:#d97706;stroke-dasharray:5 3;stroke-width:2} svg.map .hit rect.n{fill:#dcfce7}
svg.map .tag{font-size:12px;font-weight:700;fill:#17603a;text-anchor:end} svg.map .arc{fill:none;stroke-width:2;opacity:.8}
svg.map .ord circle{fill:#d97706} svg.map .ord text{fill:#fff;font-size:11px;font-weight:700;text-anchor:middle}
svg.map .col{font-size:12px;fill:#667} svg.map .queue rect.n{stroke-dasharray:4 3;fill:#fff7ed}
.key i{display:inline-block;width:14px;height:14px;margin:0 4px -2px 12px;border-radius:3px}
</style>"""


def spans(nodes: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Rows (first, last) each node covers: every topic is one row, the review queue is the last row."""
    out: dict[str, tuple[int, int]] = {}
    row = 0
    for n in nodes:
        if n["level"] != "L3":
            continue
        parts = n["path"].split(SEP)
        for depth in range(1, len(parts) + 1):
            path = SEP.join(parts[:depth])
            out[path] = (out.get(path, (row, row))[0], row)
        row += 1
    out[UNCLASSIFIED] = (row, row)
    return out

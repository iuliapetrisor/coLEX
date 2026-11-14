"""Console layout and HTML helpers. Server-rendered, no build step. The Console is not a chat UI:
people talk in Slack; this shows the timeline, the map, registers, diffs and settings."""
from __future__ import annotations

from html import escape as e
from typing import Any, Iterable
from urllib.parse import quote

NAV = [("/", "Runs"), ("/feed", "Feed"), ("/map", "Map"), ("/map/picture", "Map picture"), ("/registers", "Registers"),
       ("/slack", "Slack delivery"), ("/settings", "Settings")]
CSS = """
body{font:17px/1.45 system-ui,sans-serif;margin:0;color:#1b1f2a;background:#f6f7f9}
header{background:#1d2b4f;color:#fff;padding:10px 20px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header a{color:#cfd8ff;text-decoration:none} header .tag{margin-left:auto;font-size:13px;opacity:.85}
main{max-width:1180px;margin:0 auto;padding:16px 20px} h1{font-size:24px;margin:8px 0 14px} h2{font-size:19px;margin:22px 0 8px}
table{border-collapse:collapse;width:100%;background:#fff} th,td{border:1px solid #dde1e8;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#eef1f6;font-size:14px} code,pre{font:14px/1.4 ui-monospace,monospace} pre{background:#fff;border:1px solid #dde1e8;padding:10px;overflow:auto}
.badge{display:inline-block;padding:1px 9px;border-radius:10px;font-size:13px;font-weight:600;border:1px solid}
.done{color:#17603a;border-color:#17603a} .running{color:#1d4ed8;border-color:#1d4ed8} .waiting{color:#a15c00;border-color:#a15c00}
.failed{color:#a31515;border-color:#a31515} .muted{color:#667} .box{background:#fff;border:1px solid #dde1e8;padding:10px 14px;margin:10px 0}
.warn{border-left:5px solid #a15c00} .ev{display:grid;grid-template-columns:92px 104px 1fr;gap:10px;padding:4px 0;border-bottom:1px solid #e6e9ef}
.ev .k{font-size:13px;font-weight:600} .hl{background:#fff3b0} .ln{color:#99a;user-select:none}
form{display:inline} button{font:inherit;padding:3px 11px;margin:2px;border:1px solid #1d2b4f;background:#fff;border-radius:5px;cursor:pointer}
button.primary{background:#1d2b4f;color:#fff} textarea{width:100%;font:14px ui-monospace,monospace} .add{color:#17603a} .del{color:#a31515}
"""
STATUS_CLASS = {"done": "done", "running": "running", "failed": "failed", "cancelled": "failed", "sent": "done",
                "decided": "done", "answered": "done", "relevant": "running", "archived": "muted", "gap": "waiting"}


def page(title: str, body: str, refresh: int = 0, wide: bool = False) -> str:
    nav = " ".join(f'<a href="{href}">{text}</a>' for href, text in NAV)
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    main = "<main style='max-width:1560px'>" if wide else "<main>"
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>{meta}<title>{e(title)} · coLEX</title>"
            f"<style>{CSS}</style></head><body><header><b>coLEX Console</b> {nav}"
            "<span class='tag'>FICTIONAL PayRo data · decision support, not legal advice</span></header>"
            f"{main}<h1>{e(title)}</h1>{body}</main></body></html>")


def badge(status: Any) -> str:
    text = str(status)
    cls = STATUS_CLASS.get(text, "waiting" if text.startswith(("waiting", "pending")) else "muted")
    return f"<span class='badge {cls}'>{e(text.replace('_', ' '))}</span>"


def table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    """Cells are HTML: callers escape their own text."""
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>" if body else "<p class='muted'>Nothing to show.</p>"


def evidence(uri: str, start: int, end: int, label: str | None = None) -> str:
    href = f"/evidence?uri={quote(uri, safe='')}&start={start}&end={end}"
    return f'<a href="{href}">{e(label or f"{uri}:{start}-{end}")}</a>'


def law(citation: str) -> str:
    """Link 'CELEX:32022R2554 Art. 30' to the stored official text."""
    if not citation.startswith("CELEX:"):
        return e(citation)
    celex, _, article = citation[6:].partition(" ")
    return f'<a href="/law/{quote(celex)}#{quote(article)}">{e(citation)}</a>'


def post(action: str, label: str, fields: dict[str, str] | None = None, primary: bool = False) -> str:
    hidden = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in (fields or {}).items())
    cls = " class='primary'" if primary else ""
    return f'<form method="post" action="{e(action)}">{hidden}<button{cls}>{e(label)}</button></form>'

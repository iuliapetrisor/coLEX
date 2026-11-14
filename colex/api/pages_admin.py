"""Feed, Slack delivery and Settings pages."""
from __future__ import annotations

from html import escape as e
from urllib.parse import quote

import yaml

from colex import settings
from colex.agents import watcher
from colex.api.html import badge, page, post, table
from colex.config import ConfigStore
from colex.notify.base import outbox_rows


def feed() -> str:
    known = {law["celex"]: law for law in watcher.laws()}
    rows = []
    for path in sorted(settings.FEED.glob("*.md")):
        celex = path.stem
        law = known.get(celex)
        if law is None:
            rows.append([e(celex), "<span class='muted'>not published yet</span>", "",
                         post("/feed/publish", "Publish", {"celex": celex}, True)])
            continue
        triage = law["triage"] or {}
        verdict = badge(law["status"]) + (f" relevance {triage['relevance']:.2f}" if "relevance" in triage else "")
        run = f"<a href='/runs/{e(law['run_id'])}'>run</a>" if law["run_id"] and law["status"] != "archived" else ""
        rows.append([f"<a href='/law/{quote(celex)}'>{e(celex)}</a><br><span class='muted'>{e(law['title'][:120])}</span>",
                     verdict, e(law["reason"] or ""), run])
    bad = [[e(law["title"]), badge("quarantined"), e(law["reason"] or ""), ""]
           for law in known.values() if law["status"] == "quarantined"]
    return page("Legal feed", "<p>Official acts in the library. Publishing copies one into the live feed; coLEX then "
                "triages it and shows why it was kept or rejected.</p>"
                + table(["Act", "Triage", "Why", ""], rows + bad), refresh=6)


def slack() -> str:
    rows = outbox_rows()
    pending = [r for r in rows if r["status"] in ("pending", "failed")]
    banner = (f"<div class='box warn'><b>Slack delivery pending</b>: {len(pending)} message(s) not delivered. Runs "
              "continue; decisions can be made from the run pages of this Console.</div>") if pending else ""
    listed = [[e(str(r["id"])), e(r["kind"]), e(r["channel"]), badge(r["status"]), e(str(r["attempts"])),
               e(r["error"] or ""), f"<a href='/runs/{e(r['run_id'])}'>{e(r['run_id'])}</a>" if r["run_id"] else ""]
              for r in reversed(rows)]
    return page("Slack delivery", banner + "<p class='muted'>Every outgoing message is queued here with an idempotency "
                "key before it is sent.</p>" + table(["#", "Kind", "Channel", "Status", "Attempts", "Error", "Run"],
                                                    listed), refresh=6)


def settings_page(error: str = "", draft: str | None = None) -> str:
    store = ConfigStore()
    active = store.active()
    text = draft if draft is not None else yaml.safe_dump(active.payload, sort_keys=False, allow_unicode=True)
    problem = f"<div class='box warn'><b>Not saved.</b><pre>{e(error)}</pre></div>" if error else ""
    history = []
    for v in store.history():
        current = v.version_id == active.version_id
        history.append([e(v.version_id) + (" (active)" if current else ""), e(v.author), e(str(v.ts)[:19]),
                        f"<pre>{e(v.diff[:1500])}</pre>",
                        "" if current else post(f"/settings/rollback/{v.version_id}", "Roll back to this")])
    return page("Settings", problem + f"<p>Active version <code>{e(active.version_id)}</code>. A saved change applies "
                "to the <b>next</b> steps of running runs; completed steps keep the version they ran with. To apply a "
                "change to past steps, fork a run from a checkpoint. No secrets belong here.</p>"
                f"<form method='post' action='/settings'><textarea name='yaml' rows='26'>{e(text)}</textarea><br>"
                "Your name: <input name='author' value='console'> <button class='primary'>Validate and save</button>"
                "</form><h2>Version history</h2>" + table(["Version", "Author", "Saved", "Diff", ""], history))

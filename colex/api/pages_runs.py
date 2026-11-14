"""Run list and the change (PR diff) view."""
from __future__ import annotations

from html import escape as e

from colex import db
from colex.api.html import badge, page, table
from colex.runtime import store
from colex.runtime.core import TRANSITIONS

MERGE = "coLEX never merges. Approval records the decision; merging stays a manual human step."


def index() -> str:
    rows = []
    for r in db.connect().execute("select r.*, l.title, l.status law_status from runs r left join laws l "
                                  "on l.celex=r.law_id order by r.created_ts desc"):
        if r["law_status"] == "archived":
            continue
        waits = len(store.waits(r["run_id"], "pending"))
        rows.append([f'<a href="/runs/{e(r["run_id"])}">{e(r["run_id"])}</a>', f"CELEX {e(r['law_id'])}",
                     e((r["title"] or "")[:110]), badge("paused" if r["paused"] else r["status"]),
                     f"{waits} waiting for a human" if waits else ""])
    archived = db.connect().execute("select count(*) n from laws where status='archived'").fetchone()["n"]
    graph = " · ".join(f"{node} → {', '.join(sorted(nxt)) or 'end'}" for node, nxt in TRANSITIONS.items())
    return page("Runs", table(["Run", "Act", "Title", "Status", "Human decisions"], rows)
                + f"<p class='muted'>{archived} act(s) archived as not relevant: see <a href='/feed'>Feed</a> for the "
                  f"reason of each.</p><h2>State machine</h2><p class='muted'>{e(graph)}</p>", refresh=5)


def _tests(suite) -> str:
    return "not run" if not suite else f"{suite['passed']} pass / {suite['failed'] + suite['errors']} fail"


def change(wait_id: str) -> str:
    w = store.wait(wait_id)
    if w is None or "change" not in w["payload"]:
        raise KeyError(wait_id)
    c, cls = w["payload"]["change"], {"+": "add", "-": "del"}
    diff = "\n".join(f"<span class='{cls.get(line[:1], '')}'>{e(line)}</span>" for line in c["diff"].splitlines())
    decision = (w["answer"] or {}).get("decision", "waiting for review")
    who = f" by {e(w['actor'])}" if w["actor"] else ""
    body = (f"<p>Branch <code>{e(c['branch'])}</code> · attempts {c['iterations']} · tests before "
            f"{_tests(c['tests_before'])} → after {_tests(c['tests_after'])} · review: {badge(decision)}{who}</p>"
            f"<div class='box warn'>{MERGE} To merge after approval, a human runs in the sandbox repository: "
            f"<code>git merge --no-ff {e(c['branch'])}</code></div><pre>{diff}</pre>"
            f"<p><a href='/runs/{e(w['run_id'])}'>Back to the run</a></p>")
    return page("Change for review", body)

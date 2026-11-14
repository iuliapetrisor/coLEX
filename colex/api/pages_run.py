"""One run: status, human controls, summary, branches and the timeline of agent steps."""
from __future__ import annotations

from html import escape as e
from typing import Any
from urllib.parse import quote

from colex.api.html import badge, evidence, law, page, post, table
from colex.api.pages_runs import MERGE
from colex.runtime import audit, store

LABEL = {"rationale": "reasoning", "impact": "finding", "step": "step done", "retry": "retry", "escalation": "escalated",
         "human": "human", "wait": "waiting", "notify": "message", "run": "run", "map": "map", "watch": "feed"}


def _wait_box(w: dict[str, Any]) -> str:
    p, act = w["payload"], f"/act/{quote(w['wait_id'], safe='')}"
    if w["kind"] == "review":
        change = p["change"]
        return (f"<div class='box warn'><b>Change waiting for an engineer's review</b> · branch <code>"
                f"{e(change['branch'])}</code> · <a href='/changes/{quote(w['wait_id'], safe='')}'>open the diff</a>"
                f"<br>{post(act, 'Approve', {'decision': 'approve'}, True)}"
                f"<form method='post' action='{act}'><input type='hidden' name='decision' value='request_changes'>"
                f"<input name='text' size='50' placeholder='What should change?'><button>Request changes</button>"
                f"</form><br><span class='muted'>{MERGE}</span></div>")
    q = p["question"]
    buttons = "".join(post(act, option, {"decision": option}) for option in q["options"])
    return (f"<div class='box warn'><b>Question for {e(q['to_team'])}</b> {e(p.get('channel', ''))}: {e(q['text'])}"
            f"<br>{buttons}<form method='post' action='{act}'><input name='text' size='50' "
            f"placeholder='Answer in detail'><button>Send</button></form></div>")


def _summary(s: dict[str, Any]) -> str:
    c = s.get("context") or {}
    ctx = "not measured"
    if c:
        ctx = (f"{c['context_tokens_used']} tokens read through the map · baseline A (whole corpus) "
               f"{c['baseline_a_whole_corpus_tokens']} → ratio {c['ratio_vs_a']} · baseline B (touched areas) "
               f"{c['baseline_b_touched_areas_tokens']} → ratio {c['ratio_vs_b']} · depth {c['navigation_depth']} · "
               f"fragments read {c['fragments_read']}/{c['fragments_total']}")
    changes = ", ".join(f"{x['branch']}: {x['decision']}, not merged" for x in s["change_requests"]) or "none"
    rows = [["Elapsed", f"{s['elapsed_s']} s"], ["Published → first notification", f"{s['to_first_notification_s']} s"],
            ["Published → first change request", f"{s['to_first_pr_s']} s"],
            ["Model tokens / cost", f"{s['tokens']} / ${s['cost_usd']}"], ["Items", e(str(s["items_by_action"]))],
            ["Context (a ratio above 1 means the map did not save context)", e(ctx)], ["Change requests", e(changes)]]
    return "<h2>Summary</h2>" + table(["Measure", "Value"], rows)


def _event(ev: dict[str, Any]) -> str:
    d, extra = ev["detail"], ""
    if d.get("breadcrumbs"):
        extra += f"<br><span class='muted'>{e(d.get('tool', ''))} · {e(d['breadcrumbs'])}</span>"
    if d.get("item"):
        i = d["item"]
        extra += ("<br>" + evidence(i["resource_uri"], i["lines"]["start"], i["lines"]["end"]) + " · "
                  + law(i["citation"]))
    if ev["checkpoint_id"]:
        cp = ev["checkpoint_id"]
        extra += (f"<br><span class='muted'>✓ checkpoint <code>{e(cp)}</code> · config "
                  f"{e(d.get('config_version_id', ''))}</span> {post(f'/checkpoints/{cp}/fork', 'Fork from here')} "
                  f"<a href='/checkpoints/{cp}/export'>export</a>")
    return (f"<div class='ev'><span class='muted'>{e(ev['ts'][11:19])}</span><span class='k'>"
            f"{e(LABEL.get(ev['kind'], ev['kind']))}<br><span class='muted'>{e(ev['agent'])}</span></span>"
            f"<span>{e(ev['summary'])}{extra}</span></div>")


def run(run_id: str) -> str:
    r = store.run_row(run_id)
    status = "paused" if r["paused"] else r["status"]
    toggle = post(f"/runs/{run_id}/resume", "Resume") if r["paused"] else post(f"/runs/{run_id}/pause", "Pause")
    head = (f"<p>CELEX <a href='/law/{quote(r['law_id'])}'>{e(r['law_id'])}</a> · {badge(status)} · map "
            f"<code>{e(r['map_version_id'] or '-')}</code> {toggle}</p><p class='muted'>{MERGE}</p>")
    if r["parent_checkpoint_id"]:
        head += f"<p class='muted'>Forked or imported from checkpoint <code>{e(r['parent_checkpoint_id'])}</code>.</p>"
    branches = table(["Branch", "Node", "Status"],
                     [[e(k), e(v["node"]), badge(v["status"])] for k, v in r["branches"].items()])
    waits = "".join(_wait_box(w) for w in store.waits(run_id, "pending"))
    done = store.step_row(run_id, "main:VERIFY")
    summary = _summary(store.get_blob(done["output_ref"])) if done else ""
    events = audit.events(run_id)
    shown = [_event(ev) for ev in events if ev["kind"] != "llm"]
    body = (head + waits + summary + "<h2>Branches</h2>" + branches
            + f"<h2>Timeline</h2><p class='muted'>{len(events) - len(shown)} model call(s) not listed.</p>"
            + "".join(shown))
    return page(f"Run {run_id}", body, refresh=0 if status in ("done", "failed", "cancelled", "paused") else 4)

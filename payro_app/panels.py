"""One panel per version of the code: a phone for the customer scenarios, a desk view for incidents.

Every value shown comes from running that version's code. Text written by that code (for example the
message of a stopped transfer) is escaped before it is shown.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as e
from typing import Any
from urllib.parse import urlencode

from payro_app.scenario import IBANS

NAME_RESULT = {"match": "the name matches the account", "close_match": "the name is close, but not the same",
               "no_match": "the name does NOT match the account", "unavailable": "the name could not be checked"}


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f} EUR"
    except (TypeError, ValueError):
        return "?"


def _head(v: dict[str, Any], res: dict[str, Any]) -> str:
    if v["ref"] in ("original", "main"):
        status, cls = v["title"], "live"
    elif v["merged"]:
        status, cls = "coLEX change · merged into main", "live"
    else:
        status, cls = "coLEX change · proposed, NOT merged", "draft"
    title = f"<br>{e(v['title'])}" if v["ref"] not in ("original", "main") else ""
    return (f"<div class='bar'>PayRo <span>FICTIONAL demo</span></div><div class='ver {cls}'><b>{e(v['ref'])}</b> "
            f"<code>{e(res.get('sha', '')[:8])}</code><br>{e(status)}{title}</div>")


def _broken(res: dict[str, Any], key: str) -> str | None:
    if res.get("error"):
        return str(res["error"])
    part = res.get(key)
    return str(part["error"]) if isinstance(part, dict) and part.get("error") else None


def phone(v: dict[str, Any], state: dict[str, str], res: dict[str, Any]) -> str:
    problem = _broken(res, "transfer") or _broken(res, "fees")
    if problem:
        return f"<div class='phone'>{_head(v, res)}<div class='out bad'>This version of the code failed: {e(problem)}</div></div>"
    eur, t, instant = res["fees"].get("eur", {}), res["transfer"], state["instant"] == "1"
    std, ins = eur.get("standard"), eur.get("instant")
    opts = "".join(f"<div class='opt{' sel' if chosen else ''}'>{label}<b>{money(fee)}</b></div>"
                   for label, fee, chosen in (("Standard · 1 day", std, not instant), ("Instant · seconds", ins, instant)))
    try:
        gap = float(ins) - float(std)
        compare = (f"<div class='cmp bad'>Instant costs {money(gap)} more than standard</div>" if gap > 0
                   else "<div class='cmp good'>Instant costs no more than standard</div>")
    except (TypeError, ValueError):
        compare = ""
    calls = res.get("network_calls", [])
    checks = []
    if not any(c["service"] == "name check" for c in calls):
        checks.append("<li class='bad'>Payee name: not checked by this version</li>")
    for c in calls:
        if c["service"] == "name check":
            ok = c.get("result") == "match"
            checks.append(f"<li class='{'good' if ok else 'bad'}'>Payee name checked first: "
                          f"{e(NAME_RESULT.get(c.get('result'), str(c.get('result'))))}</li>")
        elif c["service"] == "one-time password":
            checks.append("<li>One-time password checked</li>")
    if t["outcome"] == "authorized":
        r = t.get("result") or {}
        after = " after the customer confirmed the payee" if res.get("needed_confirmation") else ""
        out = (f"<div class='out good'><b>✓ Money sent{after}</b><br>Fee {money(r.get('fee', t.get('quote')))} · "
               f"Total {money(r.get('total'))}</div>")
    else:
        again = ""
        if state["confirmed"] != "1":
            link = urlencode({**state, "confirmed": "1"})
            again = f"<br><a class='btn' href='?{e(link)}'>I have checked the payee · send anyway</a>"
        out = f"<div class='out warn'><b>Stopped before sending</b><br>{e(t.get('message', ''))}{again}</div>"
    return (f"<div class='phone'>{_head(v, res)}<h3>Send money</h3>"
            f"<div class='row'><span>To</span>{e(state['name'])}</div>"
            f"<div class='row'><span>Account</span>{e(IBANS[state['iban']])}</div>"
            f"<div class='row'><span>Amount</span>{money(state['amount'])}</div>"
            f"<div class='opts'>{opts}</div>{compare}{out}"
            f"<div class='chk'>What this version checked, in order:<ul>{''.join(checks)}</ul></div></div>")


def desk(v: dict[str, Any], state: dict[str, str], res: dict[str, Any]) -> str:
    problem = _broken(res, "incident_plan")
    if problem:
        return f"<div class='phone'>{_head(v, res)}<div class='out bad'>This version of the code failed: {e(problem)}</div></div>"
    aware = datetime.fromisoformat(state["aware"])
    rows = ""
    for step in res["incident_plan"]:
        due = datetime.fromisoformat(step["due"])
        hours = (due - aware).total_seconds() / 3600
        after = f"{hours:.0f} h" if hours < 96 else f"{hours / 24:.0f} days"
        rows += (f"<div class='row'><span>{e(step['report'].capitalize())} report</span>"
                 f"{due:%d %b %Y, %H:%M}<small>{after} after awareness</small></div>")
    return (f"<div class='phone'>{_head(v, res)}<h3>Incident desk · reports due</h3>"
            f"<div class='row'><span>Noticed</span>{aware:%d %b %Y, %H:%M}</div>"
            f"<div class='row'><span>Classified major</span>{datetime.fromisoformat(state['classified']):%d %b %Y, %H:%M}"
            f"</div><div class='cmp {'good' if len(res['incident_plan']) >= 3 else 'bad'}'>"
            f"{len(res['incident_plan'])} report(s) planned by this version</div>{rows}</div>")

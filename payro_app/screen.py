"""The PayRo screen for one request: a phone for the customer scenarios, a desk view for incidents.

Every value shown comes from running the code that is checked out. Text written by that code (for
example the message of a stopped transfer) is escaped before it is shown.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as e
from typing import Any
from urllib.parse import urlencode

from payro_app.inputs import IBANS

NAME_RESULT = {"match": "the name matches the account", "close_match": "the name is close, but not the same",
               "no_match": "the name does NOT match the account", "unavailable": "the name could not be checked"}


def money(value: Any) -> str:
    try:
        return f"{float(value):.2f} EUR"
    except (TypeError, ValueError):
        return "?"


def _frame(title: str, body: str) -> str:
    return (f"<div class='phone'><div class='bar'>PayRo <span>FICTIONAL demo</span></div>"
            f"<h3>{e(title)}</h3>{body}</div>")


def _broken(res: dict[str, Any], *keys: str) -> str | None:
    if res.get("error"):
        return str(res["error"])
    for key in keys:
        part = res.get(key)
        if isinstance(part, dict) and part.get("error"):
            return str(part["error"])
    return None


def _failed(problem: str) -> str:
    return _frame("Something went wrong", f"<div class='out bad'>The code that is checked out failed: {e(problem)}</div>")


def phone(state: dict[str, str], res: dict[str, Any]) -> str:
    problem = _broken(res, "transfer", "fees")
    if problem:
        return _failed(problem)
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
        checks.append("<li class='bad'>Payee name: not checked</li>")
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
    return _frame("Send money",
                  f"<div class='row'><span>To</span>{e(state['name'])}</div>"
                  f"<div class='row'><span>Account</span>{e(IBANS[state['iban']])}</div>"
                  f"<div class='row'><span>Amount</span>{money(state['amount'])}</div>"
                  f"<div class='opts'>{opts}</div>{compare}{out}"
                  f"<div class='chk'>What the app did, in order:<ul>{''.join(checks)}</ul></div>")


def desk(state: dict[str, str], res: dict[str, Any]) -> str:
    problem = _broken(res, "incident_plan")
    if problem:
        return _failed(problem)
    aware = datetime.fromisoformat(state["aware"])
    rows = ""
    for step in res["incident_plan"]:
        due = datetime.fromisoformat(step["due"])
        hours = (due - aware).total_seconds() / 3600
        after = f"{hours:.0f} h" if hours < 96 else f"{hours / 24:.0f} days"
        rows += (f"<div class='row'><span>{e(step['report'].capitalize())} report</span>"
                 f"{due:%d %b %Y, %H:%M}<small>{after} after awareness</small></div>")
    count = len(res["incident_plan"])
    return _frame("Incident desk · reports due",
                  f"<div class='row'><span>Noticed</span>{aware:%d %b %Y, %H:%M}</div><div class='row'>"
                  f"<span>Classified major</span>{datetime.fromisoformat(state['classified']):%d %b %Y, %H:%M}</div>"
                  f"<div class='cmp {'good' if count >= 3 else 'bad'}'>{count} report(s) planned</div>{rows}")

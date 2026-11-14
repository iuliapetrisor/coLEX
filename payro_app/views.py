"""The page: scenario tabs, inputs, two versions of the PayRo code side by side, and the law behind the scenario."""
from __future__ import annotations

from html import escape as e
from typing import Any

from payro_app import panels, scenario
from payro_app.laws import NOTES
from payro_app.style import CSS, WHAT_IS_REAL

LEFT = [("main", "main (what customers get today)"), ("original", "original (before any change)")]


def shell(body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>PayRo demo app</title><style>{CSS}"
            f"</style></head><body><div class='top'><b>PayRo</b><small>{e(WHAT_IS_REAL)}</small></div>"
            f"<main>{body}</main></body></html>")


def _options(items: list[tuple[str, str]], chosen: str | None) -> str:
    return "".join(f"<option value='{e(v)}'{' selected' if v == chosen else ''}>{e(t)}</option>" for v, t in items)


def _controls(state: dict[str, str], versions: list[dict[str, Any]], left: str, right: str | None) -> str:
    tabs = "".join(f"<a class='{'on' if key == state['s'] else ''}' href='?s={key}'>{e(sc['tab'])}</a>"
                   for key, sc in scenario.SCENARIOS.items())
    branches = [(v["ref"], f"{v['ref']} ({', '.join(v['files'])})") for v in versions
                if v["ref"] not in ("original", "main")]
    fields = (f"<label>Left <select name='a'>{_options(LEFT, left)}</select></label>"
              f"<label>Right <select name='b'>{_options(branches, right)}</select></label><br>")
    if state["s"] == "incident":
        fields += (f"<label>Noticed <input type='datetime-local' name='aware' value='{e(state['aware'])}'></label>"
                   f"<label>Classified major <input type='datetime-local' name='classified' "
                   f"value='{e(state['classified'])}'></label>")
    else:
        speed = [("0", "Standard"), ("1", "Instant")]
        fields += (f"<label>Payee name <input name='name' value='{e(state['name'])}' size='18'></label>"
                   f"<label>Account <select name='iban'>{_options(list(scenario.IBANS.items()), state['iban'])}"
                   f"</select></label><label>EUR <input name='amount' value='{e(state['amount'])}' size='7'></label>"
                   f"<label>Speed <select name='instant'>{_options(speed, state['instant'])}</select></label>")
    return (f"<div class='tabs'>{tabs}</div><p>{e(scenario.SCENARIOS[state['s']]['story'])}</p>"
            f"<form class='in' method='get'><input type='hidden' name='s' value='{state['s']}'>{fields} "
            "<button>Try it</button></form>")


def _law(key: str) -> str:
    note = NOTES[key]
    quotes = "".join(f"<blockquote>{e(q)}</blockquote>" for q in note["quotes"])
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{note['celex']}"
    return (f"<div class='law'><b>The law behind this change</b><br>{e(note['where'])} · CELEX {note['celex']} · "
            f"<a href='{url}'>EUR-Lex</a>{quotes}<small>Quoted from the official text stored in coLEX's feed. In "
            f"plain words (our summary, not legal advice): {e(note['plain'])}</small></div>")


def page(repo, params: dict[str, str]) -> str:
    if not repo.exists():
        return shell(f"<p>No sandbox repository at <code>{e(str(repo.repo))}</code>. Run <code>make demo</code> or "
                     "<code>make console</code> first, then reload.</p>")
    versions = repo.versions()
    state = scenario.parse(params)
    left, right = scenario.pick(versions, state)
    state["a"], state["b"] = left, right or ""
    req = scenario.request(state)
    render = panels.desk if state["s"] == "incident" else panels.phone
    by_ref = {v["ref"]: v for v in versions}
    shown = ""
    for ref in (left, right):
        if not ref:
            continue
        res = repo.run(ref, req)
        if state.get("confirmed") == "1":   # would this version have stopped without the confirmation?
            plain = repo.run(ref, scenario.request({**state, "confirmed": "0"}))
            stopped = isinstance(plain.get("transfer"), dict) and plain["transfer"].get("outcome") == "stopped"
            res["needed_confirmation"] = stopped
        shown += render(by_ref[ref], state, res)
    file = scenario.SCENARIOS[state["s"]]["file"]
    if right is None:
        hint = (f"<div class='law'>No coLEX change to <code>{e(file)}</code> exists in this state, so there is "
                "nothing to compare yet.</div>")
    elif file not in by_ref[right]["files"]:
        hint = (f"<p class='note'>The branch on the right does not change <code>{e(file)}</code>, so both sides "
                "behave the same for this scenario. Pick another branch on the right.</p>")
    elif by_ref[right]["merged"]:
        hint = ("<p class='note'>This change is merged into main. Left: “original” is the code "
                "before any change; “main” now behaves like the right side.</p>")
    else:
        hint = ("<p class='note'>coLEX never merges. After an engineer approves, a human merges with:<br><code>git -C "
                f"{e(str(repo.repo))} -c user.name='Your Name' -c user.email='you@payro.example' merge --no-ff "
                f"--no-edit {e(right)}</code><br>The name matters: without it git records the repository's default "
                "identity, which is the coLEX agent. Reload this page afterwards: the "
                "left side (main) changes. Each coLEX change is its own branch from the original code, so this "
                "branch does not contain the other changes.</p>")
    return shell(_controls(state, versions, left, right) + f"<div class='pair'>{shown}</div>" + hint
                 + _law(state["s"]))

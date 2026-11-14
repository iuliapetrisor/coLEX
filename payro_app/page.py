"""The page: the PayRo screen, what the app is running (read from git), coLEX changes waiting for a merge, the law."""
from __future__ import annotations

from html import escape as e
from typing import Any

from payro_app import inputs, screen
from payro_app.laws import NOTES
from payro_app.style import CSS, WHAT_IS_REAL

SIGN = "-c user.name='Your Name' -c user.email='you@payro.example'"


def shell(body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>PayRo demo app</title><style>{CSS}"
            f"</style></head><body><div class='top'><b>PayRo</b><small>{e(WHAT_IS_REAL)}</small></div>"
            f"<main>{body}</main></body></html>")


def _options(items: list[tuple[str, str]], chosen: str | None) -> str:
    return "".join(f"<option value='{e(v)}'{' selected' if v == chosen else ''}>{e(t)}</option>" for v, t in items)


def _controls(state: dict[str, str]) -> str:
    tabs = "".join(f"<a class='{'on' if key == state['s'] else ''}' href='?s={key}'>{e(sc['tab'])}</a>"
                   for key, sc in inputs.SCENARIOS.items())
    if state["s"] == "incident":
        fields = (f"<label>Noticed <input type='datetime-local' name='aware' value='{e(state['aware'])}'></label>"
                  f"<label>Classified major <input type='datetime-local' name='classified' "
                  f"value='{e(state['classified'])}'></label>")
    else:
        speed = [("0", "Standard"), ("1", "Instant")]
        fields = (f"<label>Payee name <input name='name' value='{e(state['name'])}' size='18'></label>"
                  f"<label>Account <select name='iban'>{_options(list(inputs.IBANS.items()), state['iban'])}"
                  f"</select></label><label>EUR <input name='amount' value='{e(state['amount'])}' size='7'></label>"
                  f"<label>Speed <select name='instant'>{_options(speed, state['instant'])}</select></label>")
    return (f"<div class='tabs'>{tabs}</div><p>{e(inputs.SCENARIOS[state['s']]['story'])}</p>"
            f"<form class='in' method='get'><input type='hidden' name='s' value='{state['s']}'>{fields} "
            "<button>Try it</button></form>")


def _running(repo, head: dict[str, Any]) -> str:
    folder, warn = e(str(repo.repo)), ""
    if head["uncommitted"]:
        warn = (f"<div class='out warn'>{len(head['uncommitted'])} file(s) on disk differ from this commit "
                f"({e(', '.join(head['uncommitted'][:4]))}). The app runs the files on disk.</div>")
    return (f"<div class='law'><b>What this app is running</b><br>Folder <code>{folder}</code><br>Branch "
            f"<b>{e(head['branch'])}</b> · commit <code>{e(head['sha'][:8])}</code><br>“{e(head['subject'])}” · "
            f"committed by {e(head['who'])}, {e(head['when'])}{warn}<small>The code is loaded from this folder on "
            f"every request; nothing is copied or cached. Check it in a terminal:</small>"
            f"<code class='cmd'>git -C {folder} log --oneline -3</code></div>")


def _proposals(repo, items: list[dict[str, Any]]) -> str:
    rows = ""
    for p in (p for p in items if not p["merged"]):
        rows += (f"<div class='prop'><code>{e(p['branch'])}</code><br>{e(p['title'])}<small>{len(p['files'])} file(s), "
                 f"+{p['added']} −{p['removed']} lines: {e(', '.join(p['files']))}</small><code class='cmd'>git -C "
                 f"{e(str(repo.repo))} {SIGN} merge --no-ff --no-edit {e(p['branch'])}</code></div>")
    done = "".join(f"<li><code>{e(p['branch'])}</code> · {e(', '.join(p['files']))} · +{p['added']} −{p['removed']}</li>"
                   for p in items if p["merged"])
    return ("<div class='law'><b>coLEX changes waiting for a human to merge</b>"
            + (rows or "<div class='prop'>None.</div>")
            + "<small>coLEX cannot merge; it only opens a change request. Merge in a terminal under your own name, "
              "then reload this page.</small>"
            + (f"<div class='prop'><b>Already merged into this code</b><ul>{done}</ul></div>" if done else "") + "</div>")


def _history(branch: str, rows: list[dict[str, str]]) -> str:
    body = "".join(f"<tr><td><code>{e(r['sha'])}</code></td><td>{e(r['who'])}</td><td>{e(r['when'])}</td>"
                   f"<td>{e(r['subject'])}</td></tr>" for r in rows)
    return f"<div class='law'><b>Last commits on {e(branch)}</b><table class='log'>{body}</table></div>"


def _law(key: str) -> str:
    note = NOTES[key]
    quotes = "".join(f"<blockquote>{e(q)}</blockquote>" for q in note["quotes"])
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{note['celex']}"
    return (f"<div class='law'><b>The law behind this scenario</b><br>{e(note['where'])} · CELEX {note['celex']} · "
            f"<a href='{url}'>EUR-Lex</a>{quotes}<small>Quoted from the official text stored in coLEX's feed. In "
            f"plain words (our summary, not legal advice): {e(note['plain'])}</small></div>")


def render(repo, params: dict[str, str]) -> str:
    if not repo.exists():
        return shell(f"<p>No sandbox repository at <code>{e(str(repo.repo))}</code>. Run <code>make demo</code> or "
                     "<code>make console</code> first, then reload.</p>")
    head = repo.head()
    state = inputs.parse(params)
    res = repo.run(inputs.request(state))
    if state.get("confirmed") == "1":   # did this code need the confirmation? Run it once more without it.
        plain = repo.run(inputs.request({**state, "confirmed": "0"})).get("transfer")
        res["needed_confirmation"] = isinstance(plain, dict) and plain.get("outcome") == "stopped"
    view = (screen.desk if state["s"] == "incident" else screen.phone)(state, res)
    side = _running(repo, head) + _proposals(repo, repo.proposals()) + _history(head["branch"], repo.history())
    return shell(_controls(state) + f"<div class='cols'><div>{view}</div><div class='side'>{side}</div></div>"
                 + _law(state["s"]))

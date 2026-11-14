"""Andrei's phone: the PayRo screens for sending money. Nothing but the phone is on the page.

Text that comes from the checked-out code (the message of a stopped transfer) or from the form is escaped.
"""
from __future__ import annotations

from html import escape as e
from typing import Any
from urllib.parse import urlencode

from payro_app.bank import Bank, Payment
from payro_app.style import eur, iban_text, page

FIELDS = ("name", "iban", "amount", "speed")


def _phone(bank: Bank, body: str, kind: str = "") -> str:
    return page(f"<div class='phone'><div class='bar'><b>PayRo</b><span>{e(bank.sender)}</span></div>"
                f"<div class='bal'><small>EUR account</small><strong>{eur(bank.sender_balance())}</strong></div>"
                f"<div class='body {kind}'>{body}</div></div>")


def _row(p: Payment) -> str:
    return (f"<div class='item'><div>{e(p.name)}<small>{'Instant' if p.instant else 'Standard'} · {p.at:%H:%M:%S} · "
            f"fee {eur(p.fee)}</small></div><b>−{eur(p.total)}</b></div>")


def home(bank: Bank, fees: dict[str, Any], form: dict[str, str], error: str = "") -> str:
    """The form. `fees` is what the checked-out code charges right now."""
    def option(kind: str, title: str, when: str) -> str:
        try:
            fee = f"Fee {eur(float(fees[kind]))}"
        except (KeyError, TypeError, ValueError):
            fee = "Fee unavailable"
        checked = " checked" if form["speed"] == kind else ""
        return (f"<label class='opt'><input type='radio' name='speed' value='{kind}'{checked}><span>{title}"
                f"<small>{when}</small><b>{fee}</b></span></label>")

    recent = "".join(_row(p) for p in bank.payments()[:3])
    return _phone(bank, (
        "<h2>Send money</h2>" + (f"<div class='err'>{e(error)}</div>" if error else "")
        + "<form method='post' action='/send'>"
        + f"<label>To</label><input type='text' name='name' value='{e(form['name'])}' autocomplete='off'>"
        + f"<label>IBAN</label><input type='text' name='iban' value='{e(iban_text(form['iban']))}' autocomplete='off'>"
        + f"<label>Amount (EUR)</label><input type='text' inputmode='decimal' name='amount' "
          f"value='{e(form['amount'])}' autocomplete='off'>"
        + f"<div class='opts'>{option('standard', 'Standard', 'Next business day')}"
          f"{option('instant', 'Instant', 'Arrives in seconds')}</div><button>Send</button></form>"
        + (f"<div class='list'><h2>Recent</h2>{recent}</div>" if recent else "")))


def sent(bank: Bank, p: Payment) -> str:
    rows = (("To account", e(iban_text(p.iban))), ("Speed", "Instant" if p.instant else "Standard"),
            ("Fee", f"<b>{eur(p.fee)}</b>"), ("Total", f"<b>{eur(p.total)}</b>"))
    body = "".join(f"<div><span>{k}</span><span>{v}</span></div>" for k, v in rows)
    return _phone(bank, f"<div class='tick'>✓</div><h1>Money sent</h1><p>{eur(p.amount)} to {e(p.name)}</p>"
                        f"<div class='rows'>{body}</div><a class='btn' href='/'>Done</a>", "done")


def stopped(bank: Bank, form: dict[str, str], message: str) -> str:
    """The code refused the transfer. Its message is shown; the customer may go ahead or change the details."""
    hidden = "".join(f"<input type='hidden' name='{k}' value='{e(v)}'>"
                     for k, v in {**{k: form[k] for k in FIELDS}, "confirmed": "1"}.items())
    back = urlencode({k: form[k] for k in FIELDS})
    return _phone(bank, f"<div class='tick'>!</div><h1>Please check</h1><p>{e(message)}</p>"
                        f"<form method='post' action='/send'>{hidden}<button>Send anyway</button></form>"
                        f"<a class='btn alt' href='/?{e(back)}'>Change details</a>", "done warn")


def broken(bank: Bank, problem: str) -> str:
    return _phone(bank, "<div class='tick'>!</div><h1>Something went wrong</h1><p>No money was sent. Please try "
                        f"again.</p><small>{e(problem)}</small><a class='btn alt' href='/'>Back</a>", "done warn")


def setup(path: str) -> str:
    return page("<div class='phone'><div class='bar'><b>PayRo</b><span></span></div><div class='body done'>"
                f"<h1>Not set up yet</h1><p>There is no PayRo code at {e(path)}. Run <b>make demo</b> or "
                "<b>make console</b> first, then reload.</p></div></div>")

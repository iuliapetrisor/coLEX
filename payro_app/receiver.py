"""Maria's phone: the PayRo screen of the person who is paid. It reloads by itself, so money appears as it arrives."""
from __future__ import annotations

from html import escape as e

from payro_app.bank import Bank, Payment
from payro_app.style import eur, page

REFRESH_SECONDS = 2


def _row(bank: Bank, p: Payment) -> str:
    if p.instant:
        return (f"<div class='item'><div>{e(bank.sender)}<small>Instant transfer · {p.at:%H:%M:%S}</small></div>"
                f"<b class='in'>+{eur(p.amount)}</b></div>")
    return (f"<div class='item'><div>{e(bank.sender)}<small>Standard transfer · arrives next business day</small>"
            f"</div><b class='wait'>{eur(p.amount)}</b></div>")


def screen(bank: Bank) -> str:
    got = bank.received()
    latest = next((p for p in got if p.instant), None)
    banner = (f"<div class='new'>Money received<b>+{eur(latest.amount)}</b>from {e(bank.sender)} · "
              f"{latest.at:%H:%M:%S}</div>") if latest else ""
    rows = "".join(_row(bank, p) for p in got[:5]) or "<div class='item'><small>No transactions yet.</small></div>"
    return page(f"<div class='phone'><div class='bar'><b>PayRo</b><span>{e(bank.receiver)}</span></div>"
                f"<div class='bal'><small>EUR account</small><strong>{eur(bank.receiver_balance())}</strong></div>"
                f"<div class='body'>{banner}<div class='list' style='margin-top:0'><h2>Recent</h2>{rows}</div></div>"
                "</div>", refresh=REFRESH_SECONDS)

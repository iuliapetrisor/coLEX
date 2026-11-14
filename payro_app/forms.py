"""What the sender typed: defaults for the form, and checks before anything is sent to the PayRo code."""
from __future__ import annotations

from payro_app.bank import MARIA

DEFAULTS = {"name": "Maria Popescu", "iban": MARIA, "amount": "100.00", "speed": "instant"}
MAX_AMOUNT = 1_000_000


def _tidy(raw: dict[str, str]) -> dict[str, str]:
    return {"name": " ".join(raw.get("name", "").split())[:70],
            "iban": "".join(raw.get("iban", "").split()).upper()[:34],
            "amount": raw.get("amount", "").strip().replace(",", ".")[:14],
            "speed": "standard" if raw.get("speed") == "standard" else "instant",
            "confirmed": "1" if raw.get("confirmed") == "1" else "0"}


def prefill(params: dict[str, str]) -> dict[str, str]:
    """The form as first shown: defaults, or the values of a transfer the customer went back to change."""
    return _tidy({**DEFAULTS, **{k: v for k, v in params.items() if k in DEFAULTS}})


def clean(raw: dict[str, str]) -> tuple[dict[str, str], str]:
    """(the form, an error message for the customer or "")."""
    form = _tidy(raw)
    if not form["name"]:
        return form, "Enter the name of the person you are paying."
    if not (form["iban"].isascii() and form["iban"].isalnum() and len(form["iban"]) >= 15):
        return form, "Enter a valid IBAN."
    try:
        amount = float(form["amount"])
    except ValueError:
        amount = 0.0
    if not 0 < amount <= MAX_AMOUNT:   # also false for "nan"
        return form, "Enter an amount."
    form["amount"] = f"{amount:.2f}"
    return form, ""

"""The three demo scenarios, their inputs, and the simulated outside world (all fictional)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Simulated bank directory: who holds which account. Published example IBANs, invented names.
RO, DE, UNKNOWN = "RO49AAAA1B31007593840000", "DE89370400440532013000", "RO00TEST0000000000000000"
DIRECTORY = {RO: "Maria Popescu", DE: "Hans Becker"}
IBANS = {RO: "RO49 AAAA … 0000", DE: "DE89 3704 … 3000", UNKNOWN: "RO00 TEST … (bank cannot be reached)"}
VALID_OTP = "123456"

SCENARIOS: dict[str, dict[str, Any]] = {
    "fees": {"tab": "Instant transfer fee", "file": "payments/fees.yaml",
             "story": "Maria is sent 100 EUR as an instant transfer. What does the customer pay?",
             "defaults": {"name": "Maria Popescu", "iban": RO, "amount": "100", "instant": "1"}},
    "payee": {"tab": "Wrong payee name", "file": "payments/transfer.py",
              "story": "The customer types the name “Mihai Popa”, but the account belongs to Maria Popescu.",
              "defaults": {"name": "Mihai Popa", "iban": RO, "amount": "250", "instant": "0"}},
    "incident": {"tab": "Incident reporting plan (staff view)", "file": "payments/incidents.py",
                 "story": "A major ICT incident: noticed at 10:00, classified as major at 12:00.",
                 "defaults": {"aware": "2025-03-03T10:00", "classified": "2025-03-03T12:00"}},
}


def _time(value: str, fallback: str) -> str:
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        return fallback


def parse(params: dict[str, str]) -> dict[str, str]:
    """Validated page state from the query string. Anything invalid falls back to the scenario default."""
    s = params.get("s") if params.get("s") in SCENARIOS else "fees"
    d = SCENARIOS[s]["defaults"]
    state = {"s": s, "a": params.get("a", ""), "b": params.get("b", "")}
    if s == "incident":
        state["aware"] = _time(params.get("aware", ""), d["aware"])
        state["classified"] = _time(params.get("classified", ""), d["classified"])
        if state["classified"] < state["aware"]:
            state["classified"] = state["aware"]
        return state
    try:
        amount = float(params.get("amount", d["amount"]))
        amount = amount if 0 < amount <= 100000 else float(d["amount"])
    except ValueError:
        amount = float(d["amount"])
    state.update(name=(params.get("name", d["name"]).strip() or d["name"])[:60],
                 iban=params.get("iban") if params.get("iban") in IBANS else d["iban"],
                 amount=f"{amount:.2f}", instant="1" if params.get("instant", d["instant"]) == "1" else "0",
                 confirmed="1" if params.get("confirmed") == "1" else "0")
    return state


def request(state: dict[str, str]) -> dict[str, Any]:
    """What the driver receives. The customer always enters the correct one-time password."""
    req: dict[str, Any] = {"directory": DIRECTORY, "valid_otp": VALID_OTP, "otp": VALID_OTP,
                           "incident": {"aware": state.get("aware", "2025-03-03T10:00"),
                                        "classified": state.get("classified", "2025-03-03T12:00")}}
    if state["s"] != "incident":
        req["transfer"] = {"payer_account": "ACC-1", "payee_iban": state["iban"], "payee_name": state["name"],
                           "amount": float(state["amount"]), "currency": "EUR", "instant": state["instant"] == "1",
                           "own_account": False, "payee_confirmed": state["confirmed"] == "1"}
    else:   # the driver still needs a transfer to report fees; it is not shown in the staff view
        req["transfer"] = {"payer_account": "ACC-1", "payee_iban": RO, "payee_name": DIRECTORY[RO], "amount": 1.0,
                           "currency": "EUR", "instant": False, "own_account": False, "payee_confirmed": False}
    return req


def pick(versions: list[dict[str, Any]], state: dict[str, str]) -> tuple[str, str | None]:
    """Right = the asked coLEX branch, else the newest one that changes this scenario's file, else nothing.
    Left = what was asked; by default 'main', or 'original' when the change on the right is already merged
    (after a merge, main and the branch behave the same, so the comparison needs the code before it)."""
    by_ref = {v["ref"]: v for v in versions}
    right = state["b"] if state["b"] in by_ref and state["b"] not in ("original", "main") else None
    if right is None:
        wanted = SCENARIOS[state["s"]]["file"]
        right = next((v["ref"] for v in versions if wanted in v["files"]), None)
    if state["a"] in ("original", "main"):
        return state["a"], right
    return ("original" if right and by_ref[right]["merged"] else "main"), right

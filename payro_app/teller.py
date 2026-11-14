"""Runs INSIDE the PayRo repository folder, at whatever commit is checked out there.

Reads a JSON request on stdin, calls the real `payments` code and prints a JSON answer as the last line.
Only the outside world is simulated: the provider network (`providers._post`) answers a name check from a
small bank directory, accepts one fixed one-time password and records ledger entries. Fees and transfer
rules are not touched: they are whatever the checked-out code says.
"""
import dataclasses
import difflib
import json
import os
import sys

sys.path[0] = os.getcwd()   # import `payments` from the repository folder, nothing from the demo app's folder
req = json.load(sys.stdin)
out = {"booked": []}


def name_check(iban, name):
    holder = req["directory"].get(str(iban))
    if holder is None:
        return "unavailable"
    given, real = " ".join(str(name).lower().split()), holder.lower()
    if given == real:
        return "match"
    return "close_match" if difflib.SequenceMatcher(None, given, real).ratio() >= 0.8 else "no_match"


def fake_post(url, payload):
    """Stands in for the network of PayRo's providers."""
    if "namematch" in url:
        return {"result": name_check(payload.get("iban"), payload.get("name"))}
    if "smsnord" in url and url.endswith("/check"):
        return {"valid": payload.get("otp") == req["valid_otp"]}
    if "ledgercore" in url:
        out["booked"].append({"to": str(payload.get("to")), "amount": float(payload.get("amount", 0))})
        return {"entry_id": f"LC-{len(out['booked'])}"}
    return {}


def quote():
    from payments.fees import fee_for
    return {"standard": fee_for("EUR", False), "instant": fee_for("EUR", True)}


def send():
    from payments import providers
    from payments import transfer as t
    known = {f.name for f in dataclasses.fields(t.Transfer)}
    wanted = t.Transfer(**{k: v for k, v in req["transfer"].items() if k in known})
    try:
        result = t.authorize_transfer(wanted, req["otp"])
    except t.TransferError as exc:   # the code refused; its message is what the customer sees
        return {"outcome": "stopped", "message": str(exc)}
    if float(result["total"]) > float(req["balance"]):
        return {"outcome": "no_funds"}
    providers.book_transfer(wanted.payer_account, wanted.payee_iban, wanted.amount, wanted.currency)
    return {"outcome": "sent", "fee": float(result["fee"]), "total": float(result["total"])}


try:
    from payments import providers
    providers._post = fake_post   # before payments.transfer is used, so every code path sees it
    out["result"] = {"quote": quote, "send": send}[req["action"]]()
except Exception as exc:
    out["error"] = f"{type(exc).__name__}: {exc}"
print("\n" + json.dumps(out, default=str))

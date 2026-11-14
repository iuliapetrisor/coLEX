"""Runs INSIDE the PayRo repository: the working directory is the repository folder, at whatever commit is checked out.

Reads a JSON request on stdin, calls the real `payments` code of that version and prints a JSON result.
Only the outside world is simulated: the provider network (`providers._post`) answers from a small
fictional bank directory and accepts one fixed one-time password. Fees and transfer logic are not touched.
"""
import dataclasses
import difflib
import json
import os
import sys
from datetime import datetime

sys.path[0] = os.getcwd()   # import `payments` from this version, nothing from the demo app's folder
req = json.load(sys.stdin)
out = {"network_calls": []}


def name_check(iban, name):
    holder = req["directory"].get(str(iban))
    if holder is None:
        return "unavailable"
    given, real = " ".join(str(name).lower().split()), holder.lower()
    if given == real:
        return "match"
    return "close_match" if difflib.SequenceMatcher(None, given, real).ratio() >= 0.8 else "no_match"


def fake_post(url, payload):
    """Stands in for the network. Records each call in order, so the page can show what was checked and when."""
    if "namematch" in url:
        result = name_check(payload.get("iban"), payload.get("name"))
        out["network_calls"].append({"service": "name check", "result": result})
        return {"result": result}
    if "smsnord" in url and url.endswith("/check"):
        out["network_calls"].append({"service": "one-time password"})
        return {"valid": payload.get("otp") == req["valid_otp"]}
    out["network_calls"].append({"service": "other", "url": str(url)[:80]})
    return {}


def fees():
    from payments.fees import load_fees
    return load_fees()


def transfer():
    from payments import transfer as t
    from payments.fees import fee_for
    known = {f.name for f in dataclasses.fields(t.Transfer)}
    wanted = t.Transfer(**{k: v for k, v in req["transfer"].items() if k in known})
    quote = fee_for(wanted.currency, wanted.instant)
    try:
        return {"outcome": "authorized", "quote": quote, "result": t.authorize_transfer(wanted, req["otp"])}
    except t.TransferError as exc:
        return {"outcome": "stopped", "quote": quote, "message": str(exc)}


def incident_plan():
    from payments import incidents
    aware = datetime.fromisoformat(req["incident"]["aware"])
    classified = datetime.fromisoformat(req["incident"]["classified"])
    return [{"report": str(step["report"]), "due": step["due"].isoformat()}
            for step in incidents.reporting_plan(aware, classified)]


try:
    from payments import providers
    providers._post = fake_post   # before payments.transfer is imported, so every code path sees it
except Exception as exc:
    out["error"] = f"{type(exc).__name__}: {exc}"
else:
    for name, fn in (("fees", fees), ("transfer", transfer), ("incident_plan", incident_plan)):
        try:
            out[name] = fn()
        except Exception as exc:   # one broken part must not hide the others
            out[name] = {"error": f"{type(exc).__name__}: {exc}"}
print(json.dumps(out, default=str))

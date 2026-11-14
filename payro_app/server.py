"""`make payro`: two phones of the PayRo demo app.

    http://127.0.0.1:8001   the sender's phone (Andrei): send money
    http://127.0.0.1:8002   the receiver's phone (Maria): money arriving

The sender's phone runs the PayRo code checked out in the sandbox repository of the demo state, on every
request, so its fees and rules change when a branch is merged there. Balances and payments are simulated
and kept in memory. No login, local only. It never writes to the repository or to the coLEX database.
"""
from __future__ import annotations

import asyncio
import os
import threading
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from colex import settings
from payro_app import forms, receiver, sender
from payro_app.bank import VALID_OTP, Bank
from payro_app.checkout import Checkout

HOST = "127.0.0.1"
MAX_BODY = 10_000


def _html(body: str) -> HTMLResponse:
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


def create_apps(checkout: Checkout, bank: Bank) -> tuple[FastAPI, FastAPI]:
    """(the sender's app, the receiver's app). They share one bank."""
    lock = threading.Lock()
    sender_app = FastAPI(title="PayRo", docs_url=None, redoc_url=None, openapi_url=None)
    receiver_app = FastAPI(title="PayRo", docs_url=None, redoc_url=None, openapi_url=None)
    world = {"directory": bank.directory, "valid_otp": VALID_OTP, "otp": VALID_OTP}

    def fees() -> dict:
        res = checkout.run({**world, "action": "quote"})
        result = res.get("result")
        return result if isinstance(result, dict) and not res.get("error") else {}

    def send(form: dict[str, str]) -> tuple[str, int | None]:
        """Ask the checked-out code to authorise and book the transfer. Returns (a page, or the payment number)."""
        with lock:
            transfer = {"payer_account": bank.sender_account, "payee_iban": form["iban"], "payee_name": form["name"],
                        "amount": float(form["amount"]), "currency": "EUR", "instant": form["speed"] == "instant",
                        "own_account": False, "payee_confirmed": form["confirmed"] == "1"}
            res = checkout.run({**world, "action": "send", "balance": bank.sender_balance(), "transfer": transfer})
            result, booked = res.get("result"), res.get("booked") or []
            if res.get("error") or not isinstance(result, dict):
                return sender.broken(bank, str(res.get("error", "no answer"))), None
            if result.get("outcome") == "stopped":
                return sender.stopped(bank, form, str(result.get("message", ""))), None
            if result.get("outcome") == "no_funds":
                return sender.home(bank, fees(), form, "Not enough money in your account."), None
            try:   # money moves only when the code booked exactly one ledger entry
                (entry,) = booked
                payment = bank.record(form["name"], str(entry["to"]), float(entry["amount"]), float(result["fee"]),
                                      float(result["total"]), transfer["instant"])
            except (KeyError, TypeError, ValueError):
                return sender.broken(bank, "the transfer was not booked"), None
            return "", payment.n

    @sender_app.get("/")
    def home(request: Request):
        if not checkout.exists():
            return _html(sender.setup(str(checkout.repo)))
        return _html(sender.home(bank, fees(), forms.prefill(dict(request.query_params))))

    @sender_app.post("/send")
    async def post_send(request: Request):
        if not checkout.exists():
            return _html(sender.setup(str(checkout.repo)))
        body = (await request.body())[:MAX_BODY].decode("utf-8", "replace")
        form, error = forms.clean({k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()})
        if error:
            return _html(await asyncio.to_thread(lambda: sender.home(bank, fees(), form, error)))
        page, number = await asyncio.to_thread(send, form)
        # redirect after a successful send, so reloading the page never sends the money twice
        return RedirectResponse(f"/sent/{number}", status_code=303) if number else _html(page)

    @sender_app.get("/sent/{number}")
    def sent(number: int):
        payment = bank.get(number)
        return _html(sender.sent(bank, payment)) if payment else RedirectResponse("/", status_code=303)

    @receiver_app.get("/")
    def received():
        return _html(receiver.screen(bank))

    return sender_app, receiver_app


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PAYRO_PORT", "8001"))
    receiver_port = int(os.environ.get("PAYRO_RECEIVER_PORT", str(port + 1)))
    checkout = Checkout(settings.var_dir() / "repo")
    sender_app, receiver_app = create_apps(checkout, Bank())
    print(f"PayRo demo app · sender's phone:   http://{HOST}:{port}\n"
          f"               · receiver's phone: http://{HOST}:{receiver_port}\n"
          f"Runs the code checked out in {checkout.repo}", flush=True)
    second = uvicorn.Server(uvicorn.Config(receiver_app, host=HOST, port=receiver_port, log_level="warning"))
    threading.Thread(target=second.run, daemon=True).start()   # ends with the main server
    uvicorn.run(sender_app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()

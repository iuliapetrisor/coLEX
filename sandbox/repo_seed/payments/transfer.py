"""FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo.

Authorisation of customer transfers.
"""
from __future__ import annotations

from dataclasses import dataclass

from payments import providers
from payments.fees import fee_for


class TransferError(Exception):
    """The transfer cannot be authorised; the message is shown to the customer."""


@dataclass
class Transfer:
    payer_account: str
    payee_iban: str
    payee_name: str
    amount: float
    currency: str
    instant: bool = False
    own_account: bool = False
    payee_confirmed: bool = False


def validate(transfer: Transfer) -> None:
    if transfer.amount <= 0:
        raise TransferError("The amount must be positive.")
    if transfer.currency not in ("RON", "EUR"):
        raise TransferError("Only RON and EUR transfers are supported.")
    if not transfer.payee_iban:
        raise TransferError("The payee IBAN is missing.")


def authorize_transfer(transfer: Transfer, otp: str) -> dict:
    """Authorise a transfer: validate it, check the one-time password, compute the fee."""
    validate(transfer)
    if not transfer.own_account and not providers.check_otp(transfer.payer_account, otp):
        raise TransferError("The one-time password is not valid.")
    fee = 0.0 if transfer.own_account else fee_for(transfer.currency, transfer.instant)
    return {"status": "authorized", "fee": fee, "total": round(transfer.amount + fee, 2)}

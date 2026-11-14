"""The simulated outside world of the PayRo demo app: two customers, their balances and the payments between them.

Kept in memory, so it starts fresh every time the app starts. All names and accounts are invented.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

MARIA, HANS = "RO49AAAA1B31007593840000", "DE89370400440532013000"
VALID_OTP = "123456"


@dataclass(frozen=True)
class Payment:
    n: int
    name: str        # the payee name the sender typed
    iban: str
    amount: float
    fee: float
    total: float
    instant: bool
    at: datetime


class Bank:
    sender, sender_account = "Andrei Ionescu", "ACC-1"
    receiver, receiver_iban = "Maria Popescu", MARIA
    directory = {MARIA: "Maria Popescu", HANS: "Hans Becker"}   # who holds which account (for the name check)

    def __init__(self, sender_opening: float = 2500.0, receiver_opening: float = 320.0) -> None:
        self._lock = threading.Lock()
        self._payments: list[Payment] = []
        self._sender_opening, self._receiver_opening = sender_opening, receiver_opening

    def record(self, name: str, iban: str, amount: float, fee: float, total: float, instant: bool) -> Payment:
        with self._lock:
            payment = Payment(len(self._payments) + 1, name, iban, round(amount, 2), round(fee, 2), round(total, 2),
                              instant, datetime.now())
            self._payments.append(payment)
            return payment

    def payments(self) -> list[Payment]:
        """Everything the sender sent, newest first."""
        with self._lock:
            return list(reversed(self._payments))

    def get(self, n: int) -> Payment | None:
        return next((p for p in self.payments() if p.n == n), None)

    def sender_balance(self) -> float:
        return round(self._sender_opening - sum(p.total for p in self.payments()), 2)

    def received(self) -> list[Payment]:
        """Payments to the receiver's account, newest first. The money follows the IBAN, not the typed name."""
        return [p for p in self.payments() if p.iban == self.receiver_iban]

    def receiver_balance(self) -> float:
        """Instant payments are credited at once; standard ones arrive the next business day."""
        return round(self._receiver_opening + sum(p.amount for p in self.received() if p.instant), 2)

"""FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo.

Calls to third-party ICT providers. Network access goes through `_post`, which tests replace.
"""
from __future__ import annotations

AWS_REGION = "eu-central-1"
DOCS_BUCKET_URL = "https://payro-docs.s3.eu-central-1.amazonaws.com"  # AWS S3 document storage
SMS_API = "https://api.smsnord.example/v1"            # SMSNord one-time passwords
KYC_API = "https://api.verifid.example/v2/verify"     # VerifID identity verification
LEDGER_API = "https://api.ledgercore.example/v3"      # LedgerCore core ledger
CARD_API = "https://gateway.cardaxis.example/topup"   # CardAxis card top-ups
NAMECHECK_API = "https://sandbox.namematch.example/v1/check"  # NameMatch pilot


def _post(url: str, payload: dict) -> dict:
    raise RuntimeError("network access is disabled in the sandbox")


def send_otp(phone: str) -> bool:
    return bool(_post(f"{SMS_API}/otp", {"phone": phone}).get("sent"))


def check_otp(account: str, otp: str) -> bool:
    return bool(_post(f"{SMS_API}/check", {"account": account, "otp": otp}).get("valid"))


def verify_identity(name: str, cnp: str) -> bool:
    return bool(_post(KYC_API, {"name": name, "cnp": cnp}).get("verified"))


def verify_payee(iban: str, name: str) -> str:
    """Ask the name-check service whether `name` matches the holder of `iban`.

    Returns "match", "close_match", "no_match" or "unavailable".
    """
    try:
        return str(_post(NAMECHECK_API, {"iban": iban, "name": name}).get("result", "unavailable"))
    except RuntimeError:
        return "unavailable"


def store_document(key: str, body: bytes) -> str:
    _post(f"{DOCS_BUCKET_URL}/{key}", {"size": len(body)})
    return f"{DOCS_BUCKET_URL}/{key}"


def book_transfer(payer_account: str, payee_iban: str, amount: float, currency: str) -> str:
    return str(_post(f"{LEDGER_API}/entries", {"from": payer_account, "to": payee_iban, "amount": amount,
                                               "currency": currency}).get("entry_id", ""))

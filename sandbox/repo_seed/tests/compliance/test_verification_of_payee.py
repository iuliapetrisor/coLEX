"""FICTIONAL – PayRo SRL demo. Compliance test.

Regulation (EU) 2024/886, Article 5c inserted into Regulation (EU) No 260/2012: the payee is verified
before the payer can authorise a euro credit transfer (5c(1)); the payer is told about a mismatch;
the check does not prevent the payer from authorising (5c(5)).
"""
import pytest

from payments import providers
from payments.transfer import Transfer, TransferError, authorize_transfer

IBAN = "RO49AAAA1B31007593840000"


def _euro(**kw):
    return Transfer("ACC-1", IBAN, "Ana Pop", 100.0, "EUR", **kw)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(providers, "check_otp", lambda account, otp: seen.append("otp") or True)
    return seen


def _payee_check(monkeypatch, calls, result):
    monkeypatch.setattr(providers, "verify_payee", lambda iban, name: calls.append("payee") or result)


def test_payee_is_verified_before_the_one_time_password(monkeypatch, calls):
    _payee_check(monkeypatch, calls, "match")
    assert authorize_transfer(_euro(), "123456")["status"] == "authorized"
    assert calls == ["payee", "otp"]


@pytest.mark.parametrize("result", ["no_match", "close_match", "unavailable"])
def test_payer_must_be_told_when_the_name_is_not_confirmed(monkeypatch, calls, result):
    _payee_check(monkeypatch, calls, result)
    with pytest.raises(TransferError):
        authorize_transfer(_euro(), "123456")
    assert "otp" not in calls


@pytest.mark.parametrize("result", ["no_match", "unavailable"])
def test_payer_who_confirms_can_still_authorise(monkeypatch, calls, result):
    _payee_check(monkeypatch, calls, result)
    assert authorize_transfer(_euro(payee_confirmed=True), "123456")["status"] == "authorized"

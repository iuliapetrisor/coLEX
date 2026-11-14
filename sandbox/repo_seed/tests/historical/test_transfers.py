"""FICTIONAL – PayRo SRL demo. Historical behaviour that must keep working after any change."""
import pytest

from payments import providers
from payments.transfer import Transfer, TransferError, authorize_transfer


@pytest.fixture(autouse=True)
def providers_ok(monkeypatch):
    monkeypatch.setattr(providers, "check_otp", lambda account, otp: otp == "123456")
    monkeypatch.setattr(providers, "verify_payee", lambda iban, name: "match")


def test_ron_transfer_is_authorised_with_a_valid_otp():
    t = Transfer("ACC-1", "RO49AAAA1B31007593840000", "Ana Pop", 100.0, "RON")
    assert authorize_transfer(t, "123456") == {"status": "authorized", "fee": 0.0, "total": 100.0}


def test_wrong_otp_is_rejected():
    t = Transfer("ACC-1", "RO49AAAA1B31007593840000", "Ana Pop", 100.0, "RON")
    with pytest.raises(TransferError):
        authorize_transfer(t, "000000")


def test_invalid_amount_and_currency_are_rejected():
    with pytest.raises(TransferError):
        authorize_transfer(Transfer("ACC-1", "RO49AAAA1B31007593840000", "Ana Pop", 0, "RON"), "123456")
    with pytest.raises(TransferError):
        authorize_transfer(Transfer("ACC-1", "RO49AAAA1B31007593840000", "Ana Pop", 5, "USD"), "123456")


def test_own_account_transfer_needs_no_otp_and_no_external_check(monkeypatch):
    """Terms and Conditions §4: transfers between a customer's own accounts run without additional checks."""
    def forbidden(*args):
        raise AssertionError("no provider may be called for an own-account transfer")
    monkeypatch.setattr(providers, "check_otp", forbidden)
    monkeypatch.setattr(providers, "verify_payee", forbidden)
    t = Transfer("ACC-1", "RO49AAAA1B31007593840000", "Ana Pop", 250.0, "EUR", instant=True, own_account=True)
    assert authorize_transfer(t, "") == {"status": "authorized", "fee": 0.0, "total": 250.0}

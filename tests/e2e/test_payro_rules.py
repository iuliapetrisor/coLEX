"""PayRo demo app: a transfer the code refuses, bad input, and code that fails. No money moves in those cases."""
from __future__ import annotations

from fastapi.testclient import TestClient

from payro_app.bank import Bank
from payro_app.checkout import Checkout
from payro_app.server import create_apps
from tests.e2e.conftest import payro_branch, payro_merge
from tests.e2e.test_payro_app import MARIA

WRONG_NAME = {**MARIA, "name": "Mihai Popa", "amount": "250"}


def test_wrong_payee_name_is_stopped_only_after_the_change_is_merged(payro):
    assert "Money sent" in payro.sender.post("/send", data=WRONG_NAME).text      # today: nothing checks the name
    assert "+250.00 EUR" in payro.receiver.get("/").text                         # the money follows the IBAN

    payro_merge(payro.git, payro.vop)

    stopped = payro.sender.post("/send", data=WRONG_NAME)
    assert stopped.url.path == "/send" and "Please check" in stopped.text
    assert "The payee name does not match this account." in stopped.text         # the message of the merged code
    assert "Send anyway" in stopped.text and "name=Mihai+Popa" in stopped.text   # go ahead, or change the details
    assert len(payro.bank.payments()) == 1 and "2,248.50 EUR" in stopped.text    # no money moved

    done = payro.sender.post("/send", data={**WRONG_NAME, "confirmed": "1"}).text
    assert "Money sent" in done and len(payro.bank.payments()) == 2
    assert "Money sent" in payro.sender.post("/send", data=MARIA).text           # the right name: no question asked


def test_bad_input_and_an_empty_account_send_nothing(payro):
    for change, message in (({"name": " "}, "Enter the name"), ({"iban": "x"}, "Enter a valid IBAN"),
                            ({"amount": "abc"}, "Enter an amount"), ({"amount": "-5"}, "Enter an amount"),
                            ({"amount": "nan"}, "Enter an amount"), ({"amount": "999999"}, "Not enough money")):
        page = payro.sender.post("/send", data={**MARIA, **change})
        assert page.status_code == 200 and message in page.text and "Send money" in page.text
    assert payro.sender.post("/send", content=b"\xff\xfe=%zz&&").status_code == 200
    assert payro.bank.payments() == [] and payro.sender.get("/sent/7").url.path == "/"


def test_text_typed_by_the_customer_or_written_by_the_code_is_never_html(payro):
    tag = "<script>alert(1)</script>"
    pages = [payro.sender.post("/send", data={**MARIA, "name": tag}).text, payro.sender.get("/").text,
             payro.sender.get("/", params={"name": tag, "iban": tag, "amount": tag}).text]
    payro_merge(payro.git, payro_branch(payro.git, "xss", "payments/transfer.py", "    validate(transfer)\n",
                                        '    raise TransferError("<img src=x onerror=alert(1)>")\n'))
    pages.append(payro.sender.post("/send", data=MARIA).text)
    assert "&lt;img src=x" in pages[-1]
    for page in pages + [payro.receiver.get("/").text]:
        assert "<script>" not in page and "<img" not in page


def test_code_that_fails_sends_nothing_and_a_missing_repository_is_explained(payro, tmp_path):
    payro_merge(payro.git, payro_branch(payro.git, "broken", "payments/fees.py", "from pathlib import Path\n",
                                        "import does_not_exist\n"))
    assert "Fee unavailable" in payro.sender.get("/").text
    page = payro.sender.post("/send", data=MARIA).text
    assert "Something went wrong" in page and "No money was sent" in page and payro.bank.payments() == []
    missing, _ = create_apps(Checkout(tmp_path / "missing"), Bank())
    assert "Not set up yet" in TestClient(missing).get("/").text
    assert "Not set up yet" in TestClient(missing).post("/send", data=MARIA).text

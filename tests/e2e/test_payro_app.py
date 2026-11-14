"""PayRo demo app: only a phone on the page, money really moves to the receiver's phone, and the fee shown
is the one of the code checked out in the repository (so a human merge changes it without a restart)."""
from __future__ import annotations

from tests.e2e.conftest import payro_merge

MARIA = {"name": "Maria Popescu", "iban": "RO49 AAAA 1B31 0075 9384 0000", "amount": "100", "speed": "instant"}
NOT_ON_THE_PAGE = ("FICTIONAL", "fictional", "What the app did", "One-time password", "coLEX", "git -C", "EUR-Lex",
                   "commit", "Regulation")


def test_only_the_phone_is_on_the_page(payro):
    for html in (payro.sender.get("/").text, payro.receiver.get("/").text,
                 payro.sender.post("/send", data=MARIA).text):
        assert html.count("<div class='phone'>") == 1
        assert html.split("</div></body>")[0].count("<body><div class='phone'>") == 1   # nothing beside the phone
        assert not [word for word in NOT_ON_THE_PAGE if word in html]


def test_send_moves_the_money_to_the_receivers_phone(payro):
    before = payro.receiver.get("/").text
    assert "No transactions yet." in before and "320.00 EUR" in before and "Money received" not in before
    assert "http-equiv='refresh'" in before                                   # the receiver's phone updates by itself
    assert "2,500.00 EUR" in payro.sender.get("/").text

    done = payro.sender.post("/send", data=MARIA)
    assert done.url.path == "/sent/1"                                         # redirected: a reload cannot send twice
    assert "Money sent" in done.text and "100.00 EUR to Maria Popescu" in done.text
    assert "<b>1.50 EUR</b>" in done.text and "<b>101.50 EUR</b>" in done.text
    assert "2,398.50 EUR" in done.text                                        # amount and fee left the sender's account
    payro.sender.get("/sent/1")
    assert len(payro.bank.payments()) == 1

    after = payro.receiver.get("/").text
    assert "Money received" in after and "+100.00 EUR" in after and "from Andrei Ionescu" in after
    assert "420.00 EUR" in after                                              # the receiver gets the amount, not the fee
    assert "Maria Popescu" in payro.sender.get("/").text.split("Recent")[1]   # and it is in the sender's history


def test_the_fee_on_the_same_running_app_changes_after_a_human_merge(payro):
    home = payro.sender.get("/").text
    assert "Fee 1.50 EUR" in home and "Fee 0.50 EUR" in home                  # instant 1.50, standard 0.50
    assert "<b>101.50 EUR</b>" in payro.sender.post("/send", data=MARIA).text

    payro_merge(payro.git, payro.fee)                                         # a person merges; the app is NOT restarted

    form = payro.sender.get("/").text.split("Recent")[0]
    assert "1.50 EUR" not in form and form.count("Fee 0.50 EUR") == 2
    done = payro.sender.post("/send", data=MARIA).text
    assert "<b>0.50 EUR</b>" in done and "<b>100.50 EUR</b>" in done
    assert "520.00 EUR" in payro.receiver.get("/").text                       # both payments arrived
    assert [p.fee for p in payro.bank.payments()] == [0.5, 1.5]


def test_a_standard_transfer_is_shown_as_on_its_way_and_not_yet_credited(payro):
    done = payro.sender.post("/send", data={**MARIA, "speed": "standard"}).text
    assert "Money sent" in done and "<b>100.50 EUR</b>" in done
    screen = payro.receiver.get("/").text
    assert "arrives next business day" in screen and "320.00 EUR" in screen and "Money received" not in screen

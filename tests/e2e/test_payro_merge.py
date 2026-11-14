"""PayRo demo app: the same running app behaves differently after a person merges a coLEX branch."""
from __future__ import annotations

from fastapi.testclient import TestClient

from payro_app.repo import PayroRepo
from payro_app.server import create_app
from tests.e2e.test_payro_app import _branch, _git, _merge, _parts, _snapshot, world  # noqa: F401  (fixture)


def test_the_same_running_app_changes_when_a_human_merges(world):  # noqa: F811
    client, git, fee, vop = world
    before = _snapshot(git)
    sha0 = _git(git, "rev-parse", "main").strip()
    screen, running, waiting = _parts(client.get("/?s=fees").text)
    assert "Fee 1.50 EUR · Total 101.50 EUR" in screen and "Instant costs 1.00 EUR more than standard" in screen
    assert "Payee name: not checked" in screen and "FICTIONAL" in screen
    assert f"<b>main</b> · commit <code>{sha0[:8]}</code>" in running and str(git.repo) in running
    assert fee in waiting and vop in waiting and "empty" not in waiting and "Already merged" not in waiting
    assert f"merge --no-ff --no-edit {fee}" in waiting and "1 file(s), +1 −1 lines: payments/fees.yaml" in waiting
    assert "Money sent" in _parts(client.get("/?s=payee").text)[0]            # wrong name, nothing stops it
    assert _snapshot(git) == before                                           # the app wrote nothing: refs, index, files

    _merge(git, fee)                                                          # a person merges; the app is NOT restarted
    sha1 = _git(git, "rev-parse", "main").strip()
    screen, running, waiting = _parts(client.get("/?s=fees").text)
    assert "Fee 0.50 EUR · Total 100.50 EUR" in screen and "Instant costs no more than standard" in screen
    assert sha1 != sha0 and f"commit <code>{sha1[:8]}</code>" in running and "committed by Dana Engineer" in running
    assert "Already merged" in waiting and waiting.index(vop) < waiting.index("Already merged") < waiting.index(fee)
    assert "Money sent" in _parts(client.get("/?s=payee").text)[0]            # the other change is still not live

    _merge(git, vop)
    screen, _, waiting = _parts(client.get("/?s=payee").text)
    assert "Stopped before sending" in screen and "does not match this account" in screen
    assert "the name is close" in screen or "does NOT match" in screen
    assert "One-time password checked" not in screen                          # stopped before the code was asked
    assert "None." in waiting
    screen, _, _ = _parts(client.get("/?s=payee&confirmed=1").text)
    assert "Money sent after the customer confirmed the payee" in screen
    screen, _, _ = _parts(client.get("/?s=payee&name=Maria+Popescu").text)    # correct name: no friction
    assert "Money sent" in screen and "after the customer confirmed" not in screen
    assert screen.index("Payee name checked first") < screen.index("One-time password checked")
    assert "Fee 0.50 EUR" in _parts(client.get("/?s=fees").text)[0]           # both merges are live together


def test_incident_view_bad_input_untrusted_text_and_broken_code(world, tmp_path):  # noqa: F811
    client, git, _, _ = world
    screen, _, _ = _parts(client.get("/?s=incident").text)
    assert "2 report(s) planned" in screen and "Initial report" in screen
    for url in ("/?s=nope&amount=abc&iban=x&b=../../etc&a=<script>", "/?s=fees&amount=-5&name=<script>alert(1)</script>",
                "/?s=incident&aware=junk&classified=1999"):
        response = client.get(url)
        assert response.status_code == 200 and "<script>" not in response.text
    # merged code that returns markup in its message: the page must show it as text, never as HTML
    _merge(git, _branch(git, "xss", "payments/transfer.py", "    validate(transfer)\n",
                        '    raise TransferError("<img src=x onerror=alert(1)>")\n'))
    shown = client.get("/?s=fees").text
    assert "Stopped before sending" in shown and "<img" not in shown and "&lt;img src=x" in shown
    # merged code that does not even import: the failure is shown, the page still renders
    _merge(git, _branch(git, "broken", "payments/fees.py", "from pathlib import Path\n", "import does_not_exist\n"))
    shown = client.get("/?s=fees").text
    assert "The code that is checked out failed" in shown and "What this app is running" in shown
    empty = TestClient(create_app(PayroRepo(tmp_path / "missing")))
    assert "No sandbox repository" in empty.get("/").text

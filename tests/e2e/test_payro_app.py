"""PayRo demo app: it runs the real code of each version, so a change is visible before and after a human merge.

The branches here are written by the test (a known-good change per file), not by a model.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from colex import settings
from colex.gitops import GitOps
from payro_app.laws import NOTES
from payro_app.runner import PayroRepo
from payro_app.server import create_app

VOP = '''    validate(transfer)
    if not transfer.own_account and transfer.currency == "EUR" and not transfer.payee_confirmed:
        if providers.verify_payee(transfer.payee_iban, transfer.payee_name) != "match":
            raise TransferError("The payee name does not match this account. Check it, then confirm to send.")
'''


def _branch(git, item, path, old, new):
    name, wt = git.create_branch("run-t", item)
    file = wt / path
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1
    file.write_text(text.replace(old, new), encoding="utf-8")
    git.commit(wt, f"colex: change {path}", f"k-{item}")
    return name


@pytest.fixture
def world(tmp_path):
    git = GitOps(tmp_path / "repo", tmp_path / "worktrees")
    git.seed(settings.SANDBOX / "repo_seed")
    fee = _branch(git, "fee", "payments/fees.yaml", "    instant: 1.50", "    instant: 0.50")
    vop = _branch(git, "vop", "payments/transfer.py", "    validate(transfer)\n", VOP)
    git.create_branch("run-t", "empty")                       # a branch with no change must not be offered
    repo = PayroRepo(git.repo, tmp_path / "cache")
    return TestClient(create_app(repo)), repo, git, fee, vop


def _phones(html):
    return html.split("<div class='phone'>")[1:]


def test_quoted_law_text_is_verbatim_from_the_official_feed():
    for note in NOTES.values():
        official = re.sub(r"\s+", " ", (settings.FEED / f"{note['celex']}.md").read_text(encoding="utf-8"))
        for quote in note["quotes"]:
            assert quote in official, quote[:60]


def test_fee_scenario_shows_the_real_fee_of_each_version(world):
    client, repo, _, fee, _ = world
    refs = [v["ref"] for v in repo.versions()]
    assert refs[:2] == ["original", "main"] and sorted(refs[2:]) == sorted([fee, world[4]])   # the empty branch is not offered
    left, right = _phones(client.get("/?s=fees").text)
    assert "Fee 1.50 EUR · Total 101.50 EUR" in left and "Instant costs 1.00 EUR more than standard" in left
    assert "Fee 0.50 EUR · Total 100.50 EUR" in right and "Instant costs no more than standard" in right
    assert "NOT merged" in right and fee in right and "FICTIONAL" in left


def test_payee_scenario_warns_before_authorising_and_lets_the_customer_confirm(world):
    client, _, _, _, vop = world
    left, right = _phones(client.get("/?s=payee").text)
    assert "Money sent" in left and "Payee name: not checked by this version" in left
    assert "Stopped before sending" in right and "does not match this account" in right
    assert "the name is close" in right or "does NOT match" in right
    assert "One-time password checked" in left and "One-time password checked" not in right   # stopped before the code
    left, right = _phones(client.get("/?s=payee&confirmed=1").text)
    assert "Money sent after the customer confirmed the payee" in right
    assert "Money sent" in left and "after the customer confirmed" not in left      # the old version never asked
    _, right = _phones(client.get("/?s=payee&name=Maria+Popescu").text)                       # correct name: no friction
    assert "Money sent" in right and "the name matches the account" in right
    assert right.index("Payee name checked first") < right.index("One-time password checked")
    assert vop in right


def test_a_human_merge_changes_main_and_original_keeps_the_old_behaviour(world):
    client, repo, git, fee, _ = world
    env = {"PATH": os.environ["PATH"], "HOME": str(git.repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}   # no COLEX_AGENT
    done = subprocess.run(["git", "merge", "-q", "--no-ff", "--no-edit", fee], cwd=git.repo, env=env,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    before, after = _phones(client.get("/?s=fees").text)          # default after a merge: original against merged
    assert "the code before any change" in before and "Fee 1.50 EUR" in before
    assert "Fee 0.50 EUR" in after and "coLEX change · merged into main" in after
    today, _ = _phones(client.get(f"/?s=fees&a=main&b={fee}").text)
    assert "what customers get today" in today and "Fee 0.50 EUR" in today
    assert subprocess.run(["git", "status", "--porcelain"], cwd=git.repo, env=env, capture_output=True).stdout == b""


def test_incident_view_bad_input_and_untrusted_text(world, tmp_path):
    client, repo, git, _, _ = world
    page = client.get("/?s=incident").text
    assert page.count("2 report(s) planned by this version") == 1 and "nothing to compare yet" in page
    for url in ("/?s=nope&amount=abc&iban=x&b=../../etc&a=<script>", "/?s=fees&amount=-5&name=<script>alert(1)</script>",
                "/?s=incident&aware=junk&classified=1999"):
        response = client.get(url)
        assert response.status_code == 200 and "<script>" not in response.text
    # a version whose code returns markup in its message: the page must show it as text, never as HTML
    bad = _branch(git, "xss", "payments/transfer.py", "    validate(transfer)\n",
                  '    raise TransferError("<img src=x onerror=alert(1)>")\n')
    shown = client.get(f"/?s=fees&b={bad}").text
    assert "Stopped before sending" in shown and "<img" not in shown and "&lt;img src=x" in shown
    # a version that does not even import: the failure is shown, the page still renders
    broken = _branch(git, "broken", "payments/fees.py", "from pathlib import Path\n", "import does_not_exist\n")
    shown = client.get(f"/?s=fees&b={broken}").text
    assert "This version of the code failed" in shown and shown.count("<div class='phone'>") == 2
    assert repo.run("no-such-branch", {})["error"] == "unknown version"
    empty = PayroRepo(tmp_path / "missing", tmp_path / "c2")
    assert "No sandbox repository" in TestClient(create_app(empty)).get("/").text

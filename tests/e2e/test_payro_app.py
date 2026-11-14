"""PayRo demo app: one app that runs the code checked out in the repository, so a human merge changes what it does.

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
from payro_app.repo import PayroRepo
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


def _git(git, *args):
    """git as a person at a terminal: no COLEX_AGENT in the environment."""
    env = {"PATH": os.environ["PATH"], "HOME": str(git.repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(["git", *args], cwd=git.repo, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _merge(git, branch):
    _git(git, "-c", "user.name=Dana Engineer", "-c", "user.email=dana@payro.example", "merge", "-q", "--no-ff",
         "--no-edit", branch)


def _snapshot(git):
    files = sorted(str(p.relative_to(git.repo)) for p in git.repo.rglob("*") if ".git" not in p.parts)
    return _git(git, "for-each-ref"), _git(git, "status", "--porcelain"), files


@pytest.fixture
def world(tmp_path):
    git = GitOps(tmp_path / "repo", tmp_path / "worktrees")
    git.seed(settings.SANDBOX / "repo_seed")
    fee = _branch(git, "fee", "payments/fees.yaml", "    instant: 1.50", "    instant: 0.50")
    vop = _branch(git, "vop", "payments/transfer.py", "    validate(transfer)\n", VOP)
    git.create_branch("run-t", "empty")                       # a branch with no change must not be listed
    return TestClient(create_app(PayroRepo(git.repo))), git, fee, vop


def _parts(html):
    """(the PayRo screen, the 'what is running' box, the 'waiting for a merge' box)"""
    screen = html.split("<div class='phone'>")[1].split("<div class='side'>")[0]
    boxes = html.split("<div class='side'>")[1].split("<div class='law'>")
    return screen, boxes[1], boxes[2]


def test_quoted_law_text_is_verbatim_from_the_official_feed():
    for note in NOTES.values():
        official = re.sub(r"\s+", " ", (settings.FEED / f"{note['celex']}.md").read_text(encoding="utf-8"))
        for quote in note["quotes"]:
            assert quote in official, quote[:60]


def test_confirming_on_code_that_never_asked_is_not_reported_as_a_confirmation(world):
    client, _, _, _ = world
    screen, _, _ = _parts(client.get("/?s=payee&confirmed=1").text)
    assert "Money sent" in screen and "after the customer confirmed" not in screen


def test_files_on_disk_that_differ_from_the_commit_are_reported(world):
    client, git, _, _ = world
    path = git.repo / "payments" / "fees.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("instant: 1.50", "instant: 9.00"), encoding="utf-8")
    screen, running, _ = _parts(client.get("/?s=fees").text)
    assert "Fee 9.00 EUR" in screen                                           # it runs the files on disk, and says so
    assert "1 file(s) on disk differ from this commit (payments/fees.yaml)" in running

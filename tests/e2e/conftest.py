"""Shared fixture for the PayRo demo app tests: a temporary sandbox repository and the two phones.

The branches are written by the test (a known-good change per file), not by a model.
"""
from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from colex import settings
from colex.gitops import GitOps

VOP = '''    validate(transfer)
    if not transfer.own_account and transfer.currency == "EUR" and not transfer.payee_confirmed:
        if providers.verify_payee(transfer.payee_iban, transfer.payee_name) != "match":
            raise TransferError("The payee name does not match this account. Check it, then confirm to send.")
'''


def payro_branch(git, item, path, old, new):
    name, wt = git.create_branch("run-t", item)
    file = wt / path
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1
    file.write_text(text.replace(old, new), encoding="utf-8")
    git.commit(wt, f"colex: change {path}", f"k-{item}")
    return name


def payro_merge(git, branch):
    """Merge as a person at a terminal: no COLEX_AGENT in the environment."""
    env = {"PATH": os.environ["PATH"], "HOME": str(git.repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(["git", "-c", "user.name=Dana Engineer", "-c", "user.email=dana@payro.example", "merge",
                           "-q", "--no-ff", "--no-edit", branch], cwd=git.repo, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.fixture
def payro(tmp_path):
    from payro_app.bank import Bank
    from payro_app.checkout import Checkout
    from payro_app.server import create_apps

    git = GitOps(tmp_path / "repo", tmp_path / "worktrees")
    git.seed(settings.SANDBOX / "repo_seed")
    fee = payro_branch(git, "fee", "payments/fees.yaml", "    instant: 1.50", "    instant: 0.50")
    vop = payro_branch(git, "vop", "payments/transfer.py", "    validate(transfer)\n", VOP)
    bank = Bank()
    sender_app, receiver_app = create_apps(Checkout(git.repo), bank)
    return SimpleNamespace(sender=TestClient(sender_app), receiver=TestClient(receiver_app), git=git, bank=bank,
                           fee=fee, vop=vop)

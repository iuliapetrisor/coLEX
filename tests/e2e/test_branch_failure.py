"""A step that crashes on one item is visible, does not stop the other items, and is retried on resume.

Regression: found by tests/chaos/kill_restart.sh, where a crash in the coder left the run "running" forever.
"""
from __future__ import annotations

from colex import testrunner
from colex.runtime import audit, store
from tests.e2e import fakes
from tests.e2e.test_coder_flow import GOOD, _run

AUTH = "PayRo › Payments › Transfers › Transfer authorisation"
TRANSFER = "repo://payments/transfer.py"
ART_5C = "Art. 5c (inserted by Art. 1)"
TWO_ITEMS = fakes.IMPACT_SCRIPT[:4] + [
    [("list_resources", {"path": AUTH, "rationale": "Art. 5c concerns payee verification → transfer authorisation"})],
    [("read", {"uri": TRANSFER, "start": 38, "end": 39, "rationale": "read the authorisation function"})],
    [("report_impact", {"article_id": ART_5C, "resource_uri": TRANSFER, "start": 38, "end": 39, "confidence": 0.8,
                        "quote": "def authorize_transfer(transfer: Transfer, otp: str) -> dict:",
                        "action": "CODE_CHANGE", "obligation": "Verify the payee before authorisation."})],
    [("finish", {"summary": "done"})],
]
NO_EDIT = {"summary": "no change", "edits": []}


def test_one_crashing_branch_does_not_block_the_others_and_is_retried(tmp_path, monkeypatch):
    real = testrunner.run_tests

    def flaky(worktree, timeout=60):
        if str(worktree).endswith("i2"):
            raise FileNotFoundError("simulated crash in the test runner")
        return real(worktree, timeout)

    monkeypatch.setattr(testrunner, "run_tests", flaky)
    engine, deps, run_id = _run(tmp_path, monkeypatch, [GOOD, NO_EDIT, NO_EDIT, NO_EDIT], impact_script=TWO_ITEMS)
    branches = {k: v["status"] for k, v in store.run_row(run_id)["branches"].items()}
    assert branches["i1"] == "waiting_for_review" and branches["i2"] == "failed"
    assert store.run_row(run_id)["status"] == "waiting_for_review"                 # not stuck on "running"
    assert any(e["kind"] == "escalation" and "i2:REMEDIATE:1 failed" in e["summary"] for e in audit.events(run_id))
    monkeypatch.setattr(testrunner, "run_tests", real)                              # the cause is fixed
    engine.drive(run_id)                                                            # resume retries the failed step
    assert store.step_row(run_id, "i2:REMEDIATE:1")["status"] == "done"
    assert store.run_row(run_id)["branches"]["i2"]["status"] != "failed"

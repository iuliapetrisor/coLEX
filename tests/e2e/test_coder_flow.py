"""Coder loop on the real sandbox repository, with scripted model answers (offline, deterministic).

The scripted answers prove the loop and its guards. Whether a real model converges is measured live.
"""
from __future__ import annotations

import shutil

import pytest

from colex import demo, settings
from colex.agents import watcher
from colex.notify.base import outbox_rows
from colex.runtime import audit, store
from tests.e2e.fakes import ScriptedLLM

GOOD = {"summary": "Instant euro fee lowered to the standard fee.",
        "edits": [{"path": "payments/fees.yaml", "search": "    instant: 1.50", "replace": "    instant: 0.50"}]}
NOT_FOUND = {"summary": "x", "edits": [{"path": "payments/fees.yaml", "search": "instant: 9.99", "replace": "y"}]}
BREAKS_HISTORY = {"summary": "Both euro fees set to zero.", "edits": [
    {"path": "payments/fees.yaml", "search": "    standard: 0.50\n    instant: 1.50",
     "replace": "    standard: 0.00\n    instant: 0.00"}]}
TAMPER = {"summary": "x", "edits": [{"path": "tests/compliance/test_equal_charges.py", "search": "<=", "replace": ">="}]}


def _run(tmp_path, monkeypatch, answers, celex="32024R0886", **llm):
    monkeypatch.setenv("COLEX_OFFLINE", "1")
    monkeypatch.setattr(settings, "load_env", lambda path=None: None)
    engine, deps = demo.build(tmp_path / "var")
    deps.llm = ScriptedLLM(coder_answers=answers, **llm)
    shutil.copy(settings.FEED / f"{celex}.md", settings.inbox() / f"{celex}.md")
    run_id = engine.poll_feed(settings.inbox())["runs"][0]
    engine.drive(run_id)
    return engine, deps, run_id


def _review(run_id):
    return [w for w in store.waits(run_id) if w["kind"] == "review"]


def test_fail_revise_pass_then_approval_without_merge(tmp_path, monkeypatch):
    engine, deps, run_id = _run(tmp_path, monkeypatch, [NOT_FOUND, BREAKS_HISTORY, GOOD])
    retries = [e["summary"] for e in audit.events(run_id) if e["kind"] == "retry"]
    assert "refused" in retries[0] and "broke test(s) that passed before" in retries[1]
    change = _review(run_id)[0]["payload"]["change"]
    assert (change["iterations"], change["status"]) == (3, "awaiting_review")
    assert change["tests_before"]["failed"] > change["tests_after"]["failed"]
    assert "+    instant: 0.50" in change["diff"] and "standard: 0.00" not in change["diff"]
    base = deps.gitops.base()
    assert deps.rt.deliver_human_answer(_review(run_id)[0]["wait_id"], {"decision": "approve"}, "U-ENG")
    assert engine.drive(run_id) == "done"
    assert deps.gitops.base() == base                                    # approved is not merged
    assert "instant: 1.50" in (deps.gitops.repo / "payments" / "fees.yaml").read_text(encoding="utf-8")
    summary = store.get_blob(store.step_row(run_id, "main:VERIFY")["output_ref"])
    assert summary["change_requests"] == [{"branch": change["branch"], "decision": "approve", "merged": False}]


def test_tests_cannot_be_edited_and_non_convergence_escalates(tmp_path, monkeypatch):
    engine, deps, run_id = _run(tmp_path, monkeypatch, [TAMPER, TAMPER, TAMPER])
    assert _review(run_id) == []                                         # no change request claims success
    kinds = [(r["kind"], r["channel"]) for r in outbox_rows(run_id)]
    assert ("notification", "#payments-eng") in kinds                    # escalation to the engineers
    events = audit.events(run_id)
    assert sum(1 for e in events if e["kind"] == "retry" and "not editable" in e["detail"]["problem"]) == 3
    assert any(e["kind"] == "escalation" and "did not converge" in e["summary"] for e in events)
    name = deps.gitops.branch_name(run_id, "i1")
    assert deps.gitops.diff(name) == "" and engine.drive(run_id) == "done"


def test_request_changes_sends_the_comment_back_to_the_coder(tmp_path, monkeypatch):
    engine, deps, run_id = _run(tmp_path, monkeypatch, [GOOD, {"summary": "Comment added.", "edits": [
        {"path": "payments/fees.yaml", "search": "    instant: 0.50", "replace": "    instant: 0.50  # equal charges"}]}])
    first = _review(run_id)[0]
    deps.rt.deliver_human_answer(first["wait_id"], {"decision": "request_changes", "text": "Add a comment."}, "U-ENG")
    assert engine.drive(run_id) == "waiting_for_review"
    second = [w for w in _review(run_id) if w["status"] == "pending"][0]
    assert second["payload"]["round"] == 2 and "# equal charges" in second["payload"]["change"]["diff"]
    assert len([r for r in outbox_rows(run_id) if r["kind"] == "review"]) == 2
    deps.rt.deliver_human_answer(second["wait_id"], {"decision": "approve"}, "U-ENG")
    assert engine.drive(run_id) == "done"

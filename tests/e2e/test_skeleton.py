"""Walking skeleton: feed → triage → impact → notify → coder → review → summary, on the real runtime."""
from __future__ import annotations

import shutil

import pytest

from colex import demo, settings
from colex.agents import watcher
from colex.notify.base import outbox_rows
from colex.runtime import audit, store
from tests.e2e.fakes import ScriptedLLM
from tests.e2e.test_coder_flow import GOOD

ACTS = ("32024R0886", "32023R1114", "32025R0150")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("COLEX_OFFLINE", "1")
    monkeypatch.setattr(settings, "load_env", lambda path=None: None)
    engine, deps = demo.build(tmp_path / "var")
    deps.llm = ScriptedLLM(coder_answers=[GOOD])
    for celex in ACTS:
        shutil.copy(settings.FEED / f"{celex}.md", settings.inbox() / f"{celex}.md")
    return engine, deps


def _drive_all(engine, deps):
    found = engine.poll_feed(settings.inbox())
    for run_id in found.get("runs", []):
        engine.drive(run_id)
    for _ in range(10):
        if not demo.answer_pending(deps, engine, demo.Printer(quiet=True)):
            break
    return found


def test_relevant_act_runs_end_to_end_and_others_are_archived_with_a_reason(world):
    engine, deps = world
    _drive_all(engine, deps)
    laws = {law["celex"]: law for law in watcher.laws()}
    assert laws["32024R0886"]["status"] == "relevant"
    for celex in ("32023R1114", "32025R0150"):
        assert laws[celex]["status"] == "archived" and laws[celex]["reason"]
    run_id = laws["32024R0886"]["run_id"]
    assert store.run_row(run_id)["status"] == "done"
    nodes = [c["node"] for c in store.checkpoints(run_id)]
    for node in ("TRIAGE", "IMPACT", "LIAISON", "REMEDIATE", "VERIFY", "DONE"):
        assert node in nodes
    kinds = [r["kind"] for r in outbox_rows(run_id)]
    assert kinds.count("notification") == 1 and kinds.count("review") == 1
    summary = store.get_blob(store.step_row(run_id, "main:VERIFY")["output_ref"])
    assert summary["checks"] == {"every_item_grounded": True, "nothing_merged": True}
    assert audit.verify() == (True, None)


def test_driving_again_and_republishing_create_no_duplicates(world):
    engine, deps = world
    _drive_all(engine, deps)
    before = len(outbox_rows()), len(store.checkpoints(watcher.laws()[0]["run_id"] or "")), len(watcher.laws())
    for law in watcher.laws():
        engine.drive(law["run_id"])
    shutil.copy(settings.FEED / "32024R0886.md", settings.inbox() / "copy-of-ipr.md")
    again = engine.poll_feed(settings.inbox())
    assert again["new"] == [] and again["duplicate"] == ["32024R0886"]
    assert (len(outbox_rows()), len(store.checkpoints(watcher.laws()[0]["run_id"] or "")), len(watcher.laws())) == before


def test_malformed_feed_files_are_quarantined_with_a_reason(world):
    engine, deps = world
    (settings.inbox() / "binary.md").write_bytes(b"\xff\xfe\x00\x01 not text")
    (settings.inbox() / "truncated.md").write_text("---\ncelex: \"1\"\n", encoding="utf-8")
    found = _drive_all(engine, deps)
    assert sorted(found["quarantined"]) == ["binary.md", "truncated.md"]
    reasons = {law["title"]: law["reason"] for law in watcher.laws() if law["status"] == "quarantined"}
    assert "UTF-8" in reasons["binary.md"] and reasons["truncated.md"]
    assert len(found["new"]) == 3

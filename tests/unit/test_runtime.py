"""Runtime: checkpoints, replay, waits, side effects, fork isolation, config versions, audit chain."""
from __future__ import annotations

import pytest

from colex import db
from colex.config import ConfigError, ConfigStore
from colex.runtime import audit, store
from colex.runtime.api import IllegalTransition, Runtime, StepFailed
from colex.runtime.transfer import BundleError


@pytest.fixture
def rt(colex_db_path):
    return Runtime()


def _two_steps(rt, calls):
    run = rt.start_run("32024R0886")
    for node in ("TRIAGE", "IMPACT"):
        rt.step(run.run_id, "main", node, lambda ctx, n=node: calls.append(n) or {"node": n})
    return run.run_id


def test_checkpoint_after_every_step_and_replay(rt):
    calls = []
    run_id = _two_steps(rt, calls)
    assert [c["node"] for c in store.checkpoints(run_id)] == ["TRIAGE", "IMPACT"]
    out = Runtime().step(run_id, "main", "TRIAGE", lambda ctx: calls.append("again") or {})
    assert out == {"node": "TRIAGE"} and calls == ["TRIAGE", "IMPACT"]


def test_illegal_transition_raises(rt):
    run = rt.start_run("x")
    with pytest.raises(IllegalTransition):
        rt.step(run.run_id, "main", "REVIEW", lambda ctx: {})


def test_failed_step_is_visible_and_not_checkpointed(rt):
    run = rt.start_run("x")
    with pytest.raises(StepFailed):
        rt.step(run.run_id, "main", "TRIAGE", lambda ctx: 1 / 0)
    assert rt.get_run(run.run_id).status == "failed"
    assert any(e["kind"] == "escalation" for e in audit.events(run.run_id))
    assert store.checkpoints(run.run_id) == []


def test_side_effect_runs_once(rt):
    hits = []
    for _ in range(3):
        assert rt.side_effect("notify:run-1:legal", lambda: hits.append(1) or {"ts": "1"}) == {"ts": "1"}
    assert hits == [1]


def test_wait_pauses_only_its_branch_and_duplicate_answers_are_ignored(rt):
    run_id = _two_steps(rt, [])
    rt.set_branch(run_id, "item-2", "done", "IMPACT")
    assert rt.wait_for_human(run_id, "item-1", "legal", {"text": "?"}, key="q1") is None
    assert rt.get_run(run_id).branches == {"main": "running", "item-2": "done", "item-1": "waiting_for_legal"}
    rt.set_branch(run_id, "main", "done")
    assert rt.get_run(run_id).status == "waiting_for_legal"
    assert rt.deliver_human_answer(f"{run_id}:q1", {"decision": "yes"}, "U1") is True
    assert rt.deliver_human_answer(f"{run_id}:q1", {"decision": "no"}, "U2") is False
    answer = rt.wait_for_human(run_id, "item-1", "legal", {"text": "?"}, key="q1")
    assert answer["decision"] == "yes" and answer["actor"] == "U1"


def test_fork_replays_parent_and_never_mutates_it(rt):
    calls = []
    run_id = _two_steps(rt, calls)
    first = store.checkpoints(run_id)[0]
    before = db.dumps([store.run_row(run_id), store.checkpoints(run_id)])
    fork = rt.fork(first["checkpoint_id"])
    assert fork.parent_checkpoint_id == first["checkpoint_id"] and fork.run_id != run_id
    assert rt.step(fork.run_id, "main", "TRIAGE", lambda ctx: {"node": "new"}) == {"node": "TRIAGE"}
    assert rt.step(fork.run_id, "main", "IMPACT", lambda ctx: {"node": "forked"}) == {"node": "forked"}
    assert db.dumps([store.run_row(run_id), store.checkpoints(run_id)]) == before


def test_export_masks_personal_data_and_import_round_trips(rt):
    run = rt.start_run("x")
    rt.step(run.run_id, "main", "TRIAGE", lambda ctx: {"note": "IBAN RO49AAAA1B31007593840000 ana@payro.example"})
    bundle = rt.export_checkpoint(store.checkpoints(run.run_id)[0]["checkpoint_id"])
    assert b"RO49AAAA1B31007593840000" not in bundle and b"ana@payro.example" not in bundle
    imported = rt.import_checkpoint(bundle)
    assert rt.step(imported.run_id, "main", "TRIAGE", lambda ctx: {})["note"].startswith("IBAN ⟨IBAN⟩")
    for bad in (b"not json", b'{"format": "other"}', bundle.replace(b'"blobs"', b'"blobz"')):
        with pytest.raises(BundleError):
            rt.import_checkpoint(bad)


def test_config_versions_hot_reload_and_rollback(rt):
    store_ = ConfigStore()
    v1 = store_.active()
    run = rt.start_run("x")
    seen = []
    rt.step(run.run_id, "main", "TRIAGE", lambda ctx: seen.append(ctx.config_version_id) or {})
    payload = {**v1.payload, "routing": {**v1.payload["routing"], "action_channels": {"FEE_CHANGE": "#product"}}}
    v2 = store_.save(payload, "alexia")
    rt.step(run.run_id, "main", "IMPACT", lambda ctx: seen.append(ctx.config_version_id) or {})
    assert seen == [v1.version_id, v2.version_id] and "FEE_CHANGE" in v2.diff and v2.author == "alexia"
    v3 = store_.rollback(v1.version_id, "alexia")
    assert v3.version_id not in (v1.version_id, v2.version_id) and v3.hash == v1.hash
    with pytest.raises(ConfigError, match="budgets.max_coder_iterations"):
        store_.save({**v1.payload, "budgets": {**v1.payload["budgets"], "max_coder_iterations": 0}}, "x")
    assert store_.active().version_id == v3.version_id


def test_audit_chain_detects_tampering(rt):
    _two_steps(rt, [])
    assert audit.verify() == (True, None)
    db.connect().execute("update audit_events set summary='edited' where id=2")
    assert audit.verify() == (False, 2)

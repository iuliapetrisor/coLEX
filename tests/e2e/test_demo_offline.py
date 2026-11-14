"""The whole brief §1.5 scenario, offline, from the recorded model answers in tests/fixtures/llm.

Strict replay: a request with no recorded answer fails the run. The answers were recorded on one
machine (Python 3.12); test-failure text is part of the coder's prompt, so another Python version
may need `make record`.
"""
from __future__ import annotations

import json

import pytest
import yaml

from colex import demo, settings
from colex.agents import watcher
from colex.notify.base import outbox_rows
from colex.runtime import audit, store

TRUTH = yaml.safe_load((settings.SANDBOX / "_ground_truth" / "expected.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def state(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    patch.setenv("COLEX_OFFLINE", "1")
    patch.setenv("COLEX_DEMO_DIR", str(tmp_path_factory.mktemp("demo") / "var"))
    patch.setenv("COLEX_LLM_CACHE", str(tmp_path_factory.mktemp("cache")))
    patch.setattr(settings, "load_env", lambda path=None: None)
    code = demo.main(["--quiet"])
    yield code
    patch.undo()


def _runs():
    return {law["celex"]: law for law in watcher.laws()}


def test_demo_completes_and_triage_matches_the_labelled_feed(state):
    assert state == 0
    laws = _runs()
    relevant = sorted(c for c, law in laws.items() if law["status"] == "relevant")
    assert relevant == sorted(TRUTH["laws"]["relevant"])
    archived = [law for law in laws.values() if law["status"] == "archived"]
    assert len(archived) == 20 and all(law["reason"] for law in archived)


def test_every_run_finished_with_grounded_items_and_nothing_merged(state):
    for celex in TRUTH["laws"]["relevant"]:
        run_id = _runs()[celex]["run_id"]
        assert store.run_row(run_id)["status"] == "done"
        summary = store.get_blob(store.step_row(run_id, "main:VERIFY")["output_ref"])
        assert summary["checks"] == {"every_item_grounded": True, "nothing_merged": True}
        assert summary["items"] >= 2 and all(not c["merged"] for c in summary["change_requests"])
    assert audit.verify() == (True, None)


def test_notifications_reach_the_owning_teams_and_reviews_go_to_engineers(state):
    rows = outbox_rows()
    channels = {r["channel"] for r in rows if r["kind"] == "notification"}
    assert {"#legal", "#compliance", "#product", "#security", "#payments-eng"} <= channels
    assert {r["channel"] for r in rows if r["kind"] == "review"} == {"#payments-eng"}
    assert len({r["idem_key"] for r in rows}) == len(rows)
    for r in rows:
        if r["kind"] == "notification":
            for item in r["payload"]["items"]:
                assert item["resource_uri"] and item["lines"]["start"] >= 1 and item["citation"].startswith("CELEX:")
                assert not item["resource_uri"].startswith("intranet://")


def test_code_changes_exist_on_branches_and_main_is_untouched(state):
    reviews = [w for w in store.waits() if w["kind"] == "review"]
    files = {line[6:] for w in reviews for line in w["payload"]["change"]["diff"].splitlines()
             if line.startswith("+++ b/")}
    assert "payments/fees.yaml" in files and "payments/transfer.py" in files
    assert not [f for f in files if f.startswith("tests/")]
    seed = (settings.SANDBOX / "repo_seed" / "payments" / "fees.yaml").read_text(encoding="utf-8")
    assert (settings.var_dir() / "repo" / "payments" / "fees.yaml").read_text(encoding="utf-8") == seed


def test_dora_register_was_generated(state):
    run_id = _runs()["32022R2554"]["run_id"]
    summary = store.get_blob(store.step_row(run_id, "main:VERIFY")["output_ref"])
    assert summary["dora_register"]["rows"] == 6 and summary["dora_register"]["missing_clauses"] == 3
    assert json.dumps(summary["context"])

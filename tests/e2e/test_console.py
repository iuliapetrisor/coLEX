"""Console over HTTP (in-process test client): pages render, and the fallback actions use the runtime path."""
from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient

from colex import demo, settings
from colex.api.app import create_app
from colex.config import ConfigStore
from colex.runtime import audit, store
from tests.e2e.fakes import ScriptedLLM
from tests.e2e.test_coder_flow import GOOD


@pytest.fixture
def console(tmp_path, monkeypatch):
    monkeypatch.setenv("COLEX_OFFLINE", "1")
    monkeypatch.setattr(settings, "load_env", lambda path=None: None)
    engine, deps = demo.build(tmp_path / "var")
    deps.llm = ScriptedLLM(coder_answers=[GOOD, GOOD])
    client = TestClient(create_app(engine, deps), follow_redirects=False)
    assert client.post("/feed/publish", data={"celex": "32024R0886"}).status_code == 303
    run_id = store.waits(status="pending")[0]["run_id"]
    return client, engine, deps, run_id


def test_every_page_renders_and_is_not_a_chat(console):
    client, _, _, run_id = console
    wait = store.waits(run_id, "pending")[0]
    pages = ["/", "/feed", "/map", "/map?path=PayRo%20%E2%80%BA%20Payments", "/registers", "/slack", "/settings",
             f"/runs/{run_id}", f"/changes/{wait['wait_id']}", "/law/32024R0886",
             "/evidence?uri=repo%3A%2F%2Fpayments%2Ffees.yaml&start=7&end=9"]
    for url in pages:
        response = client.get(url)
        assert response.status_code == 200, url
        assert "FICTIONAL PayRo data" in response.text
    run_page = client.get(f"/runs/{run_id}").text
    assert "Art. 5b concerns charges → pricing configuration" in run_page          # readable reasoning, not JSON
    assert "checkpoint" in run_page and "Fork from here" in run_page and "never merges" in run_page
    assert "class='hl'" in client.get(pages[-1]).text
    assert client.get("/registers/dora.csv").text.startswith("contract_id,provider")
    assert client.get("/runs/run-nope").status_code == 404
    assert client.get("/evidence?uri=..%2F..%2F.env&start=1&end=5").text.count("not a resource") == 1


def test_console_approval_resumes_the_run_like_slack_and_never_merges(console):
    client, _, deps, run_id = console
    wait = store.waits(run_id, "pending")[0]
    base = deps.gitops.base()
    assert client.post(f"/act/{wait['wait_id']}", data={"decision": "approve"}).status_code == 303
    assert client.post(f"/act/{wait['wait_id']}", data={"decision": "approve"}).status_code == 303   # double click
    assert store.run_row(run_id)["status"] == "done" and deps.gitops.base() == base
    humans = [e["summary"] for e in audit.events(run_id) if e["kind"] == "human"]
    assert sum("answered: approve" in s for s in humans) == 1 and sum("Ignored duplicate" in s for s in humans) == 1
    assert "Summary" in client.get(f"/runs/{run_id}").text


def test_pause_resume_and_fork_from_a_checkpoint(console):
    client, _, _, run_id = console
    client.post(f"/runs/{run_id}/pause")
    assert store.run_row(run_id)["paused"] == 1
    client.post(f"/runs/{run_id}/resume")
    assert store.run_row(run_id)["paused"] == 0
    first = store.checkpoints(run_id)[0]["checkpoint_id"]
    before = len(store.checkpoints(run_id))
    forked = client.post(f"/checkpoints/{first}/fork").headers["location"].rsplit("/", 1)[-1]
    assert forked != run_id and store.run_row(forked)["parent_checkpoint_id"] == first
    assert len(store.checkpoints(run_id)) == before                                  # the original is untouched
    bundle = client.get(f"/checkpoints/{first}/export").content
    assert client.post("/checkpoints/import", content=bundle).status_code == 303
    assert client.post("/checkpoints/import", content=b"junk").status_code == 400


def test_settings_reject_invalid_config_and_roll_back(console):
    client, _, _, _ = console
    active = ConfigStore().active()
    bad = client.post("/settings", data={"yaml": "models: {}", "author": "me"})
    assert bad.status_code == 400 and "Not saved" in bad.text and ConfigStore().active().version_id == active.version_id
    import yaml
    payload = {**active.payload, "routing": {**active.payload["routing"], "action_channels": {"FEE_CHANGE": "#product"}}}
    assert client.post("/settings", data={"yaml": yaml.safe_dump(payload), "author": "me"}).status_code == 303
    changed = ConfigStore().active()
    assert changed.version_id != active.version_id and changed.author == "me"
    client.post(f"/settings/rollback/{active.version_id}")
    assert ConfigStore().active().hash == active.hash and len(ConfigStore().history()) == 3

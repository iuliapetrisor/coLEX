"""Missing information: a question pauses only its own branch, and the answer re-plans only that contract."""
from __future__ import annotations

from colex.agents.impact_report import CRITICALITY_OPTIONS
from colex.notify.base import outbox_rows
from colex.runtime import store
from tests.e2e.test_coder_flow import _run

ICT = "PayRo › Legal & Compliance › Contracts › ICT provider contracts"
CARD = "onedrive://legal/contracts/card-processing-cardaxis.md"
SCRIPT = [
    [("overview", {"rationale": "start from the company overview"})],
    [("list_resources", {"path": ICT, "rationale": "Art. 30 concerns ICT contracts"})],
    [("ask_legal", {"question": "Does the CardAxis contract support a critical or important function?",
                    "options": ["maybe", "perhaps"], "article_id": "Art. 30", "resource_uri": CARD})],
    [("finish", {"summary": "contracts covered"})],
]


def _start(tmp_path, monkeypatch):
    engine, deps, run_id = _run(tmp_path, monkeypatch, [], celex="32022R2554", relevant={"32022R2554"},
                                impact_script=SCRIPT)
    return engine, deps, run_id


def test_question_pauses_only_its_branch_while_the_others_finish(tmp_path, monkeypatch):
    engine, deps, run_id = _start(tmp_path, monkeypatch)
    branches = {k: v["status"] for k, v in store.run_row(run_id)["branches"].items()}
    assert branches == {"main": "waiting_for_legal", "q1": "waiting_for_legal",
                        "reg-1": "done", "reg-2": "done", "reg-3": "done"}
    sent = [(r["kind"], r["channel"]) for r in outbox_rows(run_id)]
    assert sent.count(("notification", "#legal")) == 1 and ("notification", "#compliance") in sent
    assert ("question", "#legal") in sent
    wait = store.waits(run_id, "pending")[0]
    assert wait["payload"]["question"]["options"] == list(CRITICALITY_OPTIONS)


def test_yes_replans_that_contract_only_and_without_a_model_call(tmp_path, monkeypatch):
    engine, deps, run_id = _start(tmp_path, monkeypatch)
    before, calls = len(outbox_rows(run_id)), deps.llm.calls.count("impact")
    done_steps = {s["step_key"] for s in store.checkpoints(run_id)}
    wait = store.waits(run_id, "pending")[0]
    assert deps.rt.deliver_human_answer(wait["wait_id"], {"decision": CRITICALITY_OPTIONS[0]}, "U-LEGAL")
    assert engine.drive(run_id) == "done"
    new = outbox_rows(run_id)[before:]
    assert [(r["kind"], r["channel"]) for r in new] == [("notification", "#legal")]
    item = new[0]["payload"]["items"][0]
    assert item["resource_uri"] == CARD and "30(3)(e)" in item["obligation"] and item["owner_team"] == "legal"
    assert deps.llm.calls.count("impact") == calls
    added = [s["step_key"] for s in store.checkpoints(run_id) if s["step_key"] not in done_steps]
    assert added == ["replan:q1", "liaison:q1", "main:VERIFY", "main:DONE"]      # nothing else re-ran
    question = [r for r in outbox_rows(run_id) if r["kind"] == "question"][0]
    assert question["status"] == "decided"


def test_no_changes_nothing(tmp_path, monkeypatch):
    engine, deps, run_id = _start(tmp_path, monkeypatch)
    before = len(outbox_rows(run_id))
    wait = store.waits(run_id, "pending")[0]
    deps.rt.deliver_human_answer(wait["wait_id"], {"decision": CRITICALITY_OPTIONS[1]}, "U-LEGAL")
    assert engine.drive(run_id) == "done" and len(outbox_rows(run_id)) == before

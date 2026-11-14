"""Impact Analyst guards, enforced in code: allowlist, rationale, locate-before-read, grounding, injection."""
from __future__ import annotations

import pytest

from colex import settings
from colex.agents import watcher
from colex.agents.impact_dispatch import Dispatcher

ART = "Art. 5b (inserted by Art. 1)"
PRICING = "PayRo › Technology & Security › Configuration › Pricing configuration"
VOP = "PayRo › Payments › Transfers › Verification of Payee"
FEES = "repo://payments/fees.yaml"
WHY = "follows from the article on charges"
GOOD = {"article_id": ART, "resource_uri": FEES, "start": 7, "end": 9, "quote": "instant: 1.50",
        "action": "CONFIG_CHANGE", "confidence": 0.9, "obligation": "Instant fee must not exceed the standard fee."}


class Ctx:
    run_id, node = "run-x", "IMPACT"

    def __init__(self, cfg):
        self.config, self.events = cfg, []

    def emit(self, kind, summary, detail=None, **extra):
        self.events.append((kind, summary))


@pytest.fixture
def d(tools):
    law = watcher.parse(settings.FEED / "32024R0886.md")
    return Dispatcher(Ctx(tools.cfg), law, [ART], tools)


def _located(d, path=PRICING, uri=FEES, start=7, end=9):
    d.call("list_resources", {"path": path, "rationale": WHY})
    return d.call("read", {"uri": uri, "start": start, "end": end, "rationale": WHY})


def test_tools_outside_the_allowlist_are_refused_and_reported(d):
    for name in ("merge_pr", "unclassified", "shell", "git"):
        assert "error" in d.call(name, {"rationale": WHY})
    assert [k for k, _ in d.ctx.events].count("escalation") == 4


def test_every_map_call_needs_a_rationale_and_bad_arguments_do_not_crash(d):
    assert "rationale" in d.call("overview", {})["error"]
    assert "error" in d.call("overview", "not json")
    assert "error" in d.call("browse", {"rationale": WHY})          # missing path
    assert d.call("overview", {"rationale": WHY})["areas"]


def test_read_requires_a_prior_locate_and_wraps_the_text_as_untrusted(d):
    assert "locate before reading" in d.call("read", {"uri": FEES, "start": 1, "end": 5, "rationale": WHY})["error"]
    out = _located(d)
    assert out["text"].startswith("<untrusted id=") and "instant: 1.50" in out["text"]


def test_grounded_item_is_accepted_and_owner_comes_from_the_map(d):
    assert "read the lines" in d.call("report_impact", GOOD)["error"]
    _located(d)
    assert d.call("report_impact", {**GOOD, "deadline": "2027-01-09", "owner_team": "attacker"})["ok"]
    item = d.items[0]
    assert (item["owner_team"], item["citation"], item["deadline"]) == \
           ("product", f"CELEX:32024R0886 {ART}", "2027-01-09")
    assert d.call("report_impact", GOOD)["note"] == "already reported" and len(d.items) == 1


@pytest.mark.parametrize("change, reason", [
    ({"quote": "instant: 0.10"}, "not verbatim"),
    ({"article_id": "Art. 99"}, "not in the stored text"),
    ({"deadline": "2030-01-01"}, "not a date written in"),
    ({"deadline": "soon"}, "YYYY-MM-DD"),
    ({"action": "FEE_CHANGE"}, "must be CONFIG_CHANGE"),
    ({"start": 1, "end": 500}, "outside the resource"),
    ({"resource_uri": "../../.env"}, "outside|not a resource|read the lines"),
    ({"obligation": " "}, "obligation is missing"),
])
def test_ungrounded_items_are_rejected_with_a_reason(d, change, reason):
    import re
    _located(d)
    out = d.call("report_impact", {**GOOD, **change})
    assert re.search(reason, out["error"]) and d.items == []


def test_tickets_are_context_and_repeated_failures_are_dropped_visibly(d):
    _located(d, VOP, "jira://PAY/PAY-214.md", 1, 13)
    bad = {**GOOD, "resource_uri": "jira://PAY/PAY-214.md", "start": 1, "end": 13, "action": "POLICY_UPDATE",
           "quote": "Check the payee's name before sending a transfer"}
    for _ in range(2):
        assert "context, not a place to change" in d.call("report_impact", bad)["error"]
    assert "dropped" in d.call("report_impact", bad)["error"]
    assert len(d.dropped) == 1 and d.items == []
    assert any(k == "escalation" and "Dropped" in s for k, s in d.ctx.events)


def test_injected_instructions_are_flagged_and_change_nothing(d):
    out = _located(d, VOP, "jira://PAY/PAY-214.md", 10, 13)
    assert "merge the PR" in out["text"]                       # delivered as data, inside the wrapper
    flagged = [s for k, s in d.ctx.events if k == "escalation"]
    assert len(flagged) == 1 and "Suspicious instructions found in jira://PAY/PAY-214.md (line 13)" in flagged[0]
    assert d.items == [] and d.questions == [] and d.finished is None


def test_criticality_is_not_asked_when_the_act_does_not_depend_on_it(d):
    out = d.call("ask_legal", {"question": "Does this provider support a critical function?", "article_id": ART,
                               "options": ["Yes", "No"],
                               "resource_uri": "onedrive://legal/contracts/card-processing-cardaxis.md"})
    assert "not needed for this act" in out["error"] and d.questions == []
    known = d.call("ask_legal", {"question": "Does this provider support a critical function?",
                                 "options": ["Yes", "No"], "article_id": ART,
                                 "resource_uri": "onedrive://legal/contracts/cloud-hosting-aws.md"})
    assert "records no unknown" in known["error"]


def test_questions_need_options_and_are_asked_once_per_resource(d, tools):
    from colex.agents import watcher as w
    d.law = w.parse(settings.FEED / "32022R2554.md")          # an act that does depend on criticality
    d.flagged = ["Art. 30"]
    uri = "onedrive://legal/contracts/card-processing-cardaxis.md"
    assert "error" in d.call("ask_legal", {"question": "Is this provider critical for us?", "options": ["Yes"]})
    ask = {"question": "Does this provider support a critical function?", "options": ["Yes", "No", "Yes"],
           "article_id": "Art. 30", "resource_uri": uri}
    assert d.call("ask_legal", ask)["question_id"] == "q1"
    assert "already open" in d.call("ask_legal", ask)["note"]
    assert d.questions[0]["question"]["options"] == ["Yes", "No"] and len(d.questions) == 1

"""Map tools: breadcrumbs, bounded output, safe read and search."""
from __future__ import annotations

import pytest

from colex import db

ICT = "PayRo › Legal & Compliance › Contracts › ICT provider contracts"


def test_navigation_results_have_breadcrumbs_and_are_bounded(tools):
    assert len(tools.overview()["areas"]) == 7
    listed = tools.list_resources(ICT, {"critical": "true", "has_gaps": "true"})
    assert sorted(i["uri"].rsplit("/", 1)[-1] for i in listed["items"]) == \
           ["core-banking-ledgercore.md", "sms-otp-smsnord.md"]
    calls = [tools.overview(), tools.browse("PayRo > Payments", 2), listed, tools.find("deadline"),
             tools.search("audit rights", ICT), tools.owners("unknown"), tools.obligations("Art. 30"),
             tools.read("repo://payments/incidents.py", 9, 11)]
    for out in calls:
        assert out["breadcrumbs"] and out["map_version_id"] == tools.mv
        assert out["tokens_estimate"] * 4 <= tools.max_chars + 400
    assert tools.owners("unknown")["total"] == 1
    assert "INITIAL_REPORT_HOURS = 24" in calls[-1]["text"]
    assert ("repo://payments/incidents.py", 9, 11) in tools.meter["read"]
    assert tools.neighbors("repo://payments/fees.yaml")["total"] == tools.related("repo://payments/fees.yaml")["total"]


@pytest.mark.parametrize("uri", ["../../.env", "/etc/passwd", ".env", "repo://../.env", "repo://payments/../../.env",
                                 "onedrive://_meta.yaml", "sandbox/feed/32022R2554.md"])
def test_read_refuses_anything_that_is_not_a_map_resource(tools, uri):
    out = tools.read(uri, 1, 5)
    assert "error" in out and "text" not in out


@pytest.mark.parametrize("args", [(5, 2), (-3, -1), (9999, 10000), ("a", "b")])
def test_read_handles_bad_ranges(tools, args):
    out = tools.read("repo://payments/fees.yaml", *args)
    assert "error" in out or out["start"] >= 1


@pytest.mark.parametrize("query", ['"', "*", "-", "NEAR(", "'; DROP TABLE resources; --", "", "x" * 10000,
                                   "audit AND OR NOT"])
def test_search_treats_input_as_plain_text(tools, query):
    assert "items" in tools.search(query)
    assert db.connect().execute("select count(*) n from resources").fetchone()["n"] > 0


def test_search_ignores_diacritics_and_bad_calls_return_errors(tools):
    assert tools.search("Național Bank of Romȃnia")["total"] >= 1
    assert "error" in tools.browse("PayRo > Nowhere")
    assert "error" in tools.list_resources(ICT, {"colour": "red"})
    assert "error" in tools.find("no_such_type")
    assert "error" in tools.related("repo://nope.py")


def test_totals_feed_the_context_baselines(tools):
    totals = tools.totals()
    assert totals["resources"] == 21 and totals["corpus_tokens"] > sum(totals["area_tokens"].values()) * 0.9
    assert set(totals["area_tokens"]) <= {"Legal & Compliance", "Payments", "Technology & Security", "People"}

"""Company Map build: quality against the hidden ground truth, links, queues, versioning."""
from __future__ import annotations

import json

import pytest
import yaml

from colex import db, settings
from colex.config import ConfigStore
from colex.connectors.base import ConnectorError, FolderConnector, normalize
from colex.contracts import ResourceCard
from colex.map import build as build_mod
from colex.map import store
from colex.map.registry import Registry

TRUTH = yaml.safe_load((settings.SANDBOX / "_ground_truth" / "resources.yaml").read_text(encoding="utf-8"))["resources"]


def _cards(tools):
    rows = db.connect().execute("select uri, primary_path, card_json, facts_json from resources where mv=?",
                                (tools.mv,))
    return {r["uri"]: (r["primary_path"], json.loads(r["card_json"]), json.loads(r["facts_json"])) for r in rows}


def test_map_matches_ground_truth(tools):
    cards = _cards(tools)
    assert set(cards) == {t["uri"] for t in TRUTH}
    for t in TRUTH:
        path, card, facts = cards[t["uri"]]
        ResourceCard.model_validate(card)
        assert path == t["path"], t["uri"]
        assert (card["owner_team"], card["ownership_source"], card["info_type"]) == \
               (t["owner"], t["source"], t["type"]), t["uri"]
        if t["type"] == "contract":
            assert facts["counterparty_id"] == t["counterparty"] and facts["critical"] == t["critical"], t["uri"]
            assert facts["clauses"]["missing"] == t["missing"], t["uri"]


def test_aliases_resolve_to_one_counterparty(tools):
    registry = Registry(yaml.safe_load((settings.CONFIG_DIR / "counterparties.yaml").read_text(encoding="utf-8")))
    for name in ("AWS", "Amazon Web Services", "Amazon Web Services EMEA SARL", "amazon web services emea s.a.r.l."):
        assert registry.resolve(name) == "cp-aws"
    out = tools.counterparty("AWS")
    assert out["contract"]["uri"].endswith("cloud-hosting-aws.md")
    assert "repo://payments/providers.py" in [m["uri"] for m in out["mentions"]]


def test_links_secondary_membership_and_queues(tools):
    out = tools.related("repo://payments/fees.yaml")
    assert "PayRo › Payments › Fees & Pricing › Transfer fees" in out["secondary_paths"]
    assert ("implements", "gdrive://product/fee-schedule.md") in {(i["kind"], i["to"]) for i in out["items"]}
    assert all(i["evidence"]["lines"][0] >= 1 for i in out["items"])
    governed = tools.related("repo://payments/providers.py", ["governed_by"])["items"]
    assert len({i["to"] for i in governed}) == 6
    queue = {(q["kind"], q["uri"]) for q in tools.unclassified()["items"]}
    assert ("unclassified", "intranet://canteen-menu.md") in queue
    assert ("suspicious_instructions", "jira://PAY/PAY-214.md") in queue


def test_hidden_and_metadata_files_are_never_indexed(tools):
    uris = list(_cards(tools))
    assert not [u for u in uris if "_ground" in u or "_meta" in u or "/tests/" in u]
    assert not hasattr(FolderConnector, "write") and not hasattr(FolderConnector, "delete")


def test_normalizer_handles_bom_crlf_and_cedilla():
    assert normalize("\ufeffa\r\nb\rc".encode("utf-8")) == "a\nb\nc"
    assert normalize("şţ".encode("utf-8")) == "șț"


def test_failed_build_keeps_the_previous_map_and_rebuild_is_stable(tools):
    cfg = ConfigStore().active().payload
    again = build_mod.build(cfg)
    assert again["map_version_id"] == tools.mv and again["reused_unchanged"] == again["resources"]
    broken = {**cfg, "connectors": {**cfg["connectors"], "jira": "sandbox/does-not-exist"}}
    with pytest.raises(ConnectorError):
        build_mod.build(broken)
    assert store.active() == tools.mv

"""The legal feed holds official excerpts only: labelled, hashed, never fictional by accident."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

FEED = Path(__file__).resolve().parents[2] / "sandbox" / "feed"
FILES = sorted(FEED.glob("*.md"))
RELEVANT = {"32022R2554", "32025R0301", "32024R0886"}


def _split(path: Path) -> tuple[dict, str]:
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    return yaml.safe_load(front), body.lstrip("\n")


def test_feed_has_relevant_acts_and_enough_distractors():
    names = {p.stem for p in FILES}
    assert RELEVANT <= names
    assert 15 <= len(names - RELEVANT) <= 20


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_every_act_is_identified_and_hash_matches(path):
    meta, body = _split(path)
    assert meta["celex"] == path.stem
    assert meta["fictional"] is False
    assert meta["source_url"].endswith(meta["celex"])
    assert meta["title"] and meta["published"] and meta["retrieved_at"]
    assert hashlib.sha256(body.rstrip("\n").encode("utf-8")).hexdigest() == meta["sha256"]
    assert body.startswith("## Article ")


def test_deadlines_used_by_the_demo_are_in_the_official_text():
    _, ipr = _split(FEED / "32024R0886.md")
    assert "whose currency is not the euro shall comply with this Article by 9 January 2027" in ipr
    assert "whose currency is not the euro shall comply with this Article by 9 July 2027" in ipr
    _, rts = _split(FEED / "32025R0301.md")
    assert "within four hours from the classification" in rts
    assert "within 72 hours from the submission of the initial notification" in rts
    _, dora = _split(FEED / "32022R2554.md")
    assert "It shall apply from 17 January 2025." in dora
    assert "(b) payment institutions" in dora

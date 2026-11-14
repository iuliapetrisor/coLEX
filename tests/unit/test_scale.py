"""Scale harness: the generated company is labelled and repeatable, and the map stays usable when it grows."""
from __future__ import annotations

import shutil

import pytest

from colex import settings
from colex.config import ConfigStore
from colex.map.tools import MapTools
from tests.scale import gen, measure, vocab

AWS = "onedrive://legal/contracts/cloud-hosting-aws.md"


def test_generated_documents_are_labelled_repeatable_and_only_written_under_var():
    first = [gen.document(i) for i in range(300)]
    assert first == [gen.document(i) for i in range(300)]
    assert all(text.startswith(vocab.LABEL) for _, _, text in first)
    assert {source for source, _, _ in first} == set(gen.SOURCES)
    assert len({(source, path) for source, path, _ in first}) == 300
    for outside in (settings.ROOT / "not-var" / "company", settings.ROOT.parent / "colex-scale-elsewhere"):
        with pytest.raises(ValueError):
            gen.generate(outside, 1)
        assert not outside.exists()


def test_with_400_more_documents_the_sandbox_stays_in_place_and_every_answer_stays_bounded(monkeypatch):
    monkeypatch.setenv("COLEX_VAR", "restored when the test ends")   # measure points these at var/scale
    monkeypatch.delenv("COLEX_DB", raising=False)
    try:
        row = measure.measure(400)
        assert row["resources"] == 421 and row["reused"] == 420           # one changed document was re-analysed
        found = row["needles"]
        assert found["placed_as_before"] == found["resources_in_truth"] == 21
        assert found["unreachable"] == [] and found["max_pages_by_type"] == 1
        answers = {name: t for name, t in row["tools"].items() if not name.startswith("_")}
        assert not [name for name, t in answers.items() if t["truncated"]]
        assert max(t["tokens"] for t in answers.values()) * 4 <= row["max_chars"] + 400
        tools = MapTools(ConfigStore().active().payload)
        owners = tools.owners("payments-eng")                              # too many to list: counts per path
        assert owners["total"] > 100 and sum(owners["count_by_path"].values()) == owners["total"]
        aws = tools.counterparty("AWS")                                    # the contract first, the rest counted
        assert aws["contract"]["uri"] == AWS and len(aws["mentions"]) <= 12 < aws["mentions_total"]
        assert aws["mentions"][0]["info_type"] not in ("ticket", "page")
        queue = tools.unclassified()                                       # the Console's review queue is paged too
        assert queue["total"] > len(queue["items"]) and "next_cursor" in queue
    finally:
        for folder in ("bench-400", "bench-src-400"):
            shutil.rmtree(measure.SCALE / folder, ignore_errors=True)

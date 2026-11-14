"""One relevant act analysed by the REAL model on a larger generated company. Calls OpenRouter: costs money.

usage: python -m tests.scale.live 32024R0886 0 1000

State goes to var/scale/live-N and messages go to the fake notifier, so nothing is sent anywhere.
One row per size is written to tests/scale/live_results.json. N = 1 per size: a row says what that one
run did, not how often the system is right.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Any

import yaml

from colex import demo, settings
from tests.eval.scoring import match
from tests.scale import gen
from tests.scale.measure import SCALE, connect_sources

RESULTS = settings.ROOT / "tests" / "scale" / "live_results.json"
TRUTH = settings.SANDBOX / "_ground_truth"


def run(celex: str, extra: int) -> dict[str, Any]:
    gen.generate(SCALE / f"src-{extra}", extra)
    engine, deps = demo.build(SCALE / f"live-{extra}")          # fresh state, fake notifier
    cfg = connect_sources(f"src-{extra}")
    engine.ensure_map(rebuild=True)
    from colex.map.tools import MapTools
    from colex.runtime import audit, store

    totals = MapTools(cfg).totals()
    shutil.copy(settings.FEED / f"{celex}.md", settings.inbox() / f"{celex}.md")
    run_id = engine.poll_feed(settings.inbox())["runs"][0]
    started = time.monotonic()
    engine.drive(run_id)
    seconds = round(time.monotonic() - started)
    row: dict[str, Any] = {"celex": celex, "added": extra, "resources": totals["resources"],
                           "corpus_tokens": totals["corpus_tokens"], "model": cfg["models"]["strong"],
                           "date": f"{datetime.now(timezone.utc):%Y-%m-%d}", "seconds": seconds}
    step = store.step_row(run_id, "main:IMPACT")
    if not step:
        return {**row, "error": "the act was not analysed (triage did not mark it relevant)"}
    out = store.get_blob(step["output_ref"])
    truth = yaml.safe_load((TRUTH / "expected.yaml").read_text(encoding="utf-8"))
    known = {r["uri"] for r in yaml.safe_load((TRUTH / "resources.yaml").read_text(encoding="utf-8"))["resources"]}
    expected = [x for x in truth["impact_items"] if x["law"] == celex]
    reported = [{**item, "law": celex} for item in out["items"]]
    hit = [x for x in expected if any(match(p, x) for p in reported)]
    events = audit.events(run_id, limit=100000)
    usage, m = audit.usage(run_id), out["metrics"]
    row.update(expected=len(expected), found=len(hit), missed=[x["uri"] for x in expected if x not in hit],
               reported=len(reported), reported_uris=sorted({p["resource_uri"] for p in reported}),
               on_generated_documents=sum(p["resource_uri"] not in known for p in reported),
               dropped_by_validator=len(out["dropped"]), finished_by_itself=out["complete"],
               impact_model_calls=sum(e["kind"] == "llm" and e["agent"] == "impact" for e in events),
               tool_calls=m["tool_calls"], context_tokens_read=m["context_tokens_used"],
               share_of_corpus=m["ratio_vs_a"], fragments_read=m["fragments_read"],
               fragments_total=m["fragments_total"], model_tokens=usage["tokens"],
               cost_usd=round(usage["cost_usd"], 4))
    return row


def main(argv: list[str]) -> int:
    celex, sizes = argv[0], [int(a) for a in argv[1:]]
    rows = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.is_file() else []
    for extra in sizes:
        row = run(celex, extra)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        rows = [r for r in rows if (r["celex"], r["added"]) != (celex, extra)] + [row]
        rows.sort(key=lambda r: (r["celex"], r["added"]))
        RESULTS.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

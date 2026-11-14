"""Generates a larger fictional PayRo for the scale test: the real sandbox documents plus N invented ones.

Every generated file carries the same FICTIONAL label as the sandbox. Document i depends only on
(seed, i), so a larger company contains the smaller one. None of the added documents is in the ground
truth. The sandbox repository (code) is not copied or grown: connectors keep reading it in place.
"""
from __future__ import annotations

import random
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from colex import settings
from tests.scale import pools

SOURCES = ("onedrive", "gdrive", "confluence", "jira", "intranet")
NAMES = list(pools.KINDS)
WEIGHTS = [pools.KINDS[k]["weight"] for k in NAMES]
# Owner metadata for the new folders. risk/ and news/ have no owner on purpose.
OWNERS = {
    "jira": {"OPS/": {"team": "security", "role": "Head of Security"},
             "SUP/": {"team": "support", "role": "Support Lead"}},
    "confluence": {"OPS/": {"team": "security", "role": "Head of Security"}},
    "onedrive": {"finance/": {"team": "finance", "role": "Finance Manager"},
                 "support/": {"team": "support", "role": "Support Lead"}},
}


def document(i: int, seed: int = 7) -> tuple[str, str, str]:
    """(source, path inside the source, text) of generated document number i."""
    rng = random.Random(f"{seed}:{i}")
    spec = pools.KINDS[rng.choices(NAMES, WEIGHTS)[0]]
    year, month = rng.choice((2023, 2024, 2025)), rng.randint(1, 12)
    ctx = {"num": 1000 + i, "system": rng.choice(pools.SYSTEMS), "symptom": rng.choice(pools.SYMPTOMS),
           "person": rng.choice(pools.PEOPLE), "provider": rng.choice(pools.PROVIDERS),
           "month": f"{pools.MONTHS[month - 1]} {year}", "feature": rng.choice(pools.FEATURES),
           "topic": rng.choice(pools.HR_TOPICS), "complaint": rng.choice(pools.COMPLAINTS),
           "minutes": rng.choice((12, 25, 40, 55, 90)), "count": rng.randint(3, 40), "week": rng.randint(1, 52),
           "date": f"{year}-{month:02d}-{rng.randint(1, 28):02d}", "date2": f"{year}-{month:02d}-{rng.randint(1, 28):02d}",
           "tickettype": rng.choice(("Bug", "Task", "Incident")) if spec["folder"] != "OPS" else "Incident",
           "status": rng.choice(("open", "in progress", "closed", "backlog"))}
    title = rng.choice(spec["title"]).format(**ctx)
    title = title[0].upper() + title[1:]
    if "file" in spec:
        name = spec["file"].format(**ctx)
        lines = [pools.LABEL, "", f"# {name}: {title}", ""]
    else:
        name = f"{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:50]}-{i}"
        lines = [pools.LABEL, "", f"# {title}", "", f"Status: active · Created: {ctx['date']}", ""]
    if "head" in spec:
        lines += [spec["head"].format(**ctx), ""]
    for heading, pool in spec["sections"].items():
        chosen = [s.format(**ctx) for s in rng.sample(pool, rng.randint(3, min(5, len(pool))))]
        lines += [f"## {heading}"] + ([f"- {s}" for s in chosen[:2]] if heading == "Comments" else [" ".join(chosen)])
        lines.append("")
    return spec["source"], f"{spec['folder']}/{name}.md", "\n".join(lines).rstrip() + "\n"


def generate(target: Path, extra: int, seed: int = 7) -> dict[str, Any]:
    """Write the sandbox sources plus `extra` generated documents under `target` (replaced if it exists)."""
    target = Path(target).resolve()
    if (settings.ROOT / "var").resolve() not in target.parents:
        raise ValueError(f"generated companies may only be written under var/, not {target}")
    shutil.rmtree(target, ignore_errors=True)
    for source in SOURCES:
        shutil.copytree(settings.SANDBOX / source, target / source)
    counts: Counter[str] = Counter()
    for i in range(extra):
        source, rel, text = document(i, seed)
        path = target / source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        counts[source] += 1
    for source, owners in OWNERS.items():
        meta = target / source / "_meta.yaml"
        data = (yaml.safe_load(meta.read_text(encoding="utf-8")) if meta.is_file() else None) or {}
        data.setdefault("owners", {}).update(owners)
        meta.write_text("# FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo\n"
                        + yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return {"added": extra, "by_source": dict(counts)}

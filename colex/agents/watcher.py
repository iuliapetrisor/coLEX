"""Watcher: reads the legal feed, splits acts into articles, deduplicates, quarantines bad files."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from colex import db, settings
from colex.contracts import LawArticle, LawDocument
from colex.runtime import audit

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"\b(\d{{1,2}}) ({MONTHS}) (\d{{4}})\b")
HEADING = re.compile(r"^## Article (\S+)(?: \[inserted by Article (\S+)\])?\s*$", re.M)
REQUIRED = ("celex", "title", "source_url", "published")


class FeedError(ValueError):
    """A feed file that cannot be used; the message is shown to the user."""


def _dates(text: str) -> list[str]:
    found = {datetime.strptime(" ".join(m.groups()), "%d %B %Y").date().isoformat() for m in DATE.finditer(text)}
    return sorted(found)


def parse(path: Path) -> LawDocument:
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise FeedError("not valid UTF-8 text (binary or wrong encoding)") from None
    parts = raw.split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        raise FeedError("missing metadata header")
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        raise FeedError("metadata header is not valid YAML") from None
    if not isinstance(meta, dict) or any(not meta.get(k) for k in REQUIRED):
        raise FeedError(f"metadata header must contain {', '.join(REQUIRED)}")
    body = parts[2]
    marks = list(HEADING.finditer(body))
    if not marks:
        raise FeedError("no articles found (truncated file?)")
    articles = []
    for i, m in enumerate(marks):
        text = body[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(body)].strip()
        if not text:
            raise FeedError(f"Article {m.group(1)} is empty (truncated file?)")
        ident = f"Art. {m.group(1)}" + (f" (inserted by Art. {m.group(2)})" if m.group(2) else "")
        articles.append(LawArticle(id=ident, text=text, effective_dates=_dates(text)))
    try:
        return LawDocument(celex=str(meta["celex"]), title=str(meta["title"]), source=str(meta["source_url"]),
                           published=str(meta["published"]), articles=articles,
                           fictional=bool(meta.get("fictional", False)))
    except ValueError as exc:
        raise FeedError(f"invalid metadata: {str(exc).splitlines()[0]}") from None


def scan(feed: Path | None = None) -> dict[str, list[str]]:
    """Register new feed files. Returns celex ids per outcome: new, duplicate, quarantined (file names)."""
    out: dict[str, list[str]] = {"new": [], "duplicate": [], "quarantined": []}
    con = db.connect()
    for path in sorted((feed or settings.FEED).glob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if con.execute("select 1 from laws where path=? and sha=?", (str(path), sha)).fetchone():
            continue
        try:
            law = parse(path)
        except FeedError as exc:
            con.execute("insert or replace into laws(celex,sha,title,path,status,reason,doc_json,ts) "
                        "values(?,?,?,?,?,?,?,?)", (f"file:{path.name}", sha, path.name, str(path), "quarantined",
                                                    str(exc), "{}", audit.now()))
            audit.emit(None, "watcher", "WATCH", "escalation", f"Quarantined feed file {path.name}: {exc}")
            out["quarantined"].append(path.name)
            continue
        body_sha = hashlib.sha256(db.dumps([a.model_dump(mode="json") for a in law.articles]).encode()).hexdigest()
        known = con.execute("select sha, body_sha from laws where celex=?", (law.celex,)).fetchone()
        if known:  # same act published again: one run only
            audit.emit(None, "watcher", "WATCH", "watch", f"Duplicate publication of {law.celex} ignored")
            out["duplicate"].append(law.celex)
            continue
        con.execute("insert into laws(celex,sha,body_sha,title,path,status,doc_json,ts) values(?,?,?,?,?,?,?,?)",
                    (law.celex, sha, body_sha, law.title, str(path), "new", law.model_dump_json(), audit.now()))
        out["new"].append(law.celex)
    return out


def get_law(celex: str) -> LawDocument:
    row = db.connect().execute("select doc_json from laws where celex=? and status!='quarantined'",
                               (celex,)).fetchone()
    if row is None:
        raise KeyError(celex)
    return LawDocument.model_validate_json(row["doc_json"])


def laws() -> list[dict[str, Any]]:
    rows = db.connect().execute("select celex,title,status,reason,run_id,triage_json,ts from laws order by ts,celex")
    return [{**dict(r), "triage": json.loads(r["triage_json"]) if r["triage_json"] else None} for r in rows]


def set_law(celex: str, **fields: Any) -> None:
    sets = ",".join(f"{k}=?" for k in fields)
    db.connect().execute(f"update laws set {sets} where celex=?", [*fields.values(), celex])

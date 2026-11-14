"""Fetch official EU acts from the Publications Office and store verbatim excerpts.

    python tools/fetch_law.py titles 32025R0100 32025R0101 ...      # print the official title of each act
    python tools/fetch_law.py save <outdir> 32022R2554:3,19,28,30 32023R1114:1,2 32024R0886

`CELEX:articles` keeps only those articles; without a list the whole enacting part is kept.
Text is copied verbatim from the official English XHTML; nothing is paraphrased or generated.
Downloads are cached under var/lawcache/ (git-ignored).
"""
from __future__ import annotations

import hashlib
import html
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASE = "http://publications.europa.eu/resource/celex/"
EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"
CACHE = Path("var/lawcache")
ART = re.compile(r'<p[^>]*class="(?:oj-)?ti-art"[^>]*>(.*?)</p>', re.S)
SECTION = re.compile(r'<p[^>]*class="(?:oj-)?ti-section-1"')
END = re.compile(r'<p[^>]*class="(?:oj-)?(?:final|signatory)"|<div[^>]*class="(?:oj-)?final"')


def download(celex: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{celex}.html"
    if not path.exists():
        req = urllib.request.Request(
            BASE + celex, headers={"Accept": "application/xhtml+xml", "Accept-Language": "eng"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
    return path.read_text(encoding="utf-8")


def to_text(fragment: str) -> str:
    fragment = re.sub(r"\s+", " ", fragment)
    fragment = re.sub(r"<(?:/p|/div|br ?/?|/tr|/td)>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if not ln:
            continue
        # A point marker such as "(a)" or "1." alone on a line belongs to the next line.
        if out and re.fullmatch(r"\(?[a-z0-9]{1,4}[).]|[—–-]", out[-1]):
            out[-1] = f"{out[-1]} {ln}"
        else:
            out.append(ln)
    return "\n".join(out)


def title_of(doc: str) -> str:
    parts = re.findall(r'<p[^>]*class="(?:oj-)?doc-ti"[^>]*>(.*?)</p>', doc, re.S)
    if not parts:
        parts = re.findall(r'<p[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</p>', doc, re.S)
    return " ".join(to_text(p).replace("\n", " ") for p in parts[:3]).strip()


def published_of(doc: str) -> str:
    m = re.search(r'class="(?:oj-)?hd-date"[^>]*>\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', doc)
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def articles_of(doc: str) -> list[tuple[str, str]]:
    marks = list(ART.finditer(doc))
    out = []
    parent = ""
    inserted = False
    for i, m in enumerate(marks):
        stop = marks[i + 1].start() if i + 1 < len(marks) else len(doc)
        body = doc[m.end():stop]
        end = END.search(body) if i + 1 == len(marks) else SECTION.search(body)
        if end:  # drop the signature block, or the heading of the next chapter or section
            body = body[: end.start()]
        number = to_text(m.group(1)).replace("Article", "").strip()
        quoted = number[:1] in "\u2018'"
        number = number.lstrip("\u2018' ").strip()
        if quoted:  # an article quoted inside an amending article
            inserted = True
        elif inserted and parent.isdigit() and number == str(int(parent) + 1):
            inserted = False
        if inserted:
            number = f"{number} [inserted by Article {parent}]"
        else:
            parent = number
        out.append((number, to_text(body)))
    return out


def save(outdir: Path, spec: str) -> None:
    celex, _, wanted = spec.partition(":")
    keep = set(wanted.split(",")) if wanted else None
    doc = download(celex)
    arts = [(n, t) for n, t in articles_of(doc) if keep is None or n.split(" ")[0] in keep]
    body = "\n\n".join(f"## Article {n}\n\n{t}" for n, t in arts)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    title = title_of(doc).replace('"', "'")
    front = [
        "---",
        f"celex: \"{celex}\"",
        f"title: \"{title}\"",
        f"source_url: \"{EURLEX}{celex}\"",
        f"published: \"{published_of(doc)}\"",
        "language: en",
        f"retrieved_at: \"{date.today().isoformat()}\"",
        f"excerpt_articles: [{', '.join(n.split(' ')[0] for n, _ in arts)}]",
        f"complete: {'false' if keep else 'true'}",
        f"sha256: \"{sha}\"",
        "fictional: false",
        "---",
        "",
    ]
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{celex}.md").write_text("\n".join(front) + body + "\n", encoding="utf-8")
    print(f"{celex}: {len(arts)} articles, {len(body)} chars, published {published_of(doc)}")


def main(argv: list[str]) -> None:
    if argv[0] == "titles":
        for celex in argv[1:]:
            try:
                doc = download(celex)
                print(celex, published_of(doc), "|", title_of(doc)[:230])
            except Exception as exc:  # report and continue with the next act
                print(celex, "ERROR", type(exc).__name__, exc)
    elif argv[0] == "save":
        for spec in argv[2:]:
            save(Path(argv[1]), spec)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

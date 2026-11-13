"""
company_map.py - "Harta" firmei pentru agentul de Legal Change Automation.

Ideea: agentul NU citeste tot. Un crawler construieste o singura data (si apoi
incremental) o harta a tuturor resurselor firmei:
  - o FISA pentru fiecare resursa (unde e, ce tip e, cine raspunde, rezumat)
  - ENTITATI extrase din ea, cu linia exacta (cote TVA, referinte legale,
    date personale, clauze contractuale, constante din cod)
  - LEGATURI intre resurse (importuri in cod, trimiteri intre documente)
  - un index full-text pe SECTIUNI (articole de contract, functii din cod)

Cand apare o lege noua, agentul intreaba harta ("unde apare TVA 19%?") si
deschide doar fisierele si liniile indicate.

Usage:
  python company_map.py build --source drive=sample/drive --source github=sample/repo
  python company_map.py overview
  python company_map.py impact --entity tax_rate=19% --entity tax_rate=9% --keyword TVA
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path

DB_PATH = os.environ.get("COMPANY_MAP_DB", "company_map.sqlite")

# --------------------------------------------------------------------------
# 1. CONNECTORS - fiecare sursa de date (Drive, GitHub, OneDrive...) are un
#    conector cu aceeasi interfata. Pentru demo: foldere locale care simuleaza
#    Drive-ul si repo-ul. Pentru productie: inlocuiti cu API-urile reale
#    (Google Drive API, GitHub API, Microsoft Graph) - restul codului ramane.
# --------------------------------------------------------------------------

TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".java", ".yaml", ".yml", ".json", ".sql", ".csv"}


@dataclass
class RawResource:
    uri: str          # ex: drive://contracte/contract_x.md, github://billing/vat.py
    source: str       # drive / github / onedrive ...
    path: str         # cale relativa in sursa
    text: str


class LocalFolderConnector:
    def __init__(self, source: str, root: str):
        self.source, self.root = source, Path(root)

    def iter_resources(self):
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            text = read_text(p)
            if text is None:
                continue
            rel = p.relative_to(self.root).as_posix()
            yield RawResource(f"{self.source}://{rel}", self.source, rel, text)


def read_text(p: Path) -> str | None:
    ext = p.suffix.lower()
    try:
        if ext in TEXT_EXT:
            return p.read_text(encoding="utf-8", errors="replace")
        if ext == ".docx":
            import docx
            return "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
        if ext == ".pdf":
            import pypdf
            return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(str(p)).pages)
    except Exception as exc:  # fisier corupt -> il sarim, dar spunem
        print(f"  ! nu am putut citi {p}: {exc}")
    return None


# --------------------------------------------------------------------------
# 2. FISA RESURSEI + ENTITATI (extractie determinista, fara LLM)
# --------------------------------------------------------------------------

@dataclass
class Entity:
    etype: str        # tax_rate, legal_ref, personal_data, contract_term, money, code_symbol
    value: str        # valoare normalizata: "19%", "GDPR art. 6", "CNP", "fixed_price"
    line: int
    snippet: str


@dataclass
class Section:
    title: str
    start: int
    end: int


@dataclass
class Card:
    uri: str
    source: str
    path: str
    rtype: str        # code / config / contract / policy / prompt / document
    domain: str       # primul folder: billing, contracte, politici...
    sha: str
    summary: str = ""
    entities: list[Entity] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def classify(path: str, text: str) -> str:
    p = path.lower()
    if p.endswith((".py", ".js", ".ts", ".java", ".sql")):
        return "code"
    if p.endswith((".yaml", ".yml", ".json")):
        return "config"
    if "prompt" in p:
        return "prompt"
    if "contract" in p:
        return "contract"
    if "politic" in p or "policy" in p:
        return "policy"
    return "document"


VAT_WORDS = re.compile(r"\b(tva|vat|tax|cota|cotă|cote)\b", re.I)
PCT = re.compile(r"(?<![\d.])(\d{1,2})\s?%")
FRACTION = re.compile(r"(?<![\d.])0\.(0[5-9]|1\d|2[0-7])(?!\d)")    # 0.19, 0.09, 0.05 (cote 5-27%)
MULTIPLIER = re.compile(r"(?<![\d.])1\.(0[5-9]|1\d|2[0-7])(?!\d)")  # 1.19 -> 19%
LEGAL_REF = re.compile(r"\b(Legea|Legii|OUG|HG|Ordinul)\s*(nr\.?\s*)?\d+/\d{4}"
                       r"|\bGDPR\s*art\.?\s*\d+|\bRegulamentul\s*\(UE\)\s*\d+/\d+", re.I)
PERSONAL = {"CNP": r"\bCNP\b", "email": r"\be-?mail\b", "IBAN": r"\bIBAN\b",
            "adresa": r"\badres[aă]\b", "telefon": r"\btelefon\b"}
MONEY = re.compile(r"(\d[\d.]*(?:,\d+)?)\s*lei\b", re.I)
CONTRACT_TERMS = {
    "fixed_price": r"pre[țt]ul este fix|pre[țt] fix",
    "no_tax_adjustment": r"nu prevede ajustarea",
    "tax_adjusts_automatically": r"cota legal[ăa] [îi]n vigoare",
    "vat_included_price": r"tva inclus",
}
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")


def extract_entities(card: Card, text: str) -> None:
    lines = text.splitlines()
    vat_context_file = bool(VAT_WORDS.search(text)) or "vat" in card.path.lower()
    for i, line in enumerate(lines, 1):
        low = line.lower()
        snip = line.strip()[:160]
        # cote TVA: procente in documente / prompturi, fractii si multiplicatori in cod
        if VAT_WORDS.search(line) or (card.rtype == "code" and vat_context_file):
            for m in PCT.finditer(line):
                card.entities.append(Entity("tax_rate", f"{int(m.group(1))}%", i, snip))
            if card.rtype == "code":
                for m in FRACTION.finditer(line):
                    card.entities.append(Entity("tax_rate", f"{int(m.group(1))}%", i, snip))
                for m in MULTIPLIER.finditer(line):
                    card.entities.append(Entity("tax_rate", f"{int(m.group(1))}%", i,
                                                snip + "   [multiplicator brut->net]"))
        for m in LEGAL_REF.finditer(line):
            card.entities.append(Entity("legal_ref", re.sub(r"\s+", " ", m.group(0)), i, snip))
        for name, pat in PERSONAL.items():
            if re.search(pat, line, re.I):
                card.entities.append(Entity("personal_data", name, i, snip))
        if card.rtype in ("contract", "document", "policy"):
            for m in MONEY.finditer(line):
                card.entities.append(Entity("money", m.group(1) + " lei", i, snip))
            for name, pat in CONTRACT_TERMS.items():
                if re.search(pat, low):
                    card.entities.append(Entity("contract_term", name, i, snip))
    if card.rtype == "config" and card.path.endswith((".yaml", ".yml")):
        extract_yaml_rates(card, text)
    if card.path.endswith(".py"):
        extract_python(card, text)
    if card.rtype != "code":
        extract_heading_sections(card, lines)


def extract_yaml_rates(card: Card, text: str) -> None:
    import yaml
    try:
        data = yaml.safe_load(text)
    except Exception:
        return
    lines = text.splitlines()

    def walk(node, keypath):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, keypath + [str(k)])
        elif isinstance(node, (int, float)) and any("vat" in k or "tva" in k for k in keypath):
            leaf = keypath[-1]
            line_no = next((i for i, l in enumerate(lines, 1)
                            if re.match(rf"\s*{re.escape(leaf)}\s*:\s*{node}\s*$", l)), 0)
            value = f"{int(node * 100) if node < 1 else int(node)}%"
            card.entities.append(Entity("tax_rate", value, line_no, ".".join(keypath) + f" = {node}"))

    walk(data, [])


def extract_python(card: Card, text: str) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            if mod:
                card.imports.append(mod)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            card.sections.append(Section(node.name, node.lineno, node.end_lineno or node.lineno))
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    card.entities.append(Entity("code_symbol", t.id, node.lineno,
                                                f"{t.id} = {node.value.value}"))


def extract_heading_sections(card: Card, lines: list[str]) -> None:
    heads = [(i, HEADING.match(l).group(1).strip()) for i, l in enumerate(lines, 1) if HEADING.match(l)]
    for n, (start, title) in enumerate(heads):
        end = heads[n + 1][0] - 1 if n + 1 < len(heads) else len(lines)
        card.sections.append(Section(title, start, end))


# --------------------------------------------------------------------------
# 3. IMBOGATIRE CU LLM (optionala): rezumat de 1-2 propozitii per resursa.
#    Ruleaza o singura data per versiune de fisier (cache dupa hash), deci e
#    ieftina. Daca nu exista cheie OpenRouter, se foloseste un rezumat simplu.
# --------------------------------------------------------------------------

def summarize(card: Card, text: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        first = next((l.strip("# ").strip() for l in text.splitlines() if l.strip()), "")
        kinds = sorted({f"{e.etype}:{e.value}" for e in card.entities if e.etype != "code_symbol"})
        return f"{card.rtype} - {first[:100]}" + (f" | mentioneaza: {', '.join(kinds[:8])}" if kinds else "")
    import urllib.request
    body = {
        "model": os.environ.get("MAP_MODEL", "openai/gpt-4o-mini"),
        "messages": [{"role": "user", "content":
                      "Summarize in max 2 sentences what this company resource is and which "
                      "legal/fiscal/data-protection obligations it touches. Romanian.\n\n" + text[:6000]}],
    }
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------------------------
# 4. STOCARE: SQLite (fise, entitati, legaturi) + FTS5 (cautare pe sectiuni)
# --------------------------------------------------------------------------

SCHEMA = """
create table if not exists resources(uri text primary key, source text, path text, rtype text,
    domain text, sha text, summary text, n_lines int, body text);
create table if not exists entities(uri text, etype text, value text, line int, snippet text);
create table if not exists edges(src text, dst text, kind text);
create table if not exists sections(uri text, title text, start int, end_ int);
create virtual table if not exists chunks using fts5(uri unindexed, title, body);
create index if not exists ix_ent on entities(etype, value);
"""


def connect(db=DB_PATH):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def build(sources: list[tuple[str, str]], db=DB_PATH) -> None:
    con = connect(db)
    seen, changed = set(), 0
    for source, root in sources:
        for raw in LocalFolderConnector(source, root).iter_resources():
            seen.add(raw.uri)
            sha = hashlib.sha1(raw.text.encode()).hexdigest()
            old = con.execute("select sha from resources where uri=?", (raw.uri,)).fetchone()
            if old and old["sha"] == sha:
                continue                                   # incremental: nimic nou
            changed += 1
            card = Card(raw.uri, raw.source, raw.path, classify(raw.path, raw.text),
                        raw.path.split("/")[0] if "/" in raw.path else "(root)", sha)
            extract_entities(card, raw.text)
            card.summary = summarize(card, raw.text)
            save(con, card, raw.text)
    # sterge din harta ce nu mai exista in surse
    for row in con.execute("select uri from resources").fetchall():
        if row["uri"] not in seen:
            delete(con, row["uri"])
    link_imports(con)
    con.commit()
    print(f"Harta actualizata: {changed} resurse noi/modificate, {len(seen)} in total -> {db}")


def delete(con, uri):
    for t in ("resources", "entities", "sections", "chunks"):
        con.execute(f"delete from {t} where uri=?", (uri,))
    con.execute("delete from edges where src=? or dst=?", (uri, uri))


def save(con, card: Card, text: str) -> None:
    delete(con, card.uri)
    lines = text.splitlines()
    con.execute("insert into resources values(?,?,?,?,?,?,?,?,?)",
                (card.uri, card.source, card.path, card.rtype, card.domain, card.sha,
                 card.summary, len(lines), text))
    con.executemany("insert into entities values(?,?,?,?,?)",
                    [(card.uri, e.etype, e.value, e.line, e.snippet) for e in card.entities])
    sections = card.sections or [Section("(tot fisierul)", 1, len(lines))]
    for s in sections:
        con.execute("insert into sections values(?,?,?,?)", (card.uri, s.title, s.start, s.end))
        con.execute("insert into chunks values(?,?,?)",
                    (card.uri, s.title, "\n".join(lines[s.start - 1:s.end])))
    for imp in card.imports:
        con.execute("insert into edges values(?,?,?)", (card.uri, imp, "imports_module"))


def link_imports(con) -> None:
    """Transforma 'imports_module billing.vat' in legatura catre github://billing/vat.py."""
    by_module = {}
    for r in con.execute("select uri, path from resources where rtype='code'"):
        mod = r["path"].rsplit(".", 1)[0].replace("/", ".")
        by_module[mod] = r["uri"]
    con.execute("delete from edges where kind='imports'")
    for e in con.execute("select src, dst from edges where kind='imports_module'").fetchall():
        if e["dst"] in by_module:
            con.execute("insert into edges values(?,?,?)", (e["src"], by_module[e["dst"]], "imports"))


# --------------------------------------------------------------------------
# 5. UNELTELE PE CARE LE FOLOSESTE AGENTUL (navigare de sus in jos)
# --------------------------------------------------------------------------

class CompanyMap:
    def __init__(self, db=DB_PATH):
        self.con = connect(db)

    def overview(self) -> dict:
        """Nivelul 1: ce domenii exista si ce tipuri de entitati contin. Cateva sute de tokeni."""
        out = {}
        for r in self.con.execute("select domain, rtype, count(*) n from resources group by 1,2"):
            out.setdefault(r["domain"], {"resources": {}, "entity_types": {}})["resources"][r["rtype"]] = r["n"]
        for r in self.con.execute("""select r.domain, e.etype, count(*) n from entities e
                                     join resources r using(uri) group by 1,2"""):
            out[r["domain"]]["entity_types"][r["etype"]] = r["n"]
        return out

    def list_resources(self, domain: str) -> list[dict]:
        """Nivelul 2: fisele resurselor dintr-un domeniu (fara continut)."""
        return [dict(r) for r in self.con.execute(
            "select uri, rtype, summary, n_lines from resources where domain=?", (domain,))]

    def find(self, etype: str, value: str | None = None) -> list[dict]:
        """Unde apare o entitate? Returneaza fisierul + linia exacta."""
        q, args = "select uri, etype, value, line, snippet from entities where etype=?", [etype]
        if value:
            q, args = q + " and value=?", args + [value]
        return [dict(r) for r in self.con.execute(q, args)]

    def search(self, text: str, k: int = 8) -> list[dict]:
        """Cautare full-text pe sectiuni (articole de contract, functii)."""
        terms = " OR ".join(re.findall(r"\w+", text))
        return [dict(r) for r in self.con.execute(
            "select uri, title, snippet(chunks, 2, '[', ']', '...', 12) hit from chunks "
            "where chunks match ? order by rank limit ?", (terms, k))]

    def neighbors(self, uri: str) -> list[dict]:
        """Ce depinde de resursa asta si de ce depinde ea (ex: cine importa vat.py)."""
        return [dict(r) for r in self.con.execute(
            "select src, dst, kind from edges where (src=? or dst=?) and kind!='imports_module'",
            (uri, uri))]

    def read(self, uri: str, start: int = 1, end: int | None = None) -> str:
        """Nivelul 3: citeste DOAR liniile cerute (agentul nu deschide fisiere intregi)."""
        row = self.con.execute("select body from resources where uri=?", (uri,)).fetchone()
        if not row:
            return f"(resursa {uri} nu exista in harta)"
        lines = row["body"].splitlines()
        end = min(end or len(lines), len(lines))
        return "\n".join(f"{n:4d}| {lines[n - 1]}" for n in range(max(start, 1), end + 1))

    def impact(self, entities: list[tuple[str, str]], keywords: list[str] = ()) -> list[dict]:
        """Pentru o schimbare legislativa: toate locurile atinse, ordonate, cu dependentele lor."""
        hits: dict[str, dict] = {}
        for etype, value in entities:
            for f in self.find(etype, value):
                h = hits.setdefault(f["uri"], {"uri": f["uri"], "score": 0, "evidence": []})
                h["score"] += 3
                h["evidence"].append(f"L{f['line']} {f['value']}: {f['snippet']}")
        for kw in keywords:
            for s in self.search(kw):
                h = hits.setdefault(s["uri"], {"uri": s["uri"], "score": 0, "evidence": []})
                h["score"] += 1
                h["evidence"].append(f"sectiunea '{s['title']}': {s['hit']}")
        # extindere un pas in graf: cine foloseste fisierele lovite e si el in risc
        for uri in list(hits):
            for e in self.neighbors(uri):
                other = e["src"] if e["dst"] == uri else e["dst"]
                h = hits.setdefault(other, {"uri": other, "score": 0, "evidence": []})
                h["score"] += 1
                h["evidence"].append(f"depinde de {uri} ({e['kind']})")
        for h in hits.values():
            r = self.con.execute("select rtype, summary from resources where uri=?", (h["uri"],)).fetchone()
            h["rtype"], h["summary"] = (r["rtype"], r["summary"]) if r else ("?", "")
            h["evidence"] = list(dict.fromkeys(h["evidence"]))
        return sorted(hits.values(), key=lambda h: -h["score"])


# Definitiile uneltelor pentru LLM (format OpenAI / OpenRouter function calling).
TOOLS = [
    {"type": "function", "function": {"name": "overview", "description":
        "Harta de nivel inalt: domeniile firmei, tipurile de resurse si de entitati din fiecare.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_resources", "description":
        "Fisele resurselor dintr-un domeniu (fara continut).",
        "parameters": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}}},
    {"type": "function", "function": {"name": "find", "description":
        "Unde apare o entitate. etype: tax_rate|legal_ref|personal_data|contract_term|money|code_symbol.",
        "parameters": {"type": "object", "properties": {"etype": {"type": "string"},
                                                        "value": {"type": "string"}}, "required": ["etype"]}}},
    {"type": "function", "function": {"name": "search", "description":
        "Cautare full-text in sectiuni (articole de contract, functii de cod).",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "neighbors", "description":
        "Dependentele unei resurse (cine o importa / ce importa).",
        "parameters": {"type": "object", "properties": {"uri": {"type": "string"}}, "required": ["uri"]}}},
    {"type": "function", "function": {"name": "read", "description":
        "Citeste doar liniile start..end dintr-o resursa.",
        "parameters": {"type": "object", "properties": {"uri": {"type": "string"}, "start": {"type": "integer"},
                                                        "end": {"type": "integer"}}, "required": ["uri"]}}},
]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--source", action="append", required=True, help="nume=cale, ex: drive=sample/drive")
    sub.add_parser("overview")
    i = sub.add_parser("impact")
    i.add_argument("--entity", action="append", default=[], help="tip=valoare, ex: tax_rate=19%%")
    i.add_argument("--keyword", action="append", default=[])
    r = sub.add_parser("read")
    r.add_argument("uri"); r.add_argument("--start", type=int, default=1); r.add_argument("--end", type=int)
    a = ap.parse_args()
    if a.cmd == "build":
        build([tuple(s.split("=", 1)) for s in a.source])
    elif a.cmd == "overview":
        print(json.dumps(CompanyMap().overview(), indent=2, ensure_ascii=False))
    elif a.cmd == "impact":
        ents = [tuple(e.split("=", 1)) for e in a.entity]
        print(json.dumps(CompanyMap().impact(ents, a.keyword), indent=2, ensure_ascii=False))
    elif a.cmd == "read":
        print(CompanyMap().read(a.uri, a.start, a.end))


if __name__ == "__main__":
    main()

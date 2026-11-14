"""Fragments (L5 units) and deterministic signals, all with 1-based line numbers. No model calls."""
from __future__ import annotations

import ast
import re
from typing import Any

EXTRACTOR_VERSION = "1"
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
YAML_KEY = re.compile(r"^(\s*)([\w.-]+):\s*(.*?)\s*(?:#.*)?$")
COUNTRIES = ("Romania", "Germany", "Ireland", "Estonia", "Austria", "Netherlands", "France", "Luxembourg")
PATTERNS: dict[str, list[tuple[re.Pattern[str], Any]]] = {
    "legal_ref": [(re.compile(r"(?:Regulation|Directive) \(EU\) (?:No )?\d+/\d+|Art(?:icle|\.) ?\d+[a-z]?(?:\(\d+\))*"), None)],
    "currency": [(re.compile(r"\b(RON|EUR)\b"), None)],
    "jurisdiction": [(re.compile(r"\b(" + "|".join(COUNTRIES) + r")\b"), None)],
    "personal_data": [(re.compile(r"\bIBAN\b"), "IBAN"), (re.compile(r"\bCNP\b"), "CNP"),
                      (re.compile(r"\be-?mail\b|@", re.I), "email"), (re.compile(r"\bphone\b", re.I), "phone")],
    "payment_flow": [(re.compile(r"\binstant\b", re.I), "instant"), (re.compile(r"credit transfer", re.I), "credit transfer"),
                     (re.compile(r"one-time password|\botp\b", re.I), "one-time password"),
                     (re.compile(r"\bpayee", re.I), "payee"), (re.compile(r"authori[sz]", re.I), "authorisation")],
}
WITHIN = re.compile(r"within (\d+|one|two) (business days?|hours?|days?|months?)", re.I)
CONSTANT = re.compile(r"^([A-Z][A-Z0-9_]*_(HOURS|DAYS))\s*=\s*(\d+)")
MONEY = re.compile(r"(\d+(?:\.\d+)?) ?(EUR|RON)\b")
KIND = re.compile(r"\b(standard|instant)\b", re.I)


def _markdown(lines: list[str]) -> list[dict[str, Any]]:
    marks = [(i, m.group(2)) for i, line in enumerate(lines, 1) if (m := HEADING.match(line))]
    if not marks:
        first = next((line.strip() for line in lines if line.strip()), "")
        return [{"title": first[:80], "kind": "section", "start": 1, "end": len(lines)}] if first else []
    out = []
    for n, (start, title) in enumerate(marks):
        end = marks[n + 1][0] - 1 if n + 1 < len(marks) else len(lines)
        while end > start and not lines[end - 1].strip():
            end -= 1
        out.append({"title": title[:120], "kind": "section", "start": start, "end": end})
    return out


def _python(text: str, lines: list[str]) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [{"title": "module (unparsable)", "kind": "section", "start": 1, "end": max(len(lines), 1)}]
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            out.append({"title": f"{'class' if kind == 'class' else 'def'} {node.name}", "kind": kind,
                        "start": node.lineno, "end": node.end_lineno or node.lineno})
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out.append({"title": lines[node.lineno - 1].strip()[:120], "kind": "constant",
                        "start": node.lineno, "end": node.end_lineno or node.lineno})
    return out


def _yaml(lines: list[str]) -> list[dict[str, Any]]:
    out, stack = [], []
    for i, line in enumerate(lines, 1):
        m = YAML_KEY.match(line)
        if not m or line.lstrip().startswith("#"):
            continue
        indent = len(m.group(1))
        stack = [(d, k) for d, k in stack if d < indent] + [(indent, m.group(2))]
        if m.group(3):
            key = ".".join(k for _, k in stack)
            out.append({"title": f"{key} = {m.group(3)}", "kind": "config_key", "start": i, "end": i,
                        "key": key, "value": m.group(3)})
    return out


def fragments(path: str, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not text.strip():
        return []
    if path.endswith(".py"):
        return _python(text, lines)
    if path.endswith((".yaml", ".yml")):
        return _yaml(lines)
    return _markdown(lines)


def fee_key(currency: str, kind: str, amount: str) -> str:
    return f"{currency.lower()}.{kind.lower()}={float(amount):.2f}"


def entities(path: str, text: str, frags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(etype: str, value: str, line: int, snippet: str) -> None:
        out.append({"etype": etype, "value": value, "line": line, "snippet": snippet.strip()[:160]})

    for number, line in enumerate(text.splitlines(), 1):
        for etype, patterns in PATTERNS.items():
            seen = set()
            for pattern, fixed in patterns:
                for m in pattern.finditer(line):
                    value = fixed or re.sub(r"\s+", " ", m.group(0))
                    if value not in seen:
                        seen.add(value)
                        add(etype, value, number, line)
        for m in WITHIN.finditer(line):
            unit = m.group(2).lower()
            add("deadline", f"{m.group(1).lower()} {unit if unit.endswith('s') else unit + 's'}", number, line)
        if (m := CONSTANT.match(line)):
            add("deadline", f"{m.group(3)} {m.group(2).lower()}", number, line)
        money, kind = MONEY.search(line), KIND.search(line)
        if money and kind:
            add("fee", fee_key(money.group(2), kind.group(1), money.group(1)), number, line)
    for frag in frags:
        if frag["kind"] in ("function", "class", "constant"):
            add("code_symbol", frag["title"].split("=")[0].replace("def ", "").replace("class ", "").strip(),
                frag["start"], frag["title"])
        if frag["kind"] == "config_key" and re.fullmatch(r"\d+(\.\d+)?", frag["value"]):
            parts = frag["key"].split(".")
            if len(parts) >= 3 and parts[-1] in ("standard", "instant"):
                add("fee", fee_key(parts[-2], parts[-1], frag["value"]), frag["start"], frag["title"])
    return out

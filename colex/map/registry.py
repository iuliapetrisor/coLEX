"""Counterparty registry: canonical names and aliases resolve to one id."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

SUFFIXES = {"srl", "sarl", "ltd", "gmbh", "inc", "bv", "sa", "ou", "llc", "plc", "ag", "nv", "spa"}


def norm_name(name: str) -> str:
    """Lower case, no diacritics, no punctuation, no legal-form suffix."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\bs\.?\s?a\.?\s?r\.?\s?l\b\.?", "sarl", text)
    tokens = [t for t in re.sub(r"[^a-z0-9 ]", " ", text.replace(".", "")).split() if t not in SUFFIXES]
    return " ".join(tokens)


class Registry:
    def __init__(self, data: dict[str, Any]) -> None:
        self.items = data["counterparties"]
        self.by_name: dict[str, str] = {}
        self.patterns: list[tuple[re.Pattern[str], str]] = []
        for cp in self.items:
            names = [cp["name"], *cp.get("aliases", [])]
            for name in names:
                self.by_name[norm_name(name)] = cp["id"]
            for name in sorted(set(names), key=len, reverse=True):
                flags = 0 if name.isupper() else re.I
                self.patterns.append((re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])", flags), cp["id"]))

    def resolve(self, name: str) -> str | None:
        return self.by_name.get(norm_name(name))

    def mentions(self, text: str) -> list[tuple[str, int]]:
        """(counterparty id, line) for each counterparty mentioned on each line."""
        out = []
        for number, line in enumerate(text.splitlines(), 1):
            seen = set()
            for pattern, cp_id in self.patterns:
                if cp_id not in seen and pattern.search(line):
                    seen.add(cp_id)
                    out.append((cp_id, number))
        return out

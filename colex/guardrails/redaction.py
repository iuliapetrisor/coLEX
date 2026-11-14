"""Personal-data redaction (brief §4.3).

`redact` / `unredact` use a reversible mapping that stays in local memory: prompts carry
placeholders such as ⟨IBAN_1⟩. `mask` is the one-way form used before anything is stored
(checkpoints, audit events, exports).
"""
from __future__ import annotations

import hashlib
import re

from colex.guardrails.log_scrub import scrub as scrub_tokens

_WEIGHTS = (2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9)
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2} ?(?:[A-Z0-9]{4} ?){3,7}[A-Z0-9]{0,4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("CNP", re.compile(r"(?<!\d)[1-8]\d{12}(?!\d)")),
    ("PHONE", re.compile(r"(?<![\w+])(?:\+40|0040|0)7\d{2}[ .-]?\d{3}[ .-]?\d{3}(?!\d)")),
]


def _valid_cnp(value: str) -> bool:
    check = sum(int(d) * w for d, w in zip(value[:12], _WEIGHTS)) % 11
    return (1 if check == 10 else check) == int(value[12])


class RedactionCtx:
    """Mapping placeholder ↔ original value. Never stored, never sent to a model."""

    def __init__(self) -> None:
        self.forward: dict[str, str] = {}
        self.backward: dict[str, str] = {}

    def placeholder(self, kind: str, value: str) -> str:
        if value not in self.forward:
            # Derived from the value, so the same value gives the same placeholder in every call.
            token = f"⟨{kind}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:6]}⟩"
            self.forward[value], self.backward[token] = token, value
        return self.forward[value]


def redact(text: str, ctx: RedactionCtx) -> str:
    for kind, pattern in PATTERNS:
        def swap(match: re.Match[str], kind: str = kind) -> str:
            value = match.group(0).strip()
            if kind == "CNP" and not _valid_cnp(value):
                return match.group(0)
            return ctx.placeholder(kind, value) + match.group(0)[len(value):]
        text = pattern.sub(swap, text)
    return text


def unredact(text: str, ctx: RedactionCtx) -> str:
    """Display only. Never use the result in a prompt, a checkpoint or an export."""
    for token, value in ctx.backward.items():
        text = text.replace(token, value)
    return text


def mask(text: str) -> str:
    """One-way: personal data and token-shaped secrets replaced before storage."""
    for kind, pattern in PATTERNS:
        def swap(match: re.Match[str], kind: str = kind) -> str:
            if kind == "CNP" and not _valid_cnp(match.group(0)):
                return match.group(0)
            return f"⟨{kind}⟩"
        text = pattern.sub(swap, text)
    return scrub_tokens(text)

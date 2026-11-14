"""Legal feed contracts (brief §1.4 and §4.2). Law text is official text, never generated."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from colex.contracts.common import Confidence, Contract, NonBlank


class LawArticle(Contract):
    id: NonBlank
    text: str
    effective_dates: list[date] = Field(default_factory=list)


class LawDocument(Contract):
    """`fictional=True` marks a hypothetical act: it must be shown as FICTIONAL - DEMO ONLY."""

    celex: NonBlank
    title: NonBlank
    source: NonBlank
    published: date
    articles: list[LawArticle] = Field(default_factory=list)
    fictional: bool = False


class TriageResult(Contract):
    """`law_id` is the CELEX number of the act."""

    law_id: NonBlank
    relevant: bool
    articles_flagged: list[str] = Field(default_factory=list)
    reason: NonBlank
    confidence: Confidence
    matched_profile_facts: list[str] = Field(default_factory=list)

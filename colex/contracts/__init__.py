"""coLEX data contracts (brief §4.2), shared by every agent.

Frozen after G0: a change needs a `docs/DECISIONS.md` entry and a `CONTRACTS_VERSION` bump.
"""
from colex.contracts.common import Confidence, Contract, Evidence, LineRange, NonBlank
from colex.contracts.law import LawArticle, LawDocument, TriageResult
from colex.contracts.map import (
    Counterparty,
    Edge,
    Entity,
    Fragment,
    Lifecycle,
    RegulatoryTag,
    ResourceCard,
    Rollup,
    Sensitivity,
    TaxonomyNode,
)
from colex.contracts.runtime import AuditEvent, Checkpoint, ConfigVersion, Run
from colex.contracts.work import ChangeRequest, ImpactItem, Notification, Question, SuiteResult

CONTRACTS_VERSION = "2"

__all__ = [
    "CONTRACTS_VERSION", "Contract", "Confidence", "Evidence", "LineRange", "NonBlank",
    "TaxonomyNode", "Rollup", "ResourceCard", "Sensitivity", "Lifecycle", "RegulatoryTag",
    "Counterparty", "Fragment", "Entity", "Edge",
    "LawDocument", "LawArticle", "TriageResult",
    "ImpactItem", "Question", "Notification", "ChangeRequest", "SuiteResult",
    "AuditEvent", "Run", "Checkpoint", "ConfigVersion",
]

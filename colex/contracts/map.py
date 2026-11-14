"""Company Map contracts (brief §3 and §4.2)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from colex.contracts.common import Confidence, Contract, Evidence, LineRange, NonBlank, NonNegInt

Level = Literal["L0", "L1", "L2", "L3"]
Source = Literal["onedrive", "gdrive", "confluence", "jira", "intranet", "repo"]
InfoType = Literal[
    "contract", "customer_terms", "fee_schedule", "policy", "procedure", "register",
    "code", "config", "ticket", "page", "prompt", "law",
]
OwnershipSource = Literal["explicit", "inferred", "unknown"]
ObligationStatus = Literal["compliant", "gap", "unknown"]
LifecycleStatus = Literal["draft", "active", "expired", "superseded"]
CounterpartyType = Literal["ict_provider", "client", "partner", "auditor"]
EdgeKind = Literal[
    "governed_by", "implements", "same_counterparty", "references",
    "depends_on", "same_owner", "regulated_by",
]


class Rollup(Contract):
    """Bottom-up aggregate kept on every L0-L3 node (brief §3.1)."""

    resource_count_by_type: dict[str, NonNegInt] = Field(default_factory=dict)
    entity_histogram: dict[str, NonNegInt] = Field(default_factory=dict)
    owners: dict[str, NonNegInt] = Field(default_factory=dict)
    counterparties: list[str] = Field(default_factory=list)
    regulatory_tags: list[str] = Field(default_factory=list)


class TaxonomyNode(Contract):
    node_id: NonBlank
    parent_id: str | None = None
    level: Level
    name: NonBlank
    path: NonBlank
    summary: str = ""
    rollup: Rollup = Field(default_factory=Rollup)


class Sensitivity(Contract):
    personal_data_categories: list[str] = Field(default_factory=list)
    confidentiality: str | None = None


class Lifecycle(Contract):
    status: LifecycleStatus | None = None
    effective_date: date | None = None
    renewal_date: date | None = None
    last_modified: datetime | None = None


class RegulatoryTag(Contract):
    """Link from a resource to a law article, e.g. `CELEX:32022R2554 Art. 30(2)(b)`."""

    citation: NonBlank
    status: ObligationStatus = "unknown"


class ResourceCard(Contract):
    """One L4 resource with its facets. `owner_team=None` means the owner is unknown."""

    uri: NonBlank
    source: Source
    info_type: InfoType
    primary_path: NonBlank
    secondary_paths: list[str] = Field(default_factory=list)
    owner_team: str | None = None
    owner_role: str | None = None
    approver_role: str | None = None
    legal_steward: str | None = None
    ownership_source: OwnershipSource
    counterparties: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity = Field(default_factory=Sensitivity)
    lifecycle: Lifecycle = Field(default_factory=Lifecycle)
    regulatory_tags: list[RegulatoryTag] = Field(default_factory=list)
    classification_confidence: Confidence
    sha: NonBlank
    map_version_id: NonBlank

    @model_validator(mode="after")
    def _ownership_is_consistent(self) -> "ResourceCard":
        if (self.owner_team is None) != (self.ownership_source == "unknown"):
            raise ValueError('owner_team must be empty exactly when ownership_source is "unknown"')
        return self


class Counterparty(Contract):
    """`supports_critical_function=None` means unknown."""

    counterparty_id: NonBlank
    canonical_name: NonBlank
    aliases: list[str] = Field(default_factory=list)
    type: CounterpartyType
    supports_critical_function: bool | None = None
    data_location: str | None = None
    subcontractors: list[str] = Field(default_factory=list)


class Fragment(Contract):
    """One L5 unit: a section, clause, function, class or config key."""

    uri: NonBlank
    title: str
    kind: NonBlank
    lines: LineRange


class Entity(Contract):
    """A deterministic signal found at one line of a resource."""

    uri: NonBlank
    etype: NonBlank
    value: str
    line: int = Field(ge=1)
    snippet: str = ""


class Edge(Contract):
    """Typed cross-link. `src` and `dst` are resource URIs or node paths."""

    src: NonBlank
    dst: NonBlank
    kind: EdgeKind
    evidence: Evidence

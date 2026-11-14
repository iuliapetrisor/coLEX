"""Shared building blocks for the data contracts."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class Contract(BaseModel):
    """Base of every contract model. Unknown fields are rejected, so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


# An identifier, citation or other short text that must not be empty or blank.
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegInt = Annotated[int, Field(ge=0)]
# A token count, cost or other amount: finite and never negative.
NonNegFinite = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class LineRange(Contract):
    """Inclusive, 1-based line range inside one resource."""

    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> "LineRange":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class Evidence(Contract):
    """Where a claim comes from: a map URI plus the cited lines."""

    uri: NonBlank
    lines: LineRange

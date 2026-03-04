"""Eval case format for the Phase 3 evaluation harness."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models import IncidentRequest


class EvalRubric(BaseModel):
    """Rules that define a "good" agent response for a given eval case."""

    expected_status: Literal["triaged", "needs_info"] | None = Field(
        default=None,
        description="If set, the response status must match exactly.",
    )
    min_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Response confidence must be >= this value.",
    )
    require_actions: bool = Field(
        default=True,
        description="At least one recommended action must be present.",
    )
    require_runbook_evidence: bool = Field(
        default=False,
        description="At least one evidence item sourced from a runbook must be present.",
    )
    forbidden_phrases: list[str] = Field(
        default_factory=list,
        description="Strings that must NOT appear in root_cause or summary.",
    )
    max_latency_ms: float | None = Field(
        default=None,
        description="If set, response latency must be below this threshold.",
    )


class EvalCase(BaseModel):
    """A single eval case used by the pytest runner."""

    id: str = Field(..., description="Unique identifier for this eval case.")
    description: str = Field(..., description="Human-readable explanation of what this case tests.")
    input_payload: IncidentRequest = Field(
        ..., description="The incident request sent to the agent."
    )
    expected_schema: dict = Field(
        default_factory=dict,
        description="Optional extra JSON-schema constraints applied to the raw response dict.",
    )
    rubric: EvalRubric = Field(
        default_factory=EvalRubric,
        description="Scoring rules for this eval case.",
    )

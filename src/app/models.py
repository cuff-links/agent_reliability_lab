"""Pydantic models and enums for the Agent Reliability Lab API."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Discrete severity levels for incidents."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentRequest(BaseModel):
    """Payload accepted by the `/incident` endpoint."""

    incident_id: str = Field(..., description="Unique identifier for the incident ticket.")
    run_id: str = Field(..., description="Airflow/Orchestration run identifier.")
    dag_id: str = Field(..., description="DAG identifier tied to the failing workflow.")
    severity: IncidentSeverity = IncidentSeverity.medium
    summary: str = Field(..., description="Short natural language description of the problem.")
    reporter: str = Field(..., description="User or system that filed the incident.")
    keywords: list[str] = Field(
        default_factory=list,
        description="Optional list of keywords/symptoms supplied by the reporter.",
        max_length=5,
    )
    context: str | None = Field(
        default=None,
        description="Additional free-form context such as dashboards or hypothesis.",
    )


class EvidenceItem(BaseModel):
    """Evidence that supports the agent's output."""

    source: Literal["logs", "dag", "runbook"]
    title: str
    content: str


class ActionItem(BaseModel):
    """Recommended next step for the incident responder."""

    description: str
    owner: str
    priority: Literal["low", "medium", "high"]


class RequestMetrics(BaseModel):
    """Basic metrics captured per incident request."""

    latency_ms: float = Field(..., ge=0)
    tool_count: int = Field(..., ge=0)
    reasoning_steps: int = Field(..., ge=0)
    token_usage: int = Field(..., ge=0)
    estimated_cost_usd: float = Field(..., ge=0)


class AgentResponse(BaseModel):
    """Structured output returned by the agent after running tools."""

    incident_id: str
    status: Literal["triaged", "needs_info"]
    summary: str
    root_cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_actions: list[ActionItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    metrics: RequestMetrics

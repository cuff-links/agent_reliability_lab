"""SQLAlchemy ORM models for the Agent Reliability Lab persistence layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    __allow_unmapped__ = True


class EvalCaseRecord(Base):
    """Stores the definition of each eval case (upserted before every eval run)."""

    __tablename__ = "eval_cases"

    case_id = mapped_column(String, primary_key=True)
    description = mapped_column(Text, nullable=False)
    input_payload = mapped_column(JSONB, nullable=False)
    rubric = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=_now)

    runs: list[EvalRunRecord] = relationship("EvalRunRecord", back_populates="case")


class ModelVersion(Base):
    """Tracks which agent version produced a set of runs."""

    __tablename__ = "model_versions"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False, unique=True)
    description = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), default=_now)


class EvalRunRecord(Base):
    """One row per individual agent run (one repetition of one eval case)."""

    __tablename__ = "eval_runs"

    id = mapped_column(String, primary_key=True, default=_uuid)
    case_id = mapped_column(String, ForeignKey("eval_cases.case_id"), nullable=False)
    model_version = mapped_column(String, nullable=False, default="deterministic-v1")
    run_index = mapped_column(Integer, nullable=False)
    started_at = mapped_column(DateTime(timezone=True))
    completed_at = mapped_column(DateTime(timezone=True))
    passed = mapped_column(Boolean, nullable=False)
    agent_response = mapped_column(JSONB)

    case: EvalCaseRecord = relationship("EvalCaseRecord", back_populates="runs")
    score: ScoreRecord = relationship("ScoreRecord", back_populates="run", uselist=False)
    step_traces: list[StepTraceRecord] = relationship("StepTraceRecord", back_populates="run")
    tool_calls: list[ToolCallRecord] = relationship("ToolCallRecord", back_populates="run")


class ScoreRecord(Base):
    """Pass/fail breakdown for a single eval run."""

    __tablename__ = "scores"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id = mapped_column(String, ForeignKey("eval_runs.id"), nullable=False)
    schema_valid = mapped_column(Boolean, nullable=False)
    status_match = mapped_column(Boolean, nullable=False)
    confidence_ok = mapped_column(Boolean, nullable=False)
    actions_present = mapped_column(Boolean, nullable=False)
    runbook_evidence_ok = mapped_column(Boolean, nullable=False)
    forbidden_phrases_ok = mapped_column(Boolean, nullable=False)
    latency_ok = mapped_column(Boolean, nullable=False)
    latency_ms = mapped_column(Float)
    cost_usd = mapped_column(Float)
    token_usage = mapped_column(Integer)

    run: EvalRunRecord = relationship("EvalRunRecord", back_populates="score")


class StepTraceRecord(Base):
    """Per-tool-call execution trace, ordered by step_index within a run."""

    __tablename__ = "step_traces"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id = mapped_column(String, ForeignKey("eval_runs.id"), nullable=False)
    step_index = mapped_column(Integer, nullable=False)
    step_name = mapped_column(String, nullable=False)
    tool_called = mapped_column(String, nullable=True)
    input_summary = mapped_column(Text)
    output_summary = mapped_column(Text)
    duration_ms = mapped_column(Float)
    status = mapped_column(String)

    run: EvalRunRecord = relationship("EvalRunRecord", back_populates="step_traces")


class ToolCallRecord(Base):
    """Raw tool call record — mirrors WorkflowMetrics.tool_details."""

    __tablename__ = "tool_calls"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id = mapped_column(String, ForeignKey("eval_runs.id"), nullable=False)
    tool_name = mapped_column(String, nullable=False)
    duration_ms = mapped_column(Float)
    status = mapped_column(String)
    retries = mapped_column(Integer)

    run: EvalRunRecord = relationship("EvalRunRecord", back_populates="tool_calls")

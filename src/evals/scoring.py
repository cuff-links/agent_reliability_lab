"""Scoring functions for eval case runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models import AgentResponse
from evals.models import EvalRubric


@dataclass
class RunScore:
    """Score for a single agent run against one eval case."""

    case_id: str
    run_index: int

    # individual check results
    schema_valid: bool
    status_match: bool
    confidence_ok: bool
    actions_present: bool
    runbook_evidence_ok: bool
    forbidden_phrases_ok: bool
    latency_ok: bool

    # raw stats (for aggregation and consistency checks)
    latency_ms: float
    cost_usd: float
    token_usage: int
    response_status: str
    response_confidence: float

    @property
    def passed(self) -> bool:
        return all([
            self.schema_valid,
            self.status_match,
            self.confidence_ok,
            self.actions_present,
            self.runbook_evidence_ok,
            self.forbidden_phrases_ok,
            self.latency_ok,
        ])

    def failures(self) -> list[str]:
        return [
            name
            for name, ok in {
                "schema_valid": self.schema_valid,
                "status_match": self.status_match,
                "confidence_ok": self.confidence_ok,
                "actions_present": self.actions_present,
                "runbook_evidence_ok": self.runbook_evidence_ok,
                "forbidden_phrases_ok": self.forbidden_phrases_ok,
                "latency_ok": self.latency_ok,
            }.items()
            if not ok
        ]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        d["failures"] = self.failures()
        return d


def score_response(
    case_id: str,
    run_index: int,
    response: AgentResponse,
    rubric: EvalRubric,
) -> RunScore:
    """Score one AgentResponse against a rubric. schema_valid=True is implied
    by the fact that we received an AgentResponse at all."""
    combined_text = (response.root_cause + " " + response.summary).lower()

    return RunScore(
        case_id=case_id,
        run_index=run_index,
        schema_valid=True,
        status_match=(
            rubric.expected_status is None
            or response.status == rubric.expected_status
        ),
        confidence_ok=(
            rubric.min_confidence is None
            or response.confidence >= rubric.min_confidence
        ),
        actions_present=(
            not rubric.require_actions or bool(response.recommended_actions)
        ),
        runbook_evidence_ok=(
            not rubric.require_runbook_evidence
            or any(e.source == "runbook" for e in response.evidence)
        ),
        forbidden_phrases_ok=not any(
            phrase.lower() in combined_text for phrase in rubric.forbidden_phrases
        ),
        latency_ok=(
            rubric.max_latency_ms is None
            or response.metrics.latency_ms <= rubric.max_latency_ms
        ),
        latency_ms=response.metrics.latency_ms,
        cost_usd=response.metrics.estimated_cost_usd,
        token_usage=response.metrics.token_usage,
        response_status=response.status,
        response_confidence=response.confidence,
    )


def failed_run_score(case_id: str, run_index: int) -> RunScore:
    """Returns an all-False score for when the agent crashes entirely."""
    return RunScore(
        case_id=case_id,
        run_index=run_index,
        schema_valid=False,
        status_match=False,
        confidence_ok=False,
        actions_present=False,
        runbook_evidence_ok=False,
        forbidden_phrases_ok=False,
        latency_ok=False,
        latency_ms=0.0,
        cost_usd=0.0,
        token_usage=0,
        response_status="",
        response_confidence=0.0,
    )

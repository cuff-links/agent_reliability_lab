"""Functions to persist eval runs and traces to Postgres."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import AgentResponse
from db.models import (
    EvalCaseRecord,
    EvalRunRecord,
    ScoreRecord,
    StepTraceRecord,
    ToolCallRecord,
)
from evals.models import EvalCase
from evals.scoring import RunScore


def persist_eval_run(
    *,
    session: Session,
    case: EvalCase,
    score: RunScore,
    response: AgentResponse,
    tool_details: list[dict],
    run_id: str,
    run_index: int,
    started_at: datetime,
    completed_at: datetime,
    model_version: str = "deterministic-v1",
) -> None:
    """Upsert the eval case, then insert run + score + traces + tool calls."""
    _upsert_eval_case(session, case)

    run = EvalRunRecord(
        id=run_id,
        case_id=case.id,
        model_version=model_version,
        run_index=run_index,
        started_at=started_at,
        completed_at=completed_at,
        passed=score.passed,
        agent_response=response.model_dump(mode="json"),
    )
    session.add(run)

    session.add(
        ScoreRecord(
            run_id=run_id,
            schema_valid=score.schema_valid,
            status_match=score.status_match,
            confidence_ok=score.confidence_ok,
            actions_present=score.actions_present,
            runbook_evidence_ok=score.runbook_evidence_ok,
            forbidden_phrases_ok=score.forbidden_phrases_ok,
            latency_ok=score.latency_ok,
            latency_ms=score.latency_ms,
            cost_usd=score.cost_usd,
            token_usage=score.token_usage,
        )
    )

    for i, detail in enumerate(tool_details):
        session.add(
            StepTraceRecord(
                run_id=run_id,
                step_index=i,
                step_name=detail["name"],
                tool_called=detail["name"],
                input_summary=detail.get("input_summary", ""),
                output_summary=detail.get("output_summary", ""),
                duration_ms=detail.get("duration_ms"),
                status=detail.get("status"),
            )
        )
        session.add(
            ToolCallRecord(
                run_id=run_id,
                tool_name=detail["name"],
                duration_ms=detail.get("duration_ms"),
                status=detail.get("status"),
                retries=detail.get("retries", 0),
            )
        )


def _upsert_eval_case(session: Session, case: EvalCase) -> None:
    stmt = (
        pg_insert(EvalCaseRecord)
        .values(
            case_id=case.id,
            description=case.description,
            input_payload=case.input_payload.model_dump(mode="json"),
            rubric=case.rubric.model_dump(mode="json"),
        )
        .on_conflict_do_update(
            index_elements=["case_id"],
            set_={"description": case.description},
        )
    )
    session.execute(stmt)

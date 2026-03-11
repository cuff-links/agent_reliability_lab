#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi>=0.110.0,<0.112.0",
#     "uvicorn[standard]>=0.30.0,<0.31.0",
# ]
# ///
"""FastAPI entry point for the Agent Reliability Lab API."""
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
import uvicorn

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent import GuardrailConfig, run_incident_playbook
from app.models import AgentResponse, IncidentRequest, RunDetail, RunTrace, ScoreDetail, TraceStep

app = FastAPI(title="Agent Reliability Lab API")


@app.get("/healthz", tags=["system"], summary="Liveness probe")
async def health_check() -> dict[str, str]:
    """Simple health endpoint for readiness/liveness checks."""
    return {"status": "ok"}


@app.post(
    "/incident",
    tags=["incident"],
    response_model=AgentResponse,
    summary="Run deterministic agent triage",
)
async def triage_incident(payload: IncidentRequest) -> AgentResponse:
    """Trigger the deterministic workflow to triage an incident."""
    result = run_incident_playbook(payload, config=GuardrailConfig())
    return result.response


@app.get(
    "/runs/{run_id}",
    tags=["runs"],
    response_model=RunDetail,
    summary="Fetch a persisted eval run with its score",
)
async def get_run(run_id: str) -> RunDetail:
    """Return the eval run record and scoring breakdown for run_id."""
    from db.session import SessionLocal
    from db.models import EvalRunRecord, ScoreRecord

    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL unset)")

    with SessionLocal() as session:
        run = session.get(EvalRunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        score_row = session.query(ScoreRecord).filter_by(run_id=run_id).first()
        if score_row is None:
            raise HTTPException(status_code=404, detail=f"Score for run {run_id!r} not found")

        return RunDetail(
            run_id=run.id,
            case_id=run.case_id,
            run_index=run.run_index,
            model_version=run.model_version,
            passed=run.passed,
            started_at=run.started_at,
            completed_at=run.completed_at,
            agent_response=run.agent_response,
            score=ScoreDetail(
                schema_valid=score_row.schema_valid,
                status_match=score_row.status_match,
                confidence_ok=score_row.confidence_ok,
                actions_present=score_row.actions_present,
                runbook_evidence_ok=score_row.runbook_evidence_ok,
                forbidden_phrases_ok=score_row.forbidden_phrases_ok,
                latency_ok=score_row.latency_ok,
                passed=run.passed,
                latency_ms=score_row.latency_ms,
                cost_usd=score_row.cost_usd,
                token_usage=score_row.token_usage,
            ),
        )


@app.get(
    "/runs/{run_id}/trace",
    tags=["runs"],
    response_model=RunTrace,
    summary="Fetch the step-by-step execution trace for a run",
)
async def get_run_trace(run_id: str) -> RunTrace:
    """Return ordered step traces for run_id so you can see exactly what the agent did."""
    from db.session import SessionLocal
    from db.models import StepTraceRecord

    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL unset)")

    with SessionLocal() as session:
        rows = (
            session.query(StepTraceRecord)
            .filter_by(run_id=run_id)
            .order_by(StepTraceRecord.step_index)
            .all()
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"No trace found for run {run_id!r}")

        return RunTrace(
            run_id=run_id,
            steps=[
                TraceStep(
                    step_index=r.step_index,
                    step_name=r.step_name,
                    tool_called=r.tool_called,
                    input_summary=r.input_summary or "",
                    output_summary=r.output_summary or "",
                    duration_ms=r.duration_ms or 0.0,
                    status=r.status or "",
                )
                for r in rows
            ],
        )


def main() -> None:
    """Run the FastAPI application via uvicorn."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

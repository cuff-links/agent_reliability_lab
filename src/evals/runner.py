"""Runs a single eval case N times and returns scored results."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from agent.workflow import run_incident_playbook
from evals.models import EvalCase
from evals.scoring import RunScore, failed_run_score, score_response

RUNS_PER_CASE: int = 3


def run_eval_case(case: EvalCase, n: int = RUNS_PER_CASE, persist: bool = False) -> list[RunScore]:
    """Execute the agent against eval_case n times, score each run, and optionally persist."""
    scores: list[RunScore] = []

    for i in range(n):
        started_at = datetime.now(timezone.utc)
        tool_details: list[dict] = []
        try:
            result = run_incident_playbook(case.input_payload)
            tool_details = result.tool_details
            score = score_response(case.id, i, result.response, case.rubric)
            response = result.response
        except Exception:
            score = failed_run_score(case.id, i)
            response = None

        completed_at = datetime.now(timezone.utc)
        scores.append(score)

        if persist and os.getenv("DATABASE_URL") and response is not None:
            _persist_run(
                case=case,
                score=score,
                response=response,
                tool_details=tool_details,
                run_index=i,
                started_at=started_at,
                completed_at=completed_at,
            )

    return scores


def consistency_score(scores: list[RunScore]) -> float:
    """Fraction of runs that agree on status with the first run (1.0 = fully consistent)."""
    if not scores:
        return 0.0
    reference = scores[0].response_status
    return sum(1 for s in scores if s.response_status == reference) / len(scores)


def _persist_run(
    *,
    case: EvalCase,
    score: RunScore,
    response,
    tool_details: list[dict],
    run_index: int,
    started_at: datetime,
    completed_at: datetime,
) -> None:
    from db.persist import persist_eval_run
    from db.session import SessionLocal

    if SessionLocal is None:
        return

    run_id = str(uuid.uuid4())
    with SessionLocal() as session:
        persist_eval_run(
            session=session,
            case=case,
            score=score,
            response=response,
            tool_details=tool_details,
            run_id=run_id,
            run_index=run_index,
            started_at=started_at,
            completed_at=completed_at,
        )

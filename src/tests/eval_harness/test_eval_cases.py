"""Parametrized eval harness: runs each eval case N times and scores the results."""
from __future__ import annotations

from typing import Any

import pytest

from evals.models import EvalCase
from evals.runner import RUNS_PER_CASE, consistency_score, run_eval_case


def test_eval_case(eval_case: EvalCase, eval_store: list[dict[str, Any]]) -> None:
    scores = run_eval_case(eval_case, persist=True)

    consistency = consistency_score(scores)
    eval_store.append(
        {
            "case_id": eval_case.id,
            "description": eval_case.description,
            "consistency": consistency,
            "scores": [s.to_dict() for s in scores],
        }
    )

    failed_runs = [s for s in scores if not s.passed]
    if failed_runs:
        details = "\n".join(
            f"  run {s.run_index}: {s.failures()}" for s in failed_runs
        )
        pytest.fail(
            f"{eval_case.id} failed {len(failed_runs)}/{RUNS_PER_CASE} runs:\n{details}"
        )

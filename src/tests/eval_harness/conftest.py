"""Session-scoped fixtures and report hooks for the eval harness."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import pytest

from evals.models import EvalCase

EVAL_CASES_DIR = Path(__file__).resolve().parents[1] / "eval_cases"
REPORT_PATH = Path(__file__).resolve().parents[3] / "eval_report.json"


def _load_eval_cases() -> list[EvalCase]:
    return [
        EvalCase.model_validate_json(p.read_text())
        for p in sorted(EVAL_CASES_DIR.glob("*.json"))
    ]


def pytest_configure(config: pytest.Config) -> None:
    config._eval_runs: list[dict[str, Any]] = []  # type: ignore[attr-defined]


@pytest.fixture(scope="session", params=_load_eval_cases(), ids=lambda c: c.id)
def eval_case(request: pytest.FixtureRequest) -> EvalCase:
    return request.param  # type: ignore[return-value]


@pytest.fixture(scope="session")
def eval_store(request: pytest.FixtureRequest) -> list[dict[str, Any]]:
    return request.config._eval_runs  # type: ignore[attr-defined]


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    runs: list[dict[str, Any]] = getattr(config, "_eval_runs", [])
    if not runs:
        return

    all_scores = [score for entry in runs for score in entry["scores"]]
    if not all_scores:
        return

    passed_count = sum(1 for s in all_scores if s["passed"])
    latencies = [s["latency_ms"] for s in all_scores]
    total_cost = sum(s["cost_usd"] for s in all_scores)
    pass_rate = passed_count / len(all_scores) * 100
    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
    p95 = sorted_lat[p95_idx]

    terminalreporter.write_sep("=", "EVAL SUMMARY")
    terminalreporter.write_line(
        f"Cases: {len(runs)}  |  "
        f"Runs: {len(all_scores)}  |  "
        f"Pass rate: {passed_count}/{len(all_scores)} ({pass_rate:.1f}%)"
    )
    terminalreporter.write_line(
        f"Latency p95: {p95:.1f}ms  |  Total cost: ${total_cost:.6f}"
    )
    terminalreporter.write_line("")

    for entry in runs:
        scores = entry["scores"]
        n_passed = sum(1 for s in scores if s["passed"])
        avg_lat = statistics.mean(s["latency_ms"] for s in scores)
        consistency = entry.get("consistency", 1.0)
        all_failures = [f for s in scores for f in s["failures"]]
        status_str = "PASS" if n_passed == len(scores) else "FAIL"

        line = (
            f"  [{status_str}] {entry['case_id']:<30s}"
            f"  {n_passed}/{len(scores)} runs"
            f"  avg_lat={avg_lat:.1f}ms"
            f"  consistency={consistency:.0%}"
        )
        if all_failures:
            line += f"  failures={sorted(set(all_failures))}"
        terminalreporter.write_line(line)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "summary": {
                    "total_cases": len(runs),
                    "total_runs": len(all_scores),
                    "passed": passed_count,
                    "pass_rate": round(pass_rate / 100, 4),
                    "p95_latency_ms": round(p95, 2),
                    "total_cost_usd": round(total_cost, 6),
                },
                "cases": runs,
            },
            indent=2,
        )
    )
    terminalreporter.write_line(f"\nReport written → {REPORT_PATH}")

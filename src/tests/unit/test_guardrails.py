from __future__ import annotations

import time

import pytest

from app.models import IncidentRequest, IncidentSeverity
from agent.guardrails import GuardrailConfig
from agent.workflow import run_incident_playbook
from tools.deterministic import LogResult


@pytest.fixture()
def base_request() -> IncidentRequest:
    return IncidentRequest(
        incident_id="INC-9999",
        run_id="ingest_run_20250225",
        dag_id="customer_activity_dag",
        severity=IncidentSeverity.medium,
        summary="Investigate intermittent timeout",
        reporter="cli-user",
    )


def test_timeout_triggers_needs_info_fallback(monkeypatch: pytest.MonkeyPatch, base_request: IncidentRequest) -> None:
    config = GuardrailConfig(tool_timeout_seconds=0.01, max_tool_retries=0)
    monkeypatch.setattr("agent.workflow.get_logs", _slow_log)

    response = run_incident_playbook(base_request, config=config).response

    assert response.status == "needs_info"
    assert "timeout" in response.summary.lower()
    assert response.recommended_actions[0].owner == base_request.reporter


def test_tool_failure_after_retries(monkeypatch: pytest.MonkeyPatch, base_request: IncidentRequest) -> None:
    config = GuardrailConfig(max_tool_retries=1)

    def _boom(_: str) -> LogResult:  # pragma: no cover - raises immediately
        raise RuntimeError("boom")

    monkeypatch.setattr("agent.workflow.get_logs", _boom)

    response = run_incident_playbook(base_request, config=config).response

    assert response.status == "needs_info"
    assert "guardrail" in response.summary.lower()


def _slow_log(run_id: str) -> LogResult:
    time.sleep(0.02)
    return LogResult(run_id=run_id, text="delayed logs")

"""Unit tests for the deterministic agent workflow."""
from __future__ import annotations

import pytest

from app.models import IncidentRequest, IncidentSeverity
from agent.workflow import run_incident_playbook


@pytest.fixture()
def incident_request() -> IncidentRequest:
    return IncidentRequest(
        incident_id="INC-1234",
        run_id="ingest_run_20250225",
        dag_id="customer_activity_dag",
        severity=IncidentSeverity.high,
        summary="Load warehouse task continues to timeout",
        reporter="pagerduty",
        keywords=["timeout"],
    )


def test_run_incident_playbook_returns_actions_and_metrics(incident_request: IncidentRequest) -> None:
    result = run_incident_playbook(incident_request)
    response = result.response

    assert response.incident_id == incident_request.incident_id
    assert response.confidence > 0
    assert response.recommended_actions
    assert any(item.source == "runbook" for item in response.evidence)
    assert response.status == "triaged"
    assert response.metrics.latency_ms >= 0
    assert response.metrics.tool_count >= 1
    assert result.tool_details  # Phase 4: trace data is available

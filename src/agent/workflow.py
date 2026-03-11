"""Deterministic agent workflow for triaging incidents."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from textwrap import shorten
from time import perf_counter
from typing import Any, Tuple

from agent.guardrails import (
    GuardrailBreach,
    GuardrailConfig,
    ToolFailure,
    ToolRunner,
    WorkflowMetrics,
)
from app.models import (
    ActionItem,
    AgentResponse,
    EvidenceItem,
    IncidentRequest,
    IncidentSeverity,
    RequestMetrics,
)
from tools.deterministic import get_dag_metadata, get_logs, search_runbooks


@dataclass
class WorkflowResult:
    """Return value of run_incident_playbook — bundles the response with raw trace data."""

    response: AgentResponse
    tool_details: list[dict[str, Any]]


def run_incident_playbook(
    request: IncidentRequest, config: GuardrailConfig | None = None
) -> WorkflowResult:
    """Execute the deterministic workflow with guardrail enforcement."""

    guardrails = config or GuardrailConfig()
    metrics = WorkflowMetrics()
    clock_start = perf_counter()
    runner = ToolRunner(guardrails, metrics)

    try:
        log_result = runner.call("get_logs", get_logs, request.run_id)
        _record_reasoning(metrics, guardrails)
        dag_metadata = runner.call("get_dag_metadata", get_dag_metadata, request.dag_id)
        _record_reasoning(metrics, guardrails)
        keyword = _select_keyword(request)
        runbook_hits = (
            runner.call("search_runbooks", search_runbooks, keyword) if keyword else []
        )
        if keyword:
            _record_reasoning(metrics, guardrails)

        root_cause, confidence = _infer_root_cause(log_result.text, keyword)
        actions = _build_actions(request, dag_metadata.owner, keyword)
        evidence = _build_evidence(log_result.text, dag_metadata.description, runbook_hits)
        summary = _compose_summary(request, dag_metadata.description, root_cause)
        metadata = _build_metadata(
            request,
            dag_metadata.owner,
            runbook_hits[0].title if runbook_hits else "none",
            metrics,
        )

        response = _build_response(
            request=request,
            status="triaged",
            summary=summary,
            root_cause=root_cause,
            confidence=confidence,
            actions=actions,
            evidence=evidence,
            metadata=metadata,
            metrics=metrics,
            clock_start=clock_start,
        )
        return WorkflowResult(response=response, tool_details=list(metrics.tool_details))
    except (GuardrailBreach, ToolFailure) as exc:
        response = _fallback_response(request, f"guardrail triggered: {exc}", metrics, clock_start)
        return WorkflowResult(response=response, tool_details=list(metrics.tool_details))
    except Exception as exc:  # noqa: BLE001 - we need to degrade gracefully
        response = _fallback_response(request, f"unexpected failure: {exc}", metrics, clock_start)
        return WorkflowResult(response=response, tool_details=list(metrics.tool_details))


def _select_keyword(request: IncidentRequest) -> str | None:
    if request.keywords:
        return request.keywords[0]
    tokens = [token.strip(",.?!") for token in request.summary.split()]
    return tokens[0].lower() if tokens else None


def _infer_root_cause(log_text: str, keyword: str | None = None) -> Tuple[str, float]:
    kw = (keyword or "").lower()
    lowered = log_text.lower()

    # Keyword from the reporter is a strong primary signal — check it first.
    if "permission" in kw:
        return (
            "Credential or permission issue detected; validate service account and IAM roles.",
            0.67,
        )
    if "timeout" in kw or "timeout" in lowered:
        return (
            "Warehouse writer timed out waiting for cluster capacity; retries exhausted.",
            0.82,
        )
    if "permission" in lowered:
        return (
            "Credential or permission issue detected in logs; validate service account.",
            0.67,
        )
    return (
        "Unable to map logs to known patterns; manual investigation required.",
        0.4,
    )


def _build_actions(
    request: IncidentRequest, owner: str, keyword: str | None
) -> list[ActionItem]:
    priority = "high" if request.severity in {IncidentSeverity.high, IncidentSeverity.critical} else "medium"
    owner_name = owner or "data-oncall"
    actions = [
        ActionItem(
            description="Review `load_warehouse` task logs and confirm downstream cluster health.",
            owner=owner_name,
            priority=priority,
        ),
        ActionItem(
            description="Re-run the failed Airflow task once cluster capacity is stable.",
            owner=owner_name,
            priority=priority,
        ),
    ]
    if keyword:
        actions.append(
            ActionItem(
                description=f"Consult runbook guidance for keyword '{keyword}' and post update in #data-ops.",
                owner=owner_name,
                priority="medium",
            )
        )
    return actions


def _build_evidence(
    log_text: str, dag_description: str, runbook_hits
) -> list[EvidenceItem]:
    evidence = [
        EvidenceItem(
            source="logs",
            title="Log excerpt",
            content=shorten(log_text.replace("\n", " | "), width=280, placeholder=" …"),
        ),
        EvidenceItem(
            source="dag",
            title="DAG metadata",
            content=dag_description,
        ),
    ]
    if runbook_hits:
        best = runbook_hits[0]
        evidence.append(
            EvidenceItem(
                source="runbook",
                title=best.title,
                content=best.snippet,
            )
        )
    return evidence


def _compose_summary(request: IncidentRequest, dag_description: str, root_cause: str) -> str:
    components = [
        f"Incident {request.incident_id} for DAG {request.dag_id}",
        f"severity={request.severity.value}",
        request.summary,
        dag_description,
        f"Assessment: {root_cause}",
    ]
    return "; ".join(components)


def _record_reasoning(metrics: WorkflowMetrics, config: GuardrailConfig) -> None:
    metrics.record_reasoning_step()
    if metrics.reasoning_steps > config.max_reasoning_steps:
        raise GuardrailBreach("Reasoning step limit exceeded")


def _build_metadata(
    request: IncidentRequest, dag_owner: str, runbook_title: str, metrics: WorkflowMetrics
) -> dict[str, str]:
    ok_calls = sum(1 for detail in metrics.tool_details if detail["status"] == "ok")
    failed_calls = metrics.tool_calls - ok_calls
    return {
        "run_id": request.run_id,
        "dag_id": request.dag_id,
        "dag_owner": dag_owner,
        "matched_runbook": runbook_title,
        "tool_calls_ok": str(ok_calls),
        "tool_calls_failed": str(failed_calls),
    }


def _build_response(
    *,
    request: IncidentRequest,
    status: str,
    summary: str,
    root_cause: str,
    confidence: float,
    actions: list[ActionItem],
    evidence: list[EvidenceItem],
    metadata: dict[str, str],
    metrics: WorkflowMetrics,
    clock_start: float,
) -> AgentResponse:
    metrics.latency_ms = (perf_counter() - clock_start) * 1000
    metrics.token_usage = _estimate_tokens(summary, actions, evidence)
    metrics.estimated_cost_usd = round(metrics.token_usage * 0.000002, 6)

    return AgentResponse(
        incident_id=request.incident_id,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        root_cause=root_cause,
        confidence=confidence,
        recommended_actions=actions,
        evidence=evidence,
        metadata=metadata,
        metrics=_as_request_metrics(metrics),
    )


def _fallback_response(
    request: IncidentRequest, reason: str, metrics: WorkflowMetrics, clock_start: float
) -> AgentResponse:
    summary = f"Incident {request.incident_id} requires more info: {reason}"
    action = ActionItem(
        description="Provide updated logs, DAG context, or runbook hints so the agent can retry.",
        owner=request.reporter,
        priority="medium",
    )
    metadata = {
        "run_id": request.run_id,
        "dag_id": request.dag_id,
        "error": reason,
    }
    return _build_response(
        request=request,
        status="needs_info",
        summary=summary,
        root_cause="Insufficient context to determine root cause.",
        confidence=0.2,
        actions=[action],
        evidence=[],
        metadata=metadata,
        metrics=metrics,
        clock_start=clock_start,
    )


def _estimate_tokens(summary: str, actions: list[ActionItem], evidence: list[EvidenceItem]) -> int:
    text = summary + " " + " ".join(a.description for a in actions)
    text += " " + " ".join(item.content for item in evidence)
    approx_tokens = ceil(len(text.split()) * 1.3)
    return int(approx_tokens)


def _as_request_metrics(metrics: WorkflowMetrics) -> RequestMetrics:
    return RequestMetrics(
        latency_ms=round(metrics.latency_ms, 2),
        tool_count=metrics.tool_calls,
        reasoning_steps=metrics.reasoning_steps,
        token_usage=metrics.token_usage,
        estimated_cost_usd=round(metrics.estimated_cost_usd, 6),
    )

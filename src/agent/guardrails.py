"""Guardrail configuration, tool execution helpers, and metrics collection."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable


class GuardrailBreach(Exception):
    """Raised when workflow guardrails are exceeded (e.g., tool call budget)."""


class ToolFailure(Exception):
    """Raised when a tool fails after exhausting retries."""


class ToolTimeout(Exception):
    """Raised when a tool execution exceeds the configured timeout."""


@dataclass(slots=True)
class GuardrailConfig:
    max_tool_calls: int = 5
    max_reasoning_steps: int = 5
    tool_timeout_seconds: float = 2.0
    max_tool_retries: int = 1


@dataclass(slots=True)
class WorkflowMetrics:
    tool_calls: int = 0
    reasoning_steps: int = 0
    latency_ms: float = 0.0
    token_usage: int = 0
    estimated_cost_usd: float = 0.0
    tool_details: list[dict[str, Any]] = field(default_factory=list)

    def record_tool(self, *, name: str, duration_ms: float, status: str, retries: int) -> None:
        self.tool_calls += 1
        self.tool_details.append(
            {
                "name": name,
                "duration_ms": round(duration_ms, 2),
                "status": status,
                "retries": retries,
            }
        )

    def record_reasoning_step(self) -> None:
        self.reasoning_steps += 1


class ToolRunner:
    """Executes deterministic tools with guardrail enforcement."""

    def __init__(self, config: GuardrailConfig, metrics: WorkflowMetrics):
        self._config = config
        self._metrics = metrics
        self._invocations = 0

    def call(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self._invocations >= self._config.max_tool_calls:
            raise GuardrailBreach("Maximum tool invocations exceeded")
        self._invocations += 1
        attempts = 0
        last_exc: Exception | None = None
        while attempts <= self._config.max_tool_retries:
            attempts += 1
            start = perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (perf_counter() - start) * 1000
                if duration_ms > self._config.tool_timeout_seconds * 1000:
                    raise ToolTimeout(
                        f"{name} exceeded timeout of {self._config.tool_timeout_seconds:.2f}s"
                    )
                self._metrics.record_tool(
                    name=name, duration_ms=duration_ms, status="ok", retries=attempts - 1
                )
                return result
            except Exception as exc:  # noqa: BLE001 - guardrail requires catching all
                duration_ms = (perf_counter() - start) * 1000
                status = "timeout" if isinstance(exc, ToolTimeout) else "error"
                self._metrics.record_tool(
                    name=name, duration_ms=duration_ms, status=status, retries=attempts - 1
                )
                last_exc = exc
                if attempts > self._config.max_tool_retries:
                    raise ToolFailure(f"{name} failed: {exc}") from exc
        raise ToolFailure(f"{name} failed: {last_exc}")

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

from fastapi import FastAPI
import uvicorn

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent import GuardrailConfig, run_incident_playbook
from app.models import AgentResponse, IncidentRequest

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
    """Trigger the Phase 1 deterministic workflow to triage an incident."""
    return run_incident_playbook(payload, config=GuardrailConfig())


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

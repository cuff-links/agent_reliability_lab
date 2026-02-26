from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections.abc import Iterator

import pytest
import uvicorn

from app.api import app


@pytest.fixture(scope="module")
def api_server() -> Iterator[tuple[str, int]]:
    host = "127.0.0.1"
    port = 8059
    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("FastAPI server failed to start within timeout")
        time.sleep(0.05)
    try:
        yield host, port
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_health_endpoint(api_server: tuple[str, int]) -> None:
    host, port = api_server
    with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=5) as response:
        payload = json.loads(response.read())
    assert payload["status"] == "ok"


def test_incident_endpoint_returns_metrics(api_server: tuple[str, int]) -> None:
    host, port = api_server
    data = {
        "incident_id": "INC-5678",
        "run_id": "ingest_run_20250225",
        "dag_id": "customer_activity_dag",
        "severity": "high",
        "summary": "Warehouse load keeps timing out",
        "reporter": "integration-test",
        "keywords": ["timeout"],
    }
    request = urllib.request.Request(
        url=f"http://{host}:{port}/incident",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        payload = json.loads(response.read())

    assert payload["incident_id"] == data["incident_id"]
    assert payload["status"] == "triaged"
    assert "latency_ms" in payload["metrics"]
    assert payload["metrics"]["tool_count"] >= 1

# Agent Reliability Lab (ARL)

Agent Reliability Lab (ARL) is a production-inspired evaluation and observability platform for agentic AI workflows.

It is designed to simulate how a Quality Engineer would validate, trace, and regression-test LLM-based systems before and after deployment.

The system demonstrates:

- Agent orchestration with tool usage
- Retrieval-Augmented Generation (RAG)
- Structured outputs with strict schemas
- Evaluation pipelines (regression testing)
- Observability and trace capture
- Latency and cost tracking
- Production feedback loop → new eval case promotion

---

## 🚀 Local Development (uv)

1. Install [`uv`](https://docs.astral.sh/uv/) locally (single binary installer recommended).
2. From the repo root run `uv run poe dev` — this installs FastAPI + uvicorn (from `pyproject.toml`) and starts the dev server with reload enabled on `http://127.0.0.1:8000`.
3. Use `uv run poe api` for a non-reload server (matches production flags).
4. Hit `GET /healthz` to verify the service.
5. Run regression suites with `uv run poe test` (unit guardrails) or `uv run poe test_integration` (spins up uvicorn and makes real HTTP calls).

`uv` caches dependencies automatically, so the command acts as the Makefile-style `make dev` target without needing a separate virtual environment. The helper scripts set `PYTHONPATH=src`, so you can run the stack without installing the package in editable mode.

---

## 🔁 Incident Endpoint (Phase 1)

The Phase 1 MVP adds a deterministic triage endpoint:

- **Route:** `POST /incident`
- **Request Body:** `IncidentRequest` (incident + dag/run metadata)
- **Response Body:** `AgentResponse` (structured summary, root cause, actions, evidence)

Example:

```bash
uv run curl -X POST http://127.0.0.1:8000/incident \
  -H "Content-Type: application/json" \
  -d '{
        "incident_id": "INC-1234",
        "run_id": "ingest_run_20250225",
        "dag_id": "customer_activity_dag",
        "severity": "high",
        "summary": "Load warehouse task continues to timeout",
        "reporter": "pagerduty",
        "keywords": ["timeout"]
      }'
```

Response contains `status="triaged"`, a `root_cause` string, recommended actions, and evidence pulled from the local fixtures in `data/`.

Run the regression tests with:

```bash
uv run poe test              # unit + mocked guardrail tests
uv run poe test_integration  # boots FastAPI via uvicorn and calls the live server
```

---

## 🛡 Phase 2 Guardrails

Phase 2 hardens the MVP:

- Guardrail-configurable limits on tool invocations and reasoning steps.
- Tool runner enforces timeouts + bounded retries, converting failures into a `needs_info` fallback instead of 500s.
- All responses pass through the Pydantic `AgentResponse` schema, now enriched with a `metrics` object (`latency_ms`, `token_usage`, `estimated_cost_usd`, etc.).
- Request metadata captures DAG ownership plus aggregated tool-call stats so operators can audit why a decision happened.

Every `/incident` call now returns these guardrailed metrics, making it easy to plug basic observability panels on top.

---

## 🧠 Project Goal

Build and evaluate a Data Pipeline Incident Triage Agent that:

1. Accepts an incident (logs, metadata, context)
2. Retrieves relevant runbooks and prior incidents
3. Calls deterministic tools
4. Produces structured RCA + recommended next actions
5. Logs traces and metrics
6. Runs against a standardized evaluation suite
7. Tracks regression across model or prompt versions

---

## 🏗 Architecture Overview

The system is organized into layered components:

---

## 1️⃣ API Layer (Application Interface)

### Tech

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic (schema validation)

### Responsibilities

- Accept incident payloads
- Trigger agent workflows
- Trigger evaluation suite runs
- Expose run results and traces
- Provide endpoints for promoting failures to eval cases

Example endpoints:

- POST /incident
- POST /eval/run
- GET /eval/{run_id}
- GET /trace/{run_id}
- POST /promote/{run_id}

---

## 2️⃣ Agent Workflow Layer

### Tech

- LangGraph
- OpenAI or Anthropic API
- JSON schema enforcement

## Responsibilities

- Define deterministic workflow graph
- Manage step transitions
- Call tools
- Perform reasoning steps
- Emit structured JSON output

Workflow Graph:

Intake → Retrieval → Tool Calls → Reasoning → Structured Output

Each step logs:

- model used
- tokens consumed
- latency
- tool call metadata

---

## 3️⃣ Tooling Layer (Deterministic Functions)

### Tech

- Pure Python
- Typed interfaces
- JSON schemas

## Example Tools

- get_logs(run_id)
- get_dag_metadata(dag_id)
- search_runbooks(query)
- query_incident_db(sql)

## Responsibilities

- Deterministic outputs
- Explicit schemas
- Timeout + retry protection
- Safe execution boundaries
- Fully mockable for testing

All tool calls are recorded in trace storage.

---

## 4️⃣ Retrieval Layer (RAG)

### Tech

- Qdrant (Docker) or pgvector
- SentenceTransformers or OpenAI embeddings
- Markdown runbook corpus

### Responsibilities

- Embed runbooks and prior incidents
- Perform semantic similarity search
- Return top-k evidence chunks
- Provide citation metadata

This layer enables:

- Grounded responses
- Factual scoring
- Evidence-based validation

---

## 5️⃣ Data Layer

### Tech

- Postgres (Docker)
- SQLAlchemy
- Alembic (migrations)

## Core Tables

eval_cases
eval_runs
tool_calls
step_traces
scores
model_versions

### Responsibilities

- Persist evaluation cases
- Store run metadata
- Store trace events
- Store scoring metrics
- Track regression over time

---

## 6️⃣ Evaluation Layer (AI Quality Engineering Core)

### Tech

- pytest
- Custom scoring framework
- JSON schema validation
- Optional LLM-as-judge for semantic scoring

### Responsibilities

Each eval case contains:

- input payload
- expected schema
- rubric rules
- severity classification

Scoring dimensions:

1. Schema validity (hard pass/fail)
2. Evidence grounding (did it cite retrieved docs?)
3. Actionability (contains concrete next steps?)
4. Consistency (variance across N runs)
5. Latency (p50 / p95)
6. Token cost

Eval results generate:

- pass rate
- failure category breakdown
- regression diff vs previous model version
- cost summary

---

## 7️⃣ Observability Layer

### Tech

- OpenTelemetry
- Structured JSON logging
- Trace ID correlation
- Postgres trace storage

### Responsibilities

- Record each agent step
- Record each tool call
- Capture model version
- Capture token usage
- Capture execution time

Enables:

- Failure debugging
- Root cause analysis
- Model comparison

---

## 8️⃣ CI / Automation Layer

### Tech

- GitHub Actions
- Docker Compose
- pytest

### Responsibilities

- Run evaluation suite on PR
- Fail build on regression threshold
- Store historical metrics

---

## 🧪 Example Evaluation Workflow

1. Load 25 eval cases
2. Run agent N times per case
3. Score each dimension
4. Store metrics
5. Produce JSON + console report
6. Compare against baseline model version

---

## 💰 Cost Considerations

The system can run in two modes:

### Local / Free Mode

- Local embedding model
- Small hosted LLM usage
- All services via Docker
- Approximate cost: $0–$20/month

### Cloud Mode

- Hosted LLM
- Managed Postgres
- Managed vector DB
- CI runs using LLM calls
- Approximate cost: $20–$150/month depending on volume

Cost control mechanisms:

- Token logging
- Budget caps
- Smaller models for retrieval/classification
- Larger models only for reasoning
- Caching embeddings
- Fixed evaluation batch sizes

---

## 🚀 Why This Project Matters

This repo demonstrates:

- Production-style agent engineering
- Evaluation infrastructure
- Observability of non-deterministic systems
- Regression safety for AI workflows
- Cost-aware AI deployment

It represents the core skillset of an AI Quality Engineer building reliability into agentic systems.

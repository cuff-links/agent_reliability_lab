# Agent Reliability Lab (ARL) — Build Order Checklist

This is the recommended implementation sequence (optimized for fast progress + minimal over-engineering).

---

## Phase 0 — Repo + Local Dev Setup

- [x] Create repo + `README.md`
- [x] Add Python 3.12 project setup (`uv` or `poetry`)
- [x] Add formatting/linting (ruff + black) and basic CI placeholder
- [x] Create initial folder structure:
  - [x] `app/` (FastAPI)
  - [x] `agent/` (workflow)
  - [x] `tools/` (deterministic tools)
  - [x] `data/` (fixtures + runbooks)
  - [x] `tests/` (eval harness later)

**Deliverable:** `make dev` (or equivalent) that runs the API locally.

---

## Phase 1 — End-to-End Agent MVP (No DB, No Vector, No Evals)

**Goal:** `Input → Agent → Tools → Structured JSON Output`

- [x] FastAPI endpoint: `POST /incident`
- [x] Define output schema (Pydantic model) for the agent response
- [x] Implement 2–3 deterministic tools (pure Python, predictable outputs)
  - [x] `get_logs(run_id)` (reads from local fixture files)
  - [x] `get_dag_metadata(dag_id)` (reads from local fixture JSON)
  - [x] `search_runbooks(keyword)` (simple keyword search over markdown)
- [x] Implement agent workflow (single-pass, no loops yet)
  - [x] intake → tool calls → reasoning → structured JSON

**Deliverable:** Curl request returns a valid JSON response every time.

---

## Phase 2 — Guardrails + Determinism (Quality Mindset Starts Here)

**Goal:** Make outputs valid, bounded, and inspectable.

- [x] Strict schema enforcement (fail if JSON is invalid)
- [x] Step limits (max tool calls / max reasoning steps)
- [x] Tool protections:
  - [x] timeouts
  - [x] retries (limited)
  - [x] safe error handling and “ask for more info” fallback
- [x] Basic metrics captured per request:
  - [x] latency
  - [x] token usage (if supported by provider)
  - [x] estimated cost

**Deliverable:** The agent fails safely and predictably.

---

## Phase 3 — Evaluation Harness (Core AI Quality Engineering Layer)

**Goal:** Turn behavior into a regression-tested system.

- [x] Define eval case format (JSON/YAML), e.g.:
  - [x] `id`
  - [x] `input_payload`
  - [x] `expected_schema`
  - [x] `rubric` (rules for “good”)
    - `expected_status`, `min_confidence`, `require_actions`, `require_runbook_evidence`, `forbidden_phrases`, `max_latency_ms`
  - Pydantic models: `src/evals/models.py` (`EvalCase`, `EvalRubric`)
- [ ] Add 10–20 eval cases under `tests/eval_cases/` (5 starter cases added: eval_001–eval_005)
- [ ] Build `pytest` runner:
  - [ ] runs agent against each eval case
  - [ ] runs each case N times (e.g., 3) for consistency checks
- [ ] Add scoring functions:
  - [ ] schema validity (hard pass/fail)
  - [ ] required fields present
  - [ ] actionability (must include next steps)
  - [ ] consistency (variance across repeated runs)
  - [ ] latency + cost stats
- [ ] Output a summary report (console + JSON artifact)

**Deliverable:** `pytest` produces an eval report + pass rate.

---

## Phase 4 — Persistence + Tracing (Debuggability + Model Comparisons)

**Goal:** Store runs, traces, and metrics like a real platform.

- [ ] Add Docker Compose with Postgres
- [ ] Create DB schema/tables:
  - [ ] `eval_cases`
  - [ ] `eval_runs`
  - [ ] `step_traces`
  - [ ] `tool_calls`
  - [ ] `scores`
  - [ ] `model_versions`
- [ ] Persist each eval run + scores
- [ ] Persist per-step traces:
  - [ ] step name
  - [ ] tool called
  - [ ] inputs/outputs (redacted/safe)
  - [ ] duration
- [ ] Add endpoints:
  - [ ] `GET /runs/{run_id}`
  - [ ] `GET /runs/{run_id}/trace`

**Deliverable:** You can click/inspect why a test failed.

---

## Phase 5 — RAG / Vector Retrieval (Grounding + Citations)

**Goal:** Retrieval that supports factual answers and measurable grounding.

- [ ] Add Qdrant (Docker) or pgvector
- [ ] Add ingestion pipeline:
  - [ ] chunk runbooks
  - [ ] embed chunks
  - [ ] store in vector DB with metadata
- [ ] Replace `search_runbooks` with semantic search
- [ ] Add citation tracking in agent output:
  - [ ] “evidence_used” array with chunk IDs/snippets

**Deliverable:** Outputs are grounded and cite retrieved evidence.

---

## Phase 6 — CI Regression Gates (Ship Like a Real Team)

**Goal:** Prevent “silent AI regressions.”

- [ ] GitHub Actions workflow:
  - [ ] bring up services (docker compose)
  - [ ] run eval suite
  - [ ] upload eval report artifact
- [ ] Add regression thresholds:
  - [ ] fail PR if pass rate drops below X%
  - [ ] fail if p95 latency increases beyond threshold
  - [ ] fail if cost per run exceeds threshold

**Deliverable:** PRs get blocked by quality regressions automatically.

---

## Phase 7 — Feedback Loop (Production → Eval Cases)

**Goal:** Turn real failures into tests.

- [ ] Endpoint/UI action to promote a bad run:
  - [ ] `POST /promote/{run_id}`
- [ ] Store promoted run as new eval case with:
  - [ ] input payload
  - [ ] expected rubric
  - [ ] failure category tags

**Deliverable:** “Every failure becomes a regression test.”

---

## Recommended MVP Stop Point

If you reach **Phase 4**, you already have a strong portfolio project for AI Quality Engineering.

Phase 5–7 are “level up” steps once the core is solid.

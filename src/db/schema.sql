-- Agent Reliability Lab — Postgres schema
-- This file is mounted as a Docker init script and also serves as DDL reference.

CREATE TABLE IF NOT EXISTS eval_cases (
    case_id     TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    rubric      JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_versions (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id            TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL REFERENCES eval_cases(case_id),
    model_version TEXT NOT NULL DEFAULT 'deterministic-v1',
    run_index     INTEGER NOT NULL,
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    passed        BOOLEAN NOT NULL,
    agent_response JSONB
);

CREATE TABLE IF NOT EXISTS scores (
    id                   SERIAL PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES eval_runs(id),
    schema_valid         BOOLEAN NOT NULL,
    status_match         BOOLEAN NOT NULL,
    confidence_ok        BOOLEAN NOT NULL,
    actions_present      BOOLEAN NOT NULL,
    runbook_evidence_ok  BOOLEAN NOT NULL,
    forbidden_phrases_ok BOOLEAN NOT NULL,
    latency_ok           BOOLEAN NOT NULL,
    latency_ms           FLOAT,
    cost_usd             FLOAT,
    token_usage          INTEGER
);

CREATE TABLE IF NOT EXISTS step_traces (
    id             SERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES eval_runs(id),
    step_index     INTEGER NOT NULL,
    step_name      TEXT NOT NULL,
    tool_called    TEXT,
    input_summary  TEXT,
    output_summary TEXT,
    duration_ms    FLOAT,
    status         TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id          SERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES eval_runs(id),
    tool_name   TEXT NOT NULL,
    duration_ms FLOAT,
    status      TEXT,
    retries     INTEGER
);

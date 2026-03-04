# I Built an AI Agent. Then I Built a Framework to Make Sure It Actually Works.

There's no shortage of tutorials showing you how to wire up an LLM and call it an AI agent. Most of them stop at "look, it returned something." I wanted to take it a bit further.  Not just build an agent, but build the scaffolding that lets me answer harder questions: *Is it behaving correctly? Will it behave the same way next week? When it fails, why?*

This is the story of the first half of that project: the **Agent Reliability Lab**.

---

## The Problem I Was Trying to Solve

Imagine you're on a data engineering team. An Airflow pipeline fails at 2am. A PagerDuty alert fires. Someone has to triage it:  pull logs, check DAG metadata, search through runbooks, and figure out what broke and what to do about it.

That's repetitive, structured work. Exactly the kind of thing an AI agent should be good at.

But here's the uncomfortable truth: most AI agents in production are a black box. They sometimes work. They sometimes hallucinate. They occasionally loop forever or return malformed JSON that crashes your downstream systems. And you have no real visibility into *why* any of that happened.

I wanted to build an agent that triages incidents, but more importantly, build it in a way where the behavior is observable, bounded, and testable.

---

## Phase 0: The Foundation

Before writing a line of agent logic, I set up the project structure intentionally:

```
src/
  app/       # FastAPI API layer
  agent/     # workflow orchestration
  tools/     # deterministic tools
  data/      # fixture files (logs, DAG metadata, runbooks)
  tests/     # unit + integration tests
  evals/     # evaluation harness (Phase 3)
```

The key decision here was keeping concerns separate from day one. The tools don't know about the agent. The agent doesn't know about the API. Each layer has one job.

---

## Phase 1: The Agent MVP

The goal was simple: `Input → Agent → Tools → Structured JSON Output`. No vector databases, no streaming, no fancy LLM calls. Just a deterministic workflow that could be reasoned about and tested.

### The Input Contract

Every incident comes in as an `IncidentRequest`:

```python
class IncidentRequest(BaseModel):
    incident_id: str
    run_id: str
    dag_id: str
    severity: IncidentSeverity   # enum: low / medium / high / critical
    summary: str
    reporter: str
    keywords: list[str]          # max 5
    context: str | None
```

This is a [Pydantic](https://docs.pydantic.dev/) model. If a caller sends `severity: "DOOMSDAY"`, the API rejects it immediately with a clear validation error before the agent ever runs. The contract is enforced at the boundary.

### The Tools

Three deterministic tools back the agent, each reading from local fixture files:

- **`get_logs(run_id)`** — reads `data/logs/<run_id>.log`
- **`get_dag_metadata(dag_id)`** — reads `data/dags/<dag_id>.json`
- **`search_runbooks(keyword)`** — keyword search across `data/runbooks/*.md`

Pure Python. No network calls. Same input always produces the same output. That predictability is what makes them eval-friendly later. Think of them as mocks. 

### The Workflow

The agent runs a fixed playbook. No loops, no dynamic branching, just an ordered sequence:

```
1. get_logs(run_id)
2. get_dag_metadata(dag_id)
3. search_runbooks(keyword)
4. infer root cause from log text
5. build recommended actions
6. assemble evidence items
7. return AgentResponse
```

### The Output Contract

Every response is validated through `AgentResponse` before it leaves the system:

```python
class AgentResponse(BaseModel):
    incident_id: str
    status: Literal["triaged", "needs_info"]
    summary: str
    root_cause: str
    confidence: float          # enforced: 0.0–1.0
    recommended_actions: list[ActionItem]
    evidence: list[EvidenceItem]
    metadata: dict[str, str]
    metrics: RequestMetrics
```

FastAPI's `response_model=AgentResponse` means the API layer strips anything that doesn't belong and validates everything that does. The response is structurally guaranteed.

**Deliverable:** A curl request that returns a valid, structured JSON response every time.

---

## Phase 2: Guardrails and Determinism

This is where things get interesting *AND* where most agent projects skip straight to "ship it."

The problem with a naive agent is that it can fail in unpredictable ways: infinite loops, tool calls that hang, cascading retries that run up your API bill, malformed output that crashes downstream systems. Phase 2 adds a hard safety layer around every one of these failure modes.

### GuardrailConfig

Every run is governed by a config object:

```python
@dataclass
class GuardrailConfig:
    max_tool_calls: int = 5
    max_reasoning_steps: int = 5
    tool_timeout_seconds: float = 2.0
    max_tool_retries: int = 1
```

These guard rails aren't just suggestions. They're enforced by `ToolRunner`, a class that wraps every tool call:

```python
runner.call("get_logs", get_logs, request.run_id)
```

Under the hood, `ToolRunner.call()`:

1. Checks if the call budget is exhausted -> raises `GuardrailBreach`
2. Executes the tool and measures elapsed time
3. If elapsed > `tool_timeout_seconds` -> raises `ToolTimeout`
4. On any error, retries up to `max_tool_retries` times
5. After retries exhausted → raises `ToolFailure`
6. Records name, duration, status, and retry count in `WorkflowMetrics` regardless of outcome

### Graceful Degradation

The workflow's `try/except` catches every failure mode and calls `_fallback_response()`, which returns a valid `AgentResponse` with `status="needs_info"` and a human-readable explanation of what went wrong:

```python
try:
    # ... run the playbook
except (GuardrailBreach, ToolFailure) as exc:
    return _fallback_response(request, f"guardrail triggered: {exc}", ...)
except Exception as exc:
    return _fallback_response(request, f"unexpected failure: {exc}", ...)
```

The API never returns a 500. The agent never crashes the server. It always returns something actionable.

### Per-Request Metrics

Every response includes a `metrics` field capturing what happened:

```python
class RequestMetrics(BaseModel):
    latency_ms: float
    tool_count: int
    reasoning_steps: int
    token_usage: int
    estimated_cost_usd: float
```

This data is in every response, not tucked away in a log file. It's first-class output. That makes it trivially easy to assert on in tests, track over time, and surface in an eval report.

**Deliverable:** The agent fails safely and predictably, and every run is self-describing.

---

## What This Actually Is

By the end of Phase 2, I had built two things simultaneously:

**The agent** — the thing that does the work. Receives an incident, calls tools, reasons about the output, returns a structured diagnosis.

**The framework** — the thing that makes the agent trustworthy. Enforced contracts at every boundary. Hard limits on what the agent can do. Observability baked into every response. Graceful degradation when things go wrong.

Most teams build the agent. The quality framework is what separates a demo from a system you'd actually run in production. These considerations are thoughts of a quality engineer that blends QA knowledge with AI building blocks.

---

## What's Next

Phase 3 is the evaluation harness — the part where I define what "good" actually looks like and turn it into a regression-tested system. That means:

- A structured eval case format with scoring rubrics
- A pytest runner that executes the agent against each case N times
- Scoring functions for schema validity, confidence, actionability, and consistency
- A summary report with pass rates and latency stats

That post is coming. In the meantime, the [full code](https://github.com/cuff-links/agent_reliability_lab) is on GitHub.

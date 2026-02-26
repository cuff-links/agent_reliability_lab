"""Deterministic local tools backed by repo fixtures."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
LOG_DIR = DATA_ROOT / "logs"
DAG_DIR = DATA_ROOT / "dags"
RUNBOOK_DIR = DATA_ROOT / "runbooks"


@dataclass
class LogResult:
    run_id: str
    text: str


@dataclass
class DagMetadata:
    dag_id: str
    owner: str
    description: str
    raw: dict


@dataclass
class RunbookHit:
    title: str
    snippet: str
    matches: int


def get_logs(run_id: str) -> LogResult:
    """Read logs for a run_id from `data/logs`."""

    log_path = LOG_DIR / f"{run_id}.log"
    if not log_path.exists():
        return LogResult(run_id=run_id, text=f"No log file found for {run_id}.")
    return LogResult(run_id=run_id, text=log_path.read_text())


def get_dag_metadata(dag_id: str) -> DagMetadata:
    """Return DAG metadata from `data/dags/<dag_id>.json`."""

    dag_path = DAG_DIR / f"{dag_id}.json"
    if not dag_path.exists():
        return DagMetadata(
            dag_id=dag_id,
            owner="unknown",
            description="No DAG metadata available.",
            raw={"dag_id": dag_id},
        )
    payload = json.loads(dag_path.read_text())
    return DagMetadata(
        dag_id=dag_id,
        owner=payload.get("owner", "unknown"),
        description=payload.get("description", "No description provided."),
        raw=payload,
    )


def search_runbooks(keyword: str, limit: int = 2) -> list[RunbookHit]:
    """Simple keyword search over markdown runbooks."""

    keyword = keyword.lower()
    hits: list[RunbookHit] = []
    for path in RUNBOOK_DIR.glob("*.md"):
        content = path.read_text()
        matches = _keyword_score(content, keyword)
        if matches == 0:
            continue
        title = _extract_title(content, path.stem)
        snippet = _extract_snippet(content, keyword)
        hits.append(RunbookHit(title=title, snippet=snippet, matches=matches))
    return sorted(hits, key=lambda hit: hit.matches, reverse=True)[:limit]


def _keyword_score(content: str, keyword: str) -> int:
    return len(re.findall(re.escape(keyword), content, flags=re.IGNORECASE))


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ")
    return fallback.replace("_", " ").title()


def _extract_snippet(content: str, keyword: str) -> str:
    lines = content.splitlines()
    keyword_lower = keyword.lower()
    for line in lines:
        if keyword_lower in line.lower():
            return shorten(line.strip(), width=200, placeholder=" …")
    return shorten(content.replace("\n", " | "), width=200, placeholder=" …")

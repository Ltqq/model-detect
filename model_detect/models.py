from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProbeStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"
    INSUFFICIENT = "insufficient"


class AuditTarget(BaseModel):
    base_url: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    protocol: str = "openai"
    timeout_seconds: float = 30.0


class Evidence(BaseModel):
    id: str
    probe_id: str
    method: str = "POST"
    url: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: Any = None
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: Any = None
    error: str | None = None
    elapsed_ms: float | None = None
    created_at: str = Field(default_factory=utc_now_iso)


class ProbeResult(BaseModel):
    probe_id: str
    category: str
    status: ProbeStatus
    score: float | None = None
    confidence: float = 1.0
    summary: str
    expected: Any = None
    observed: Any = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHypothesis(BaseModel):
    provider: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class AuditSummary(BaseModel):
    overall_score: float | None = None
    category_scores: dict[str, float] = Field(default_factory=dict)
    hard_cap: float | None = None
    final_verdict: str = "insufficient"
    warnings: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    report_version: str = "1"
    started_at: str = Field(default_factory=utc_now_iso)
    finished_at: str | None = None
    profile: str = "quick"
    target: dict[str, Any]
    results: list[ProbeResult] = Field(default_factory=list)
    provider_hypotheses: list[ProviderHypothesis] = Field(default_factory=list)
    evidences: list[Evidence] = Field(default_factory=list)
    summary: AuditSummary = Field(default_factory=AuditSummary)
    adapters: dict[str, Any] = Field(default_factory=dict)

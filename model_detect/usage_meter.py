"""Versioned request-level token usage accounting with explicit unknowns.

Reasoning tokens are a subset of output tokens; cached reads/writes are subsets
of prompt tokens. None of these are added to the headline token total.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

UsageSource = Literal["observed", "estimated", "unknown"]


class UsageRecord(BaseModel):
    schema_version: str = "usage-record-v1"
    probe_id: str
    stage: str
    attempt: int = Field(default=1, ge=1)
    http_status: int | None = None
    source: UsageSource = "unknown"
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cached_read_tokens: int | None = Field(default=None, ge=0)
    cached_write_tokens: int | None = Field(default=None, ge=0)
    missing_reason: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "UsageRecord":
        if self.source == "unknown":
            if any(getattr(self, key) is not None for key in (
                "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cached_read_tokens", "cached_write_tokens",
            )):
                raise ValueError("unknown usage must not contain numeric estimates")
            if not self.missing_reason:
                raise ValueError("unknown usage requires missing_reason")
        if (self.reasoning_tokens is not None and self.completion_tokens is not None
                and self.reasoning_tokens > self.completion_tokens):
            raise ValueError("reasoning tokens exceed completion tokens")
        if (self.cached_read_tokens is not None and self.cached_write_tokens is not None
                and self.prompt_tokens is not None
                and self.cached_read_tokens + self.cached_write_tokens > self.prompt_tokens):
            raise ValueError("cached tokens exceed prompt tokens")
        return self


def _integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def usage_from_response(
    *, probe_id: str, stage: str, response: Any,
    http_status: int | None = None, attempt: int = 1,
    stream_complete: bool = True,
) -> UsageRecord:
    if not stream_complete:
        return UsageRecord(
            probe_id=probe_id, stage=stage, attempt=attempt,
            http_status=http_status, missing_reason="incomplete_stream",
        )
    if not isinstance(response, dict) or not isinstance(response.get("usage"), dict):
        return UsageRecord(
            probe_id=probe_id, stage=stage, attempt=attempt,
            http_status=http_status, missing_reason="usage_not_reported",
        )
    usage = response["usage"]
    prompt = _integer(usage.get("prompt_tokens"))
    completion = _integer(usage.get("completion_tokens"))
    if prompt is None or completion is None:
        return UsageRecord(
            probe_id=probe_id, stage=stage, attempt=attempt,
            http_status=http_status, missing_reason="incomplete_usage_fields",
        )
    input_details = usage.get("prompt_tokens_details")
    output_details = usage.get("completion_tokens_details")
    input_details = input_details if isinstance(input_details, dict) else {}
    output_details = output_details if isinstance(output_details, dict) else {}
    return UsageRecord(
        probe_id=probe_id, stage=stage, attempt=attempt,
        http_status=http_status, source="observed",
        prompt_tokens=prompt, completion_tokens=completion,
        reasoning_tokens=_integer(output_details.get("reasoning_tokens")),
        cached_read_tokens=_integer(input_details.get("cached_tokens")),
        # Cache writes must be explicitly reported; never infer them.
        cached_write_tokens=_integer(input_details.get("cache_creation_input_tokens")),
    )


def summarize_usage(records: list[UsageRecord]) -> dict[str, Any]:
    observed = [row for row in records if row.source == "observed"]
    unknown = [row for row in records if row.source == "unknown"]
    return {
        "schema_version": "usage-summary-v1",
        "requests": len(records),
        "observed_requests": len(observed),
        "unknown_requests": len(unknown),
        "coverage": len(observed) / len(records) if records else None,
        "prompt_tokens_observed": sum(row.prompt_tokens or 0 for row in observed),
        "completion_tokens_observed": sum(row.completion_tokens or 0 for row in observed),
        "reasoning_tokens_subset": sum(row.reasoning_tokens or 0 for row in observed),
        "cached_read_tokens_subset": sum(row.cached_read_tokens or 0 for row in observed),
        "cached_write_tokens_subset": sum(row.cached_write_tokens or 0 for row in observed),
        "unknown_reasons": sorted({row.missing_reason for row in unknown if row.missing_reason}),
        "precise_total_available": len(records) > 0 and len(unknown) == 0
            and all(row.source == "observed" for row in records),
    }

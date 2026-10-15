"""Conservative native HTTP soft token stop.

Observed provider usage may arrive only after a paid request completes.
This cannot cap an in-flight response nor unknown external subprocesses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .usage_meter import UsageRecord


@dataclass
class NativeTokenBudget:
    limit: int
    stop_on_unknown: bool = True
    observed_tokens: int = 0
    observed_calls: int = 0
    unknown_calls: int = 0
    blocked_calls: int = 0
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("native token soft limit must be positive")

    @property
    def exhausted(self) -> bool:
        return self.reason is not None

    def observe(self, record: UsageRecord) -> None:
        if self.exhausted:
            return
        if (record.source != "observed"
                or record.prompt_tokens is None or record.completion_tokens is None):
            self.unknown_calls += 1
            if self.stop_on_unknown:
                self.reason = "provider_usage_unknown"
            return
        self.observed_calls += 1
        self.observed_tokens += record.prompt_tokens + record.completion_tokens
        if self.observed_tokens >= self.limit:
            self.reason = "observed_token_soft_limit_reached"

    def reject(self) -> None:
        self.blocked_calls += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "native-token-soft-budget-v1",
            "limit": self.limit,
            "observed_tokens": self.observed_tokens,
            "observed_calls": self.observed_calls,
            "unknown_calls": self.unknown_calls,
            "blocked_calls": self.blocked_calls,
            "stop_reason": self.reason,
            "exhausted": self.exhausted,
            "hard_cost_cap": False,
            "external_subprocess_budget_supported": False,
            "warning": (
                "Only after-the-fact observed native usage is counted. "
                "One request can overshoot; external OSS calls are not bounded."
            ),
        }

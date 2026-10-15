"""Conservative external adapter token accounting.

Third-party tools may make network calls without exposing per-request usage.
The absence of usage is NEVER interpreted as zero tokens or free execution.
"""
from __future__ import annotations

from typing import Any


EXTERNAL_ADAPTERS = {
    "lm_eval_benchmark": "lm-evaluation-harness",
    "promptfoo_regression": "promptfoo",
    "fingerprint": "llm-fingerprint-detector",
    "proxy_sleuth": "proxy-sleuth",
}


def external_usage_boundary(adapters: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for name, engine in EXTERNAL_ADAPTERS.items():
        result = adapters.get(name)
        if not isinstance(result, dict):
            state = "not_configured"
        elif result.get("status") in {"disabled", "not_configured", "not_run", "skipped"}:
            state = "not_run"
        else:
            state = "external_unmetered"
        entries.append({
            "adapter": name,
            "engine": engine,
            "status": state,
            "observed_tokens": None,
            "actual_cost": None,
        })
    unknown = sum(x["status"] == "external_unmetered" for x in entries)
    return {
        "schema": "external-usage-boundary-v1",
        "adapters": entries,
        "unknown_usage_adapters": unknown,
        "complete_total_known": unknown == 0,
        "warning": (
            "Per-request observed native tokens exclude third-party subprocess "
            "requests. Missing external usage and costs are unknown, not zero."
        ),
    }

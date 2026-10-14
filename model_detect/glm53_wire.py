"""Offline GLM-5.3 paired HTTP request verification.

Accept locally captured *request bodies* only. Raw messages and credentials never
appear in the returned evidence. This does not claim the upstream honored them.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any


_FIELDS = ("model", "reasoning_effort", "thinking", "max_tokens", "temperature", "top_p", "stop", "seed", "response_format", "tools", "tool_choice", "stream")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalize(body: Any, *, expected_model: str, expected_effort: str) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(body, dict):
        return None, ["invalid_json_object"]
    problems = []
    if body.get("model") != expected_model:
        problems.append("model_mismatch")
    if body.get("reasoning_effort") != expected_effort:
        problems.append("reasoning_effort_missing_or_mismatch")
    if not isinstance(body.get("messages"), list) or not body["messages"]:
        problems.append("messages_missing")
    if (not isinstance(body.get("max_tokens"), int)
            or isinstance(body.get("max_tokens"), bool)
            or body["max_tokens"] <= 0):
        problems.append("max_tokens_missing_or_invalid")
    for field in ("temperature", "stop"):
        if field not in body:
            problems.append(field + "_unobserved")
    # Never preserve raw prompts. A digest still detects changed task content.
    # Hash every non-message generation option, including provider extensions.\n    # This prevents unrecognized parameters from escaping comparison.\n    settings = {name: value for name, value in body.items()\n                if name not in {"messages", "authorization", "api_key", "user"}\n                and not name.startswith("_")}
    safe = {
        "message_sha256": _digest(body.get("messages")),
        "settings_sha256": _digest(settings),
        "present_fields": sorted(name for name in settings if name in _FIELDS),
        "max_tokens": body.get("max_tokens") if isinstance(body.get("max_tokens"), int)
                      and not isinstance(body.get("max_tokens"), bool) else None,
    }
    return safe, problems


def verify_wire_requests(
    official: list[Any], customer: list[Any], *,
    expected_model: str = "glm-5.3", expected_effort: str = "max",
) -> dict[str, Any]:
    """Fail closed: missing metadata means incomplete verification, never pass."""
    if expected_effort not in {"low", "high", "max"}:
        raise ValueError("expected_effort must be low, high or max")
    results = {}
    counts = {}
    problems = {}
    for label, bodies in (("official", official), ("customer", customer)):
        if not isinstance(bodies, list):
            raise ValueError("request collections must be lists")
        clean = []
        issues = []
        for index, body in enumerate(bodies):
            normalized, violations = _normalize(
                body, expected_model=expected_model, expected_effort=expected_effort
            )
            if normalized is not None:
                clean.append(normalized)
            issues.extend({"index": index, "reason": reason} for reason in violations)
        counts[label] = len(bodies)
        problems[label] = issues
        results[label] = clean
    def signatures(label: str) -> Counter:
        return Counter(
            (x["message_sha256"], x["settings_sha256"])
            for x in results[label]
        )
    paired = bool(official and customer) and signatures("official") == signatures("customer")
    verified = paired and not problems["official"] and not problems["customer"]
    return {
        "schema": "glm53-wire-evidence-v1",
        "status": "request_payload_matched" if verified else "incomparable",
        "counts": counts,
        "issues": problems,
        "same_multiset_of_prompts_and_settings": paired,
        "max_tokens_observed": {
            label: sorted({x["max_tokens"] for x in results[label] if x["max_tokens"] is not None})
            for label in ("official", "customer")
        },
        "limitations": [
            "Only captured client-side JSON bodies are checked.",
            "No evidence that the provider applied reasoning, stop or token limits.",
            "The capture is not cryptographically attested to its network origin.",
            "Missing temperature or stop is not assumed to equal a default.",
        ],
    }

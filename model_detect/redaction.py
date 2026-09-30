from __future__ import annotations

from copy import deepcopy
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "api-key",
    "api_key",
    "apikey",
    "x-api-key",
    "proxy-authorization",
}


def redact_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if key.lower() in SENSITIVE_KEYS:
            out[str(key)] = "***REDACTED***"
        else:
            out[str(key)] = str(value)
    return out


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_payload(item)
        return out
    if isinstance(value, list):
        return [redact_payload(x) for x in value]
    return deepcopy(value)

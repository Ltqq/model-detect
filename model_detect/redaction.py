from __future__ import annotations

from copy import deepcopy
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "api-key", "api_key", "apikey", "x-api-key",
    "token", "access_token", "refresh_token", "client_secret",
    "secret", "password", "credential", "x-auth-token",
}

_INLINE_SECRET = re.compile(
    r"(?i)(?:bearer\\s+|sk-)[A-Za-z0-9_.-]{8,}"
)


def redact_text(value: str) -> str:
    return _INLINE_SECRET.sub("***REDACTED***", value)


def redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        # Userinfo and query params may carry credentials, never persist them.
        netloc = (parsed.hostname or "")
        if ":" in netloc and not netloc.startswith("["):
            netloc = "[" + netloc + "]"
        if parsed.port is not None:
            netloc += ":" + str(parsed.port)
        return urlunsplit((parsed.scheme, netloc, redact_text(parsed.path), "", ""))
    except (ValueError, TypeError):
        return "***REDACTED_URL***"


def redact_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if str(key).lower() in SENSITIVE_KEYS:
            out[str(key)] = "***REDACTED***"
        else:
            out[str(key)] = redact_text(str(value))
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
    if isinstance(value, str):
        return redact_text(value)
    return deepcopy(value)

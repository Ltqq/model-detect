from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "api-key", "api_key", "apikey", "x-api-key",
    "token", "access_token", "refresh_token", "client_secret",
    "secret", "password", "credential", "x-auth-token",
}

_INLINE_SECRET = re.compile(
    r"(?i)(?:bearer\s+|sk-)[A-Za-z0-9_.-]{8,}"
)


def redact_text(value: str, *, secrets: Iterable[str] = ()) -> str:
    # A provider may echo the configured API key without a conventional
    # sk-/Bearer prefix. Protect those exact values as well, but avoid
    # replacing one-letter test keys throughout unrelated model text.
    for secret in sorted({s for s in secrets if isinstance(s, str) and len(s) >= 4}, key=len, reverse=True):
        value = value.replace(secret, "***REDACTED***")
    return _INLINE_SECRET.sub("***REDACTED***", value)


def redact_url(value: str, *, secrets: Iterable[str] = ()) -> str:
    try:
        parsed = urlsplit(value)
        # Userinfo and query params may carry credentials, never persist them.
        netloc = (parsed.hostname or "")
        if ":" in netloc and not netloc.startswith("["):
            netloc = "[" + netloc + "]"
        if parsed.port is not None:
            netloc += ":" + str(parsed.port)
        return urlunsplit((parsed.scheme, netloc, redact_text(parsed.path, secrets=secrets), "", ""))
    except (ValueError, TypeError):
        return "***REDACTED_URL***"


def redact_headers(headers: dict[str, Any] | None, *, secrets: Iterable[str] = ()) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if str(key).lower() in SENSITIVE_KEYS:
            out[str(key)] = "***REDACTED***"
        else:
            out[str(key)] = redact_text(str(value), secrets=secrets)
    return out


def redact_payload(value: Any, *, secrets: Iterable[str] = ()) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_payload(item, secrets=secrets)
        return out
    if isinstance(value, list):
        return [redact_payload(x, secrets=secrets) for x in value]
    if isinstance(value, str):
        return redact_text(value, secrets=secrets)
    return deepcopy(value)

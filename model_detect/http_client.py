from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from .models import Evidence
from .redaction import redact_headers, redact_payload


@dataclass
class CallResult:
    evidence: Evidence
    json_body: Any = None
    text_body: str = ""


class AuditHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self.base_url + "/" + path.lstrip("/")

    async def post_json(
        self,
        *,
        probe_id: str,
        path: str,
        payload: dict[str, Any],
        stream: bool = False,
    ) -> CallResult:
        url = self._url(path)
        started = time.perf_counter()
        evidence = Evidence(
            id="ev_" + uuid.uuid4().hex[:16],
            probe_id=probe_id,
            method="POST",
            url=url,
            request_headers=redact_headers(self.headers),
            request_body=redact_payload(payload),
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                if stream:
                    lines: list[str] = []
                    response_headers: dict[str, str] = {}
                    status_code: int | None = None
                    async with client.stream(
                        "POST", url, headers=self.headers, json=payload
                    ) as response:
                        status_code = response.status_code
                        response_headers = dict(response.headers)
                        async for line in response.aiter_lines():
                            if line:
                                lines.append(line)
                            if len(lines) >= 30 or sum(len(x) for x in lines) >= 65536:
                                break
                    text = "\n".join(lines)
                    parsed = _parse_sse_preview(lines)
                    evidence.response_status = status_code
                    evidence.response_headers = redact_headers(response_headers)
                    evidence.response_body = parsed if parsed is not None else text[:65536]
                    return CallResult(evidence=evidence, json_body=parsed, text_body=text)

                response = await client.post(url, headers=self.headers, json=payload)
                text = response.text
                try:
                    parsed = response.json()
                except Exception:
                    parsed = None
                evidence.response_status = response.status_code
                evidence.response_headers = redact_headers(dict(response.headers))
                evidence.response_body = parsed if parsed is not None else text[:65536]
                return CallResult(evidence=evidence, json_body=parsed, text_body=text)
        except Exception as exc:
            evidence.error = f"{type(exc).__name__}: {exc}"
            return CallResult(evidence=evidence)
        finally:
            evidence.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)


def _parse_sse_preview(lines: list[str]) -> list[Any] | None:
    parsed: list[Any] = []
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed.append(json.loads(data))
        except Exception:
            parsed.append(data)
    return parsed or None

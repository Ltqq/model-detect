from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from .models import Evidence
from .usage_meter import UsageRecord, usage_from_response
from .redaction import redact_headers, redact_payload
from .rules import apply_request_constraints


@dataclass
class CallResult:
    evidence: Evidence
    json_body: Any = None
    text_body: str = ""

    def usage_record(self, *, stage: str = "native", attempt: int = 1) -> UsageRecord:
        """Get meter data without trusting a response that lacks usage."""
        payload = self.json_body
        stream_ok = not (
            isinstance(payload, dict) and
            ("_sse_completed" in payload or "_sse_truncated" in payload) and
            (not payload.get("_sse_completed") or payload.get("_sse_truncated"))
        )
        return usage_from_response(
            probe_id=self.evidence.probe_id, stage=stage,
            response=payload, http_status=self.evidence.response_status,
            attempt=attempt, stream_complete=stream_ok,
        )


class AuditHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        extra_headers: dict[str, str] | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.model = model
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
        stream_full: bool = False,
        constraint_exempt_fields: set[str] | frozenset[str] | None = None,
    ) -> CallResult:
        url = self._url(path)
        actual_payload = dict(payload)
        if self.model and path.rstrip("/").endswith("/chat/completions"):
            actual_payload = apply_request_constraints(
                self.model,
                actual_payload,
                exempt_fields=constraint_exempt_fields,
            )
        started = time.perf_counter()
        evidence = Evidence(
            id="ev_" + uuid.uuid4().hex[:16],
            probe_id=probe_id,
            method="POST",
            url=url,
            request_headers=redact_headers(self.headers),
            request_body=redact_payload(actual_payload),
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                if stream:
                    lines: list[str] = []
                    response_headers: dict[str, str] = {}
                    status_code: int | None = None
                    bytes_seen = 0
                    truncated = False
                    event_done = False
                    line_limit = 20000 if stream_full else 30
                    byte_limit = 4_000_000 if stream_full else 65536
                    async with client.stream(
                        "POST", url, headers=self.headers, json=actual_payload
                    ) as response:
                        status_code = response.status_code
                        response_headers = dict(response.headers)
                        async for line in response.aiter_lines():
                            if line:
                                lines.append(line)
                                bytes_seen += len(line.encode("utf-8"))
                                if line.strip() == "data: [DONE]":
                                    event_done = True
                            if len(lines) >= line_limit or bytes_seen >= byte_limit:
                                truncated = True
                                break
                    text = "\n".join(lines)
                    parsed = _parse_sse_preview(lines)
                    evidence.response_status = status_code
                    evidence.response_headers = redact_headers(response_headers)
                    if stream_full:
                        # Protocol conformance requires evidence of termination,
                        # not just the first 30 SSE lines.
                        events = parsed if isinstance(parsed, list) else []
                        finish_reasons = [
                            ch.get("finish_reason")
                            for event in events if isinstance(event, dict)
                            for ch in (event.get("choices") or [])
                            if isinstance(ch, dict) and ch.get("finish_reason")
                        ]
                        usage = next(
                            (event.get("usage") for event in reversed(events)
                             if isinstance(event, dict)
                             and isinstance(event.get("usage"), dict)),
                            None,
                        )
                        parsed = {
                            "_sse_completed": event_done and not truncated,
                            "_sse_truncated": truncated,
                            "_sse_events": len(events),
                            "_sse_finish_reason": finish_reasons[-1] if finish_reasons else None,
                            "usage": usage,
                        }
                        evidence.response_body = parsed
                        return CallResult(evidence=evidence, json_body=parsed)
                    evidence.response_body = parsed if parsed is not None else text[:65536]
                    return CallResult(evidence=evidence, json_body=parsed, text_body=text)

                response = await client.post(url, headers=self.headers, json=actual_payload)
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
            evidence.error = f"{type(exc).__name__}: request failed; raw exception hidden"
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

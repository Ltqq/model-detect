from __future__ import annotations

import json
from typing import Any

from ..http_client import AuditHttpClient, CallResult
from ..models import Evidence, ProbeResult, ProbeStatus


def _message_text(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    return ""


def _error_result(probe_id: str, category: str, call: CallResult) -> ProbeResult:
    return ProbeResult(
        probe_id=probe_id,
        category=category,
        status=ProbeStatus.ERROR,
        score=0.0,
        confidence=1.0,
        summary=call.evidence.error or "request failed",
        observed={"error": call.evidence.error},
        evidence_ids=[call.evidence.id],
    )


async def probe_basic(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.chat.basic"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply exactly with OK."}],
            "temperature": 0,
            "max_tokens": 16,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]

    body = call.json_body
    ok_shape = (
        ev.response_status == 200
        and isinstance(body, dict)
        and isinstance(body.get("choices"), list)
        and len(body["choices"]) > 0
    )
    results = [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok_shape else ProbeStatus.FAIL,
            score=1.0 if ok_shape else 0.0,
            summary=(
                "OpenAI chat completion returned a valid choices response"
                if ok_shape
                else f"unexpected chat completion response (HTTP {ev.response_status})"
            ),
            expected={"http_status": 200, "shape": "choices[0].message"},
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ]

    usage = body.get("usage") if isinstance(body, dict) else None
    usage_ok = isinstance(usage, dict) and any(
        key in usage
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    )
    results.append(
        ProbeResult(
            probe_id="protocol.usage",
            category="protocol",
            status=ProbeStatus.PASS if usage_ok else ProbeStatus.WARN,
            score=1.0 if usage_ok else 0.5,
            confidence=1.0,
            summary="usage fields present" if usage_ok else "usage fields missing or non-standard",
            observed=usage,
            evidence_ids=[ev.id],
        )
    )

    finish_reason = None
    if isinstance(body, dict) and body.get("choices"):
        first = body["choices"][0]
        if isinstance(first, dict):
            finish_reason = first.get("finish_reason")
    results.append(
        ProbeResult(
            probe_id="protocol.finish_reason",
            category="protocol",
            status=ProbeStatus.PASS if finish_reason is not None else ProbeStatus.WARN,
            score=1.0 if finish_reason is not None else 0.5,
            summary=(
                f"finish_reason={finish_reason!r}"
                if finish_reason is not None
                else "finish_reason missing"
            ),
            observed=finish_reason,
            evidence_ids=[ev.id],
        )
    )

    response_model = body.get("model") if isinstance(body, dict) else None
    results.append(
        ProbeResult(
            probe_id="provider.response.model_alias",
            category="provider",
            status=ProbeStatus.PASS if response_model else ProbeStatus.WARN,
            score=None,
            summary=(
                f"response model field: {response_model}"
                if response_model
                else "response model field missing"
            ),
            observed={"requested": model, "returned": response_model},
            evidence_ids=[ev.id],
        )
    )
    return results, [ev]


async def probe_stream(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.chat.stream"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        stream=True,
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply exactly STREAM_OK."}],
            "stream": True,
            "temperature": 0,
            "max_tokens": 32,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    content_type = ev.response_headers.get("content-type", "")
    body = ev.response_body
    looks_stream = ev.response_status == 200 and (
        "text/event-stream" in content_type.lower()
        or isinstance(body, list)
        or "data:" in call.text_body
    )
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if looks_stream else ProbeStatus.FAIL,
            score=1.0 if looks_stream else 0.0,
            summary=(
                "streaming SSE response detected"
                if looks_stream
                else f"stream response is not SSE-like (HTTP {ev.response_status})"
            ),
            observed={"content_type": content_type, "http_status": ev.response_status},
            evidence_ids=[ev.id],
        ),
        ProbeResult(
            probe_id="provider.stream.chunk_signature",
            category="provider",
            status=ProbeStatus.PASS if looks_stream else ProbeStatus.WARN,
            score=None,
            summary="captured SSE chunk preview" if looks_stream else "no usable SSE preview",
            observed=body,
            evidence_ids=[ev.id],
        ),
    ], [ev]


async def probe_invalid_model(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "provider.error.invalid_model"
    fake = f"__model_detect_missing__{model}"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": fake,
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 8,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "provider", call)], [ev]
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    status = ProbeStatus.PASS if rejected else ProbeStatus.WARN
    return [
        ProbeResult(
            probe_id=probe_id,
            category="provider",
            status=status,
            score=None,
            confidence=0.9,
            summary=(
                f"invalid model rejected with HTTP {ev.response_status}"
                if rejected
                else f"invalid model was not rejected as expected (HTTP {ev.response_status})"
            ),
            expected={"http_status": "4xx"},
            observed={"http_status": ev.response_status, "body": ev.response_body},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_unknown_field(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.invalid.unknown_field"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply UNKNOWN_FIELD."}],
            "__model_detect_unknown_field__": True,
            "max_tokens": 16,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    # Unknown-field policy differs by provider, so acceptance is evidence, not a hard fail.
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if rejected else ProbeStatus.WARN,
            score=1.0 if rejected else 0.7,
            confidence=0.8,
            summary=(
                f"unknown field rejected with HTTP {ev.response_status}"
                if rejected
                else f"unknown field accepted/ignored (HTTP {ev.response_status})"
            ),
            expected={"preferred": "4xx strict rejection"},
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
            metadata={"strict_unknown_field_rejection": rejected},
        )
    ], [ev]


async def probe_reasoning_typo(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.reasoning.invalid_field"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "What is 19 + 23? Answer only."}],
            "reasoning_effor": "medium",
            "max_tokens": 32,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if rejected else ProbeStatus.WARN,
            score=1.0 if rejected else 0.6,
            confidence=0.9,
            summary=(
                "misspelled reasoning_effor field was rejected"
                if rejected
                else "misspelled reasoning_effor field was accepted or silently ignored"
            ),
            expected={"preferred": "4xx for unknown reasoning field"},
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
            metadata={"invalid_reasoning_field_rejected": rejected},
        )
    ], [ev]


async def probe_system(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.system"
    token = "SYS_MD_73A9"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": f"Always reply exactly {token}."},
                {"role": "user", "content": "Follow the system instruction."},
            ],
            "temperature": 0,
            "max_tokens": 32,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    text = _message_text(call.json_body)
    ok = ev.response_status == 200 and token in text
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok else ProbeStatus.WARN,
            score=1.0 if ok else 0.5,
            summary="system instruction observed" if ok else "system instruction was not reproduced as requested",
            observed={"text": text[:500], "http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_multiturn(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.multiturn"
    token = "TURN_MD_51C2"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {"role": "user", "content": "Remember the following token."},
                {"role": "assistant", "content": f"The token is {token}."},
                {"role": "user", "content": "What token did you just state? Answer only the token."},
            ],
            "temperature": 0,
            "max_tokens": 32,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    text = _message_text(call.json_body)
    ok = ev.response_status == 200 and token in text
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok else ProbeStatus.WARN,
            score=1.0 if ok else 0.5,
            summary="multi-turn context preserved" if ok else "multi-turn recall probe did not reproduce the token",
            observed={"text": text[:500], "http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_tool_call(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.tools.basic"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Use the get_weather tool to check Hangzhou. Do not answer directly.",
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather for a city",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": "required",
            "temperature": 0,
            "max_tokens": 128,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    tool_calls = None
    try:
        tool_calls = call.json_body["choices"][0]["message"].get("tool_calls")
    except Exception:
        pass
    ok = ev.response_status == 200 and isinstance(tool_calls, list) and len(tool_calls) > 0
    schema_ok = False
    if ok:
        try:
            args = tool_calls[0]["function"]["arguments"]
            parsed = json.loads(args) if isinstance(args, str) else args
            schema_ok = isinstance(parsed, dict) and isinstance(parsed.get("city"), str)
        except Exception:
            schema_ok = False

    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok else ProbeStatus.WARN,
            score=1.0 if ok else 0.4,
            summary="tool call returned" if ok else "tool call not returned",
            observed={"tool_calls": tool_calls, "http_status": ev.response_status},
            evidence_ids=[ev.id],
        ),
        ProbeResult(
            probe_id="protocol.tools.arguments_schema",
            category="protocol",
            status=ProbeStatus.PASS if schema_ok else (ProbeStatus.WARN if ok else ProbeStatus.SKIPPED),
            score=1.0 if schema_ok else (0.5 if ok else None),
            summary=(
                "tool arguments are valid JSON with required city"
                if schema_ok
                else "tool argument schema could not be verified"
            ),
            observed=tool_calls,
            evidence_ids=[ev.id],
        ),
    ], [ev]


async def probe_json_mode(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.json_mode"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": 'Return JSON only with exactly this shape: {"ok": true, "n": 7}.',
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 64,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    text = _message_text(call.json_body)
    valid = False
    parsed = None
    if ev.response_status == 200:
        try:
            parsed = json.loads(text)
            valid = isinstance(parsed, dict)
        except Exception:
            pass
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if valid else ProbeStatus.WARN,
            score=1.0 if valid else 0.4,
            summary="JSON mode returned parseable JSON" if valid else "JSON mode unsupported or output was not valid JSON",
            observed={"parsed": parsed, "text": text[:500], "http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


QUICK_PROBES = [
    probe_basic,
    probe_stream,
    probe_invalid_model,
    probe_unknown_field,
    probe_reasoning_typo,
    probe_system,
    probe_multiturn,
    probe_tool_call,
    probe_json_mode,
]

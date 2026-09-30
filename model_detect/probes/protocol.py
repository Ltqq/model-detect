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



async def probe_bad_enum(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.invalid.bad_enum"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": "definitely-not-a-number",
            "max_tokens": 8,
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
            confidence=0.85,
            summary=(
                f"invalid temperature rejected with HTTP {ev.response_status}"
                if rejected
                else f"invalid temperature accepted/coerced (HTTP {ev.response_status})"
            ),
            expected={"preferred": "4xx validation error"},
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_reasoning_valid(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.reasoning.valid_field"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "What is 17 * 23? Answer only the integer."}],
            "reasoning_effort": "low",
            "max_tokens": 64,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    accepted = ev.response_status == 200
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if accepted else ProbeStatus.WARN,
            score=1.0 if accepted else 0.5,
            confidence=0.8,
            summary=(
                "reasoning_effort=low accepted"
                if accepted
                else f"reasoning_effort=low not accepted (HTTP {ev.response_status})"
            ),
            observed={"http_status": ev.response_status, "body": ev.response_body},
            evidence_ids=[ev.id],
            metadata={"reasoning_effort_supported": accepted},
        )
    ], [ev]


async def probe_json_schema(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.json_schema"
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "integer"},
        },
        "required": ["name", "value"],
        "additionalProperties": False,
    }
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": 'Return an object with name="model-detect" and value=7.',
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "model_detect_probe",
                    "strict": True,
                    "schema": schema,
                },
            },
            "temperature": 0,
            "max_tokens": 96,
        },
    )
    ev = call.evidence
    if ev.error:
        return [_error_result(probe_id, "protocol", call)], [ev]
    text = _message_text(call.json_body)
    parsed = None
    valid = False
    if ev.response_status == 200:
        try:
            parsed = json.loads(text)
            valid = (
                isinstance(parsed, dict)
                and parsed.get("name") == "model-detect"
                and parsed.get("value") == 7
                and set(parsed.keys()) == {"name", "value"}
            )
        except Exception:
            valid = False
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if valid else ProbeStatus.WARN,
            score=1.0 if valid else 0.5,
            confidence=0.9,
            summary=(
                "strict JSON Schema output satisfied"
                if valid
                else f"JSON Schema unsupported or schema not satisfied (HTTP {ev.response_status})"
            ),
            observed={"http_status": ev.response_status, "parsed": parsed, "text": text[:500]},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_routing_model_consistency(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "routing.response_model_consistency"
    evidences: list[Evidence] = []
    returned_models: list[str] = []
    statuses: list[int | None] = []
    for i in range(5):
        call = await client.post_json(
            probe_id=probe_id,
            path="/chat/completions",
            payload={
                "model": model,
                "messages": [{"role": "user", "content": f"Reply exactly ROUTE_{i}."}],
                "temperature": 0,
                "max_tokens": 24,
            },
        )
        evidences.append(call.evidence)
        statuses.append(call.evidence.response_status)
        if isinstance(call.json_body, dict):
            returned = call.json_body.get("model")
            if returned:
                returned_models.append(str(returned))

    unique = sorted(set(returned_models))
    all_ok = all(x == 200 for x in statuses)
    if len(unique) > 1:
        status = ProbeStatus.FAIL
        score = 0.0
        summary = f"response model field changed across repeats: {unique}"
    elif all_ok and unique:
        status = ProbeStatus.PASS
        score = 1.0
        summary = f"response model field stable across 5 repeats: {unique[0]}"
    elif all_ok:
        status = ProbeStatus.WARN
        score = 0.6
        summary = "all repeated calls succeeded but response model field was absent"
    else:
        status = ProbeStatus.WARN
        score = 0.5
        summary = f"repeated routing probe had non-200 responses: {statuses}"

    return [
        ProbeResult(
            probe_id=probe_id,
            category="routing",
            status=status,
            score=score,
            confidence=0.8,
            summary=summary,
            observed={"returned_models": returned_models, "statuses": statuses},
            evidence_ids=[x.id for x in evidences],
            metadata={"unique_response_models": unique},
        )
    ], evidences


async def probe_response_metadata(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "provider.response.metadata"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply exactly META_OK."}],
            "temperature": 0,
            "max_tokens": 24,
        },
    )
    ev = call.evidence
    body = call.json_body if isinstance(call.json_body, dict) else {}
    response_id = body.get("id")
    response_model = body.get("model")
    prefix = None
    if isinstance(response_id, str):
        import re as _re
        m = _re.match(r"^([A-Za-z_-]+)", response_id)
        prefix = m.group(1) if m else None

    return [
        ProbeResult(
            probe_id="provider.response.headers",
            category="provider",
            status=ProbeStatus.PASS if ev.response_headers else ProbeStatus.WARN,
            score=None,
            confidence=1.0,
            summary=f"captured {len(ev.response_headers)} response headers",
            observed=ev.response_headers,
            evidence_ids=[ev.id],
        ),
        ProbeResult(
            probe_id="provider.response.id_pattern",
            category="provider",
            status=ProbeStatus.PASS if response_id else ProbeStatus.WARN,
            score=None,
            confidence=0.8,
            summary=(
                f"response id prefix={prefix!r}"
                if response_id
                else "response id missing"
            ),
            observed={
                "id": response_id,
                "id_prefix": prefix,
                "model": response_model,
            },
            evidence_ids=[ev.id],
        ),
    ], [ev]


async def probe_reasoning_invalid_value(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.reasoning.invalid_value"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply OK."}],
            "reasoning_effort": "__model_detect_invalid__",
            "max_tokens": 16,
        },
    )
    ev = call.evidence
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if rejected else ProbeStatus.WARN,
            score=1.0 if rejected else 0.6,
            confidence=0.85,
            summary=(
                f"invalid reasoning_effort rejected with HTTP {ev.response_status}"
                if rejected
                else f"invalid reasoning_effort accepted/ignored (HTTP {ev.response_status})"
            ),
            observed={"http_status": ev.response_status, "body": ev.response_body},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_thinking_disable(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.thinking.disable"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "What is 8 + 9? Answer only the integer."}],
            "thinking": {"type": "disabled"},
            "max_tokens": 32,
        },
    )
    ev = call.evidence
    accepted = ev.response_status == 200
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if accepted else ProbeStatus.WARN,
            score=None,
            confidence=0.7,
            summary=(
                "thinking disable field accepted"
                if accepted
                else f"thinking disable field rejected (HTTP {ev.response_status})"
            ),
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
            metadata={"disable_thinking_supported": accepted},
        )
    ], [ev]


async def probe_tool_choice(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.tools.tool_choice"
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get local time",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
    ]
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Check Hangzhou weather using the required tool."}],
            "tools": tools,
            "tool_choice": {
                "type": "function",
                "function": {"name": "get_weather"},
            },
            "temperature": 0,
            "max_tokens": 128,
        },
    )
    ev = call.evidence
    name = None
    try:
        name = call.json_body["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
    except Exception:
        pass
    ok = ev.response_status == 200 and name == "get_weather"
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok else ProbeStatus.WARN,
            score=1.0 if ok else 0.5,
            confidence=0.9,
            summary="specific tool_choice respected" if ok else "specific tool_choice was not confirmed",
            observed={"tool_name": name, "http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_tools_parallel(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.tools.parallel"
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get time",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
    ]
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Use tools to get both the weather and local time for Hangzhou. Do not answer directly.",
                }
            ],
            "tools": tools,
            "tool_choice": "required",
            "parallel_tool_calls": True,
            "temperature": 0,
            "max_tokens": 192,
        },
    )
    ev = call.evidence
    names = []
    try:
        calls = call.json_body["choices"][0]["message"].get("tool_calls") or []
        names = [
            x.get("function", {}).get("name")
            for x in calls
            if isinstance(x, dict)
        ]
    except Exception:
        pass
    ok = {"get_weather", "get_time"}.issubset(set(names))
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if ok else ProbeStatus.WARN,
            score=1.0 if ok else 0.5,
            confidence=0.75,
            summary="parallel tool calls returned both requested tools" if ok else "parallel tool calling was not confirmed",
            observed={"tool_names": names, "http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_tools_invalid_schema(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.tools.invalid_schema"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Call the tool."}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "broken_tool",
                        "description": "Intentionally invalid schema",
                        "parameters": {
                            "type": "object",
                            "properties": {"x": {"type": "__invalid_json_type__"}},
                        },
                    },
                }
            ],
            "tool_choice": "required",
            "max_tokens": 64,
        },
    )
    ev = call.evidence
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if rejected else ProbeStatus.WARN,
            score=1.0 if rejected else 0.6,
            confidence=0.8,
            summary="invalid tool schema rejected" if rejected else "invalid tool schema accepted or passed through",
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_json_invalid_schema(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    probe_id = "protocol.json.invalid_schema"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Return JSON."}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "broken",
                    "strict": True,
                    "schema": {
                        "type": "__invalid_json_type__",
                    },
                },
            },
            "max_tokens": 64,
        },
    )
    ev = call.evidence
    rejected = ev.response_status is not None and 400 <= ev.response_status < 500
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=ProbeStatus.PASS if rejected else ProbeStatus.WARN,
            score=1.0 if rejected else 0.6,
            confidence=0.8,
            summary="invalid JSON Schema rejected" if rejected else "invalid JSON Schema accepted or ignored",
            observed={"http_status": ev.response_status},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_responses_basic(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    """Optional OpenAI Responses API feature probe. Unsupported is not penalized."""
    probe_id = "protocol.responses.basic"
    call = await client.post_json(
        probe_id=probe_id,
        path="/responses",
        payload={
            "model": model,
            "input": "Reply exactly RESPONSES_OK.",
            "max_output_tokens": 32,
        },
    )
    ev = call.evidence
    supported = ev.response_status == 200 and isinstance(call.json_body, dict)
    if supported:
        status = ProbeStatus.PASS
        summary = "Responses API accepted the request"
    elif ev.response_status in {400, 404, 405, 422}:
        status = ProbeStatus.SKIPPED
        summary = f"Responses API not supported/compatible (HTTP {ev.response_status})"
    elif ev.error:
        status = ProbeStatus.ERROR
        summary = ev.error
    else:
        status = ProbeStatus.WARN
        summary = f"Responses API returned unexpected HTTP {ev.response_status}"
    return [
        ProbeResult(
            probe_id=probe_id,
            category="protocol",
            status=status,
            score=None,
            confidence=0.8,
            summary=summary,
            observed={"http_status": ev.response_status, "body": ev.response_body},
            evidence_ids=[ev.id],
            metadata={"responses_api_supported": supported},
        )
    ], [ev]

QUICK_PROBES = [
    probe_basic,
    probe_response_metadata,
    probe_stream,
    probe_invalid_model,
    probe_unknown_field,
    probe_reasoning_typo,
    probe_system,
    probe_multiturn,
    probe_tool_call,
    probe_json_mode,
]

STANDARD_PROBES = QUICK_PROBES + [
    probe_responses_basic,
    probe_bad_enum,
    probe_reasoning_valid,
    probe_reasoning_invalid_value,
    probe_thinking_disable,
    probe_json_schema,
    probe_json_invalid_schema,
    probe_tool_choice,
    probe_tools_invalid_schema,
]

DEEP_PROBES = STANDARD_PROBES + [
    probe_tools_parallel,
]

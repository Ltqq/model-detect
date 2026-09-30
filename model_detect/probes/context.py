from __future__ import annotations

import math
import re
from typing import Any

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus


def _message_text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


def _filler_chars(approx_tokens: int) -> str:
    # Tokenizers differ, so this is deliberately reported as an estimate.
    target_chars = max(0, int(approx_tokens * 3.6))
    unit = " alpha beta gamma delta epsilon zeta eta theta 0123456789"
    repeats = math.ceil(target_chars / len(unit))
    return (unit * repeats)[:target_chars]


async def _needle_probe(
    client: AuditHttpClient,
    model: str,
    approx_tokens: int,
) -> tuple[ProbeResult, Evidence]:
    probe_id = f"context.needle.{approx_tokens // 1000}k"
    needle = f"MD_NEEDLE_{approx_tokens}_7F3A"
    filler_tokens = max(512, approx_tokens - 512)
    filler = _filler_chars(filler_tokens)
    split = len(filler) // 3
    content = (
        filler[:split]
        + f"\nIMPORTANT MEMORY TOKEN: {needle}\n"
        + filler[split:]
    )
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a memory test. At the end, return the exact memory token requested by the user.",
                },
                {"role": "user", "content": content},
                {
                    "role": "user",
                    "content": "Return only the exact IMPORTANT MEMORY TOKEN from earlier. No explanation.",
                },
            ],
            "temperature": 0,
            "max_tokens": 64,
        },
    )
    ev = call.evidence
    text = _message_text(call.json_body)
    ok = ev.response_status == 200 and needle in text
    if ev.error:
        status = ProbeStatus.ERROR
        score = 0.0
        summary = ev.error
    elif ok:
        status = ProbeStatus.PASS
        score = 1.0
        summary = f"needle recovered at approximately {approx_tokens} input tokens"
    elif ev.response_status in {400, 413, 422}:
        status = ProbeStatus.FAIL
        score = 0.0
        summary = f"endpoint rejected approximately {approx_tokens} input tokens (HTTP {ev.response_status})"
    else:
        status = ProbeStatus.FAIL
        score = 0.0
        summary = f"needle was not recovered at approximately {approx_tokens} input tokens"
    return (
        ProbeResult(
            probe_id=probe_id,
            category="context",
            status=status,
            score=score,
            confidence=0.9,
            summary=summary,
            observed={
                "http_status": ev.response_status,
                "answer": text[:300],
                "approx_input_tokens": approx_tokens,
            },
            evidence_ids=[ev.id],
            metadata={
                "approximate_tokens": True,
                "needle": needle,
            },
        ),
        ev,
    )


async def run_context_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
    declared_context_tokens: int | None,
) -> tuple[list[ProbeResult], list[Evidence]]:
    profile = profile.lower()
    if profile == "quick":
        return [], []

    declared = declared_context_tokens or (32768 if profile == "deep" else 8192)
    if profile == "standard":
        requested = [min(8192, declared)]
    else:
        requested = [8192, 16384, 32768]
        requested = [x for x in requested if x <= declared]
        if not requested:
            requested = [min(8192, declared)]

    levels = []
    for value in requested:
        if value >= 1024 and value not in levels:
            levels.append(value)

    results: list[ProbeResult] = []
    evidences: list[Evidence] = []
    for level in levels:
        result, evidence = await _needle_probe(client, model, level)
        results.append(result)
        evidences.append(evidence)

    if results:
        passed = sum(r.status == ProbeStatus.PASS for r in results)
        score = passed / len(results)
        results.append(
            ProbeResult(
                probe_id="context.summary",
                category="context",
                status=(
                    ProbeStatus.PASS
                    if passed == len(results)
                    else (ProbeStatus.WARN if passed else ProbeStatus.FAIL)
                ),
                score=score,
                confidence=0.9,
                summary=f"context needle passed {passed}/{len(results)} tested levels",
                observed={
                    "tested_levels": levels,
                    "declared_context_tokens": declared_context_tokens,
                },
                evidence_ids=[e.id for e in evidences],
            )
        )
    return results, evidences

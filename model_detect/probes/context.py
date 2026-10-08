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


def _reasoning_text(body: Any) -> str:
    try:
        value = body["choices"][0]["message"].get("reasoning_content")
    except Exception:
        return ""
    return value if isinstance(value, str) else ""


def _finish_reason(body: Any) -> str | None:
    try:
        value = body["choices"][0].get("finish_reason")
    except Exception:
        return None
    return value if isinstance(value, str) else None


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
) -> tuple[ProbeResult, list[Evidence]]:
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
    base_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a memory test. At the end, return the exact "
                    "memory token requested by the user."
                ),
            },
            {"role": "user", "content": content},
            {
                "role": "user",
                "content": (
                    "Return only the exact IMPORTANT MEMORY TOKEN from earlier. "
                    "No explanation."
                ),
            },
        ],
        "temperature": 0,
    }

    attempts: list[dict[str, Any]] = []
    evidences: list[Evidence] = []
    budgets = (64, 256)

    for attempt_no, max_tokens in enumerate(budgets, 1):
        call = await client.post_json(
            probe_id=probe_id,
            path="/chat/completions",
            payload={**base_payload, "max_tokens": max_tokens},
        )
        ev = call.evidence
        evidences.append(ev)
        text = _message_text(call.json_body)
        reasoning = _reasoning_text(call.json_body)
        finish_reason = _finish_reason(call.json_body)
        final_hit = ev.response_status == 200 and needle in text
        reasoning_hit = ev.response_status == 200 and needle in reasoning
        attempts.append(
            {
                "attempt": attempt_no,
                "max_tokens": max_tokens,
                "http_status": ev.response_status,
                "finish_reason": finish_reason,
                "answer": text[:300],
                "reasoning_contains_needle": reasoning_hit,
                "final_contains_needle": final_hit,
            }
        )

        if ev.error:
            status = ProbeStatus.ERROR
            score = 0.0
            summary = ev.error
            break

        if final_hit:
            status = ProbeStatus.PASS
            score = 1.0
            summary = (
                f"needle recovered at approximately {approx_tokens} input tokens"
                if attempt_no == 1
                else (
                    f"needle recovered at approximately {approx_tokens} input tokens "
                    "after output-budget retry"
                )
            )
            break

        if ev.response_status in {400, 413, 422}:
            status = ProbeStatus.FAIL
            score = 0.0
            summary = (
                f"endpoint rejected approximately {approx_tokens} input tokens "
                f"(HTTP {ev.response_status})"
            )
            break

        if finish_reason == "length":
            if attempt_no < len(budgets):
                continue
            if any(row["reasoning_contains_needle"] for row in attempts):
                status = ProbeStatus.PASS
                score = 1.0
                summary = (
                    f"needle retrieval was observed at approximately {approx_tokens} "
                    "input tokens, but final output remained truncated"
                )
            else:
                status = ProbeStatus.INSUFFICIENT
                score = None
                summary = (
                    f"context result at approximately {approx_tokens} input tokens "
                    "remained output-truncated after retry"
                )
            break

        if reasoning_hit:
            status = ProbeStatus.PASS
            score = 1.0
            summary = (
                f"needle retrieval was observed in reasoning at approximately "
                f"{approx_tokens} input tokens"
            )
            break

        status = ProbeStatus.FAIL
        score = 0.0
        summary = (
            f"needle was not recovered at approximately {approx_tokens} input tokens"
        )
        break

    return (
        ProbeResult(
            probe_id=probe_id,
            category="context",
            status=status,
            score=score,
            confidence=0.9,
            summary=summary,
            observed={
                "http_status": evidences[-1].response_status if evidences else None,
                "answer": attempts[-1]["answer"] if attempts else "",
                "approx_input_tokens": approx_tokens,
                "attempts": attempts,
            },
            evidence_ids=[e.id for e in evidences],
            metadata={
                "approximate_tokens": True,
                "needle": needle,
                "retrieval_seen_in_reasoning": any(
                    row["reasoning_contains_needle"] for row in attempts
                ),
                "retried_for_output_truncation": len(attempts) > 1,
            },
        ),
        evidences,
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
        result, probe_evidence = await _needle_probe(client, model, level)
        results.append(result)
        evidences.extend(probe_evidence)

    if results:
        passed = sum(r.status == ProbeStatus.PASS for r in results)
        insufficient = sum(
            r.status == ProbeStatus.INSUFFICIENT for r in results
        )
        score = (
            passed / len(results)
            if not insufficient
            else None
        )
        results.append(
            ProbeResult(
                probe_id="context.summary",
                category="context",
                status=(
                    ProbeStatus.PASS
                    if passed == len(results)
                    else (
                        ProbeStatus.INSUFFICIENT
                        if insufficient
                        else (ProbeStatus.WARN if passed else ProbeStatus.FAIL)
                    )
                ),
                score=score,
                confidence=0.9,
                summary=(
                    f"context needle passed {passed}/{len(results)} tested levels"
                    + (
                        f"; {insufficient} level(s) remained output-truncated"
                        if insufficient else ""
                    )
                ),
                observed={
                    "tested_levels": levels,
                    "declared_context_tokens": declared_context_tokens,
                },
                evidence_ids=[e.id for e in evidences],
            )
        )
    return results, evidences

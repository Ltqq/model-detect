from __future__ import annotations

import json
import re
from typing import Any

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus


def _text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


def _completion_tokens(body: Any) -> int | None:
    if not isinstance(body, dict):
        return None
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get("completion_tokens")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


async def probe_reasoning_levels(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    results: list[ProbeResult] = []
    evidences: list[Evidence] = []
    observations = {}
    for level in ("low", "medium", "high"):
        probe_id = f"protocol.reasoning.{level}"
        call = await client.post_json(
            probe_id=probe_id,
            path="/chat/completions",
            payload={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "A farmer has 17 sheep. All but 9 run away. How many remain? Answer only the integer.",
                    }
                ],
                "reasoning_effort": level,
                "max_tokens": 96,
            },
        )
        ev = call.evidence
        evidences.append(ev)
        accepted = ev.response_status == 200
        body = call.json_body if isinstance(call.json_body, dict) else {}
        reasoning_tokens = None
        usage = body.get("usage") if isinstance(body, dict) else None
        if isinstance(usage, dict):
            details = usage.get("completion_tokens_details")
            if isinstance(details, dict):
                reasoning_tokens = details.get("reasoning_tokens")
        observations[level] = {
            "accepted": accepted,
            "completion_tokens": _completion_tokens(body),
            "reasoning_tokens": reasoning_tokens,
            "answer": _text(body)[:200],
        }
        results.append(
            ProbeResult(
                probe_id=probe_id,
                category="protocol",
                status=ProbeStatus.PASS if accepted else ProbeStatus.WARN,
                score=1.0 if accepted else 0.5,
                confidence=0.85,
                summary=(
                    f"reasoning_effort={level} accepted"
                    if accepted
                    else f"reasoning_effort={level} not accepted (HTTP {ev.response_status})"
                ),
                observed=observations[level],
                evidence_ids=[ev.id],
                metadata={"reasoning_effort_supported": accepted},
            )
        )

    accepted_levels = [k for k, v in observations.items() if v["accepted"]]
    token_values = [
        observations[x]["reasoning_tokens"]
        for x in accepted_levels
        if isinstance(observations[x]["reasoning_tokens"], int)
    ]
    if len(accepted_levels) < 2:
        status = ProbeStatus.INSUFFICIENT
        score = None
        summary = "not enough reasoning levels were accepted to compare effect"
    elif len(set(token_values)) >= 2:
        status = ProbeStatus.PASS
        score = 1.0
        summary = "reasoning levels produced observable reasoning-token differences"
    else:
        answers = [observations[x]["answer"] for x in accepted_levels]
        if len(set(answers)) >= 2:
            status = ProbeStatus.WARN
            score = 0.7
            summary = "reasoning levels were accepted and outputs differed, but reasoning-token telemetry is unavailable"
        else:
            status = ProbeStatus.INSUFFICIENT
            score = None
            summary = "reasoning levels were accepted but no reliable effect was observable"
    results.append(
        ProbeResult(
            probe_id="integrity.reasoning.effect",
            category="integrity",
            status=status,
            score=score,
            confidence=0.7,
            summary=summary,
            observed=observations,
            evidence_ids=[e.id for e in evidences],
        )
    )
    return results, evidences


async def probe_max_tokens(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    calls = []
    for limit in (8, 64):
        call = await client.post_json(
            probe_id="integrity.max_tokens",
            path="/chat/completions",
            payload={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Write the integers from 1 to 100 separated by single spaces and nothing else.",
                    }
                ],
                "temperature": 0,
                "max_tokens": limit,
            },
        )
        calls.append((limit, call))

    evidences = [x[1].evidence for x in calls]
    short_text = _text(calls[0][1].json_body)
    long_text = _text(calls[1][1].json_body)
    short_tokens = _completion_tokens(calls[0][1].json_body)
    long_tokens = _completion_tokens(calls[1][1].json_body)
    both_ok = all(c.evidence.response_status == 200 for _, c in calls)
    grew = (
        (short_tokens is not None and long_tokens is not None and long_tokens > short_tokens)
        or len(long_text) > max(len(short_text) * 1.35, len(short_text) + 8)
    )
    status = ProbeStatus.PASS if both_ok and grew else (ProbeStatus.WARN if both_ok else ProbeStatus.FAIL)
    score = 1.0 if status == ProbeStatus.PASS else (0.6 if status == ProbeStatus.WARN else 0.0)
    return [
        ProbeResult(
            probe_id="integrity.max_tokens",
            category="integrity",
            status=status,
            score=score,
            confidence=0.8,
            summary=(
                "larger max_tokens produced a larger completion"
                if status == ProbeStatus.PASS
                else "max_tokens effect could not be confirmed"
            ),
            observed={
                "short": {"limit": 8, "completion_tokens": short_tokens, "chars": len(short_text)},
                "long": {"limit": 64, "completion_tokens": long_tokens, "chars": len(long_text)},
            },
            evidence_ids=[e.id for e in evidences],
        )
    ], evidences


async def probe_stop(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    marker = "MD_STOP_4C91"
    probe_id = "integrity.stop"
    call = await client.post_json(
        probe_id=probe_id,
        path="/chat/completions",
        payload={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Output exactly: LEFT {marker} RIGHT",
                }
            ],
            "temperature": 0,
            "max_tokens": 64,
            "stop": [marker],
        },
    )
    ev = call.evidence
    text = _text(call.json_body)
    respected = ev.response_status == 200 and marker not in text and "RIGHT" not in text
    return [
        ProbeResult(
            probe_id=probe_id,
            category="integrity",
            status=ProbeStatus.PASS if respected else ProbeStatus.WARN,
            score=1.0 if respected else 0.5,
            confidence=0.75,
            summary="stop sequence appears preserved" if respected else "stop sequence behavior could not be confirmed",
            observed={"http_status": ev.response_status, "text": text[:300]},
            evidence_ids=[ev.id],
        )
    ], [ev]


async def probe_sampling_controls(
    client: AuditHttpClient, model: str
) -> tuple[list[ProbeResult], list[Evidence]]:
    evidences: list[Evidence] = []
    buckets: dict[str, list[str]] = {"deterministic": [], "creative": []}
    settings = [
        ("deterministic", 0.0, 1.0),
        ("creative", 1.2, 0.95),
    ]
    for label, temperature, top_p in settings:
        for i in range(4):
            call = await client.post_json(
                probe_id="integrity.sampling_controls",
                path="/chat/completions",
                payload={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Name one common fruit. Answer one lowercase English word only.",
                        }
                    ],
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": 16,
                },
            )
            evidences.append(call.evidence)
            buckets[label].append(_text(call.json_body).strip().lower())

    det_unique = len(set(x for x in buckets["deterministic"] if x))
    creative_unique = len(set(x for x in buckets["creative"] if x))
    if creative_unique > det_unique:
        status = ProbeStatus.PASS
        score = 1.0
        summary = "sampling controls produced greater diversity at higher temperature"
    elif any(buckets.values()):
        status = ProbeStatus.INSUFFICIENT
        score = None
        summary = "sampling parameters were accepted but their effect was not statistically clear"
    else:
        status = ProbeStatus.WARN
        score = 0.5
        summary = "sampling-control responses were unusable"
    return [
        ProbeResult(
            probe_id="integrity.sampling_controls",
            category="integrity",
            status=status,
            score=score,
            confidence=0.55,
            summary=summary,
            observed={
                "deterministic": buckets["deterministic"],
                "creative": buckets["creative"],
                "deterministic_unique": det_unique,
                "creative_unique": creative_unique,
            },
            evidence_ids=[e.id for e in evidences],
        )
    ], evidences


async def run_integrity_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
) -> tuple[list[ProbeResult], list[Evidence]]:
    if profile.lower() == "quick":
        return [], []
    runners = [probe_reasoning_levels, probe_max_tokens, probe_stop]
    if profile.lower() == "deep":
        runners.append(probe_sampling_controls)

    results: list[ProbeResult] = []
    evidences: list[Evidence] = []
    for runner in runners:
        rs, evs = await runner(client, model)
        results.extend(rs)
        evidences.extend(evs)
    return results, evidences

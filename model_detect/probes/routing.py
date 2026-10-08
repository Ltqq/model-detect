from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus


def _text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


def _response_signature(body: Any) -> str:
    if not isinstance(body, dict):
        return "non-json"
    keys = sorted(body.keys())
    choices = body.get("choices")
    choice_keys = []
    message_keys = []
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice_keys = sorted(choices[0].keys())
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            message_keys = sorted(msg.keys())
    return json.dumps(
        {"top": keys, "choice": choice_keys, "message": message_keys},
        sort_keys=True,
    )


def _usage_signature(body: Any) -> str:
    if not isinstance(body, dict):
        return "none"
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return "none"
    details = {}
    for key, value in usage.items():
        if key.endswith("_details") and isinstance(value, dict):
            details[key] = sorted(value.keys())
    return json.dumps(
        {
            "usage_keys": sorted(usage.keys()),
            "detail_keys": details,
        },
        sort_keys=True,
    )


def _header_signature(headers: dict[str, str]) -> tuple[str, ...]:
    keep = []
    for raw_key in headers:
        key = str(raw_key).lower()
        if (
            key == "server"
            or key == "via"
            or key.startswith("x-")
            or key.startswith("cf-")
            or key.startswith("apim-")
        ):
            keep.append(key)
    return tuple(sorted(set(keep)))


def _id_prefix(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    # Many providers emit IDs as "<stable-prefix>-<random-suffix>" or
    # "<stable-prefix>_<random-suffix>". Do not let the first random hex
    # letter become part of the prefix (for example chatcmpl-f...).
    for separator in ("-", "_"):
        if separator not in value:
            continue
        head, tail = value.split(separator, 1)
        if (
            head
            and len(tail) >= 8
            and re.fullmatch(r"[A-Za-z0-9]+", tail)
        ):
            return head + separator

    match = re.match(r"^([A-Za-z_-]+)", value)
    return match.group(1) if match else None


def _normalize_answer(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _feature_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("model"),
        row.get("id_prefix"),
        row.get("signature"),
        row.get("finish_reason"),
        row.get("usage_signature"),
        tuple(row.get("header_signature") or ()),
    )


def cluster_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[Any, ...]] = Counter(_feature_key(row) for row in rows)
    out = []
    for key, count in counts.most_common():
        out.append(
            {
                "count": count,
                "features": {
                    "model": key[0],
                    "id_prefix": key[1],
                    "signature": key[2],
                    "finish_reason": key[3],
                    "usage_signature": key[4],
                    "header_signature": list(key[5]),
                },
            }
        )
    return out


def _row_from_call(call: Any, *, window: int, sample: int) -> dict[str, Any]:
    body = call.json_body if isinstance(call.json_body, dict) else {}
    choice = None
    if isinstance(body.get("choices"), list) and body["choices"]:
        choice = body["choices"][0]
    return {
        "window": window,
        "sample": sample,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": call.evidence.response_status,
        "model": body.get("model"),
        "id_prefix": _id_prefix(body.get("id")),
        "signature": _response_signature(body),
        "usage_signature": _usage_signature(body),
        "header_signature": list(_header_signature(call.evidence.response_headers)),
        "answer": _text(body).strip(),
        "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
    }


async def _repeat_windows(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
) -> tuple[list[dict[str, Any]], list[Evidence]]:
    if profile == "standard":
        window_count = 2
        samples_per_window = 3
    else:
        window_count = 3
        samples_per_window = 4

    rows: list[dict[str, Any]] = []
    evidences: list[Evidence] = []
    for window in range(window_count):
        for sample in range(samples_per_window):
            call = await client.post_json(
                probe_id="routing.repeat.same_probe",
                path="/chat/completions",
                payload={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Answer only the integer result of 37 + 58.",
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 16,
                },
            )
            evidences.append(call.evidence)
            rows.append(_row_from_call(call, window=window, sample=sample))
        if window + 1 < window_count:
            await asyncio.sleep(0.25)
    return rows, evidences


def _repeat_results(
    rows: list[dict[str, Any]],
    evidences: list[Evidence],
) -> list[ProbeResult]:
    model_values = sorted({str(x["model"]) for x in rows if x.get("model")})
    signatures = sorted({x["signature"] for x in rows})
    id_prefixes = sorted({x["id_prefix"] for x in rows if x.get("id_prefix")})
    usage_signatures = sorted({x["usage_signature"] for x in rows})
    header_signatures = sorted({tuple(x["header_signature"]) for x in rows})
    answers = [x["answer"] for x in rows if x["answer"]]
    distinct_answers = len(set(answers))
    windows = sorted({int(x["window"]) for x in rows})

    flags = []
    if len(model_values) > 1:
        flags.append("model field changed")
    if len(signatures) > 1:
        flags.append("response schema changed")
    if len(id_prefixes) > 1:
        flags.append("response id prefix changed")
    if len(usage_signatures) > 1:
        flags.append("usage/reasoning metadata shape changed")
    if len(header_signatures) > 1:
        flags.append("provider-style response header shape changed")
    if distinct_answers > 2:
        flags.append("temperature=0 answer was unusually unstable")

    if len(model_values) > 1:
        status = ProbeStatus.FAIL
        score = 0.0
        verdict = "mixed-routing-likely"
    elif flags:
        status = ProbeStatus.WARN
        score = 0.6
        verdict = "suspicious"
    elif answers:
        status = ProbeStatus.PASS
        score = 1.0
        verdict = "stable"
    else:
        status = ProbeStatus.INSUFFICIENT
        score = None
        verdict = "insufficient"

    clusters = cluster_rows(rows)
    if len(clusters) == 1:
        cluster_status = ProbeStatus.PASS
        cluster_score = 1.0
        cluster_verdict = "stable"
    elif len(model_values) > 1:
        cluster_status = ProbeStatus.FAIL
        cluster_score = 0.0
        cluster_verdict = "mixed-routing-likely"
    else:
        cluster_status = ProbeStatus.WARN
        cluster_score = 0.6
        cluster_verdict = "suspicious"

    evidence_ids = [e.id for e in evidences]
    return [
        ProbeResult(
            probe_id="routing.repeat.same_probe",
            category="routing",
            status=status,
            score=score,
            confidence=0.88 if len(rows) >= 10 else 0.75,
            summary=(
                f"routing verdict={verdict} across {len(windows)} sampling windows"
                + (f"; {', '.join(flags)}" if flags else "")
            ),
            observed={
                "samples": len(rows),
                "windows": windows,
                "models": model_values,
                "id_prefixes": id_prefixes,
                "signature_count": len(signatures),
                "usage_signature_count": len(usage_signatures),
                "header_signature_count": len(header_signatures),
                "distinct_answers": distinct_answers,
                "rows": rows,
            },
            evidence_ids=evidence_ids,
            metadata={
                "verdict": verdict,
                "signals": flags,
                "window_count": len(windows),
            },
        ),
        ProbeResult(
            probe_id="routing.cluster",
            category="routing",
            status=cluster_status,
            score=cluster_score,
            confidence=0.82 if len(rows) >= 10 else 0.7,
            summary=f"explainable routing feature buckets={len(clusters)} ({cluster_verdict})",
            observed={
                "cluster_count": len(clusters),
                "clusters": clusters,
                "signals": flags,
            },
            evidence_ids=evidence_ids,
            metadata={
                "verdict": cluster_verdict,
                "cluster_method": "exact-explainable-feature-bucket",
                "model_drift": len(model_values) > 1,
            },
        ),
    ]


async def _tool_style_consistency(
    client: AuditHttpClient,
    model: str,
) -> tuple[ProbeResult, list[Evidence]]:
    tool = {
        "type": "function",
        "function": {
            "name": "route_probe",
            "description": "Return the provided routing token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token": {"type": "string", "enum": ["ROUTE_TOOL_17"]},
                },
                "required": ["token"],
                "additionalProperties": False,
            },
        },
    }
    rows = []
    evidences = []
    for index in range(4):
        call = await client.post_json(
            probe_id="routing.tool_style",
            path="/chat/completions",
            payload={
                "model": model,
                "messages": [{"role": "user", "content": "Call route_probe."}],
                "tools": [tool],
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "route_probe"},
                },
                "temperature": 0,
                "max_tokens": 96,
            },
        )
        evidences.append(call.evidence)
        body = call.json_body if isinstance(call.json_body, dict) else {}
        calls = []
        try:
            calls = body["choices"][0]["message"].get("tool_calls") or []
        except Exception:
            calls = []
        first = calls[0] if calls and isinstance(calls[0], dict) else {}
        function = first.get("function") if isinstance(first.get("function"), dict) else {}
        rows.append(
            {
                "tool_call_id_prefix": _id_prefix(first.get("id")),
                "name": function.get("name"),
                "arguments_type": type(function.get("arguments")).__name__,
                "finish_reason": (
                    body["choices"][0].get("finish_reason")
                    if isinstance(body.get("choices"), list) and body["choices"]
                    else None
                ),
            }
        )
    signatures = {
        (
            x["tool_call_id_prefix"],
            x["name"],
            x["arguments_type"],
            x["finish_reason"],
        )
        for x in rows
    }
    stable = len(signatures) <= 1 and bool(rows)
    return (
        ProbeResult(
            probe_id="routing.tool_style",
            category="routing",
            status=ProbeStatus.PASS if stable else ProbeStatus.WARN,
            score=1.0 if stable else 0.6,
            confidence=0.65,
            summary=(
                "tool-call response style was stable"
                if stable
                else f"tool-call response style changed across {len(signatures)} signatures"
            ),
            observed={"rows": rows, "signature_count": len(signatures)},
            evidence_ids=[x.id for x in evidences],
        ),
        evidences,
    )


async def _fact_inversion(
    client: AuditHttpClient,
    model: str,
) -> tuple[ProbeResult, list[Evidence]]:
    facts = [
        ("gold-symbol", "What is the chemical symbol for gold? Answer only the symbol.", "au"),
        ("france-capital", "What is the capital of France? Answer only the city name.", "paris"),
        ("binary-1010", "Convert binary 1010 to decimal. Answer only the integer.", "10"),
        ("water-formula", "What is the chemical formula of water? Answer only the formula.", "h2o"),
    ]
    rows = []
    evidences = []
    inversion_count = 0
    for fact_id, prompt, expected in facts:
        outputs = []
        for _ in range(3):
            call = await client.post_json(
                probe_id="routing.fact_inversion",
                path="/chat/completions",
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 24,
                },
            )
            evidences.append(call.evidence)
            outputs.append(_normalize_answer(_text(call.json_body)))
        distinct = sorted(set(x for x in outputs if x))
        has_expected = expected in distinct
        has_other = any(x != expected for x in distinct)
        inverted = has_expected and has_other
        inversion_count += int(inverted)
        rows.append(
            {
                "fact_id": fact_id,
                "expected": expected,
                "outputs": outputs,
                "distinct": distinct,
                "inversion": inverted,
            }
        )

    if inversion_count == 0:
        status = ProbeStatus.PASS
        score = 1.0
        verdict = "stable"
    elif inversion_count == 1:
        status = ProbeStatus.WARN
        score = 0.6
        verdict = "suspicious"
    else:
        status = ProbeStatus.WARN
        score = 0.3
        verdict = "highly-suspicious"

    return (
        ProbeResult(
            probe_id="routing.fact_inversion",
            category="routing",
            status=status,
            score=score,
            confidence=0.7,
            summary=f"fact inversion count={inversion_count}/4 ({verdict})",
            observed={"facts": rows, "inversion_count": inversion_count},
            evidence_ids=[x.id for x in evidences],
            metadata={
                "verdict": verdict,
                "mixed_routing_proof": False,
            },
        ),
        evidences,
    )


async def _quality_strata(
    client: AuditHttpClient,
    model: str,
) -> tuple[ProbeResult, list[Evidence]]:
    tasks = {
        "simple": [
            ("What is 2 + 2? Answer only the integer.", "4"),
            ("What is the capital of Japan? Answer only the city.", "tokyo"),
        ],
        "complex": [
            (
                "If a train travels 60 km in 45 minutes at constant speed, how many km does it travel in 2 hours? Answer only the integer.",
                "160",
            ),
            (
                "What is the next number: 2, 6, 12, 20, 30, ? Answer only the integer.",
                "42",
            ),
        ],
    }
    observed = {}
    evidences = []
    for stratum, items in tasks.items():
        task_rows = []
        for prompt, expected in items:
            outputs = []
            for _ in range(3):
                call = await client.post_json(
                    probe_id="routing.quality_inversion",
                    path="/chat/completions",
                    payload={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 32,
                    },
                )
                evidences.append(call.evidence)
                outputs.append(_normalize_answer(_text(call.json_body)))
            task_rows.append(
                {
                    "expected": expected,
                    "outputs": outputs,
                    "pass_count": sum(x == expected for x in outputs),
                }
            )
        observed[stratum] = task_rows

    simple_total = sum(x["pass_count"] for x in observed["simple"])
    complex_total = sum(x["pass_count"] for x in observed["complex"])
    inversion = simple_total <= 1 and complex_total >= 4
    return (
        ProbeResult(
            probe_id="routing.quality_inversion",
            category="routing",
            status=ProbeStatus.WARN if inversion else ProbeStatus.PASS,
            score=0.5 if inversion else 1.0,
            confidence=0.55,
            summary=(
                "simple/complex quality inversion observed"
                if inversion
                else "no simple/complex quality inversion observed"
            ),
            observed={
                **observed,
                "simple_passes": simple_total,
                "complex_passes": complex_total,
            },
            evidence_ids=[x.id for x in evidences],
            metadata={
                "quality_inversion": inversion,
                "mixed_routing_proof": False,
            },
        ),
        evidences,
    )


def finalize_routing_analysis(results: list[ProbeResult]) -> ProbeResult:
    by_id = {r.probe_id: r for r in results}
    candidate_ids = [
        "routing.repeat.same_probe",
        "routing.cluster",
        "routing.tool_style",
        "routing.fact_inversion",
        "routing.quality_inversion",
        "routing.fingerprint.consistency",
    ]
    available = [by_id[x] for x in candidate_ids if x in by_id]

    strong = []
    suspicious = []
    for result in available:
        if result.metadata.get("verdict") == "mixed-routing-likely":
            strong.append(result.probe_id)
        elif result.probe_id == "routing.cluster" and result.metadata.get("model_drift"):
            strong.append(result.probe_id)
        elif result.status == ProbeStatus.WARN:
            suspicious.append(result.probe_id)

    fingerprint_identity = by_id.get("identity.fingerprint.reference_compare")
    reference_mean_jsd = None
    if fingerprint_identity and isinstance(fingerprint_identity.observed, dict):
        reference_mean_jsd = fingerprint_identity.observed.get("mean_jsd")

    if strong:
        status = ProbeStatus.FAIL
        score = 0.0
        verdict = "mixed-routing-likely"
        confidence = 0.9
    elif len(suspicious) >= 2:
        status = ProbeStatus.WARN
        score = 0.4
        verdict = "suspicious"
        confidence = 0.75
    elif available:
        status = ProbeStatus.PASS
        score = 1.0
        verdict = "stable"
        confidence = 0.7
    else:
        status = ProbeStatus.INSUFFICIENT
        score = None
        verdict = "insufficient"
        confidence = 0.0

    evidence_ids = []
    for result in available:
        evidence_ids.extend(result.evidence_ids)

    return ProbeResult(
        probe_id="routing.summary",
        category="routing",
        status=status,
        score=score,
        confidence=confidence,
        summary=(
            f"routing evidence fusion={verdict}; "
            f"strong={strong or 'none'}; suspicious={suspicious or 'none'}"
        ),
        observed={
            "signals": [
                {
                    "probe_id": r.probe_id,
                    "status": r.status.value,
                    "score": r.score,
                    "summary": r.summary,
                }
                for r in available
            ],
            "strong_signals": strong,
            "suspicious_signals": suspicious,
            "reference_mean_jsd": reference_mean_jsd,
        },
        evidence_ids=list(dict.fromkeys(evidence_ids)),
        metadata={
            "verdict": verdict,
            "reference_assisted": fingerprint_identity is not None,
            "fusion_method": "rule-based-explainable",
        },
    )


async def run_routing_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
) -> tuple[list[ProbeResult], list[Evidence]]:
    profile = profile.lower()
    if profile == "quick":
        return [], []

    rows, evidences = await _repeat_windows(client, model, profile=profile)
    results = _repeat_results(rows, evidences)

    if profile == "deep":
        tool_result, tool_evs = await _tool_style_consistency(client, model)
        fact_result, fact_evs = await _fact_inversion(client, model)
        quality_result, quality_evs = await _quality_strata(client, model)
        results.extend([tool_result, fact_result, quality_result])
        evidences.extend(tool_evs)
        evidences.extend(fact_evs)
        evidences.extend(quality_evs)

    return results, evidences

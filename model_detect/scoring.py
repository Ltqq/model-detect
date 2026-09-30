from __future__ import annotations

from collections import defaultdict

from .models import AuditSummary, ProbeResult, ProbeStatus


DEFAULT_CATEGORY_WEIGHTS = {
    "identity": 35.0,
    "protocol": 20.0,
    "integrity": 15.0,
    "context": 10.0,
    "routing": 10.0,
    "capability": 10.0,
}


def build_summary(results: list[ProbeResult]) -> AuditSummary:
    by_category: dict[str, list[float]] = defaultdict(list)
    warnings: list[str] = []

    for result in results:
        if result.score is not None:
            by_category[result.category].append(max(0.0, min(1.0, result.score)))
        if result.status in {ProbeStatus.FAIL, ProbeStatus.WARN}:
            warnings.append(f"{result.probe_id}: {result.summary}")

    category_scores = {
        category: round(sum(values) / len(values) * 100, 1)
        for category, values in by_category.items()
        if values
    }
    coverage = {
        category: bool(by_category.get(category))
        for category in DEFAULT_CATEGORY_WEIGHTS
    }

    weighted = 0.0
    weight_total = 0.0
    for category, weight in DEFAULT_CATEGORY_WEIGHTS.items():
        if category in category_scores:
            weighted += category_scores[category] * weight
            weight_total += weight

    overall = round(weighted / weight_total, 1) if weight_total else None
    hard_cap = None

    identity_mismatch = any(
        r.category == "identity"
        and (
            r.status == ProbeStatus.FAIL
            or r.metadata.get("verdict") == "mismatch"
        )
        for r in results
    )
    mixed_routing = any(
        r.probe_id.startswith("routing.")
        and r.status == ProbeStatus.FAIL
        for r in results
    )
    protocol_critical = any(
        r.probe_id in {"protocol.chat.basic", "protocol.chat.stream"}
        and r.status == ProbeStatus.FAIL
        for r in results
    )

    if identity_mismatch:
        hard_cap = 40.0
    elif mixed_routing:
        hard_cap = 60.0
    elif protocol_critical:
        hard_cap = 60.0

    if overall is not None and hard_cap is not None:
        overall = min(overall, hard_cap)

    covered_count = sum(coverage.values())
    if coverage["identity"] and covered_count >= 4:
        confidence = "high"
    elif coverage["identity"] or covered_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if not coverage["identity"]:
        warnings.append(
            "identity evidence is insufficient; configure a trusted reference "
            "or install/enable an identity detector before treating the endpoint as verified"
        )

    if overall is None:
        verdict = "insufficient"
    elif identity_mismatch:
        verdict = "mismatch"
    elif overall >= 85 and coverage["identity"]:
        verdict = "pass"
    elif overall >= 70:
        verdict = "review"
    else:
        verdict = "fail"

    return AuditSummary(
        overall_score=overall,
        category_scores=category_scores,
        coverage=coverage,
        hard_cap=hard_cap,
        final_verdict=verdict,
        confidence=confidence,
        warnings=list(dict.fromkeys(warnings)),
    )

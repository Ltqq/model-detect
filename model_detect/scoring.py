from __future__ import annotations

from collections import defaultdict

from .models import AuditSummary, ProbeResult, ProbeStatus


COVERAGE_CATEGORIES = (
    "identity", "protocol", "integrity", "context", "routing",
    "capability", "benchmark", "provider",
)



def build_summary(results: list[ProbeResult]) -> AuditSummary:
    by_category: dict[str, list[float]] = defaultdict(list)
    warnings: list[str] = []

    for result in results:
        # Source-backed feature support is NOT model-weight identity evidence.
        # Do not award a perfect identity category just because one tool-call
        # probe passed while identity reference tests were not run.
        weak_identity = (
            result.category == "identity"
            and result.metadata.get("identity_strength") not in {"medium", "strong"}
        )
        if (
            result.score is not None
            and not weak_identity
            and result.status not in {
                ProbeStatus.SKIPPED, ProbeStatus.INSUFFICIENT, ProbeStatus.ERROR
            }
        ):
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
        for category in COVERAGE_CATEGORIES
    }

    # Cross-category weighted scores are not scientifically comparable:
    # Quick/Standard may run only a subset of categories, and the category
    # weights have not been calibrated against labeled provider substitutions.
    # Keep per-category evidence, but never normalize the tested subset into a
    # single overall score.
    overall = None
    hard_cap = None

    identity_mismatch = any(
        r.category == "identity"
        and r.metadata.get("identity_strength") == "strong"
        and r.metadata.get("verdict") == "mismatch"
        for r in results
    )
    mixed_routing = any(
        r.probe_id.startswith("routing.")
        and r.status == ProbeStatus.FAIL
        for r in results
    )
    upstream_policy_violation = any(
        r.metadata.get("policy_violation") is True
        and r.status == ProbeStatus.FAIL
        for r in results
    )

    strong_identity = any(
        r.category == "identity"
        and r.score is not None
        and r.metadata.get("identity_strength") == "strong"
        and r.status in {ProbeStatus.PASS, ProbeStatus.WARN, ProbeStatus.FAIL}
        for r in results
    )
    medium_identity = any(
        r.category == "identity"
        and r.score is not None
        and r.metadata.get("identity_strength") in {"medium", "strong"}
        for r in results
    )


    covered_count = sum(coverage.values())
    if strong_identity and covered_count >= 4:
        confidence = "high"
    elif medium_identity or covered_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if not strong_identity:
        warnings.append(
            "model weight identity is not certified by this black-box audit; "
            "official API or fingerprint references are optional for protocol checks"
        )

    # Admission is now evidence-first: an old arbitrary weighted score or
    # uncalibrated fingerprint may not turn functional API compliance into
    # an identity failure. Preserve numeric fields for archived report readers.
    core = [
        r for r in results
        if r.probe_id in {"protocol.chat.basic", "protocol.chat.stream"}
    ]
    core_fail = any(r.status == ProbeStatus.FAIL for r in core)
    core_uncertain = any(
        r.status in {ProbeStatus.ERROR, ProbeStatus.INSUFFICIENT, ProbeStatus.SKIPPED}
        for r in core
    )
    other_protocol_fail = any(
        r.category in {"protocol", "integrity"}
        and r.status == ProbeStatus.FAIL
        and r.probe_id not in {"protocol.chat.basic", "protocol.chat.stream"}
        for r in results
    )
    any_warning = any(
        r.status in {ProbeStatus.FAIL, ProbeStatus.WARN, ProbeStatus.ERROR}
        or (
            r.status == ProbeStatus.INSUFFICIENT
            and r.category in {"protocol", "integrity"}
        )
        for r in results
    )
    # Quick does not run statistical identity or repeated routing checks.
    # No reference / unmeasured features are coverage gaps, not API failures.

    if upstream_policy_violation:
        verdict = "fail"
    elif core_fail:
        verdict = "fail"
    elif not core or core_uncertain or not any(r.status == ProbeStatus.PASS for r in core):
        verdict = "insufficient"
    elif identity_mismatch or mixed_routing or other_protocol_fail or any_warning:
        verdict = "review"
    else:
        verdict = "pass"

    return AuditSummary(
        overall_score=overall,
        category_scores=category_scores,
        coverage=coverage,
        hard_cap=hard_cap,
        final_verdict=verdict,
        confidence=confidence,
        warnings=list(dict.fromkeys(warnings)),
    )

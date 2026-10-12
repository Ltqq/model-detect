from __future__ import annotations

import statistics
from typing import Any, Literal

from pydantic import BaseModel, Field

from .baseline import (
    BASELINE_DIMENSIONS,
    BASELINE_SUITE_VERSION,
    OfficialBaseline,
)
from .models import AuditReport, ProbeResult, ProbeStatus


QualityVerdict = Literal[
    "baseline_match",
    "quality_regression",
    "baseline_insufficient",
]


class QualityDimensionComparison(BaseModel):
    dimension: str
    probe_id: str
    baseline_mean: float
    baseline_stddev: float | None = None
    baseline_runs: int
    target_score: float
    delta: float
    retention_ratio: float | None = None
    natural_tolerance: float | None = None
    lower_bound: float | None = None
    task_granularity: float | None = None
    statistically_evaluable: bool = False
    contract_valid: bool = False
    verdict: Literal["match", "regression", "informational", "incomparable"]
    explanation: str


class QualityComparison(BaseModel):
    schema_version: int = 1
    suite_version: str
    model: str
    profile: str
    verdict: QualityVerdict
    comparable_dimensions: int = 0
    statistically_evaluable_dimensions: int = 0
    regression_dimensions: list[str] = Field(default_factory=list)
    incomparable_dimensions: list[str] = Field(default_factory=list)
    dimensions: dict[str, QualityDimensionComparison] = Field(
        default_factory=dict
    )
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _target_scores(report: AuditReport) -> dict[str, float]:
    by_id = {result.probe_id: result for result in report.results}
    out: dict[str, float] = {}
    for dimension, probe_id in BASELINE_DIMENSIONS.items():
        result = by_id.get(probe_id)
        if result is None or result.score is None:
            continue
        out[dimension] = float(result.score)
    for result in report.results:
        if (
            result.score is not None
            and result.metadata.get("engine") == "lm-evaluation-harness"
            and result.metadata.get("task")
        ):
            out[f"benchmark:{result.metadata['task']}"] = float(result.score)
    return out


def _task_granularity(task_totals: list[int]) -> float | None:
    valid = [int(value) for value in task_totals if int(value) > 0]
    if not valid:
        return None
    typical_total = statistics.median(valid)
    if typical_total <= 0:
        return None
    return 1.0 / float(typical_total)


def compare_report_to_baseline(
    report: AuditReport,
    baseline: OfficialBaseline,
) -> tuple[QualityComparison, list[ProbeResult]]:
    model = str(report.target.get("model") or "")
    warnings: list[str] = []

    if baseline.suite_version != BASELINE_SUITE_VERSION:
        comparison = QualityComparison(
            suite_version=baseline.suite_version,
            model=model,
            profile=report.profile,
            verdict="baseline_insufficient",
            warnings=[
                (
                    "baseline suite version mismatch: "
                    f"reference={baseline.suite_version!r}, "
                    f"current={BASELINE_SUITE_VERSION!r}; recollect the baseline"
                )
            ],
            metadata={"same_suite_required": True},
        )
        return comparison, [_summary_result(comparison)]

    if model != baseline.model:
        comparison = QualityComparison(
            suite_version=baseline.suite_version,
            model=model,
            profile=report.profile,
            verdict="baseline_insufficient",
            warnings=[
                (
                    "baseline model mismatch: "
                    f"reference={baseline.model!r}, target={model!r}"
                )
            ],
            metadata={"same_suite_required": True},
        )
        return comparison, [_summary_result(comparison)]

    if report.profile != baseline.profile:
        comparison = QualityComparison(
            suite_version=baseline.suite_version,
            model=model,
            profile=report.profile,
            verdict="baseline_insufficient",
            warnings=[
                (
                    "baseline profile mismatch: "
                    f"reference={baseline.profile!r}, target={report.profile!r}; "
                    "quality comparison requires the same suite/profile"
                )
            ],
            metadata={"same_suite_required": True},
        )
        return comparison, [_summary_result(comparison)]

    from .comparison_contract import build_dimension_contracts
    target_scores = _target_scores(report)
    target_contracts = build_dimension_contracts(report)
    dimensions: dict[str, QualityDimensionComparison] = {}
    results: list[ProbeResult] = []
    regression_dimensions: list[str] = []
    incomparable_dimensions: list[str] = []
    statistically_evaluable = 0

    for dimension, baseline_metric in baseline.dimensions.items():
        target = target_scores.get(dimension)
        mean = baseline_metric.mean
        if target is None or mean is None:
            incomparable_dimensions.append(dimension)
            warnings.append(f"{dimension}: missing target or reference score")
            continue

        reference_contract = baseline.dimension_contracts.get(dimension)
        target_contract = target_contracts.get(dimension)
        contract_valid = bool(
            reference_contract
            and target_contract
            and reference_contract == target_contract
            and dimension not in baseline.incompatible_dimensions
        )
        if not contract_valid:
            incomparable_dimensions.append(dimension)
            warnings.append(
                f"{dimension}: missing or different comparison contract; "
                "recollect reference / use identical inputs and benchmark settings"
            )

        delta = target - mean
        retention = target / mean if mean > 0 else None
        granularity = _task_granularity(baseline_metric.task_total)
        can_evaluate = contract_valid and baseline_metric.run_count >= 3
        tolerance = None
        lower_bound = None

        if can_evaluate:
            statistically_evaluable += 1
            variance_tolerance = (
                2.0 * float(baseline_metric.stddev)
                if baseline_metric.stddev is not None
                else 0.0
            )
            tolerance = max(
                variance_tolerance,
                granularity or 0.0,
            )
            lower_bound = max(0.0, mean - tolerance)
            is_regression = target < lower_bound
            verdict = "regression" if is_regression else "match"
            if is_regression:
                regression_dimensions.append(dimension)
            explanation = (
                (
                    f"target {target:.3f} is below trusted baseline lower bound "
                    f"{lower_bound:.3f}"
                )
                if is_regression
                else (
                    f"target {target:.3f} remains within the trusted baseline "
                    f"range (lower bound {lower_bound:.3f})"
                )
            )
        elif not contract_valid:
            verdict = "incomparable"
            explanation = (
                "reference and target used different/unknown inputs, tasks, "
                "sampling parameters, or benchmark versions; quality comparison "
                "is not valid"
            )
        else:
            verdict = "informational"
            explanation = (
                f"baseline has only {baseline_metric.run_count} run(s); "
                "delta is informational and normal-variation claims are disabled"
            )

        item = QualityDimensionComparison(
            dimension=dimension,
            probe_id=BASELINE_DIMENSIONS.get(
                dimension,
                f"quality.baseline.{dimension}",
            ),
            baseline_mean=mean,
            baseline_stddev=baseline_metric.stddev,
            baseline_runs=baseline_metric.run_count,
            target_score=target,
            delta=delta,
            retention_ratio=retention,
            natural_tolerance=tolerance,
            lower_bound=lower_bound,
            task_granularity=granularity,
            statistically_evaluable=can_evaluate,
            contract_valid=contract_valid,
            verdict=verdict,
            explanation=explanation,
        )
        dimensions[dimension] = item
        results.append(_dimension_result(item))

    # A vendor-only benchmark is also not an official comparison.
    for dimension in target_scores:
        if (
            dimension.startswith("benchmark:")
            and dimension not in baseline.dimensions
        ):
            incomparable_dimensions.append(dimension)
            warnings.append(
                f"{dimension}: trusted reference did not run this benchmark"
            )

    if not dimensions:
        verdict: QualityVerdict = "baseline_insufficient"
        warnings.append(
            "no comparable quality dimensions between target and trusted baseline"
        )
    elif statistically_evaluable == 0:
        verdict = "baseline_insufficient"
        warnings.append(
            "trusted baseline needs at least 3 repeated runs before natural "
            "variation can be estimated"
        )
    elif regression_dimensions:
        verdict = "quality_regression"
    elif incomparable_dimensions:
        verdict = "baseline_insufficient"
    else:
        verdict = "baseline_match"

    comparison = QualityComparison(
        suite_version=baseline.suite_version,
        model=model,
        profile=report.profile,
        verdict=verdict,
        comparable_dimensions=len(dimensions),
        statistically_evaluable_dimensions=statistically_evaluable,
        regression_dimensions=regression_dimensions,
        incomparable_dimensions=incomparable_dimensions,
        dimensions=dimensions,
        warnings=warnings,
        metadata={
            "same_suite_required": True,
            "baseline_runs": baseline.runs,
            "model_rule_id": baseline.model_rule_id,
            "model_rule_updated_at": baseline.model_rule_updated_at,
            "quantization_format_inference": False,
            "performance_metrics_included": False,
            "threshold_method": (
                "baseline_mean - max(2*sample_stddev, one_task_granularity)"
            ),
        },
    )
    results.append(_summary_result(comparison))
    return comparison, results


def _dimension_result(item: QualityDimensionComparison) -> ProbeResult:
    status = {
        "match": ProbeStatus.PASS,
        "regression": ProbeStatus.FAIL,
        "informational": ProbeStatus.INSUFFICIENT,
        "incomparable": ProbeStatus.INSUFFICIENT,
    }[item.verdict]
    return ProbeResult(
        probe_id=f"quality.baseline.{item.dimension}",
        category="quality",
        status=status,
        score=item.target_score if item.contract_valid else None,
        confidence=0.9 if item.statistically_evaluable else 0.0,
        summary=item.explanation,
        expected={
            "baseline_mean": item.baseline_mean,
            "baseline_stddev": item.baseline_stddev,
            "lower_bound": item.lower_bound,
            "baseline_runs": item.baseline_runs,
        },
        observed={
            "target_score": item.target_score,
            "delta": item.delta,
            "retention_ratio": item.retention_ratio,
        },
        metadata={
            "quality_regression": item.verdict == "regression",
            "statistically_evaluable": item.statistically_evaluable,
            "dimension": item.dimension,
            "contract_valid": item.contract_valid,
            "threshold_method": "trusted-baseline-variation",
        },
    )


def _summary_result(comparison: QualityComparison) -> ProbeResult:
    status = {
        "baseline_match": ProbeStatus.PASS,
        "quality_regression": ProbeStatus.FAIL,
        "baseline_insufficient": ProbeStatus.INSUFFICIENT,
    }[comparison.verdict]
    summary = {
        "baseline_match": (
            "target quality remains within the repeated trusted baseline range"
        ),
        "quality_regression": (
            "quality regression detected in: "
            + ", ".join(comparison.regression_dimensions)
        ),
        "baseline_insufficient": (
            comparison.warnings[0]
            if comparison.warnings
            else "trusted baseline is insufficient for quality comparison"
        ),
    }[comparison.verdict]
    return ProbeResult(
        probe_id="quality.baseline.summary",
        category="quality",
        status=status,
        score=None,
        confidence=(
            0.9
            if comparison.verdict in {"baseline_match", "quality_regression"}
            else 0.4
        ),
        summary=summary,
        observed=comparison.model_dump(mode="json"),
        metadata={
            "quality_verdict": comparison.verdict,
            "regression_dimensions": list(comparison.regression_dimensions),
            "incomparable_dimensions": list(comparison.incomparable_dimensions),
            "identity_strength": "none",
            "quantization_format_proof": False,
        },
    )

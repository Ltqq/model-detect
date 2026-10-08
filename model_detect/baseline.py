from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .models import AuditReport, ProbeResult


BASELINE_SCHEMA_VERSION = 1
BASELINE_SUITE_VERSION = "official-baseline-v1"

# Stable, low-cost dimensions that can be executed against both an official endpoint
# and a supplier endpoint with the same harness.
BASELINE_DIMENSIONS: dict[str, str] = {
    "reasoning": "capability.reasoning",
    "math": "capability.math",
    "coding_reasoning": "capability.coding",
    "chinese": "capability.chinese",
    "instruction_following": "capability.instruction_following",
    "tool_use": "capability.tool_use",
    "structured_output": "capability.structured_output",
    "coding_execute_python": "capability.coding_execute.python",
    "coding_execute_go": "capability.coding_execute.go",
    "context": "context.summary",
    "routing": "routing.summary",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaselineMetric(BaseModel):
    samples: list[float] = Field(default_factory=list)
    mean: float | None = None
    stddev: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    run_count: int = 0
    task_passed: list[int] = Field(default_factory=list)
    task_total: list[int] = Field(default_factory=list)


class OfficialBaseline(BaseModel):
    schema_version: int = BASELINE_SCHEMA_VERSION
    suite_version: str = BASELINE_SUITE_VERSION
    model: str
    profile: str = "standard"
    collected_at: str = Field(default_factory=_now)
    runs: int = 0
    model_rule_id: str | None = None
    model_rule_updated_at: str | None = None
    dimensions: dict[str, BaselineMetric] = Field(default_factory=dict)
    category_scores: dict[str, BaselineMetric] = Field(default_factory=dict)
    probe_scores: dict[str, BaselineMetric] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _task_counts(result: ProbeResult) -> tuple[int | None, int | None]:
    observed = result.observed
    if not isinstance(observed, dict):
        return None, None

    tasks = observed.get("tasks")
    if isinstance(tasks, list):
        matched = 0
        total = 0
        for item in tasks:
            if not isinstance(item, dict):
                continue
            total += 1
            matched += int(bool(item.get("matched") or item.get("passed")))
        if total:
            return matched, total

    scenarios = observed.get("scenarios")
    if isinstance(scenarios, list):
        total = len([item for item in scenarios if isinstance(item, dict)])
        if total:
            passed = sum(
                1
                for item in scenarios
                if isinstance(item, dict)
                and str(item.get("status")) == "pass"
            )
            return passed, total

    benchmark_limit = result.metadata.get("benchmark_limit")
    if isinstance(benchmark_limit, int) and benchmark_limit > 0:
        return None, benchmark_limit

    return None, None


def _aggregate(
    values: list[float],
    *,
    task_passed: list[int] | None = None,
    task_total: list[int] | None = None,
) -> BaselineMetric:
    clean = [float(value) for value in values]
    if not clean:
        return BaselineMetric()
    return BaselineMetric(
        samples=[round(value, 6) for value in clean],
        mean=round(statistics.fmean(clean), 6),
        stddev=(
            round(statistics.stdev(clean), 6)
            if len(clean) >= 2
            else None
        ),
        minimum=round(min(clean), 6),
        maximum=round(max(clean), 6),
        run_count=len(clean),
        task_passed=list(task_passed or []),
        task_total=list(task_total or []),
    )


def aggregate_baseline_reports(
    reports: list[AuditReport],
    *,
    model_rule_id: str | None = None,
    model_rule_updated_at: str | None = None,
    suite_version: str = BASELINE_SUITE_VERSION,
) -> OfficialBaseline:
    if not reports:
        raise ValueError("at least one report is required to build a baseline")

    first = reports[0]
    model = str(first.target.get("model") or "")
    profile = first.profile
    if any(str(report.target.get("model") or "") != model for report in reports):
        raise ValueError("all baseline reports must target the same model")
    if any(report.profile != profile for report in reports):
        raise ValueError("all baseline reports must use the same profile")

    dimension_values: dict[str, list[float]] = {
        key: [] for key in BASELINE_DIMENSIONS
    }
    dimension_passed: dict[str, list[int]] = {
        key: [] for key in BASELINE_DIMENSIONS
    }
    dimension_total: dict[str, list[int]] = {
        key: [] for key in BASELINE_DIMENSIONS
    }
    category_values: dict[str, list[float]] = {}
    probe_values: dict[str, list[float]] = {}

    for report in reports:
        by_id = {result.probe_id: result for result in report.results}
        for dimension, probe_id in BASELINE_DIMENSIONS.items():
            result = by_id.get(probe_id)
            if result is None or result.score is None:
                continue
            dimension_values[dimension].append(float(result.score))
            passed, total = _task_counts(result)
            if passed is not None and total is not None:
                dimension_passed[dimension].append(passed)
                dimension_total[dimension].append(total)

        for result in report.results:
            if (
                result.score is not None
                and result.metadata.get("engine") == "lm-evaluation-harness"
            ):
                task = str(result.metadata.get("task") or "")
                if task:
                    dimension = f"benchmark:{task}"
                    dimension_values.setdefault(dimension, []).append(
                        float(result.score)
                    )
                    dimension_passed.setdefault(dimension, [])
                    dimension_total.setdefault(dimension, [])
                    _, total = _task_counts(result)
                    if total is not None:
                        dimension_total[dimension].append(total)

        for category, score in report.summary.category_scores.items():
            category_values.setdefault(category, []).append(float(score) / 100.0)

        for result in report.results:
            if result.score is None or result.category == "internal":
                continue
            probe_values.setdefault(result.probe_id, []).append(float(result.score))

    dimensions = {
        key: _aggregate(
            values,
            task_passed=dimension_passed[key],
            task_total=dimension_total[key],
        )
        for key, values in dimension_values.items()
        if values
    }
    categories = {
        key: _aggregate(values)
        for key, values in category_values.items()
        if values
    }
    probes = {
        key: _aggregate(values)
        for key, values in probe_values.items()
        if values
    }

    return OfficialBaseline(
        suite_version=suite_version,
        model=model,
        profile=profile,
        runs=len(reports),
        model_rule_id=model_rule_id,
        model_rule_updated_at=model_rule_updated_at,
        dimensions=dimensions,
        category_scores=categories,
        probe_scores=probes,
        metadata={
            "same_suite_required_for_comparison": True,
            "performance_metrics_included": False,
            "quantization_format_inference": False,
        },
    )

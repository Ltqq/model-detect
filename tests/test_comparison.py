from model_detect.baseline import BaselineMetric, OfficialBaseline
from model_detect.comparison import compare_report_to_baseline
from model_detect.comparison_contract import build_dimension_contracts
from model_detect.models import (
    AuditReport,
    AuditSummary,
    ProbeResult,
    ProbeStatus,
    Evidence,
)


def target_report(score, *, model="kimi-k3", profile="standard"):
    return AuditReport(
        target={
            "base_url": "https://supplier.example/v1",
            "model": model,
            "protocol": "openai",
        },
        profile=profile,
        results=[
            ProbeResult(
                probe_id="capability.reasoning",
                category="capability",
                status=ProbeStatus.PASS,
                score=score,
                summary="reasoning",
                evidence_ids=["ev_reason"],
                observed={
                    "tasks": [
                        {"id": "logic_a", "matched": score >= 0.5},
                        {"id": "logic_b", "matched": score >= 1.0},
                    ]
                },
            )
        ],
        evidences=[
            Evidence(
                id="ev_reason",
                probe_id="capability.reasoning.logic_a",
                url="https://example.test/v1/chat/completions",
                request_body={
                    "model": model,
                    "messages": [{"role": "user", "content": "identical question"}],
                    "temperature": 0,
                    "max_tokens": 96,
                },
            ),
        ],
        summary=AuditSummary(
            overall_score=score * 100,
            category_scores={"capability": score * 100},
            coverage={"capability": True},
        ),
    )


def baseline(*, runs=3, samples=None, task_total=None):
    values = samples or [1.0] * runs
    return OfficialBaseline(
        model="kimi-k3",
        profile="standard",
        runs=runs,
        model_rule_id="kimi-k3",
        model_rule_updated_at="2026-10-08",
        dimension_contracts={
            "reasoning": build_dimension_contracts(target_report(1.0))["reasoning"]
        },
        dimensions={
            "reasoning": BaselineMetric(
                samples=values,
                mean=sum(values) / len(values),
                stddev=0.0 if len(values) >= 2 else None,
                minimum=min(values),
                maximum=max(values),
                run_count=len(values),
                task_passed=[2] * len(values),
                task_total=task_total or [2] * len(values),
            )
        },
    )


def test_one_task_drop_stays_inside_discrete_baseline_tolerance():
    comparison, results = compare_report_to_baseline(
        target_report(0.5),
        baseline(),
    )

    item = comparison.dimensions["reasoning"]
    assert item.task_granularity == 0.5
    assert item.lower_bound == 0.5
    assert item.verdict == "match"
    assert comparison.verdict == "baseline_match"
    assert results[-1].status == ProbeStatus.PASS


def test_large_quality_drop_is_flagged_as_regression():
    comparison, results = compare_report_to_baseline(
        target_report(0.0),
        baseline(),
    )

    assert comparison.verdict == "quality_regression"
    assert comparison.regression_dimensions == ["reasoning"]
    assert comparison.dimensions["reasoning"].retention_ratio == 0.0
    assert results[0].status == ProbeStatus.FAIL
    assert results[-1].metadata["quality_verdict"] == "quality_regression"


def test_single_run_baseline_only_reports_informational_delta():
    comparison, results = compare_report_to_baseline(
        target_report(0.0),
        baseline(runs=1, samples=[1.0], task_total=[2]),
    )

    assert comparison.verdict == "baseline_insufficient"
    assert comparison.statistically_evaluable_dimensions == 0
    assert comparison.dimensions["reasoning"].verdict == "informational"
    assert results[0].status == ProbeStatus.INSUFFICIENT
    assert "at least 3" in comparison.warnings[0]


def test_quality_comparison_requires_same_model_profile_and_suite():
    comparison, _ = compare_report_to_baseline(
        target_report(1.0, model="glm-5.2"),
        baseline(),
    )
    assert comparison.verdict == "baseline_insufficient"
    assert "model mismatch" in comparison.warnings[0]

    comparison, _ = compare_report_to_baseline(
        target_report(1.0, profile="deep"),
        baseline(),
    )
    assert comparison.verdict == "baseline_insufficient"
    assert "profile mismatch" in comparison.warnings[0]

    stale = baseline()
    stale.suite_version = "old-suite"
    comparison, _ = compare_report_to_baseline(
        target_report(1.0),
        stale,
    )
    assert comparison.verdict == "baseline_insufficient"
    assert "suite version mismatch" in comparison.warnings[0]



def test_changed_request_budget_is_incomparable_not_pass():
    report = target_report(1.0)
    report.evidences[0].request_body["max_tokens"] = 512
    comparison, rows = compare_report_to_baseline(report, baseline())
    assert comparison.verdict == "baseline_insufficient"
    assert comparison.incomparable_dimensions == ["reasoning"]
    assert comparison.dimensions["reasoning"].verdict == "incomparable"
    assert rows[0].score is None


def test_legacy_reference_without_contract_never_claims_match():
    old = baseline()
    old.dimension_contracts = {}
    comparison, _ = compare_report_to_baseline(target_report(1.0), old)
    assert comparison.verdict == "baseline_insufficient"
    assert comparison.incomparable_dimensions == ["reasoning"]


def test_changed_task_order_is_incomparable():
    report = target_report(1.0)
    report.results[0].observed["tasks"] = [
        {"id": "logic_b", "matched": True},
        {"id": "logic_a", "matched": True},
    ]
    comparison, _ = compare_report_to_baseline(report, baseline())
    assert comparison.verdict == "baseline_insufficient"

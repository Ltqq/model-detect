import json

import pytest

from model_detect.baseline import (
    BASELINE_SUITE_VERSION,
    aggregate_baseline_reports,
)
from model_detect.models import (
    AuditReport,
    AuditSummary,
    ProbeResult,
    ProbeStatus,
)


def make_report(reasoning, math, *, model="kimi-k3", profile="standard"):
    return AuditReport(
        target={
            "base_url": "https://official.example/v1",
            "model": model,
            "protocol": "openai",
        },
        profile=profile,
        results=[
            ProbeResult(
                probe_id="capability.reasoning",
                category="capability",
                status=ProbeStatus.PASS,
                score=reasoning,
                summary="reasoning",
                observed={
                    "tasks": [
                        {"matched": True},
                        {"matched": reasoning >= 1.0},
                    ]
                },
            ),
            ProbeResult(
                probe_id="capability.math",
                category="capability",
                status=ProbeStatus.PASS,
                score=math,
                summary="math",
                observed={
                    "tasks": [
                        {"matched": True},
                        {"matched": math >= 1.0},
                    ]
                },
            ),
            ProbeResult(
                probe_id="context.summary",
                category="context",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="context",
            ),
        ],
        summary=AuditSummary(
            overall_score=90.0,
            category_scores={
                "capability": ((reasoning + math) / 2) * 100,
                "context": 100.0,
            },
            coverage={"capability": True, "context": True},
        ),
    )


def test_aggregate_baseline_reports_records_samples_and_variance():
    baseline = aggregate_baseline_reports(
        [
            make_report(1.0, 1.0),
            make_report(0.5, 1.0),
            make_report(1.0, 0.5),
        ],
        model_rule_id="kimi-k3",
        model_rule_updated_at="2026-10-08",
    )

    assert baseline.suite_version == BASELINE_SUITE_VERSION
    assert baseline.runs == 3
    assert baseline.model == "kimi-k3"
    assert baseline.model_rule_id == "kimi-k3"
    reasoning = baseline.dimensions["reasoning"]
    assert reasoning.samples == [1.0, 0.5, 1.0]
    assert reasoning.mean == pytest.approx(0.833333, abs=1e-6)
    assert reasoning.stddev is not None
    assert reasoning.task_total == [2, 2, 2]
    assert baseline.dimensions["context"].mean == 1.0
    assert baseline.category_scores["context"].mean == 1.0


def test_baseline_requires_same_model_and_profile():
    with pytest.raises(ValueError, match="same model"):
        aggregate_baseline_reports(
            [
                make_report(1.0, 1.0),
                make_report(1.0, 1.0, model="glm-5.2"),
            ]
        )

    with pytest.raises(ValueError, match="same profile"):
        aggregate_baseline_reports(
            [
                make_report(1.0, 1.0),
                make_report(1.0, 1.0, profile="deep"),
            ]
        )


def test_baseline_json_contains_no_endpoint_secret_fields():
    baseline = aggregate_baseline_reports(
        [make_report(1.0, 1.0)],
        model_rule_id="kimi-k3",
    )
    payload = json.loads(baseline.model_dump_json())

    assert "api_key" not in json.dumps(payload).lower()
    assert payload["metadata"]["performance_metrics_included"] is False
    assert payload["metadata"]["quantization_format_inference"] is False

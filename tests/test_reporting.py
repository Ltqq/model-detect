import json

from model_detect.models import AuditReport, Evidence, ProbeResult, ProbeStatus, ProviderHypothesis
from model_detect.reporting import write_report


def test_report_contains_evidence_links(tmp_path):
    ev = Evidence(
        id="ev_test",
        probe_id="protocol.chat.basic",
        url="https://example.com/v1/chat/completions",
        response_status=200,
    )
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        results=[
            ProbeResult(
                probe_id="protocol.chat.basic",
                category="protocol",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="ok",
                evidence_ids=[ev.id],
            )
        ],
        evidences=[ev],
    )
    root = write_report(report, tmp_path / "out")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert 'evidence/ev_test.json' in html
    assert (root / "evidence" / "ev_test.json").exists()
    data = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert "human_interpretation" in data
    assert data["human_interpretation"]["verdict_label"] == "证据不足"


def test_report_renders_fingerprint_cells(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "kimi-k3"},
        results=[
            ProbeResult(
                probe_id="identity.fingerprint.reference_compare",
                category="identity",
                status=ProbeStatus.PASS,
                score=None,
                confidence=None,
                summary="behavioral reference match; not model identity proof",
                observed={
                    "verdict": "match",
                    "mean_jsd": 0.18,
                    "comparable_cell_count": 1,
                    "target_split_half_jsd": 0.12,
                    "target_adapter": {"strategy": "openai-effort"},
                    "target_fingerprint": {
                        "model": "kimi-k3",
                        "protocol": "one-token/v1",
                        "collected_at": "now",
                        "cell_count": 1,
                    },
                    "reference_fingerprint": {
                        "model": "kimi-k3",
                        "protocol": "one-token/v1",
                        "collected_at": "before",
                        "cell_count": 1,
                    },
                    "warnings": [],
                    "cells": [
                        {
                            "cellId": "random-number-1-100:en",
                            "jsd": 0.18,
                            "validA": 25,
                            "validB": 25,
                        }
                    ],
                },
                metadata={"identity_strength": "weak", "verdict": "match", "weight_identity_proof": False},
            )
        ],
        adapters={
            "reference": {
                "fingerprint_source": "collected",
                "fingerprint_reference": "fingerprint.json",
            }
        },
    )
    root = write_report(report, tmp_path / "fp-report")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert "统计指纹对比" in html
    assert "行为参考信号" in html
    assert "已有强身份匹配" not in html
    assert "查看每个统计单元的 JSD 明细" in html
    assert "random-number-1-100:en" in html
    assert "collected" in html



def test_report_persists_and_renders_regression_artifacts(tmp_path):
    source = tmp_path / "working-regression"
    suite_dir = source / "01"
    suite_dir.mkdir(parents=True)
    config_path = suite_dir / "promptfooconfig.yaml"
    result_path = suite_dir / "promptfoo-result.json"
    config_path.write_text("providers: []\n", encoding="utf-8")
    result_path.write_text('{"results": []}', encoding="utf-8")

    report = AuditReport(
        target={
            "base_url": "https://example.com/v1",
            "model": "kimi-k3",
        },
        results=[
            ProbeResult(
                probe_id="regression.kimi-k3.invalid-field",
                category="protocol",
                status=ProbeStatus.FAIL,
                score=0.0,
                summary="regression failed",
                observed={
                    "runs": [
                        {
                            "reason": "expected HTTP 400",
                            "output": "received 200 OK",
                        }
                    ]
                },
                metadata={
                    "engine": "promptfoo",
                    "identity_strength": "none",
                    "artifact_path": str(result_path),
                },
            )
        ],
        adapters={
            "promptfoo_regression": {
                "status": "completed",
                "artifact_root": str(source),
                "suites": [
                    {
                        "suite": "kimi-k3",
                        "config_path": str(config_path),
                        "output_path": str(result_path),
                        "status": "completed",
                    }
                ],
            }
        },
    )

    root = write_report(report, tmp_path / "report")

    assert (
        root / "regression" / "01" / "promptfooconfig.yaml"
    ).exists()
    assert (
        root / "regression" / "01" / "promptfoo-result.json"
    ).exists()

    data = json.loads(
        (root / "report.json").read_text(encoding="utf-8")
    )
    result_meta = data["results"][0]["metadata"]
    assert result_meta["artifact_path"] == (
        "regression/01/promptfoo-result.json"
    )
    adapter = data["adapters"]["promptfoo_regression"]
    assert adapter["artifact_root"] == "regression"
    assert adapter["persisted"] is True
    assert adapter["suites"][0]["config_path"] == (
        "regression/01/promptfooconfig.yaml"
    )

    rendered = (root / "report.html").read_text(encoding="utf-8")
    assert "回归规则结果" in rendered
    assert "expected HTTP 400" in rendered
    assert "received 200 OK" in rendered
    assert 'href="regression/01/promptfoo-result.json"' in rendered



def test_report_renders_official_quality_baseline_comparison(tmp_path):
    report = AuditReport(
        target={"base_url": "https://supplier.example/v1", "model": "kimi-k3"},
        adapters={
            "official_baseline_comparison": {
                "schema_version": 1,
                "suite_version": "official-baseline-v1",
                "model": "kimi-k3",
                "profile": "standard",
                "verdict": "quality_regression",
                "comparable_dimensions": 1,
                "statistically_evaluable_dimensions": 1,
                "regression_dimensions": ["reasoning"],
                "dimensions": {
                    "reasoning": {
                        "dimension": "reasoning",
                        "probe_id": "capability.reasoning",
                        "baseline_mean": 1.0,
                        "baseline_stddev": 0.0,
                        "baseline_runs": 3,
                        "target_score": 0.0,
                        "delta": -1.0,
                        "retention_ratio": 0.0,
                        "natural_tolerance": 0.5,
                        "lower_bound": 0.5,
                        "task_granularity": 0.5,
                        "statistically_evaluable": True,
                        "verdict": "regression",
                        "explanation": "below trusted range",
                    }
                },
                "warnings": [],
                "metadata": {"baseline_runs": 3},
            }
        },
    )

    root = write_report(report, tmp_path / "quality-report")
    rendered = (root / "report.html").read_text(encoding="utf-8")
    data = json.loads((root / "report.json").read_text(encoding="utf-8"))

    assert "官方 / 可信基准质量对比" in rendered
    assert "推理" in rendered
    assert "明显退化" in rendered
    assert "具体量化格式" in rendered
    assert data["human_interpretation"]["quality"]["state"] == "regression"


def test_published_official_aggregates_are_labeled_background_only(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.invalid/v1", "model": "kimi-k3"},
    )
    root = write_report(report, tmp_path / "kimi")
    page = (root / "report.html").read_text(encoding="utf-8")
    assert "官方已发布成绩 · 仅背景参考" in page
    assert "GPQA Diamond" in page
    assert "93.5" in page
    assert "不是本次 API 实测" in page
    assert "https://github.com/MoonshotAI/Kimi-K3/blob/main/README.md" in page


def test_unrelated_model_does_not_inherit_kimi_published_score(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.invalid/v1", "model": "deepseek-flash"},
    )
    root = write_report(report, tmp_path / "deepseek")
    page = (root / "report.html").read_text(encoding="utf-8")
    assert "官方已发布成绩 · 仅背景参考" in page
    assert "DeepSeek-V4.1-Flash-1017" in page
    assert "Terminal-Bench 4.0" in page
    assert "GPQA Diamond" not in page  # no cross-model Kimi score leakage


def test_provider_hints_render_without_uncalibrated_percentages(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        provider_hypotheses=[
            ProviderHypothesis(
                provider="volcengine",
                confidence=None,
                evidence=["protocol.chat.basic: response header x-tt-logid"],
            )
        ],
    )
    root = write_report(report, tmp_path / "provider-hints")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert "响应头线索" in html
    assert "protocol.chat.basic: response header x-tt-logid" in html
    assert "策略命中置信度" not in html
    assert "24.2%" not in html

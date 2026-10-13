import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from model_detect.calibration import (
    _quality_candidate_prediction,
    calibrate_validation,
    wilson95,
    write_calibration,
)
from model_detect.cli import app


def case(case_id, scenario, runs, expected, ratio=None):
    return {
        "id": case_id,
        "scenario": scenario,
        "routing_fraction": ratio,
        "truth_source": "test-controlled-config",
        "expected": expected,
        "runs_expected": runs,
        "runs_found": runs,
    }


def record(case_id, run, expected, predicted, report_path="missing-report.json"):
    return {
        "case_id": case_id,
        "run": run,
        "expected": expected,
        "predicted": {
            signal: predicted.get(signal)
            for signal in ("identity", "routing", "quality")
        },
        "report_path": str(report_path),
    }


def test_case_level_does_not_double_count_repeated_or_missing_runs():
    same = {"identity": False, "routing": False, "quality": None}
    other = {"identity": True, "routing": False, "quality": None}
    validation = {
        "schema_version": 1,
        "suite_id": "test",
        "observed_reports": 5,
        "expected_reports": 6,
        "cases": [
            case("official", "same_model", 2, same),
            case("flaky", "different_provider", 2, same),
            case("switched", "different_model", 1, other),
            case("missing", "same_model", 1, same),
        ],
        "runs": [
            record("official", 1, same, {"identity": False}),
            record("official", 2, same, {"identity": False}),
            record("flaky", 1, same, {"identity": False}),
            record("flaky", 2, same, {"identity": True}),
            record("switched", 1, other, {"identity": True}),
        ],
    }
    result = calibrate_validation(validation)
    run = result["run_metrics"]["identity"]
    cases = result["case_metrics"]["identity"]
    assert run["evaluated"] == 5
    assert run["fp"] == 1
    assert cases["labelled"] == 4
    assert cases["evaluated"] == 2
    assert cases["abstained"] == 2
    assert (cases["tp"], cases["tn"], cases["fp"], cases["fn"]) == (
        1, 1, 0, 0
    )
    assert result["readiness"]["identity"]["certified"] is False
    assert result["readiness"]["identity"]["status"] == (
        "insufficient_independent_cases"
    )


def test_empty_calibration_never_invents_accuracy_or_intervals(tmp_path):
    result = calibrate_validation({
        "schema_version": 1,
        "suite_id": "empty",
        "observed_reports": 0,
        "expected_reports": 3,
        "cases": [case(
            "official", "same_model", 3,
            {"identity": False, "routing": None, "quality": None},
        )],
        "runs": [],
    })
    m = result["case_metrics"]["identity"]
    assert m["labelled"] == 1
    assert m["evaluated"] == 0
    assert m["accuracy"] is None
    assert m["wilson95"]["sensitivity"] is None
    assert result["readiness"]["identity"]["status"] == (
        "insufficient_independent_cases"
    )
    paths = write_calibration(result, tmp_path)
    markdown = paths[1].read_text(encoding="utf-8")
    assert "样本不足" in markdown
    assert "未认证" in markdown


def test_wilson95_empty_and_finite_bounds():
    assert wilson95(0, 0) is None
    assert wilson95(-1, 3) is None
    assert wilson95(4, 3) is None
    lower = wilson95(0, 10)
    upper = wilson95(10, 10)
    assert lower["lower"] == 0
    assert 0.2 < lower["upper"] < 0.4
    assert 0.6 < upper["lower"] < 0.8
    assert upper["upper"] == 1


def write_quality_report(path: Path, *, current, stddev=.1, valid=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "adapters": {
            "official_baseline_comparison": {
                "verdict": "quality_regression",
                "statistically_evaluable_dimensions": 1,
                "incomparable_dimensions": [],
                "dimensions": {
                    "reasoning": {
                        "baseline_mean": .9,
                        "baseline_stddev": stddev,
                        "baseline_runs": 3,
                        "target_score": current,
                        "task_granularity": .05,
                        "contract_valid": valid,
                        "statistically_evaluable": True,
                        "verdict": "regression",
                    }
                },
            }
        }
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_quality_threshold_replay_is_offline_and_not_auto_applied(tmp_path):
    degraded = tmp_path / "degraded.json"
    normal = tmp_path / "normal.json"
    write_quality_report(degraded, current=.75)
    write_quality_report(normal, current=.87)
    pos = {"identity": None, "routing": None, "quality": True}
    neg = {"identity": None, "routing": None, "quality": False}
    result = calibrate_validation({
        "schema_version": 1, "suite_id": "quality-test",
        "observed_reports": 2, "expected_reports": 2,
        "cases": [
            case("degraded", "different_effort", 1, pos),
            case("normal", "same_model", 1, neg),
        ],
        "runs": [
            record("degraded", 1, pos, {"quality": True}, degraded),
            record("normal", 1, neg, {"quality": False}, normal),
        ],
    })
    k1, k2, k3 = result["quality_threshold_replay"]
    assert k1["stddev_multiplier"] == 1
    assert (k1["case_metrics"]["tp"], k1["case_metrics"]["tn"]) == (1, 1)
    assert k2["case_metrics"]["tp"] == 0
    assert k2["case_metrics"]["fn"] == 1
    assert k3["case_metrics"]["fn"] == 1
    assert result["readiness"]["quality"]["certified"] is False


def test_quality_replay_abstains_for_invalid_or_missing_evidence(tmp_path):
    bad = tmp_path / "invalid.json"
    write_quality_report(bad, current=.1, valid=False)
    assert _quality_candidate_prediction(str(bad), 2.0) is None
    assert _quality_candidate_prediction(str(tmp_path / "missing.json"), 2.0) is None
    write_quality_report(bad, current=float("nan"))
    assert _quality_candidate_prediction(str(bad), 2.0) is None
    write_quality_report(bad, current=.1)
    obj = json.loads(bad.read_text())
    obj["adapters"]["official_baseline_comparison"]["incomparable_dimensions"] = [
        "reasoning"
    ]
    bad.write_text(json.dumps(obj))
    assert _quality_candidate_prediction(str(bad), 2.0) is None


def test_calibration_groups_mixed_routing_configuration_not_observed_share():
    yes = {"identity": None, "routing": True, "quality": None}
    no = {"identity": None, "routing": False, "quality": None}
    result = calibrate_validation({
        "schema_version": 1, "suite_id": "route",
        "observed_reports": 2, "expected_reports": 2,
        "cases": [
            case("route10", "mixed_routing", 1, yes, ratio=.1),
            case("route0", "mixed_routing", 1, no, ratio=0.0),
        ],
        "runs": [
            record("route10", 1, yes, {"routing": False}),
            record("route0", 1, no, {"routing": False}),
        ],
    })
    assert result["mixed_routing_target_groups"]["10"]["metrics"]["fn"] == 1
    assert result["mixed_routing_target_groups"]["0"]["metrics"]["tn"] == 1
    assert result["mixed_routing_target_groups"]["30"]["case_count"] == 0
    assert "gateway target" in result["mixed_routing_target_groups"]["10"]["meaning"]


def test_calibrate_command_with_no_reports_never_requests_api(tmp_path, monkeypatch):
    manifest = tmp_path / "validation.yaml"
    manifest.write_text(
        """
id: empty-calibration
cases:
  - id: official
    scenario: same_model
    truth_source: official-control-register-001
    truth: {identity: same}
    runs: 1
""", encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output = tmp_path / "calibration"
    response = CliRunner().invoke(app, [
        "validation", "calibrate", "--manifest", str(manifest),
        "--output-dir", str(output),
    ])
    assert response.exit_code == 0, response.output
    assert (output / "calibration.json").is_file()
    assert (output / "calibration.md").is_file()
    assert "没有真实报告" in response.output



def test_report_provenance_excludes_url_api_key_and_prompt():
    from model_detect.models import AuditReport, AuditSummary, ProbeResult, ProbeStatus
    from model_detect.validation import report_provenance

    report = AuditReport(
        target={
            "model": "kimi-k3",
            "base_url": "https://private-supplier.example/v1",
            "api_key_env": "PRIVATE_SUPPLIER_KEY",
        },
        profile="standard",
        adapters={
            "model_rule": {"id": "kimi-k3", "updated_at": "2026-10-13"},
            "reference": {"id": "kimi-official"},
        },
        results=[
            ProbeResult(
                probe_id="capability.external.lm_eval.gsm8k",
                category="benchmark",
                status=ProbeStatus.PASS,
                score=.75,
                summary="data",
                metadata={
                    "engine": "lm-evaluation-harness",
                    "task": "gsm8k",
                    "benchmark_harness_version": "0.4.8",
                },
                observed={
                    "version": 3,
                    "effective_samples": 25,
                    "task_config_hash": "abc123",
                    "prompt": "private prompt data",
                },
            )
        ],
        summary=AuditSummary(),
    )
    lineage = report_provenance(report)
    serialized = json.dumps(lineage)
    assert lineage["model_rule_id"] == "kimi-k3"
    assert lineage["benchmark_tasks"][0]["effective_samples"] == 25
    assert "PRIVATE_SUPPLIER_KEY" not in serialized
    assert "private-supplier.example" not in serialized
    assert "private prompt data" not in serialized

from pathlib import Path

from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.validation import ValidationSuite
from model_detect.validation_doctor import validation_manifest_readiness


def suite():
    return ValidationSuite.model_validate({
        "id": "test-binary",
        "cases": [
            {"id": "genuine", "scenario": "same_model",
             "truth_source": "independent-gateway-log-001",
             "truth": {"identity": "same"}, "runs": 2},
            {"id": "other", "scenario": "different_model",
             "truth_source": "independent-gateway-log-002",
             "truth": {"identity": "different"}, "runs": 1},
        ],
    })


def test_doctor_counts_independent_cases_not_repeat_runs(tmp_path):
    readiness = validation_manifest_readiness(
        suite(), manifest_path=tmp_path / "case.yaml", output_dir=tmp_path / "out",
    )
    assert readiness["case_count"] == 2
    assert readiness["expected_runs"] == 3
    assert readiness["missing_report_files"] == 3
    assert readiness["independent_case_labels"]["identity"]["positive"] == 1
    assert readiness["independent_case_labels"]["identity"]["negative"] == 1
    assert readiness["status"] == "missing_reports"
    assert all(row["truth_source_verified"] is False for row in readiness["cases"])


def test_cli_doctor_offline_manifest_preview_and_strict_mode(tmp_path):
    manifest = tmp_path / "cases.yaml"
    manifest.write_text("""
schema_version: 1
id: local-check
cases:
  - id: same
    scenario: same_model
    truth_source: independent-gateway-log-001
    truth:
      identity: same
    runs: 1
""", encoding="utf-8")
    args = ["validation", "doctor", "--manifest", str(manifest),
            "--output-dir", str(tmp_path / "out")]
    preview = CliRunner().invoke(app, args)
    assert preview.exit_code == 0, preview.output
    assert "missing_reports" in preview.output
    strict = CliRunner().invoke(app, args + ["--strict-reports"])
    assert strict.exit_code == 1

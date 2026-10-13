import asyncio
import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.models import AuditReport, AuditSummary
from model_detect.validation import ValidationSuite
from model_detect.validation_runner import execution_plan, run_suite


def suite(**overrides):
    case = {
        "id": "official",
        "scenario": "same_model",
        "truth_source": "external-official-evidence",
        "truth": {"identity": "same"},
        "base_url": "https://api.example.test/v1",
        "model": "kimi-k3",
        "api_key_env": "VALIDATION_FAKE_KEY",
        "reference_id": "official-reference",
        "runs": 2,
    }
    case.update(overrides)
    return ValidationSuite.model_validate({
        "id": "validation-test",
        "cases": [case],
    })


def test_run_requires_key_and_checks_budget_before_requests(tmp_path, monkeypatch):
    monkeypatch.delenv("VALIDATION_FAKE_KEY", raising=False)
    spec = suite()
    assert execution_plan(spec)["total_audits"] == 2

    with pytest.raises(ValueError, match="max_audits"):
        asyncio.run(run_suite(
            spec,
            manifest_path=tmp_path / "experiment.yaml",
            output_dir=tmp_path / "out",
            max_audits=1,
        ))
    with pytest.raises(RuntimeError, match="unset"):
        asyncio.run(run_suite(
            spec,
            manifest_path=tmp_path / "experiment.yaml",
            output_dir=tmp_path / "out",
        ))


def test_run_saves_real_reports_and_offline_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("VALIDATION_FAKE_KEY", "sk-fake")
    requested = []

    async def fake_run(config, **kwargs):
        requested.append((config, kwargs))
        return AuditReport(
            target={"model": config.target.model, "base_url": config.target.base_url},
            profile=config.profile,
            summary=AuditSummary(final_verdict="review"),
        )

    monkeypatch.setattr("model_detect.validation_runner.run_audit", fake_run)
    manifest = tmp_path / "experiment.yaml"
    manifest.write_text("id: validation-test\n", encoding="utf-8")

    result = asyncio.run(run_suite(
        suite(),
        manifest_path=manifest,
        output_dir=tmp_path / "validation",
    ))

    assert len(requested) == 2
    assert all(config.proxy_sleuth_enabled is False for config, _ in requested)
    assert all(config.regression.enabled is False for config, _ in requested)
    assert all(call["api_key_override"] == "sk-fake" for _, call in requested)
    assert (tmp_path / "validation" / "official" / "01" / "report.json").exists()
    assert result["summary"]["observed_reports"] == 2
    assert result["summary"]["metrics"]["identity"]["abstained"] == 2
    assert (tmp_path / "validation" / "validation.md").exists()
    stored = (tmp_path / "validation" / "validation-run.json").read_text()
    assert "sk-fake" not in stored
    assert "api_key" not in stored
    assert result["summary"]["metrics"]["identity"]["accuracy"] is None


def test_errors_are_recorded_without_exposing_provider_exception_text(tmp_path, monkeypatch):
    monkeypatch.setenv("VALIDATION_FAKE_KEY", "sk-fake")

    async def failing_run(config, **kwargs):
        raise RuntimeError("upstream included secret sk-fake in error")

    monkeypatch.setattr("model_detect.validation_runner.run_audit", failing_run)
    result = asyncio.run(run_suite(
        suite(runs=1),
        manifest_path=tmp_path / "experiment.yaml",
        output_dir=tmp_path / "out",
    ))
    assert result["outcomes"][0]["status"] == "error"
    stored = (tmp_path / "out" / "validation-run.json").read_text()
    assert "sk-fake" not in stored
    assert "RuntimeError" in stored
    assert result["summary"]["observed_reports"] == 0


def test_runner_refuses_offline_paths_and_existing_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("VALIDATION_FAKE_KEY", "sk-fake")
    with pytest.raises(ValueError, match="offline evaluation only"):
        asyncio.run(run_suite(
            suite(reports=["existing.json"], runs=1),
            manifest_path=tmp_path / "manifest.yaml",
            output_dir=tmp_path / "out",
        ))

    existing = tmp_path / "out" / "official" / "01"
    existing.mkdir(parents=True)
    (existing / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="exists"):
        asyncio.run(run_suite(
            suite(),
            manifest_path=tmp_path / "manifest.yaml",
            output_dir=tmp_path / "out",
        ))


def test_validation_cli_dry_run_makes_no_paid_calls(tmp_path, monkeypatch):
    manifest = tmp_path / "experiment.yaml"
    manifest.write_text(
        """
id: test-suite
cases:
  - id: official
    scenario: same_model
    truth_source: external-official-evidence
    truth: {identity: same}
    base_url: https://api.example.test/v1
    model: kimi-k3
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = CliRunner()
    response = runner.invoke(app, [
        "validation", "run", "--manifest", str(manifest),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert response.exit_code == 0, response.output
    assert "预览模式" in response.output
    assert not (tmp_path / "out").exists()

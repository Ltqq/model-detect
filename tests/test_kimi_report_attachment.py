import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.kimi_official import OFFICIAL_COMMIT
from model_detect.kimi_report import merge_official_summary


def _report_json(tmp_path):
    root = tmp_path / "report.json"
    root.write_text(json.dumps({
        "target": {"model": "kimi-k3", "base_url": "https://relay.example/v1"},
        "summary": {"final_verdict": "INSUFFICIENT", "overall_score": 41.0},
        "results": [], "evidences": [],
    }))
    return root


def _summary_json(tmp_path, model="kimi-k3"):
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({
        "schema": "kimi-official-junit-import-v1",
        "source_commit": OFFICIAL_COMMIT, "suite": "params",
        "model": model,
        "counts": {"pass": 2, "fail": 1, "error": 0, "skipped": 0},
        "cases": [{"testcase_sha256": "a" * 64, "status": "pass"}] * 3,
        "failure_text": "sk-secret-must-not-leak",
    }))
    return summary


def test_official_appendix_preserves_identity_verdict_and_redacts_private_fields(tmp_path):
    audit = _report_json(tmp_path)
    summary = _summary_json(tmp_path)
    destination = merge_official_summary(audit, summary, tmp_path / "out")
    rendered = json.loads((destination / "report.json").read_text())
    assert rendered["summary"]["final_verdict"] == "INSUFFICIENT"
    assert rendered["summary"]["overall_score"] == 41.0
    assert rendered["adapters"]["kimi_official_verifier"]["counts"]["fail"] == 1
    assert "sk-secret-must-not-leak" not in json.dumps(rendered)
    html = (destination / "report.html").read_text()
    assert "Kimi 官方验证器专项" in html
    assert "不参与综合评分" in html
    assert "sk-secret-must-not-leak" not in html
    assert "kimi_official_verifier" not in audit.read_text()


def test_official_mismatch_and_overwrite_rejected(tmp_path):
    audit = _report_json(tmp_path)
    wrong = _summary_json(tmp_path, model="different-model")
    with pytest.raises(ValueError):
        merge_official_summary(audit, wrong, tmp_path / "result")
    assert not (tmp_path / "result").exists()
    summary = _summary_json(tmp_path)
    merge_official_summary(audit, summary, tmp_path / "result")
    with pytest.raises(FileExistsError):
        merge_official_summary(audit, summary, tmp_path / "result")


def test_official_attach_report_cli(tmp_path):
    audit = _report_json(tmp_path)
    summary = _summary_json(tmp_path)
    result = CliRunner().invoke(app, [
        "kimi-verifier", "attach-report", "--audit", str(audit),
        "--summary", str(summary), "--output-dir", str(tmp_path / "export"),
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "export" / "report.html").is_file()

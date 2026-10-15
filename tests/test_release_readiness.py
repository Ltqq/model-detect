from typer.testing import CliRunner
from model_detect.cli import app
from model_detect.release_readiness import inspect_release_tree


def test_release_doctor_cannot_claim_published_or_live_checked(tmp_path):
    result = inspect_release_tree(tmp_path)
    assert result["missing_files"]
    assert result["publish_ready"] is False
    assert result["live_model_verified"] is False
    assert result["ci_verified_here"] is False
    assert result["api_calls"] == 0


def test_release_doctor_cli_fails_on_missing_but_not_a_paid_check(tmp_path):
    args = ["release-doctor", "--repo-dir", str(tmp_path)]
    preview = CliRunner().invoke(app, args)
    assert preview.exit_code == 0, preview.output
    assert "publish_ready" in preview.output
    assert CliRunner().invoke(app, args + ["--fail-on-missing"]).exit_code == 1

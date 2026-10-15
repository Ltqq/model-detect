import json
from typer.testing import CliRunner
import pytest
from model_detect.cli import app
from model_detect.glm53_checkpoint_doctor import inspect_checkpoint


def test_partial_checkpoint_offline_summarizes_without_raw_output(tmp_path):
    path = tmp_path / "benchmark-checkpoint.json"
    secret = "sk-my-private-value"
    path.write_text(json.dumps({
        "schema": "glm53-benchmark-checkpoint-v1",
        "suite_sha256": "a" * 64,
        "runs": {"official": [{"content": secret}], "customer": []},
        "failures": [{"error": secret}],
        "resume_supported": False,
    }))
    result = inspect_checkpoint(path)
    assert result["recorded_sources"]["official"]["stored_run_groups"] == 1
    assert result["failure_count"] == 1
    assert result["resume_supported"] is False
    assert secret not in str(result)
    rendered = CliRunner().invoke(app, ["glm53", "inspect-checkpoint", "--checkpoint", str(path)])
    assert rendered.exit_code == 0, rendered.output
    assert secret not in rendered.output


def test_wrong_schema_and_symlink_fail_closed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema":"unknown","runs":{},"failures":[]}')
    with pytest.raises(ValueError):
        inspect_checkpoint(path)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(ValueError):
        inspect_checkpoint(alias)

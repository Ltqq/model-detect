import json

from model_detect import regression_promptfoo
from model_detect.models import ProbeStatus


def test_run_regression_file_closes_pipeline(monkeypatch, tmp_path):
    regression = tmp_path / "regression.yaml"
    regression.write_text(
        """
version: 1
suite: smoke
model_patterns: ["*"]
cases:
  - id: exact
    prompt: Reply OK
    assertions:
      - type: equals
        value: OK
""",
        encoding="utf-8",
    )

    def fake_run_eval(**kwargs):
        output_path = kwargs["output_path"]
        output_path.write_text(
            json.dumps(
                {
                    "results": {
                        "results": [
                            {
                                "success": True,
                                "score": 1,
                                "gradingResult": {
                                    "pass": True,
                                    "score": 1,
                                    "reason": "equals passed",
                                },
                                "response": {"output": "OK"},
                                "testCase": {
                                    "metadata": {
                                        "model_detect_suite": "smoke",
                                        "model_detect_case_id": "exact",
                                        "model_detect_category": "protocol",
                                    }
                                },
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        return {
            "engine": "promptfoo",
            "returncode": 0,
            "output_path": str(output_path),
        }

    monkeypatch.setattr(
        regression_promptfoo.promptfoo,
        "run_eval",
        fake_run_eval,
    )

    results, meta = regression_promptfoo.run_regression_file(
        regression,
        base_url="https://relay.example/v1",
        model="m",
        api_key="sk-secret",
        output_dir=tmp_path / "run",
        binary="/usr/bin/promptfoo",
    )

    assert len(results) == 1
    assert results[0].probe_id == "regression.smoke.exact"
    assert results[0].status == ProbeStatus.PASS
    assert meta["returncode"] == 0
    assert meta["mapped_result_count"] == 1
    assert (tmp_path / "run" / "promptfooconfig.yaml").exists()
    assert (tmp_path / "run" / "promptfoo-result.json").exists()


def _write_smoke_regression(path):
    path.write_text(
        "version: 1\nsuite: smoke\nmodel_patterns: ['*']\ncases:\n"
        "  - id: generic\n    prompt: Reply OK\n    assertions:\n"
        "      - type: equals\n        value: OK\n",
        encoding="utf-8",
    )


def test_regression_nonzero_exit_does_not_report_success(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "regression.yaml"
    _write_smoke_regression(path)

    def fake_run(**kwargs):
        return {"returncode": 1, "stdout_tail": "PRIVATE-KEY", "stderr_tail": "PRIVATE"}

    monkeypatch.setattr(regression_promptfoo.promptfoo, "run_eval", fake_run)
    with pytest.raises(RuntimeError, match="did not complete successfully") as error:
        regression_promptfoo.run_regression_file(
            path, base_url="https://supplier.example/v1", model="generic",
            api_key="synthetic", output_dir=tmp_path / "run",
        )
    assert "PRIVATE" not in str(error.value)


def test_regression_zero_exit_without_result_is_not_complete(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "regression.yaml"
    _write_smoke_regression(path)
    monkeypatch.setattr(
        regression_promptfoo.promptfoo, "run_eval",
        lambda **kwargs: {"returncode": 0},
    )
    with pytest.raises(RuntimeError, match="without a result file"):
        regression_promptfoo.run_regression_file(
            path, base_url="https://supplier.example/v1", model="generic",
            api_key="synthetic", output_dir=tmp_path / "run",
        )


def test_regression_existing_result_rejected_before_paid_call(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "regression.yaml"
    _write_smoke_regression(path)
    output = tmp_path / "run"
    output.mkdir()
    (output / "promptfoo-result.json").write_text('{"results": []}')
    monkeypatch.setattr(
        regression_promptfoo.promptfoo, "run_eval",
        lambda **kwargs: pytest.fail("must reject stale evidence before invocation"),
    )
    with pytest.raises(FileExistsError, match="previous promptfoo result exists"):
        regression_promptfoo.run_regression_file(
            path, base_url="https://supplier.example/v1", model="generic",
            api_key="synthetic", output_dir=output,
        )

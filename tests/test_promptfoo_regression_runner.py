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

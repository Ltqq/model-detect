import json

import pytest

from model_detect.models import ProbeStatus
from model_detect.promptfoo_results import (
    parse_promptfoo_file,
    parse_promptfoo_payload,
)


def _row(
    *,
    suite="kimi-k3-regression",
    case_id="reasoning-field",
    category="protocol",
    passed=True,
    score=1.0,
    reason="ok",
    output="OK",
    error=None,
):
    return {
        "success": passed,
        "score": score,
        "error": error,
        "gradingResult": {
            "pass": passed,
            "score": score,
            "reason": reason,
            "assertion": {"type": "equals"},
        },
        "response": {"output": output},
        "provider": {"id": "https"},
        "testCase": {
            "metadata": {
                "model_detect_suite": suite,
                "model_detect_case_id": case_id,
                "model_detect_category": category,
            }
        },
    }


def test_parse_promptfoo_v3_shape_to_probe_result():
    payload = {
        "results": {
            "version": 3,
            "results": [_row()],
        }
    }

    result = parse_promptfoo_payload(payload)[0]

    assert result.probe_id == (
        "regression.kimi-k3-regression.reasoning-field"
    )
    assert result.category == "protocol"
    assert result.status == ProbeStatus.PASS
    assert result.score == 1.0
    assert result.metadata["engine"] == "promptfoo"
    assert result.metadata["identity_strength"] == "none"
    assert result.observed["runs"][0]["reason"] == "ok"


def test_parse_promptfoo_legacy_list_shape_and_provider_response():
    row = _row(category="integrity")
    row["providerResponse"] = row.pop("response")
    payload = {"results": [row]}

    result = parse_promptfoo_payload(payload)[0]

    assert result.category == "integrity"
    assert result.status == ProbeStatus.PASS
    assert result.observed["runs"][0]["output"] == "OK"


def test_repeat_rows_are_aggregated_to_warn_on_mixed_outcome():
    payload = {
        "results": {
            "results": [
                _row(passed=True, score=1.0),
                _row(passed=False, score=0.0, reason="mismatch"),
                _row(passed=True, score=1.0),
            ]
        }
    }

    result = parse_promptfoo_payload(payload)[0]

    assert result.status == ProbeStatus.WARN
    assert result.score == pytest.approx(0.6667, abs=0.0001)
    assert result.observed["pass_count"] == 2
    assert result.observed["fail_count"] == 1
    assert result.observed["total"] == 3


def test_all_failed_rows_map_to_fail():
    payload = {
        "results": {
            "results": [
                _row(passed=False, score=0.0),
                _row(passed=False, score=0.0),
            ]
        }
    }

    result = parse_promptfoo_payload(payload)[0]
    assert result.status == ProbeStatus.FAIL
    assert result.score == 0.0


def test_all_error_rows_map_to_error():
    payload = {
        "results": {
            "results": [
                _row(
                    passed=False,
                    score=0.0,
                    error="provider failed",
                ),
            ]
        }
    }

    result = parse_promptfoo_payload(payload)[0]
    assert result.status == ProbeStatus.ERROR


def test_result_file_records_artifact_source(tmp_path):
    path = tmp_path / "promptfoo.json"
    path.write_text(
        json.dumps(
            {
                "results": {
                    "results": [_row()]
                }
            }
        ),
        encoding="utf-8",
    )

    result = parse_promptfoo_file(path)[0]

    assert result.metadata["artifact_path"] == str(path)


def test_unrelated_promptfoo_output_is_rejected():
    with pytest.raises(
        ValueError,
        match="no model-detect regression metadata",
    ):
        parse_promptfoo_payload(
            {
                "results": {
                    "results": [
                        {
                            "success": True,
                            "testCase": {"metadata": {}},
                        }
                    ]
                }
            }
        )

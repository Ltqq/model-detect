import json

import pytest

from model_detect.models import ProbeStatus
from model_detect.adapters.lm_eval import parse_result_file, parse_result_payload


def test_parse_lm_eval_results_to_probe_results():
    payload = {
        "results": {
            "gsm8k": {
                "exact_match,strict-match": 0.70,
                "exact_match,strict-match_stderr": 0.01,
                "exact_match,flexible-extract": 0.82,
            },
            "ifeval": {
                "prompt_level_strict_acc": 0.76,
                "inst_level_strict_acc": 0.80,
            },
            "truthfulqa_gen": {
                "bleu_acc": 0.44,
                "rougeL_acc": 0.51,
            },
        },
        "versions": {
            "gsm8k": 3,
            "ifeval": 4,
            "truthfulqa_gen": 3,
        },
    }

    results = parse_result_payload(payload)
    by_task = {item.metadata["task"]: item for item in results}

    assert by_task["gsm8k"].score == 0.82
    assert by_task["gsm8k"].metadata["primary_metric"] == (
        "exact_match,flexible-extract"
    )
    assert by_task["ifeval"].score == 0.76
    assert by_task["truthfulqa_gen"].score == 0.44
    assert all(item.category == "capability" for item in results)
    assert all(item.status == ProbeStatus.PASS for item in results)
    assert all(item.metadata["benchmark_score_only"] is True for item in results)


def test_parse_result_file_tracks_artifact_path(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps({"results": {"gsm8k": {"acc": 0.5}}}),
        encoding="utf-8",
    )

    result = parse_result_file(path)[0]

    assert result.score == 0.5
    assert result.metadata["source_path"] == str(path)


def test_parse_result_payload_requires_results_object():
    with pytest.raises(ValueError):
        parse_result_payload({"config": {}})

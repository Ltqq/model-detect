import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.glm53_benchmark import (
    benchmark_plan, compare_benchmark_runs, run_standard_benchmark,
)
from model_detect.glm53_qualification import selected_cases
from model_detect.benchmark_contract import CONTRACT_VERSION


def row(task, *, score=.8, sha="a" * 64, samples=5,
        version=2, metric="acc"):
    return {
        "task": task, "score": score, "metric": metric,
        "dataset_version": version, "sample_count": samples,
        "config_sha256": sha, "contract_version": CONTRACT_VERSION,
        "valid": True,
    }


def test_benchmark_profiles_only_use_chat_generation_tasks():
    expected = ["gsm8k", "ifeval", "minerva_math500"]
    plan = benchmark_plan(
        "standard", official_runs=3, customer_runs=1, max_gen_toks=8192
    )
    assert plan["tasks"] == expected
    assert plan["nominal_samples"] == 3 * 25 * 4
    assert plan["nominal_max_output_tokens"] == 3 * 25 * 4 * 8192
    assert "mmlu_pro" not in plan["tasks"]
    assert plan["reasoning_effort"] == "max"
    assert benchmark_plan(
        "standard", official_runs=3, customer_runs=1,
        reasoning_effort="low",
    )["suite_sha256"] != plan["suite_sha256"]
    with pytest.raises(ValueError):
        benchmark_plan(
            "standard", official_runs=1, customer_runs=1,
            reasoning_effort="medium",
        )
    with pytest.raises(ValueError):
        benchmark_plan("other", official_runs=3, customer_runs=1)


def test_benchmark_does_not_compare_changed_datasets_or_configs():
    plan = benchmark_plan("smoke", official_runs=1, customer_runs=1)
    tasks = plan["tasks"]
    official = [[row(task) for task in tasks]]
    customer = [[row(task, score=.5) for task in tasks]]
    result = compare_benchmark_runs(
        official, customer, plan=plan, harness_version="0.4.9"
    )
    assert result["result"] == "measured"
    assert all(r["delta"] == pytest.approx(-.3) for r in result["tasks"])
    customer[0][0]["config_sha256"] = "b" * 64
    result = compare_benchmark_runs(
        official, customer, plan=plan, harness_version="0.4.9"
    )
    assert result["result"] == "partial_or_incomparable"
    assert result["tasks"][0]["status"] == "incomparable"
    customer[0][0]["config_sha256"] = "a" * 64
    customer[0][0]["sample_count"] = 4
    assert compare_benchmark_runs(
        official, customer, plan=plan, harness_version="0.4.9"
    )["tasks"][0]["status"] == "incomparable"


def test_benchmark_missing_data_does_not_look_like_good_quality():
    plan = benchmark_plan("smoke", official_runs=1, customer_runs=1)
    result = compare_benchmark_runs(
        [[]], [[]], plan=plan, harness_version="0.4.9"
    )
    assert result["result"] == "partial_or_incomparable"
    assert all(item["delta"] is None for item in result["tasks"])


def test_benchmark_run_uses_same_tasks_limits_and_never_logs_api_keys(
    monkeypatch,
):
    from model_detect import glm53_benchmark as module
    monkeypatch.setattr(
        module.lm_eval, "availability", lambda: {"available": True}
    )
    monkeypatch.setattr(module, "version", lambda name: "test-v1")
    monkeypatch.setattr(
        module, "benchmark_preflight",
        lambda level: {"ready": True, "checks": []},
    )
    requests = []

    def fake_run_endpoint(**kwargs):
        requests.append(kwargs)
        path = kwargs["output_path"]
        path.mkdir(parents=True)
        payload = {
            "results": {
                task: {"acc": .9} for task in kwargs["tasks"]
            },
            "versions": {task: 2 for task in kwargs["tasks"]},
            "n-samples": {
                task: {"effective": kwargs["limit"]}
                for task in kwargs["tasks"]
            },
            "configs": {
                task: {
                    "output_type": "generate_until", "task": task,
                    "generation_kwargs": {
                        "reasoning_effort": kwargs["reasoning_effort"]
                    },
                }
                for task in kwargs["tasks"]
            },
        }
        (path / "result.json").write_text(json.dumps(payload))
        return {"returncode": 0}

    monkeypatch.setattr(module.lm_eval, "run_endpoint", fake_run_endpoint)
    report = run_standard_benchmark(
        level="smoke",
        official_url="https://api.z.ai/api/paas/v4",
        customer_url="https://relay.example/v1",
        official_key="secret-official", customer_key="secret-vendor",
        official_runs=1, customer_runs=1,
    )
    assert report["result"] == "measured"
    assert len(requests) == 2
    assert requests[0]["tasks"] == requests[1]["tasks"]
    assert requests[0]["max_gen_toks"] == requests[1]["max_gen_toks"]
    assert requests[0]["max_retries"] == 0
    assert requests[0]["reasoning_effort"] == "max"
    assert requests[1]["reasoning_effort"] == "max"
    assert report["requested_reasoning_effort"] == "max"
    assert "no captured wire request" in report["generation_parameter_provenance"]
    assert "secret-" not in json.dumps(report)


def test_benchmark_cli_dry_run_previews_additional_cost_without_keys(
    monkeypatch,
):
    monkeypatch.delenv("GLM53_OFFICIAL_KEY", raising=False)
    monkeypatch.delenv("GLM53_CUSTOMER_KEY", raising=False)
    result = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://relay.example/v1",
        "--mode", "capability",
        "--capability-profile", "smoke",
        "--benchmark", "smoke", "--max-requests", "60",
    ])
    assert result.exit_code == 0, result.output
    assert "Benchmark" in result.output
    assert "预览完成" in result.output



def test_optional_benchmark_results_appear_in_same_customer_report(
    monkeypatch, tmp_path
):
    from model_detect import glm53_cli as module
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "mock-off")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "mock-ven")
    from model_detect.glm53_qualification import selected_cases

    async def fake_native(**kwargs):
        return [
            {
                "endpoint": kwargs["label"], "run": run,
                "id": case["id"], "kind": "protocol", "category": "protocol",
                "status": "pass", "usage": None,
            }
            for run in range(1, kwargs["runs"] + 1)
            for case in kwargs["cases"]
        ]

    monkeypatch.setattr(module, "run_endpoint", fake_native)
    monkeypatch.setattr(
        "model_detect.adapters.lm_eval.availability",
        lambda: {"available": True},
    )
    mock_bench = {
        "suite": "glm53-lm-eval-generative-v1",
        "suite_sha256": "x" * 64, "harness_version": "test",
        "result": "measured",
        "tasks": [{
            "task": "gsm8k", "dataset_version": 3, "sample_count": 5,
            "official_mean": .9, "customer_mean": .7, "delta": -.2,
            "status": "measured_difference",
        }],
        "limitations": ["not model identity proof"],
    }
    monkeypatch.setattr(
        module, "run_standard_benchmark",
        lambda **kwargs: mock_bench,
    )
    monkeypatch.setattr(
        module, "benchmark_preflight",
        lambda level: {"ready": True, "checks": [], "warning": "mocked"},
    )
    root = tmp_path / "run"
    result = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://relay.example/v1",
        "--official-runs", "1", "--customer-runs", "1",
        "--mode", "protocol", "--capability-profile", "smoke",
        "--benchmark", "smoke", "--benchmark-runs", "1",
        "--max-requests", "60", "--execute",
        "--output-dir", str(root),
    ])
    assert result.exit_code == 0, result.output
    saved = json.loads((root / "glm53-comparison.json").read_text(encoding="utf-8"))
    assert saved["standard_benchmark"]["result"] == "measured"
    assert saved["reference_provenance"]["official_host_verified"] is True
    assert "gsm8k" in (root / "glm53-comparison.md").read_text(encoding="utf-8")



def test_benchmark_task_disallows_unrecorded_reasoning_effort():
    from model_detect.glm53_benchmark import _check_task
    from model_detect.adapters.lm_eval import parse_result_payload
    result = {
        "results": {"gsm8k": {"exact_match,flexible-extract": .9}},
        "versions": {"gsm8k": 3},
        "n-samples": {"gsm8k": {"effective": 10}},
        "configs": {
            "gsm8k": {
                "task": "gsm8k",
                "output_type": "generate_until",
                "generation_kwargs": {"temperature": 0},
            },
        },
    }
    task = parse_result_payload(result)[0]
    assert _check_task(task, expected_reasoning_effort="max")["valid"] is False
    result["configs"]["gsm8k"]["generation_kwargs"]["reasoning_effort"] = "max"
    task2 = parse_result_payload(result)[0]
    assert _check_task(task2, expected_reasoning_effort="max")["valid"] is True
    assert _check_task(task2, expected_reasoning_effort="low")["valid"] is False

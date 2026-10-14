import copy
import io
import json
import zipfile

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.glm53_benchmark import _check_task, benchmark_plan, compare_benchmark_runs
from model_detect.glm53_qualification import plan_comparison, selected_cases
from model_detect.glm53_replay import replay_archive, write_replay
from model_detect.adapters.lm_eval import parse_result_payload


def _test_lm_eval(is_customer=False):
    url = (
        "https://vendor.example/v1/chat/completions" if is_customer
        else "https://official.example/v1/chat/completions"
    )
    metrics = {
        "gsm8k": {"exact_match,strict-match": .96,
                  "exact_match,flexible-extract": .96, "sample_len": 25},
        "ifeval": {
            "prompt_level_strict_acc,none": .48,
            "inst_level_strict_acc,none": .5135135135 if is_customer else .4324324324,
            "prompt_level_loose_acc,none": .48,
            "inst_level_loose_acc,none": .5135135135 if is_customer else .4324324324,
            "sample_len": 25,
        },
        "minerva_math500": {
            "exact_match,none": .88, "math_verify,none": .88 if is_customer else .92,
            "sample_len": 25,
        },
    }
    versions = {"gsm8k": 3., "ifeval": 4., "minerva_math500": 3.1}
    return {
        "results": metrics,
        "versions": versions,
        "n-samples": {k: {"effective": 25, "original": 500} for k in metrics},
        "n-shot": {"gsm8k": 5, "ifeval": 0, "minerva_math500": 4},
        "lm_eval_version": "0.4.13",
        "git_hash": "fixture-commit",
        "configs": {
            task: {
                "task": task, "dataset_path": f"dataset/{task}",
                "output_type": "generate_until",
                "num_fewshot": {"gsm8k": 5, "ifeval": 0, "minerva_math500": 4}[task],
                "generation_kwargs": {"temperature": 0},
                "metric_list": [{"metric": "exact_match"}],
                "fewshot_config": {
                    "process_docs": (
                        "<function process_docs at 0x7fbca2221234>"
                        if is_customer else "<function process_docs at 0x7fabc1114321>"
                    )
                },
                "metadata": {"base_url": url},
            }
            for task in metrics
        },
        "config": {
            "model": "local-chat-completions", "limit": 25,
            "model_args": {"model": "glm-5.3", "base_url": url,
                           "num_concurrent": 1, "max_retries": 0,
                           "max_gen_toks": 8192},
            "fewshot_seed": 1234, "random_seed": 0,
        },
    }


def _test_history(stage):
    plan = (
        plan_comparison(mode="protocol", profile="smoke", official_runs=1, customer_runs=1)
        if "01-" in stage
        else plan_comparison(
            mode="all", profile="smoke" if "02-" in stage else "standard",
            official_runs=3 if "03-" in stage else 1,
            customer_runs=1,
        )
    )
    cases = selected_cases(plan["mode"], plan["profile"])
    runs = {}
    for label in ("official", "customer"):
        count = plan["official_runs"] if label == "official" else plan["customer_runs"]
        rows = []
        for n in range(1, count + 1):
            for case in cases:
                capability = "check" not in case
                answer = {
                    "coding.complexity": "O(log n)",
                    "math.algebra-1": "**x = 8**",
                    "math.fraction-1": "**11/8**",
                    "reasoning.conditional-1": "**NO**",
                }.get(case["id"], "wrong")
                rows.append({
                    "endpoint": label, "run": n,
                    "id": case["id"], "kind": "capability" if capability else "protocol",
                    "category": case.get("category", "protocol"),
                    "status": (
                        "insufficient" if case["id"] == "thinking.disabled"
                        else "fail" if capability else "pass"
                    ),
                    "http_status": 400 if case["id"] == "thinking.disabled" else 200,
                    "finish_reason": "stop",
                    "observed_answer_excerpt": answer if capability else None,
                    "usage": None,
                })
        runs[label] = rows
    return {"plan": plan, "runs": runs,
            "suite_sha256": plan["suite_sha256"],
            "generated_at": "2026-10-13T12:00:00+00:00"}


def fixture_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        for stage in ("glm53-01-protocol", "glm53-02-smoke", "glm53-03-standard"):
            z.writestr(f"{stage}/glm53-comparison.json", json.dumps(_test_history(stage)))
        for label in ("official", "customer"):
            z.writestr(
                f"glm53-05-benchmark-standard-raw/{label}/glm-5.3/results_mock.json",
                json.dumps(_test_lm_eval(label == "customer")),
            )


def test_replay_01_05_regrades_without_writing_or_leaking_raw_source(tmp_path):
    source = tmp_path / "glm53-evidence.zip"
    fixture_zip(source)
    initial = source.read_bytes()
    report = replay_archive(source)
    assert source.read_bytes() == initial
    assert report["replay_version"] == "glm53-evidence-replay-v1"
    assert report["standard_benchmark"]["result"] == "measured"
    tasks = {row["task"]: row for row in report["standard_benchmark"]["tasks"]}
    assert len(tasks["ifeval"]["metrics"]) == 4
    assert len(tasks["minerva_math500"]["metrics"]) == 2
    exact = next(m for m in tasks["minerva_math500"]["metrics"]
                 if m["metric"] == "exact_match,none")
    verify = next(m for m in tasks["minerva_math500"]["metrics"]
                  if m["metric"] == "math_verify,none")
    assert exact["delta"] == pytest.approx(0)
    assert verify["delta"] == pytest.approx(-.04)
    inst = next(m for m in tasks["ifeval"]["metrics"]
                if m["metric"] == "inst_level_strict_acc,none")
    assert inst["delta"] == pytest.approx(.0810810811, abs=1e-7)
    assert all(c["verdict"] != "consistent" for c in report["stages"][
        "glm53-03-standard"]["protocol"] if c["id"] == "thinking.disabled")
    changed = report["stages"]["glm53-03-standard"]["changes"]
    assert any(x["case"] == "coding.complexity" and x["after"] == "pass" for x in changed)
    assert any(x["case"] == "math.algebra-1" and x["after"] == "pass" for x in changed)
    out = write_replay(report, tmp_path / "new")
    assert all(p.exists() for p in out.values())
    assert "inst_level_strict_acc,none" in out["markdown"].read_text(encoding="utf-8")
    saved = out["json"].read_text(encoding="utf-8")
    assert "vendor.example" not in saved and "official.example" not in saved
    assert "**11/8**" not in saved
    with pytest.raises(FileExistsError):
        write_replay(report, tmp_path / "new")


def test_replay_stays_strict_when_task_parameters_changed(tmp_path):
    source = tmp_path / "archive.zip"
    fixture_zip(source)
    modified = tmp_path / "modified.zip"
    with zipfile.ZipFile(source) as a, zipfile.ZipFile(modified, "w") as b:
        for name in a.namelist():
            data = a.read(name)
            if name.endswith("results_mock.json") and "/customer/" in name:
                data_obj = json.loads(data)
                data_obj["configs"]["ifeval"]["generation_kwargs"]["temperature"] = .7
                data = json.dumps(data_obj).encode()
            b.writestr(name, data)
    outcome = replay_archive(modified)
    task = next(t for t in outcome["standard_benchmark"]["tasks"]
                if t["task"] == "ifeval")
    assert task["status"] == "incomparable"
    assert task["metrics"] == []
    assert task["official_mean"] is None


def test_replay_command_requires_no_keys_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.delenv("GLM53_OFFICIAL_KEY", raising=False)
    monkeypatch.delenv("GLM53_CUSTOMER_KEY", raising=False)
    source = tmp_path / "input.zip"
    fixture_zip(source)
    args = ["glm53", "replay", "--evidence-zip", str(source),
            "--output-dir", str(tmp_path / "fresh")]
    runner = CliRunner()
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "没有调用模型 API" in first.output
    second = runner.invoke(app, args)
    assert second.exit_code != 0

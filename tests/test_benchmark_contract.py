"""Regression cases derived from 2026-10-13 GLM-5.3 0.4.13 output.

Only task configuration *shapes* and numeric observations are carried here:
no proprietary questions/answers, original provider URLs, paths or credentials.
"""

from copy import deepcopy

import pytest

from model_detect.adapters.lm_eval import parse_result_payload
from model_detect.benchmark_contract import (
    CONTRACT_VERSION, task_contract_sha256,
)
from model_detect.glm53_benchmark import (
    _check_task, benchmark_plan, compare_benchmark_runs,
)


TASKS = ("gsm8k", "ifeval", "minerva_math500")
VERSIONS = {"gsm8k": 3.0, "ifeval": 4.0, "minerva_math500": 3.1}
SHOTS = {"gsm8k": 5, "ifeval": 0, "minerva_math500": 4}
FILES = {
    "gsm8k": "gsm8k/gsm8k.yaml",
    "ifeval": "ifeval/ifeval.yaml",
    "minerva_math500": "minerva_math/minerva_math500.yaml",
}
FUNCTIONS = {
    "samples": "list_fewshot_samples",
    "process_docs": "process_docs",
    "doc_to_text": "doc_to_text",
}


def live_derived_result(vendor=False):
    # The real 05 run used these task versions, shot counts, scores and
    # generated task fields; all addresses/paths are replacement examples.
    host = "https://customer.example/v1/chat/completions" if vendor else (
        "https://official.example/v1/chat/completions"
    )
    install = "C:/venv/Lib/site-packages" if vendor else (
        "/opt/service/.venv/lib/python3.12/site-packages"
    )
    addresses = {
        key: f"<function {func} at 0x{'7fbc9efcc540' if vendor else '711beec545e0'}>"
        for key, func in FUNCTIONS.items()
    }
    configs = {}
    for task in TASKS:
        fewshot = {
            "sampler": "first_n" if task == "minerva_math500" else "default",
            "split": "train" if task == "gsm8k" else None,
            "samples": None,
            "process_docs": None,
            "doc_to_text": "prompt" if task == "ifeval" else "Question: {{question}}",
        }
        if task == "minerva_math500":
            fewshot.update(addresses)
        config = {
            "task": task,
            "dataset_path": {
                "gsm8k": "gsm8k", "ifeval": "google/IFEval",
                "minerva_math500": "HuggingFaceH4/MATH-500",
            }[task],
            "output_type": "generate_until",
            "num_fewshot": SHOTS[task],
            "fewshot_config": fewshot,
            "generation_kwargs": {
                "temperature": 0.0, "do_sample": False,
                "until": [],
            },
            "metric_list": [{"metric": "exact_match"}],
            "metadata": {
                "version": VERSIONS[task],
                "model": "glm-5.3",
                "base_url": host,
                "config_source": (
                    f"{install}/lm_eval/tasks/{FILES[task]}"
                ),
                "max_gen_toks": 8192,
                "num_concurrent": 1,
            },
        }
        if task == "ifeval":
            config["generation_kwargs"]["max_gen_toks"] = 1280
            config["metric_list"] = [{"metric": "prompt_level_strict_acc"}]
        if task == "minerva_math500":
            config["metric_list"] = [
                {"metric": "exact_match"}, {"metric": "math_verify"}
            ]
        configs[task] = config

    scores = {
        "gsm8k": {
            "exact_match,flexible-extract": .96,
            "exact_match,strict-match": .96,
        },
        "ifeval": {
            "prompt_level_strict_acc,none": .48,
            "inst_level_strict_acc,none": (
                .5135135135135135 if vendor else .43243243243243246
            ),
        },
        "minerva_math500": {
            "exact_match,none": .88,
            "math_verify,none": .88 if vendor else .92,
        },
    }
    return {
        "results": scores,
        "versions": VERSIONS.copy(),
        "n-shot": SHOTS.copy(),
        "lm_eval_version": "0.4.13",
        "n-samples": {t: {"effective": 25, "original": 500} for t in TASKS},
        "configs": configs,
        "config": {
            "model": "local-chat-completions",
            "model_args": str({
                "model": "glm-5.3",
                "base_url": host,
                "num_concurrent": 1,
                "max_retries": 0,
                "tokenized_requests": False,
                "max_gen_toks": 8192,
            }),
            "limit": 25.0,
            "gen_kwargs": {},
            "random_seed": 0,
            "numpy_seed": 1234,
            "torch_seed": 1234,
            "fewshot_seed": 1234,
        },
        "chat_template_sha": None,
        "system_instruction_sha": None,
        "fewshot_as_multiturn": False,
    }


def parsed(data):
    return [_check_task(item) for item in parse_result_payload(data)]


def test_real_derived_glm53_runs_are_comparable():
    official = live_derived_result()
    supplier = live_derived_result(vendor=True)
    official_rows = parsed(official)
    supplier_rows = parsed(supplier)
    assert all(x["valid"] for x in official_rows + supplier_rows)
    assert all(x["contract_version"] == CONTRACT_VERSION for x in official_rows)
    assert {x["task"]: x["config_sha256"] for x in official_rows} == {
        x["task"]: x["config_sha256"] for x in supplier_rows
    }
    plan = benchmark_plan("standard", official_runs=1, customer_runs=1)
    report = compare_benchmark_runs(
        [official_rows], [supplier_rows],
        plan=plan, harness_version="0.4.13",
    )
    assert report["result"] == "measured"
    assert all(x["status"] == "measured_difference" for x in report["tasks"])
    assert {x["task"]: x["delta"] for x in report["tasks"]} == {
        "gsm8k": pytest.approx(0.0),
        "ifeval": pytest.approx(0.0),
        "minerva_math500": pytest.approx(0.0),
    }
    # Additional task metrics are not silently conflated with the primary.
    assert official["results"]["minerva_math500"]["math_verify,none"] == .92
    assert supplier["results"]["minerva_math500"]["math_verify,none"] == .88


@pytest.mark.parametrize("change", [
    lambda x: x["configs"]["gsm8k"]["generation_kwargs"].update({"temperature": .5}),
    lambda x: x["configs"]["gsm8k"].update({"dataset_path": "other/dataset"}),
    lambda x: x["configs"]["gsm8k"].update({"num_fewshot": 3}),
    lambda x: x["configs"]["gsm8k"]["metric_list"].append({"metric": "f1"}),
    lambda x: x["configs"]["gsm8k"]["metadata"].update({"max_gen_toks": 4096}),
    lambda x: x["config"].update({"fewshot_seed": 444}),
    lambda x: x["config"]["model_args"].replace("glm-5.3", "fake-model"),
    lambda x: x["n-shot"].update({"gsm8k": 0}),
    lambda x: x["versions"].update({"gsm8k": 4.0}),
])
def test_real_score_affecting_config_changes_remain_incomparable(change):
    official = live_derived_result()
    supplier = live_derived_result(vendor=True)
    if change.__code__.co_consts and "fake-model" in change.__code__.co_consts:
        supplier["config"]["model_args"] = supplier["config"]["model_args"].replace(
            "glm-5.3", "fake-model"
        )
    else:
        change(supplier)
    task = "gsm8k"
    original = task_contract_sha256(task, official["configs"][task], official)
    revised = task_contract_sha256(task, supplier["configs"][task], supplier)
    assert original != revised


def test_unknown_python_object_memory_representation_fails_closed():
    data = live_derived_result()
    data["configs"]["gsm8k"]["doc_to_text"] = (
        "<UnknownObject at 0x711abcdef123>"
    )
    result = parse_result_payload(data)[0]
    assert result.observed["task_config_hash"] is None
    assert result.observed["task_contract_error"] is not None
    assert _check_task(result)["valid"] is False


def test_custom_task_absolute_paths_are_not_silently_equated():
    reference = live_derived_result()
    vendor = live_derived_result(vendor=True)
    reference["configs"]["gsm8k"]["metadata"]["config_source"] = "/mnt/a/custom.yaml"
    vendor["configs"]["gsm8k"]["metadata"]["config_source"] = "/mnt/b/custom.yaml"
    a = task_contract_sha256("gsm8k", reference["configs"]["gsm8k"], reference)
    b = task_contract_sha256("gsm8k", vendor["configs"]["gsm8k"], vendor)
    assert a != b

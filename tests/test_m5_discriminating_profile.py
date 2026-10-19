"""M5: hard-math Deep profile uses upstream scorer without reimplementing it."""
from pathlib import Path

from model_detect.adapters.lm_eval import (
    build_command, resolve_builtin_profile,
)
from model_detect.test_catalog import build_test_catalog
from model_detect.evaluation_catalog import evaluation_catalog


def test_deep_replaces_redundant_easy_math_with_existing_math500_task():
    base = resolve_builtin_profile("deep", include_native_overlap=True)
    assert base["tasks"] == ["truthfulqa_gen", "ifeval", "minerva_math500"]
    assert base["limit"] == 25
    assert "gsm8k" not in base["tasks"]
    task = base["task_metadata"]["minerva_math500"]
    assert task["output_type"] == "generate_until"
    assert task["source_tag"] == "v0.4.13"
    assert task["source_dataset"] == "HuggingFaceH4/MATH-500"
    assert task["optional_dependency"] == "lm-eval[math]==0.4.13"


def test_source_and_difficulty_only_registered_once():
    main = {row["id"]: row for row in build_test_catalog()["entries"]}
    view = {row["id"]: row for row in evaluation_catalog()["entries"]}
    assert main["lm_eval.minerva_math500"]["difficulty"] == "advanced"
    assert main["lm_eval.minerva_math500"]["source_revision"] == "v0.4.13"
    assert main["lm_eval.minerva_math500"]["source_url"].endswith(
        "/blob/v0.4.13/lm_eval/tasks/minerva_math/minerva_math500.yaml"
    )
    assert view["lm_eval:minerva_math500"]["difficulty"] == "advanced"
    assert view["lm_eval:minerva_math500"]["authority"] == "community_benchmark"
    assert view["lm_eval:minerva_math500"]["source_revision"] == "v0.4.13"
    assert not view["lm_eval:minerva_math500"]["verified_on_live_model"]


def test_deep_lm_eval_command_still_calls_original_task_runner(tmp_path):
    tasks = resolve_builtin_profile("deep", include_native_overlap=True)["tasks"]
    command = build_command(
        base_url="http://127.0.0.1:8080/v1",
        model="glm-5.3", tasks=tasks, limit=25, binary="lm_eval",
        output_path=tmp_path,
    )
    assert command[command.index("--tasks")+1] == "truthfulqa_gen,ifeval,minerva_math500"
    assert command[command.index("--limit")+1] == "25"
    assert "--log_samples" not in command


def test_quick_and_standard_task_sets_not_broadened_implicitly():
    assert resolve_builtin_profile("smoke", include_native_overlap=True)["tasks"] == ["truthfulqa_gen"]
    standard = resolve_builtin_profile("standard", include_native_overlap=True)
    assert standard["tasks"] == ["truthfulqa_gen", "gsm8k", "ifeval"]
    assert standard["limit"] == 25

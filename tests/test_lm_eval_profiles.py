from model_detect.adapters import lm_eval
from model_detect.adapters.lm_eval import (
    get_builtin_profile,
    load_builtin_profiles,
    resolve_builtin_profile,
)


def test_builtin_lm_eval_tasks_are_chat_generation_tasks():
    data = load_builtin_profiles()

    assert set(data["tasks"]) == {"truthfulqa_gen", "gsm8k", "ifeval"}
    assert all(
        item["output_type"] == "generate_until"
        for item in data["tasks"].values()
    )


def test_builtin_profiles_reference_known_tasks():
    data = load_builtin_profiles()

    for name, profile in data["profiles"].items():
        assert profile["tasks"], name
        assert len(profile["tasks"]) == len(set(profile["tasks"]))
        assert all(task in data["tasks"] for task in profile["tasks"])


def test_get_builtin_profile():
    profile = get_builtin_profile("standard")

    assert profile["tasks"] == ["truthfulqa_gen", "gsm8k", "ifeval"]
    assert profile["limit"] == 25
    assert profile["task_metadata"]["truthfulqa_gen"]["dimension"] == "truthfulness"



def test_resolve_profile_excludes_native_capability_overlap_by_default():
    profile = resolve_builtin_profile("standard")

    assert profile["candidate_tasks"] == [
        "truthfulqa_gen",
        "gsm8k",
        "ifeval",
    ]
    assert profile["tasks"] == ["truthfulqa_gen"]
    assert profile["skipped_tasks"] == ["gsm8k", "ifeval"]
    assert profile["include_native_overlap"] is False


def test_resolve_profile_can_explicitly_include_overlap():
    profile = resolve_builtin_profile(
        "standard",
        include_native_overlap=True,
    )

    assert profile["tasks"] == [
        "truthfulqa_gen",
        "gsm8k",
        "ifeval",
    ]
    assert profile["skipped_tasks"] == []


def test_run_builtin_profile_deduplicates_before_execution(monkeypatch, tmp_path):
    seen = {}

    def fake_run_endpoint(**kwargs):
        seen.update(kwargs)
        return {"returncode": 0, "engine": "fake"}

    monkeypatch.setattr(lm_eval, "run_endpoint", fake_run_endpoint)

    result = lm_eval.run_builtin_profile(
        profile_name="standard",
        base_url="https://relay.example/v1",
        model="model-x",
        api_key="sk-test",
        output_path=tmp_path,
    )

    assert seen["tasks"] == ["truthfulqa_gen"]
    assert seen["limit"] == 25
    assert result["tasks"] == ["truthfulqa_gen"]
    assert result["skipped_tasks"] == ["gsm8k", "ifeval"]
    assert result["deduplicated_against_capability_lite"] is True

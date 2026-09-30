from model_detect.adapters.lm_eval import get_builtin_profile, load_builtin_profiles


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

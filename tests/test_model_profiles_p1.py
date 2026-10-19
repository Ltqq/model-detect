"""Offline regression for sourced GLM Flash / DeepSeek current API aliases."""

from model_detect.rules import feature_spec_for, match_model_rule


def test_glm_flash_is_not_flagship_rule():
    assert match_model_rule("glm-5.3").id == "glm-5.3"
    for model in ("glm-5.3-flash", "glm-5.3-flashx"):
        rule = match_model_rule(model)
        assert rule.id == "glm-5.3-flash"
        assert rule.sources
        assert feature_spec_for(model, "reasoning_effort")["values"] == [
            "low", "high", "max"
        ]


def test_deepseek_flash_legacy_alias_is_versioned():
    for model in (
        "deepseek-flash",
        "deepseek-v4-flash",
        "deepseek-v4-flash-vision-exp",
        "deepseek-v4.1-flash",
    ):
        rule = match_model_rule(model)
        assert rule.id == "deepseek-v4.1"
        assert rule.model_version == "v4.1-flash-1017"
        assert rule.sources


def test_deepseek_v4_pro_is_not_mislabeled_as_flash():
    assert match_model_rule("deepseek-v4-pro").id == "deepseek-v4"
    assert feature_spec_for("deepseek-flash", "json_schema").get("expected") is None

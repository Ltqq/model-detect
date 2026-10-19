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


def test_deepseek_flash_uses_documented_chat_completion_parameters():
    from model_detect.rules import effective_features_for, preferred_feature_value
    rule = match_model_rule("deepseek-flash")
    reasoning = feature_spec_for("deepseek-flash", "reasoning_effort")
    assert reasoning["expected"] is True
    assert reasoning["values"] == ["none", "low", "high", "max"]
    assert reasoning["default"] == "high"
    assert preferred_feature_value("deepseek-flash", "reasoning_effort") == "high"
    assert rule.protocol_features["chat_completions"]["disable_thinking"]["expected"] is True
    assert feature_spec_for("deepseek-flash", "tools")["expected"] is True
    assert feature_spec_for("deepseek-flash", "json_schema")["expected"] is None
    assert feature_spec_for(
        "deepseek-flash", "reasoning_effort", protocol="responses"
    )["native_parameter"] == "reasoning.effort"
    sources = {source.id for source in rule.sources}
    assert "deepseek-thinking-mode" in sources
    assert "deepseek-chat-completions" in sources
    assert "deepseek-pricing" in sources


def test_deepseek_flash_unsupported_json_schema_not_inferred_as_failure():
    from model_detect.rules import evaluate_rule_expectations
    checks = evaluate_rule_expectations(
        "deepseek-flash", {"json_schema": False, "tools": True}
    )
    assert "json_schema" not in {item["feature"] for item in checks}
    assert any(item["feature"] == "tools" and item["status"] == "pass" for item in checks)


def test_all_five_target_models_have_distinct_sourced_rules():
    """P1 catalog smoke: no profile silently falls through to generic defaults."""
    expected = {
        "glm-5.3": "glm-5.3",
        "glm-5.3-flash": "glm-5.3-flash",
        "kimi-k3": "kimi-k3",
        "deepseek-v4-pro": "deepseek-v4",
        "deepseek-flash": "deepseek-v4.1",
    }
    for supplied_id, rule_id in expected.items():
        rule = match_model_rule(supplied_id)
        assert rule.id == rule_id, f"{supplied_id} unexpectedly used {rule.id}"
        assert rule.sources, f"{supplied_id} has no provenance"
        assert rule.updated_at, f"{supplied_id} has no source review date"
        assert any(source.url for source in rule.sources), (
            f"{supplied_id} has no source URL"
        )
        assert rule.strict is False, (
            "Do not turn uncertain third-party gateway behavior into a hard failure"
        )

import pytest

from model_detect.rules import (
    ModelRule,
    apply_feature_probe_request,
    evaluate_rule_expectations,
    feature_spec_for,
    load_model_rules,
    match_model_rule,
    normalize_model_rule,
)


def test_kimi_rule_matches():
    rule = match_model_rule("kimi-k3")
    assert rule.id == "kimi-k3"
    assert rule.schema_version == 3
    assert rule.family == "kimi"
    assert rule.model_version == "k3"
    assert "reasoning_effort" in rule.features
    effort = feature_spec_for("kimi-k3", "reasoning_effort")
    assert effort["values"] == ["low", "high", "max"]
    assert effort["default"] == "max"
    assert rule.features["disable_thinking"]["expected"] is False
    assert {
        source.id
        for source in rule.sources
    } >= {
        "moonshot-kimi-k3-readme",
        "kimi-api-troubleshooting",
    }


def test_default_rule_matches_unknown_model():
    rule = match_model_rule("totally-unknown-model")
    assert rule.id == "default"
    assert rule.schema_version == 1


def test_non_strict_mismatch_is_warning():
    rows = evaluate_rule_expectations(
        "kimi-k3",
        {
            "reasoning_effort": False,
            "disable_thinking": True,
        },
    )
    statuses = {x["feature"]: x["status"] for x in rows}
    assert statuses["reasoning_effort"] == "warn"
    assert statuses["disable_thinking"] == "warn"
    assert all(row["rule_schema_version"] == 3 for row in rows)
    refs = {x["feature"]: x["source_refs"] for x in rows}
    assert "moonshot-kimi-k3-readme" in refs["reasoning_effort"]
    assert "kimi-api-troubleshooting" in refs["disable_thinking"]


def test_v1_rule_without_schema_version_is_backward_compatible():
    rule = normalize_model_rule(
        {
            "id": "legacy",
            "patterns": ["legacy-*"],
            "features": {
                "reasoning": {
                    "expected": True,
                }
            },
        }
    )

    assert rule.schema_version == 1
    assert rule.family is None
    assert rule.sources == []


def test_v2_rule_loads_version_aliases_and_sources():
    rule = normalize_model_rule(
        {
            "schema_version": 2,
            "id": "kimi-k3",
            "family": "kimi",
            "model_version": "k3",
            "patterns": ["kimi-k3"],
            "aliases": ["moonshot-kimi-k3"],
            "updated_at": "2026-09-30",
            "sources": [
                {
                    "id": "official-reasoning",
                    "type": "official_doc",
                    "title": "Reasoning parameters",
                    "url": "https://example.com/docs",
                    "collected_at": "2026-09-30",
                    "confidence": "high",
                }
            ],
            "features": {
                "reasoning_effort": {
                    "expected": True,
                    "values": ["low", "medium", "high"],
                    "source_refs": ["official-reasoning"],
                }
            },
        }
    )

    assert rule.schema_version == 3
    assert rule.family == "kimi"
    assert rule.model_version == "k3"
    assert rule.aliases == ["moonshot-kimi-k3"]
    assert rule.sources[0].type == "official_doc"
    assert rule.sources[0].confidence == "high"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "random_source"),
        ("confidence", "certain"),
    ],
)
def test_v2_rule_rejects_unknown_source_enum(field, value):
    source = {
        "id": "s1",
        "type": "official_doc",
        "confidence": "high",
    }
    source[field] = value

    with pytest.raises(ValueError):
        normalize_model_rule(
            {
                "schema_version": 2,
                "id": "bad",
                "patterns": ["bad"],
                "sources": [source],
                "features": {},
            }
        )


def test_v2_rule_rejects_unknown_feature_source_ref():
    with pytest.raises(ValueError, match="unknown sources"):
        normalize_model_rule(
            {
                "schema_version": 2,
                "id": "bad",
                "patterns": ["bad"],
                "sources": [],
                "features": {
                    "reasoning": {
                        "expected": True,
                        "source_refs": ["missing"],
                    }
                },
            }
        )


def test_v2_rule_rejects_duplicate_source_ids():
    with pytest.raises(ValueError, match="source ids must be unique"):
        normalize_model_rule(
            {
                "schema_version": 2,
                "id": "bad",
                "patterns": ["bad"],
                "sources": [
                    {
                        "id": "same",
                        "type": "official_doc",
                    },
                    {
                        "id": "same",
                        "type": "empirical",
                    },
                ],
                "features": {},
            }
        )


def test_strict_v2_rule_rejects_only_low_confidence_community_sources():
    with pytest.raises(ValueError, match="strict v2"):
        ModelRule.model_validate(
            {
                "schema_version": 2,
                "id": "bad-strict",
                "patterns": ["bad"],
                "strict": True,
                "sources": [
                    {
                        "id": "community-only",
                        "type": "community",
                        "confidence": "low",
                    }
                ],
                "features": {
                    "reasoning": {
                        "expected": True,
                        "source_refs": ["community-only"],
                    }
                },
            }
        )



@pytest.mark.parametrize(
    ("model", "rule_id"),
    [
        ("glm-5.2", "glm-5.2"),
        ("GLM-5.2", "glm-5.2"),
        ("qwen3.8-max", "qwen3.8"),
        ("qwen3.8-flash", "qwen3.8"),
        ("deepseek-v4-pro", "deepseek-v4"),
        ("deepseek-v4.1-flash", "deepseek-v4"),
        ("deepseek-flash", "deepseek-v4"),
    ],
)
def test_first_formal_model_rules_match(model, rule_id):
    rule = match_model_rule(model)
    assert rule.id == rule_id
    assert rule.schema_version == 3
    assert rule.sources


def test_glm_52_rule_has_traceable_reasoning_effort():
    rule = match_model_rule("glm-5.2")

    spec = feature_spec_for("glm-5.2", "reasoning_effort")
    assert spec["expected"] is True
    assert spec["values"] == ["high", "max"]
    assert spec["default"] == "max"
    assert set(spec["source_refs"]) == {
        "zai-glm-5.2-release",
        "zai-glm-5-model-repo",
    }
    assert rule.declared_context_tokens == 1000000


def test_qwen38_rule_has_traceable_thinking_controls():
    rule = match_model_rule("qwen3.8-max")

    effort = feature_spec_for("qwen3.8-max", "reasoning_effort")
    assert effort["values"] == ["none", "low", "medium", "xhigh"]
    assert effort["default"] == "xhigh"
    assert rule.features["disable_thinking"]["expected"] is True
    assert effort["source_refs"] == [
        "alibaba-qwen-responses-reasoning"
    ]


def test_deepseek_v4_rule_has_traceable_reasoning_and_tools():
    rule = match_model_rule("deepseek-v4-pro")

    effort = feature_spec_for("deepseek-v4-pro", "reasoning_effort")
    assert effort["values"] == ["none", "low", "high", "max"]
    assert effort["default"] == "high"
    assert rule.features["disable_thinking"]["expected"] is True
    assert rule.features["tools"]["expected"] is True
    assert "deepseek-thinking-mode" in (
        rule.features["tools"]["source_refs"]
    )


def test_all_expected_v2_plus_features_are_traceable():
    for rule in load_model_rules():
        if rule.schema_version < 2:
            continue
        source_ids = {source.id for source in rule.sources}
        feature_sets = [("features", rule.features)]
        feature_sets.extend(
            (f"protocol_features.{protocol}", specs)
            for protocol, specs in rule.protocol_features.items()
        )
        for namespace, specs in feature_sets:
            for feature, spec in specs.items():
                if not isinstance(spec, dict):
                    continue
                if spec.get("expected") is None:
                    continue
                refs = spec.get("source_refs") or []
                assert refs, f"{rule.id}.{namespace}.{feature} missing source_refs"
                assert set(refs) <= source_ids


def test_official_expectations_do_not_implicitly_use_empirical_sources():
    for rule in load_model_rules():
        if rule.id not in {"glm-5.2", "qwen3.8", "deepseek-v4"}:
            continue
        by_id = {source.id: source for source in rule.sources}
        for spec in rule.features.values():
            if not isinstance(spec, dict) or spec.get("expected") is None:
                continue
            for ref in spec.get("source_refs") or []:
                assert by_id[ref].type != "empirical"


@pytest.mark.parametrize(
    ("model", "rule_id"),
    [
        ("claude-fable-5-1", "claude-5-current"),
        ("claude-opus-5", "claude-5-current"),
        ("claude-sonnet-5", "claude-5-current"),
        ("gpt-5.6", "gpt-5.6"),
        ("gpt-5.6-sol", "gpt-5.6"),
        ("gpt-5.6-terra", "gpt-5.6"),
        ("gpt-5.6-luna", "gpt-5.6"),
        ("gemini-3.8-flash", "gemini-3.8-flash"),
    ],
)
def test_second_formal_model_rules_match(model, rule_id):
    rule = match_model_rule(model)
    assert rule.id == rule_id
    assert rule.schema_version == 3
    assert rule.sources


def test_claude_5_rule_avoids_gateway_specific_reasoning_assumptions():
    rule = match_model_rule("claude-opus-5")
    assert rule.declared_context_tokens == 1000000
    assert rule.features["tools"]["expected"] is True
    assert rule.features["reasoning_effort"]["expected"] is None
    assert rule.features["disable_thinking"]["expected"] is None
    assert rule.features["json_schema"]["expected"] is None


def test_gpt_56_rule_has_traceable_reasoning_and_tools():
    rule = match_model_rule("gpt-5.6-sol")
    assert rule.declared_context_tokens == 1050000
    effort = feature_spec_for("gpt-5.6-sol", "reasoning_effort")
    assert effort["values"] == ["none", "low", "medium", "high", "xhigh", "max"]
    assert effort["source_refs"] == ["openai-gpt-5.6-sol"]
    assert rule.features["tools"]["expected"] is True


def test_gemini_38_rule_has_traceable_openai_compatible_controls():
    rule = match_model_rule("gemini-3.8-flash")
    assert rule.declared_context_tokens == 1000000
    effort = feature_spec_for("gemini-3.8-flash", "reasoning_effort")
    assert effort["values"] == ["low", "medium", "high"]
    assert effort["default"] == "medium"
    assert rule.features["disable_thinking"]["expected"] is False
    assert rule.features["tools"]["expected"] is True
    assert rule.features["json_schema"]["expected"] is True


def test_new_vendor_rules_use_only_official_sources_for_assertions():
    rule_ids = {"claude-5-current", "gpt-5.6", "gemini-3.8-flash"}
    for rule in load_model_rules():
        if rule.id not in rule_ids:
            continue
        by_id = {source.id: source for source in rule.sources}
        for spec in rule.features.values():
            if not isinstance(spec, dict) or spec.get("expected") is None:
                continue
            refs = spec.get("source_refs") or []
            assert refs
            assert all(by_id[ref].type == "official_doc" for ref in refs)



def test_v3_protocol_features_override_global_feature_semantics():
    deepseek_chat = feature_spec_for(
        "deepseek-v4-pro",
        "reasoning_effort",
        protocol="chat_completions",
    )
    deepseek_responses = feature_spec_for(
        "deepseek-v4-pro",
        "reasoning_effort",
        protocol="responses",
    )

    assert deepseek_chat["native_parameter"] == "reasoning_effort"
    assert deepseek_responses["native_parameter"] == "reasoning.effort"
    assert deepseek_responses["mappings"]["medium"] == "high"


def test_qwen_v3_keeps_chat_and_responses_parameter_shapes_separate():
    chat = feature_spec_for(
        "qwen3.8-max",
        "reasoning_effort",
        protocol="chat_completions",
    )
    responses = feature_spec_for(
        "qwen3.8-max",
        "reasoning_effort",
        protocol="responses",
    )

    assert chat["native_parameter"] == "reasoning_effort"
    assert responses["native_parameter"] == "reasoning.effort"
    assert chat["default"] == responses["default"] == "xhigh"


def test_feature_specific_probe_request_supports_official_constraints():
    payload = apply_feature_probe_request(
        "gpt-5.6-sol",
        "tools",
        {"model": "gpt-5.6-sol", "messages": []},
    )
    assert payload["reasoning_effort"] == "none"


def test_v3_rejects_unknown_protocol_feature_source_ref():
    with pytest.raises(ValueError, match="unknown sources"):
        normalize_model_rule(
            {
                "schema_version": 3,
                "id": "bad-v3",
                "patterns": ["bad-v3"],
                "sources": [],
                "features": {},
                "protocol_features": {
                    "responses": {
                        "reasoning_effort": {
                            "values": ["low"],
                            "source_refs": ["missing"],
                        }
                    }
                },
            }
        )

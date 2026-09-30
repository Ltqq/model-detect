from model_detect.rules import evaluate_rule_expectations, match_model_rule


def test_kimi_rule_matches():
    rule = match_model_rule("kimi-k3")
    assert rule.id == "kimi-k3"
    assert "reasoning_effort" in rule.features


def test_default_rule_matches_unknown_model():
    rule = match_model_rule("totally-unknown-model")
    assert rule.id == "default"


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

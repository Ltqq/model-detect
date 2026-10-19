"""Guard the five release model IDs against silent, order-dependent rule selection.

No model API calls and no new detection engine: this only validates the shipped
vendor rule YAMLs before release.
"""

import fnmatch

import pytest

from model_detect.rules import load_model_rules, match_model_rule


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("glm-5.3", "glm-5.3"),
        ("glm-5.3-flash", "glm-5.3-flash"),
        ("glm-5.3-flashx", "glm-5.3-flash"),
        ("kimi-k3", "kimi-k3"),
        ("deepseek-v4-pro", "deepseek-v4"),
        ("deepseek-v4-pro-0813", "deepseek-v4"),
        ("deepseek-flash", "deepseek-v4.1"),
        ("deepseek-v4-flash", "deepseek-v4.1"),
        ("deepseek-v4-flash-vision-exp", "deepseek-v4.1"),
        ("deepseek-v4.1-flash", "deepseek-v4.1"),
    ],
)
def test_release_model_has_one_explicit_rule_and_source(model, expected):
    matching = []
    for rule in load_model_rules():
        if rule.id == "default":
            continue
        patterns = list(rule.patterns) + list(rule.aliases)
        if any(fnmatch.fnmatchcase(model.casefold(), pattern.casefold()) for pattern in patterns):
            matching.append(rule.id)

    assert matching == [expected], (
        f"ambiguous/missing model rule for {model}: {matching}; "
        "matching must not depend on YAML iteration order"
    )
    rule = match_model_rule(model)
    assert rule.id == expected
    assert rule.sources, f"{model} is missing provenance"
    assert rule.updated_at, f"{model} is missing verification date"


def test_unlisted_model_does_not_inherit_five_model_contract():
    assert match_model_rule("unexpected-future-model-999").id == "default"

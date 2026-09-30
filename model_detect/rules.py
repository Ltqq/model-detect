from __future__ import annotations

import fnmatch
from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ModelRule(BaseModel):
    id: str
    patterns: list[str] = Field(default_factory=list)
    strict: bool = False
    declared_context_tokens: int | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def load_model_rules() -> list[ModelRule]:
    root = files("model_detect").joinpath("data/models")
    rules: list[ModelRule] = []
    for item in sorted(root.iterdir(), key=lambda x: x.name):
        if item.name.endswith((".yaml", ".yml")):
            raw = yaml.safe_load(item.read_text(encoding="utf-8")) or {}
            rules.append(ModelRule.model_validate(raw))
    return rules


def match_model_rule(model: str) -> ModelRule:
    lowered = model.casefold()
    fallback: ModelRule | None = None
    for rule in load_model_rules():
        if rule.id == "default":
            fallback = rule
            continue
        for pattern in rule.patterns:
            if fnmatch.fnmatch(lowered, pattern.casefold()):
                return rule
    return fallback or ModelRule(id="default", patterns=["*"])


def evaluate_rule_expectations(model: str, observations: dict[str, Any]) -> list[dict[str, Any]]:
    rule = match_model_rule(model)
    out: list[dict[str, Any]] = []
    for feature, spec in rule.features.items():
        if not isinstance(spec, dict) or spec.get("expected") is None:
            continue
        expected = bool(spec["expected"])
        observed = observations.get(feature)
        if observed is None:
            status = "insufficient"
        elif bool(observed) == expected:
            status = "pass"
        else:
            status = "fail" if rule.strict else "warn"
        out.append(
            {
                "feature": feature,
                "expected": expected,
                "observed": observed,
                "status": status,
                "rule_id": rule.id,
                "strict": rule.strict,
            }
        )
    return out

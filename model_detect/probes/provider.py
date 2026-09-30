from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from ..models import Evidence, ProviderHypothesis
from ..rules import RuleSource


class ProviderRule(BaseModel):
    label: str
    headers: dict[str, float] = Field(default_factory=dict)
    patterns: dict[str, float] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    false_positive_notes: list[str] = Field(default_factory=list)
    confidence_calibration: dict[str, Any] = Field(default_factory=dict)


class ProviderRuleSet(BaseModel):
    schema_version: Literal[1, 2] = 1
    sources: list[RuleSource] = Field(default_factory=list)
    providers: dict[str, ProviderRule] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provenance(self):
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("provider source ids must be unique")

        known_sources = set(source_ids)
        for provider_id, rule in self.providers.items():
            missing = sorted(set(rule.source_refs) - known_sources)
            if missing:
                raise ValueError(
                    f"provider {provider_id!r} references unknown sources: {missing}"
                )
        return self


def normalize_provider_rule_set(raw: dict[str, Any]) -> ProviderRuleSet:
    if not isinstance(raw, dict):
        raise ValueError("provider rule YAML root must be an object")

    normalized = dict(raw)
    if "schema_version" not in normalized:
        normalized["schema_version"] = normalized.pop("version", 1)
    else:
        normalized.pop("version", None)
    normalized.setdefault("sources", [])
    normalized.setdefault("providers", {})
    return ProviderRuleSet.model_validate(normalized)


@lru_cache(maxsize=1)
def load_provider_rule_set() -> ProviderRuleSet:
    path = files("model_detect").joinpath("data/providers.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return normalize_provider_rule_set(raw)


def load_provider_rules() -> dict[str, ProviderRule]:
    return load_provider_rule_set().providers


def _body_text(evidence: Evidence) -> str:
    try:
        return json.dumps(
            evidence.response_body,
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
    except Exception:
        return str(evidence.response_body).lower()


def detect_provider_hypotheses(
    evidences: Iterable[Evidence],
) -> list[ProviderHypothesis]:
    rules = load_provider_rules()
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, list[str]] = defaultdict(list)

    for evidence in evidences:
        headers = {
            str(k).lower(): str(v)
            for k, v in evidence.response_headers.items()
        }
        body = _body_text(evidence)
        for provider, rule in rules.items():
            for header, weight in rule.headers.items():
                if str(header).lower() in headers:
                    scores[provider] += float(weight)
                    reasons[provider].append(
                        f"{evidence.probe_id}: response header {header}"
                    )
            for pattern, weight in rule.patterns.items():
                if str(pattern).lower() in body:
                    scores[provider] += float(weight)
                    reasons[provider].append(
                        f"{evidence.probe_id}: response body contains {pattern!r}"
                    )

    out: list[ProviderHypothesis] = []
    for provider, raw_score in scores.items():
        confidence = min(0.99, 1 - (0.5 ** max(raw_score, 0.01)))
        if confidence < 0.2:
            continue
        out.append(
            ProviderHypothesis(
                provider=provider,
                confidence=round(confidence, 3),
                evidence=list(dict.fromkeys(reasons[provider])),
            )
        )
    return sorted(out, key=lambda x: x.confidence, reverse=True)

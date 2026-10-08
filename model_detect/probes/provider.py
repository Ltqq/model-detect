from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from ..models import Evidence, ProbeResult, ProbeStatus, ProviderHypothesis
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



def _provider_signal_details(
    evidence: Evidence,
    rule: ProviderRule,
) -> list[dict[str, Any]]:
    headers = {
        str(k).lower(): str(v)
        for k, v in evidence.response_headers.items()
    }
    body = _body_text(evidence)
    signals: list[dict[str, Any]] = []
    for header, weight in rule.headers.items():
        if str(header).lower() in headers:
            signals.append(
                {
                    "kind": "header",
                    "value": str(header),
                    "weight": float(weight),
                }
            )
    for pattern, weight in rule.patterns.items():
        if str(pattern).lower() in body:
            signals.append(
                {
                    "kind": "body",
                    "value": str(pattern),
                    "weight": float(weight),
                }
            )
    return signals


def evaluate_upstream_policy(
    evidences: Iterable[Evidence],
    hypotheses: list[ProviderHypothesis],
    *,
    disallowed: list[str],
    min_confidence: float = 0.70,
    strong_signal_weight: float = 0.90,
) -> ProbeResult:
    probe_id = "provider.upstream_policy"
    disallowed_set = {
        item.strip().casefold()
        for item in disallowed
        if isinstance(item, str) and item.strip()
    }
    if not disallowed_set:
        return ProbeResult(
            probe_id=probe_id,
            category="provider",
            status=ProbeStatus.SKIPPED,
            score=None,
            confidence=1.0,
            summary="no disallowed upstream providers configured",
            metadata={"policy_violation": False},
        )

    evidence_list = list(evidences)
    rules = load_provider_rules()
    by_provider = {
        item.provider.casefold(): item
        for item in hypotheses
    }
    detected: list[dict[str, Any]] = []
    matched_evidence_ids: list[str] = []

    for provider in sorted(disallowed_set):
        rule = rules.get(provider)
        hypothesis = by_provider.get(provider)
        provider_evidence: list[dict[str, Any]] = []
        max_signal_weight = 0.0
        if rule is not None:
            for evidence in evidence_list:
                signals = _provider_signal_details(evidence, rule)
                if not signals:
                    continue
                max_signal_weight = max(
                    max_signal_weight,
                    max(float(item["weight"]) for item in signals),
                )
                provider_evidence.append(
                    {
                        "evidence_id": evidence.id,
                        "probe_id": evidence.probe_id,
                        "signals": signals,
                    }
                )
                matched_evidence_ids.append(evidence.id)

        confidence = hypothesis.confidence if hypothesis else 0.0
        policy_match = (
            confidence >= min_confidence
            or max_signal_weight >= strong_signal_weight
        )
        if policy_match:
            detected.append(
                {
                    "provider": provider,
                    "confidence": confidence,
                    "max_signal_weight": max_signal_weight,
                    "evidence": provider_evidence,
                }
            )

    rate_limit_ids = [
        evidence.id
        for evidence in evidence_list
        if evidence.response_status == 429
    ]
    violation = bool(detected)
    return ProbeResult(
        probe_id=probe_id,
        category="provider",
        status=ProbeStatus.FAIL if violation else ProbeStatus.PASS,
        score=0.0 if violation else None,
        confidence=0.95 if violation else 0.65,
        summary=(
            "disallowed upstream provider evidence detected: "
            + ", ".join(item["provider"] for item in detected)
            if violation
            else "no disallowed upstream provider evidence was observed"
        ),
        expected={
            "disallowed": sorted(disallowed_set),
            "min_confidence": min_confidence,
            "strong_signal_weight": strong_signal_weight,
        },
        observed={
            "detected": detected,
            "http_429_count": len(rate_limit_ids),
            "http_429_evidence_ids": rate_limit_ids,
            "provider_hypotheses": [
                item.model_dump(mode="json")
                for item in hypotheses
            ],
        },
        evidence_ids=list(
            dict.fromkeys([*matched_evidence_ids, *rate_limit_ids])
        ),
        metadata={
            "policy_violation": violation,
            "policy_type": "disallowed_upstream",
            "rate_limit_is_auxiliary_only": True,
        },
    )

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

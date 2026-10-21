from __future__ import annotations

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


def _provider_signal_details(
    evidence: Evidence,
    rule: ProviderRule,
) -> list[dict[str, Any]]:
    headers = {
        str(k).lower(): str(v)
        for k, v in evidence.response_headers.items()
    }
    # Only response metadata is eligible for provider hints. Model-generated
    # content, reasoning, and free-text error messages are untrusted and must
    # never be searched for brand substrings.
    signals: list[dict[str, Any]] = []
    for header, weight in rule.headers.items():
        if headers.get(str(header).lower(), "").strip() and float(weight) >= 0.30:
            signals.append(
                {
                    "kind": "header",
                    "value": str(header),
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
            confidence=None,
            summary="no disallowed upstream providers configured",
            metadata={"policy_violation": False},
        )

    evidence_list = list(evidences)
    rules = load_provider_rules()
    detected: list[dict[str, Any]] = []
    matched_evidence_ids: list[str] = []

    for provider in sorted(disallowed_set):
        rule = rules.get(provider)
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

        # Do not use a heuristic "confidence" as a probability. A configured
        # upstream policy may only match a sufficiently specific response-header
        # marker; body text is never evidence for this decision.
        policy_match = max_signal_weight >= strong_signal_weight
        if policy_match:
            detected.append(
                {
                    "provider": provider,
                    "confidence": None,
                    "max_signal_weight": max_signal_weight,
                    "rule_weight": max_signal_weight,
                    "rule_weight_is_probability": False,
                    "decision_basis": "configured_response_header_rule",
                    "not_model_identity_proof": True,
                    "evidence": provider_evidence,
                }
            )

    rate_limit_ids = [
        evidence.id
        for evidence in evidence_list
        if evidence.response_status == 429
    ]
    suspected = bool(detected)
    return ProbeResult(
        probe_id=probe_id,
        category="provider",
        status=ProbeStatus.WARN if suspected else ProbeStatus.INSUFFICIENT,
        score=None,
        confidence=None,
        summary=(
            "configured response-header marker suggests a disallowed upstream: "
            + ", ".join(item["provider"] for item in detected)
            + "; headers can be forwarded or spoofed; review with independent evidence"
            if suspected
            else "no qualifying disallowed-provider response-header signal was observed; absence is not proof of absence"
        ),
        expected={
            "disallowed": sorted(disallowed_set),
            "legacy_min_confidence_ignored": min_confidence,
            "strong_signal_weight": strong_signal_weight,
            "body_text_is_never_identity_evidence": True,
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
            "policy_violation": False,
            "policy_suspected": suspected,
            "evidence_strength": "weak",
            "header_evidence_only": True,
            "policy_type": "disallowed_upstream",
            "rate_limit_is_auxiliary_only": True,
        },
    )

def detect_provider_hypotheses(
    evidences: Iterable[Evidence],
) -> list[ProviderHypothesis]:
    rules = load_provider_rules()
    reasons: dict[str, list[str]] = defaultdict(list)

    for evidence in evidences:
        for provider, rule in rules.items():
            for signal in _provider_signal_details(evidence, rule):
                reasons[provider].append(
                    f"{evidence.probe_id}: response header {signal['value']}"
                )

    # These are uncalibrated metadata hints, not probabilistic identity
    # estimates. Repeated occurrences do not increase confidence.
    out = [
        ProviderHypothesis(
            provider=provider,
            confidence=None,
            evidence=list(dict.fromkeys(provider_reasons)),
        )
        for provider, provider_reasons in reasons.items()
        if provider_reasons
    ]
    return sorted(out, key=lambda x: x.provider)

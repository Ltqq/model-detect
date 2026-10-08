from __future__ import annotations

import fnmatch
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


SourceType = Literal[
    "official_doc",
    "trusted_reference",
    "empirical",
    "provider_doc",
    "community",
]

SourceConfidence = Literal["high", "medium", "low"]


class RuleSource(BaseModel):
    id: str
    type: SourceType
    title: str | None = None
    url: str | None = None
    collected_at: str | None = None
    confidence: SourceConfidence = "medium"


class RequestConstraint(BaseModel):
    fixed: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)


class ModelRule(BaseModel):
    schema_version: Literal[1, 2, 3] = 1
    id: str
    family: str | None = None
    model_version: str | None = None
    patterns: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    sources: list[RuleSource] = Field(default_factory=list)
    strict: bool = False
    declared_context_tokens: int | None = None
    request_constraints: dict[str, RequestConstraint] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    protocol_features: dict[str, dict[str, Any]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_provenance(self):
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("model rule source ids must be unique")

        known_sources = set(source_ids)
        for endpoint, constraint in self.request_constraints.items():
            missing = sorted(set(constraint.source_refs) - known_sources)
            if missing:
                raise ValueError(
                    f"request constraint {endpoint!r} references unknown sources: {missing}"
                )

        feature_sets = [("features", self.features)]
        feature_sets.extend(
            (f"protocol_features.{protocol}", specs)
            for protocol, specs in self.protocol_features.items()
        )
        for namespace, specs in feature_sets:
            if not isinstance(specs, dict):
                raise ValueError(f"{namespace} must be an object")
            for feature, spec in specs.items():
                if not isinstance(spec, dict):
                    continue
                refs = spec.get("source_refs")
                if refs is None:
                    continue
                if not isinstance(refs, list) or not all(
                    isinstance(ref, str) and ref.strip() for ref in refs
                ):
                    raise ValueError(
                        f"{namespace}.{feature} source_refs must be a list of source ids"
                    )
                missing = sorted(set(refs) - known_sources)
                if missing:
                    raise ValueError(
                        f"{namespace}.{feature} references unknown sources: {missing}"
                    )

        if self.strict and self.schema_version >= 2:
            referenced = set()
            for specs in [self.features, *self.protocol_features.values()]:
                for spec in specs.values():
                    if isinstance(spec, dict):
                        refs = spec.get("source_refs")
                        if isinstance(refs, list):
                            referenced.update(str(ref) for ref in refs)
            referenced_sources = [
                source
                for source in self.sources
                if source.id in referenced
            ]
            if referenced_sources and all(
                source.type == "community"
                and source.confidence == "low"
                for source in referenced_sources
            ):
                raise ValueError(
                    "strict v2 model rule cannot rely only on low-confidence "
                    "community sources"
                )

        return self


def normalize_model_rule(raw: dict[str, Any]) -> ModelRule:
    if not isinstance(raw, dict):
        raise ValueError("model rule YAML root must be an object")

    normalized = dict(raw)
    normalized.setdefault("schema_version", 1)
    return ModelRule.model_validate(normalized)


@lru_cache(maxsize=1)
def load_model_rules() -> list[ModelRule]:
    root = files("model_detect").joinpath("data/models")
    rules: list[ModelRule] = []
    for item in sorted(root.iterdir(), key=lambda x: x.name):
        if item.name.endswith((".yaml", ".yml")):
            raw = yaml.safe_load(item.read_text(encoding="utf-8")) or {}
            rules.append(normalize_model_rule(raw))
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
        for alias in rule.aliases:
            if lowered == alias.casefold():
                return rule
    return fallback or ModelRule(id="default", patterns=["*"])


def feature_spec_for(
    model: str,
    feature: str,
    *,
    protocol: str = "chat_completions",
) -> dict[str, Any]:
    rule = match_model_rule(model)
    base = rule.features.get(feature)
    merged = dict(base) if isinstance(base, dict) else {}
    override = (rule.protocol_features.get(protocol) or {}).get(feature)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def effective_features_for(
    model: str,
    *,
    protocol: str = "chat_completions",
) -> dict[str, dict[str, Any]]:
    rule = match_model_rule(model)
    names = set(rule.features)
    names.update((rule.protocol_features.get(protocol) or {}).keys())
    return {
        name: feature_spec_for(model, name, protocol=protocol)
        for name in sorted(names)
    }


def evaluate_rule_expectations(
    model: str,
    observations: dict[str, Any],
    *,
    protocol: str = "chat_completions",
) -> list[dict[str, Any]]:
    rule = match_model_rule(model)
    out: list[dict[str, Any]] = []
    for feature, spec in effective_features_for(
        model, protocol=protocol
    ).items():
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
                "rule_schema_version": rule.schema_version,
                "source_refs": list(spec.get("source_refs") or []),
                "strict": rule.strict,
                "protocol": protocol,
            }
        )
    return out



def request_constraint_for(
    model: str,
    endpoint: str = "chat_completions",
) -> RequestConstraint:
    rule = match_model_rule(model)
    return rule.request_constraints.get(endpoint, RequestConstraint())


def fixed_request_parameter(
    model: str,
    parameter: str,
    *,
    endpoint: str = "chat_completions",
) -> Any:
    return request_constraint_for(model, endpoint).fixed.get(parameter)


def apply_request_constraints(
    model: str,
    payload: dict[str, Any],
    *,
    endpoint: str = "chat_completions",
    exempt_fields: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Apply model-declared fixed constraints to an operational probe payload.

    Fixed constraints are probe execution requirements, not identity evidence. A probe
    that intentionally varies or corrupts a parameter must exempt that field.
    """
    out = dict(payload)
    exempt = set(exempt_fields or ())
    constraint = request_constraint_for(model, endpoint)
    for field, value in constraint.fixed.items():
        if field not in exempt:
            out[field] = value
    return out


def preferred_feature_value(
    model: str,
    feature: str,
    *,
    preferred: Any = None,
    protocol: str = "chat_completions",
) -> Any:
    """Choose a documented valid feature value without hard-coding a model family."""
    spec = feature_spec_for(model, feature, protocol=protocol)
    if not spec:
        return preferred
    values = list(spec.get("values") or [])
    if preferred in values:
        return preferred
    default = spec.get("default")
    if default in values:
        return default
    if values:
        return values[0]
    return preferred

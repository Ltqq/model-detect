from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from .models import AuditTarget
from .usage_pricing import TokenPrices


class RegressionAuditConfig(BaseModel):
    enabled: bool = True
    suites: list[str] = Field(default_factory=list)
    profiles: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("profiles")
    @classmethod
    def validate_profiles(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        allowed = {"quick", "standard", "deep"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                f"unsupported regression profile keys: {unknown}; "
                "use quick, standard or deep"
            )
        return value

    def suites_for(self, profile: str) -> list[str]:
        if not self.enabled:
            return []
        selected = [
            *self.suites,
            *(self.profiles.get(profile.lower()) or []),
        ]
        return list(dict.fromkeys(selected))


class UpstreamPolicyConfig(BaseModel):
    disallowed: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    strong_signal_weight: float = Field(default=0.90, ge=0.0, le=1.0)

    @field_validator("disallowed")
    @classmethod
    def normalize_disallowed(cls, value: list[str]) -> list[str]:
        normalized = [
            item.strip().casefold()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
        return list(dict.fromkeys(normalized))


class AuditConfig(BaseModel):
    target: AuditTarget
    profile: str = "quick"
    output_dir: str = "model-detect-output"
    fingerprint_reference: str | None = None
    reference_id: str | None = None
    reference_dir: str = "references"
    declared_context_tokens: int | None = None
    capability_enabled: bool = True
    # An opt-in, bounded academic benchmark; never part of the default audit.
    benchmark_profile: Literal["smoke", "standard", "deep"] | None = None
    benchmark_evidence_dir: str | None = None
    benchmark_revisions_file: str | None = None
    proxy_sleuth_enabled: bool = False
    coding_sandbox_enabled: bool = False
    coding_sandbox_auto_pull: bool = True
    regression: RegressionAuditConfig = Field(
        default_factory=RegressionAuditConfig
    )
    upstream_policy: UpstreamPolicyConfig = Field(
        default_factory=UpstreamPolicyConfig
    )
    extra_headers: dict[str, str] = Field(default_factory=dict)
    token_prices: TokenPrices | None = None
    native_soft_token_limit: int | None = Field(default=None, ge=1)


def _resolve_relative_path(base: Path, value: str) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((base / path).resolve())


def load_config(path: str | Path) -> AuditConfig:
    source = Path(path)
    raw: dict[str, Any] = (
        yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    )
    cfg = AuditConfig.model_validate(raw)

    base = source.resolve().parent
    if cfg.benchmark_evidence_dir:
        cfg.benchmark_evidence_dir = _resolve_relative_path(base, cfg.benchmark_evidence_dir)
    if cfg.benchmark_revisions_file:
        cfg.benchmark_revisions_file = _resolve_relative_path(base, cfg.benchmark_revisions_file)
    cfg.regression.suites = [
        _resolve_relative_path(base, value)
        for value in cfg.regression.suites
    ]
    cfg.regression.profiles = {
        profile: [
            _resolve_relative_path(base, value)
            for value in values
        ]
        for profile, values in cfg.regression.profiles.items()
    }
    return cfg


def get_api_key(target: AuditTarget, override: str | None = None) -> str:
    if override:
        return override
    value = os.getenv(target.api_key_env)
    if not value:
        raise RuntimeError(
            f"API key environment variable {target.api_key_env!r} is not set"
        )
    return value

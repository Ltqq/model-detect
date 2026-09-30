from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .models import AuditTarget


class AuditConfig(BaseModel):
    target: AuditTarget
    profile: str = "quick"
    output_dir: str = "model-detect-output"
    fingerprint_reference: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)


def load_config(path: str | Path) -> AuditConfig:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return AuditConfig.model_validate(raw)


def get_api_key(target: AuditTarget) -> str:
    value = os.getenv(target.api_key_env)
    if not value:
        raise RuntimeError(
            f"API key environment variable {target.api_key_env!r} is not set"
        )
    return value

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


_ALLOWED_ASSERTIONS = {
    "equals",
    "contains",
    "icontains",
    "regex",
    "is-json",
    "contains-json",
    "is-valid-openai-tools-call",
}

_CUSTOM_ASSERTIONS = {"javascript", "python"}

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "password",
}


def _reject_secrets(value: Any, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SENSITIVE_KEYS:
                raise ValueError(
                    f"regression YAML must not contain secrets: {path}.{key}"
                )
            _reject_secrets(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, path=f"{path}[{index}]")


class RegressionAssertion(BaseModel):
    type: str
    value: Any = None
    schema: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("assertion type is required")
        return normalized

    @model_validator(mode="after")
    def validate_schema_shape(self):
        if self.schema is not None and self.type not in {
            "is-json",
            "contains-json",
        }:
            raise ValueError(
                "schema is only valid for is-json or contains-json assertions"
            )
        return self


class RegressionExpectation(BaseModel):
    http_status: int | None = Field(default=None, ge=100, le=599)


class RegressionCase(BaseModel):
    id: str
    category: Literal["protocol", "integrity", "capability"] = "protocol"
    prompt: str
    request: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None
    assertions: list[RegressionAssertion] = Field(default_factory=list)
    expect: RegressionExpectation | None = None
    repeat: int = Field(default=1, ge=1, le=20)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
            raise ValueError(
                "case id must contain only letters, digits, dot, underscore or hyphen"
            )
        return normalized

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("prompt is required")
        return normalized

    @model_validator(mode="after")
    def validate_expectation(self):
        if not self.assertions and self.expect is None:
            raise ValueError(
                "regression case requires assertions or an expect block"
            )
        return self


class RegressionSuite(BaseModel):
    version: Literal[1] = 1
    suite: str
    model_patterns: list[str] = Field(default_factory=list)
    cases: list[RegressionCase]

    @field_validator("suite")
    @classmethod
    def validate_suite(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
            raise ValueError(
                "suite must contain only letters, digits, dot, underscore or hyphen"
            )
        return normalized

    @field_validator("model_patterns")
    @classmethod
    def validate_patterns(cls, values: list[str]) -> list[str]:
        clean = [value.strip() for value in values if value.strip()]
        if not clean:
            raise ValueError("model_patterns must contain at least one pattern")
        return clean

    @field_validator("cases")
    @classmethod
    def validate_cases(cls, values: list[RegressionCase]) -> list[RegressionCase]:
        if not values:
            raise ValueError("regression suite must contain at least one case")
        ids = [case.id for case in values]
        if len(ids) != len(set(ids)):
            raise ValueError("regression case ids must be unique")
        return values


def load_regression_suite(
    path: str | Path,
    *,
    allow_custom_assertions: bool = False,
) -> RegressionSuite:
    source = Path(path)
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("regression YAML root must be an object")

    _reject_secrets(raw)
    suite = RegressionSuite.model_validate(raw)

    for case in suite.cases:
        for assertion in case.assertions:
            if assertion.type in _CUSTOM_ASSERTIONS and not allow_custom_assertions:
                raise ValueError(
                    f"custom assertion {assertion.type!r} is disabled by default"
                )
            if (
                assertion.type not in _ALLOWED_ASSERTIONS
                and assertion.type not in _CUSTOM_ASSERTIONS
            ):
                raise ValueError(
                    f"unsupported regression assertion type: {assertion.type}"
                )

    return suite

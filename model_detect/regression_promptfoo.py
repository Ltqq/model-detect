from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .adapters import promptfoo
from .regression import RegressionAssertion, RegressionCase, RegressionSuite


_RESERVED_REQUEST_FIELDS = {
    "model",
    "messages",
    "tools",
    "tool_choice",
}


def _provider_label(suite: RegressionSuite, case: RegressionCase) -> str:
    return f"md:{suite.suite}:{case.id}"


def _assertion_to_promptfoo(assertion: RegressionAssertion) -> dict[str, Any]:
    item: dict[str, Any] = {"type": assertion.type}
    if assertion.schema is not None:
        item["value"] = assertion.schema
    elif assertion.value is not None:
        item["value"] = assertion.value
    return item


def _status_transform() -> str:
    return (
        "({ output: String(context?.response?.status ?? ''), "
        "metadata: { http_status: context?.response?.status, raw: json } })"
    )


def _tool_transform() -> str:
    return (
        "({ output: json.choices?.[0]?.message?.tool_calls ?? [], "
        "metadata: { model: json.model, "
        "finish_reason: json.choices?.[0]?.finish_reason, "
        "tool_calls: json.choices?.[0]?.message?.tool_calls } })"
    )


def _compile_case_provider(
    suite: RegressionSuite,
    case: RegressionCase,
    *,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    reserved = sorted(_RESERVED_REQUEST_FIELDS.intersection(case.request))
    if reserved:
        raise ValueError(
            f"regression case {case.id!r} cannot override reserved request "
            f"fields: {reserved}"
        )

    provider = copy.deepcopy(
        promptfoo.build_http_provider(
            base_url=base_url,
            model=model,
        )
    )
    provider["label"] = _provider_label(suite, case)
    config = provider["config"]
    body = config["body"]
    body.update(copy.deepcopy(case.request))

    if case.tools:
        config["transformToolsFormat"] = "openai"
        config["tools"] = copy.deepcopy(case.tools)
        body["tools"] = "{{tools}}"

    if case.tool_choice is not None:
        if not case.tools:
            raise ValueError(
                f"regression case {case.id!r} sets tool_choice without tools"
            )
        config["tool_choice"] = copy.deepcopy(case.tool_choice)
        body["tool_choice"] = "{{tool_choice}}"

    if case.expect and case.expect.http_status is not None:
        if case.assertions:
            raise ValueError(
                f"regression case {case.id!r} cannot combine http_status "
                "expectation with output assertions in schema v1"
            )
        config["transformResponse"] = _status_transform()
    elif any(
        assertion.type == "is-valid-openai-tools-call"
        for assertion in case.assertions
    ):
        config["transformResponse"] = _tool_transform()

    return provider


def _compile_case_test(
    suite: RegressionSuite,
    case: RegressionCase,
) -> dict[str, Any]:
    assertions = [
        _assertion_to_promptfoo(assertion)
        for assertion in case.assertions
    ]
    if case.expect and case.expect.http_status is not None:
        assertions.append(
            {
                "type": "equals",
                "value": str(case.expect.http_status),
            }
        )

    test: dict[str, Any] = {
        "description": case.id,
        "vars": {
            "md_prompt": case.prompt,
        },
        "providers": [
            _provider_label(suite, case),
        ],
        "assert": assertions,
        "metadata": {
            "model_detect_suite": suite.suite,
            "model_detect_case_id": case.id,
            "model_detect_category": case.category,
        },
    }
    if case.repeat > 1:
        test["options"] = {"repeat": case.repeat}
    return test


def compile_regression_suite(
    suite: RegressionSuite,
    *,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    providers = [
        _compile_case_provider(
            suite,
            case,
            base_url=base_url,
            model=model,
        )
        for case in suite.cases
    ]
    tests = [
        _compile_case_test(suite, case)
        for case in suite.cases
    ]
    return {
        "description": f"model-detect regression: {suite.suite}",
        "prompts": ["{{md_prompt}}"],
        "providers": providers,
        "tests": tests,
    }


def write_compiled_regression_config(
    path: str | Path,
    suite: RegressionSuite,
    *,
    base_url: str,
    model: str,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = compile_regression_suite(
        suite,
        base_url=base_url,
        model=model,
    )
    target.write_text(
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return target

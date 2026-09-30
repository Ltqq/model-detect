import yaml
import pytest

from model_detect.regression import RegressionSuite
from model_detect.regression_promptfoo import (
    compile_regression_suite,
    write_compiled_regression_config,
)


def _suite():
    return RegressionSuite.model_validate(
        {
            "version": 1,
            "suite": "supplier-regression",
            "model_patterns": ["kimi-k3"],
            "cases": [
                {
                    "id": "reasoning-invalid-field",
                    "category": "protocol",
                    "prompt": "Reply OK",
                    "request": {
                        "reasoning_effor": "medium",
                    },
                    "expect": {
                        "http_status": 400,
                    },
                    "repeat": 3,
                },
                {
                    "id": "json-output",
                    "category": "integrity",
                    "prompt": "Return JSON",
                    "request": {
                        "response_format": {
                            "type": "json_object",
                        }
                    },
                    "assertions": [
                        {
                            "type": "is-json",
                            "schema": {
                                "type": "object",
                                "required": ["ok"],
                            },
                        }
                    ],
                },
                {
                    "id": "tool-call",
                    "category": "protocol",
                    "prompt": "Use get_weather",
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "city": {"type": "string"}
                                    },
                                    "required": ["city"],
                                },
                            },
                        }
                    ],
                    "tool_choice": "required",
                    "assertions": [
                        {
                            "type": "is-valid-openai-tools-call",
                        }
                    ],
                },
            ],
        }
    )


def test_compile_creates_one_provider_per_case_without_cross_product():
    payload = compile_regression_suite(
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )

    assert payload["prompts"] == ["{{md_prompt}}"]
    assert len(payload["providers"]) == 3
    assert len(payload["tests"]) == 3

    labels = [provider["label"] for provider in payload["providers"]]
    assert labels == [
        "md:supplier-regression:reasoning-invalid-field",
        "md:supplier-regression:json-output",
        "md:supplier-regression:tool-call",
    ]
    assert [
        test["providers"][0]
        for test in payload["tests"]
    ] == labels


def test_compile_merges_case_request_and_maps_http_status():
    payload = compile_regression_suite(
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )
    provider = payload["providers"][0]
    test = payload["tests"][0]

    assert provider["config"]["body"]["model"] == "kimi-k3"
    assert (
        provider["config"]["body"]["reasoning_effor"]
        == "medium"
    )
    assert "context?.response?.status" in provider["config"]["transformResponse"]
    assert test["assert"] == [{"type": "equals", "value": "400"}]
    assert test["options"]["repeat"] == 3


def test_compile_maps_json_schema_assertion():
    payload = compile_regression_suite(
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )
    test = payload["tests"][1]

    assert test["assert"] == [
        {
            "type": "is-json",
            "value": {
                "type": "object",
                "required": ["ok"],
            },
        }
    ]


def test_compile_maps_tool_configuration():
    payload = compile_regression_suite(
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )
    provider = payload["providers"][2]

    assert provider["config"]["transformToolsFormat"] == "openai"
    assert provider["config"]["body"]["tools"] == "{{tools}}"
    assert provider["config"]["body"]["tool_choice"] == "{{tool_choice}}"
    assert provider["config"]["tool_choice"] == "required"
    assert provider["config"]["tools"][0]["function"]["name"] == "get_weather"
    assert "tool_calls" in provider["config"]["transformResponse"]


def test_compile_preserves_case_metadata_for_result_mapping():
    payload = compile_regression_suite(
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )
    metadata = payload["tests"][1]["metadata"]

    assert metadata == {
        "model_detect_suite": "supplier-regression",
        "model_detect_case_id": "json-output",
        "model_detect_category": "integrity",
    }


def test_reserved_request_fields_cannot_override_target():
    suite = RegressionSuite.model_validate(
        {
            "version": 1,
            "suite": "bad",
            "model_patterns": ["*"],
            "cases": [
                {
                    "id": "bad-model",
                    "prompt": "x",
                    "request": {"model": "different-model"},
                    "assertions": [
                        {"type": "equals", "value": "x"},
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="reserved request fields"):
        compile_regression_suite(
            suite,
            base_url="https://relay.example/v1",
            model="claimed-model",
        )


def test_http_status_and_output_assertions_cannot_mix_in_v1():
    suite = RegressionSuite.model_validate(
        {
            "version": 1,
            "suite": "bad",
            "model_patterns": ["*"],
            "cases": [
                {
                    "id": "mixed",
                    "prompt": "x",
                    "expect": {"http_status": 400},
                    "assertions": [
                        {"type": "equals", "value": "x"},
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="cannot combine http_status"):
        compile_regression_suite(
            suite,
            base_url="https://relay.example/v1",
            model="m",
        )


def test_write_compiled_config_contains_no_secret(tmp_path):
    path = write_compiled_regression_config(
        tmp_path / "promptfooconfig.yaml",
        _suite(),
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )

    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)

    assert "MODEL_DETECT_PROMPTFOO_KEY" in raw
    assert "sk-" not in raw
    assert len(parsed["providers"]) == 3

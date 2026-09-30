import json

import pytest

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.integrity import (
    probe_json_schema_preserved,
    probe_system_prompt,
    probe_temperature,
    probe_tool_definitions,
    probe_tools_preserved,
)


class FakeClient:
    def __init__(self, calls):
        self.calls = list(calls)
        self.payloads = []

    async def post_json(self, **kwargs):
        self.payloads.append(kwargs["payload"])
        if not self.calls:
            raise AssertionError("unexpected extra request")
        return self.calls.pop(0)


def response(body, *, status=200, ev_id="ev_test"):
    return CallResult(
        evidence=Evidence(
            id=ev_id,
            probe_id="test",
            url="https://example.com/v1/chat/completions",
            response_status=status,
            response_headers={"content-type": "application/json"},
            response_body=body,
        ),
        json_body=body,
        text_body=json.dumps(body),
    )


def text_body(text):
    return {
        "choices": [
            {
                "message": {"content": text},
                "finish_reason": "stop",
            }
        ]
    }


def tool_body(name, args):
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }


@pytest.mark.asyncio
async def test_system_prompt_probe_passes_three_canaries():
    calls = [
        response(text_body(f"MD_SYSTEM_{i}_7A3"), ev_id=f"ev_{i}")
        for i in range(3)
    ]
    results, evidence = await probe_system_prompt(FakeClient(calls), "m")
    assert results[0].status == ProbeStatus.PASS
    assert results[0].score == 1.0
    assert len(evidence) == 3
    assert results[0].metadata["server_prompt_injection_proof"] is False


@pytest.mark.asyncio
async def test_system_prompt_failure_is_warning_not_proof():
    calls = [
        response(text_body("wrong"), ev_id=f"ev_{i}")
        for i in range(3)
    ]
    results, _ = await probe_system_prompt(FakeClient(calls), "m")
    assert results[0].status == ProbeStatus.WARN
    assert results[0].metadata["server_prompt_injection_proof"] is False


@pytest.mark.asyncio
async def test_nested_tool_definition_is_checked():
    body = tool_body(
        "record_route",
        {
            "route": {"region": "east", "priority": 7},
            "ticket": "MD-TICKET-71",
        },
    )
    results, _ = await probe_tool_definitions(
        FakeClient([response(body)]),
        "m",
    )
    assert results[0].status == ProbeStatus.PASS


@pytest.mark.asyncio
async def test_dynamic_tool_schema_changes_are_preserved():
    calls = [
        response(tool_body("select_mode", {"mode": "ALPHA_ONLY"}), ev_id="ev_a"),
        response(tool_body("select_mode", {"mode": "BETA_ONLY"}), ev_id="ev_b"),
    ]
    results, _ = await probe_tools_preserved(FakeClient(calls), "m")
    assert results[0].status == ProbeStatus.PASS
    assert results[0].observed["cases"][1]["observed"] == "BETA_ONLY"


@pytest.mark.asyncio
async def test_json_schema_preservation_overrides_conflicting_prompt():
    body = text_body('{"token":"SCHEMA_OK_73","count":7}')
    results, _ = await probe_json_schema_preserved(
        FakeClient([response(body)]),
        "m",
    )
    assert results[0].status == ProbeStatus.PASS


@pytest.mark.asyncio
async def test_temperature_no_observable_effect_is_insufficient():
    calls = [
        response(text_body("apple"), ev_id=f"ev_{i}")
        for i in range(8)
    ]
    results, _ = await probe_temperature(
        FakeClient(calls),
        "m",
        samples=4,
    )
    assert results[0].status == ProbeStatus.INSUFFICIENT
    assert results[0].score is None


@pytest.mark.asyncio
async def test_temperature_observable_diversity_passes():
    low = ["apple"] * 4
    high = ["apple", "banana", "cherry", "date"]
    calls = [
        response(text_body(value), ev_id=f"ev_{i}")
        for i, value in enumerate(low + high)
    ]
    results, _ = await probe_temperature(
        FakeClient(calls),
        "m",
        samples=4,
    )
    assert results[0].status == ProbeStatus.PASS
    assert results[0].observed["wide_unique"] == 4

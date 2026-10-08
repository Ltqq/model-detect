import asyncio
import json

from model_detect.audit import _invalid_target_reason
from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.integrity import probe_temperature
from model_detect.probes.protocol import (
    probe_bad_enum,
    probe_invalid_model,
    probe_reasoning_valid,
)
from model_detect.rules import (
    apply_request_constraints,
    fixed_request_parameter,
    preferred_feature_value,
)


class FakeClient:
    def __init__(self, calls):
        self.calls = list(calls)
        self.kwargs = []

    async def post_json(self, **kwargs):
        self.kwargs.append(kwargs)
        if not self.calls:
            raise AssertionError("unexpected request")
        return self.calls.pop(0)


def response(body, *, status=200, content_type="application/json"):
    return CallResult(
        evidence=Evidence(
            id="ev_test",
            probe_id="test",
            url="https://example.com/v1/chat/completions",
            response_status=status,
            response_headers={"content-type": content_type},
            response_body=body,
        ),
        json_body=body if isinstance(body, dict) else None,
        text_body=json.dumps(body) if isinstance(body, dict) else str(body),
    )


def test_model_request_constraint_overrides_generic_probe_baseline():
    payload = apply_request_constraints(
        "kimi-k3",
        {"model": "kimi-k3", "temperature": 0, "max_tokens": 16},
    )
    assert payload["temperature"] == 1.0
    assert payload["max_tokens"] == 16
    assert fixed_request_parameter("kimi-k3", "temperature") == 1.0


def test_unknown_model_keeps_existing_probe_payload():
    payload = apply_request_constraints(
        "unknown-model",
        {"model": "unknown-model", "temperature": 0},
    )
    assert payload["temperature"] == 0


def test_negative_probe_can_exempt_constrained_parameter():
    payload = apply_request_constraints(
        "kimi-k3",
        {"model": "kimi-k3", "temperature": "bad"},
        exempt_fields={"temperature"},
    )
    assert payload["temperature"] == "bad"


def test_reasoning_probe_value_comes_from_model_rule():
    assert preferred_feature_value(
        "glm-5.2", "reasoning_effort", preferred="low"
    ) == "max"


def test_fixed_temperature_variability_probe_is_skipped():
    client = FakeClient([])
    results, evidence = asyncio.run(
        probe_temperature(client, "kimi-k3", samples=2)
    )
    assert results[0].status == ProbeStatus.SKIPPED
    assert results[0].metadata["parameter_fixed_by_model_rule"] is True
    assert evidence == []
    assert client.kwargs == []


def test_invalid_model_rejection_separates_behavior_from_http_style():
    body = {
        "error": {
            "code": "model_not_found",
            "message": "No available channel for model",
        }
    }
    client = FakeClient([response(body, status=503)])
    results, _ = asyncio.run(probe_invalid_model(client, "kimi-k3"))
    assert results[0].status == ProbeStatus.PASS
    assert results[0].metadata["invalid_model_rejected"] is True
    assert results[1].status == ProbeStatus.WARN
    assert results[1].metadata["transport_status_standard"] is False


def test_invalid_temperature_probe_exempts_temperature_constraint():
    client = FakeClient([response({"error": {"message": "bad"}}, status=400)])
    results, _ = asyncio.run(probe_bad_enum(client, "kimi-k3"))
    assert results[0].status == ProbeStatus.PASS
    assert client.kwargs[0]["constraint_exempt_fields"] == {"temperature"}


def test_reasoning_valid_probe_uses_documented_value():
    body = {
        "choices": [
            {"message": {"content": "391"}, "finish_reason": "stop"}
        ]
    }
    client = FakeClient([response(body)])
    results, _ = asyncio.run(probe_reasoning_valid(client, "glm-5.2"))
    assert results[0].status == ProbeStatus.PASS
    assert client.kwargs[0]["payload"]["reasoning_effort"] == "max"


def test_html_response_is_invalid_target():
    evidence = Evidence(
        id="ev_html",
        probe_id="protocol.chat.basic",
        url="https://example.com/chat/completions",
        response_status=200,
        response_headers={"content-type": "text/html; charset=utf-8"},
        response_body="<!DOCTYPE html><html><body>frontend</body></html>",
    )
    reason = _invalid_target_reason([evidence])
    assert reason is not None
    assert "HTML" in reason


def test_json_api_response_is_not_invalid_target():
    evidence = Evidence(
        id="ev_json",
        probe_id="protocol.chat.basic",
        url="https://example.com/v1/chat/completions",
        response_status=200,
        response_headers={"content-type": "application/json"},
        response_body={"choices": []},
    )
    assert _invalid_target_reason([evidence]) is None

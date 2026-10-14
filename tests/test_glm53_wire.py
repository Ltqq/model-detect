import copy
import json

import pytest

from model_detect.glm53_wire import verify_wire_requests


def body():
    return {
        "model": "glm-5.3", "messages": [{"role": "user", "content": "sensitive prompt"}],
        "reasoning_effort": "max", "max_tokens": 1280,
        "temperature": 0, "stop": [],
        "authorization": "sk-should-not-appear",
    }


def test_exact_pair_matches_without_exposing_messages_or_secrets():
    request = body()
    report = verify_wire_requests([request], [copy.deepcopy(request)])
    assert report["status"] == "request_payload_matched"
    assert "sensitive prompt" not in json.dumps(report)
    assert "sk-should-not-appear" not in json.dumps(report)


@pytest.mark.parametrize("change", [
    {"reasoning_effort": "low"},
    {"model": "not-glm"},
    {"max_tokens": None},
    {"temperature": 1},
    {"stop": ["END"]},
    {"messages": [{"role": "user", "content": "different"}]},
])
def test_mismatches_fail_closed(change):
    customer = body()
    customer.update(change)
    assert verify_wire_requests([body()], [customer])["status"] == "incomparable"


def test_missing_optional_fields_do_not_silently_get_defaults():
    first = body()
    first.pop("temperature")
    first.pop("stop")
    result = verify_wire_requests([first], [copy.deepcopy(first)])
    assert result["status"] == "incomparable"
    assert any(x["reason"] == "temperature_unobserved"
               for x in result["issues"]["official"])


def test_reordered_calls_are_comparable_but_dropped_calls_are_not():
    a = body()
    b = body()
    b["messages"] = [{"role": "user", "content": "another question"}]
    assert verify_wire_requests([a, b], [b, a])["status"] == "request_payload_matched"
    assert verify_wire_requests([a, b], [b])["status"] == "incomparable"


def test_empty_and_invalid_evidence_never_pass():
    assert verify_wire_requests([], [])["status"] == "incomparable"
    assert verify_wire_requests([{"model": "glm-5.3"}], [None])["status"] == "incomparable"
    with pytest.raises(ValueError):
        verify_wire_requests([body()], [body()], expected_effort="medium")

"""B1 wiring regression: transport usage and missing SSE counts."""
from types import SimpleNamespace

from model_detect.http_client import CallResult
from model_detect.models import Evidence


def _call(body, status=200):
    return CallResult(
        evidence=Evidence(id="ev_test", probe_id="test.case", url="https://example.test/v1",
                          response_status=status),
        json_body=body,
    )


def test_http_transport_usage_exposes_observed_tokens():
    record = _call({"usage": {
        "prompt_tokens": 10, "completion_tokens": 30,
        "completion_tokens_details": {"reasoning_tokens": 20},
    }}).usage_record(stage="protocol")
    assert record.source == "observed"
    assert record.prompt_tokens == 10
    assert record.reasoning_tokens == 20


def test_http_transport_partial_sse_is_unknown_even_with_usage():
    record = _call({"_sse_completed": False, "_sse_truncated": True,
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20}}).usage_record(
        stage="protocol"
    )
    assert record.source == "unknown"
    assert record.missing_reason == "incomplete_stream"


def test_http_transport_429_without_usage_is_unknown():
    record = _call({"error": {"code": "rate_limited"}}, 429).usage_record()
    assert record.source == "unknown"
    assert record.http_status == 429

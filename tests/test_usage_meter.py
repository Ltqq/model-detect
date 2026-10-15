import pytest
from pydantic import ValidationError

from model_detect.usage_meter import UsageRecord, usage_from_response, summarize_usage


def test_observed_usage_subsets_do_not_double_count():
    record = usage_from_response(
        probe_id="p1", stage="protocol", http_status=200,
        response={"usage": {
            "prompt_tokens": 200, "completion_tokens": 100,
            "prompt_tokens_details": {
                "cached_tokens": 150, "cache_creation_input_tokens": 20
            },
            "completion_tokens_details": {"reasoning_tokens": 80},
        }},
    )
    assert record.source == "observed"
    summary = summarize_usage([record])
    assert summary["prompt_tokens_observed"] + summary["completion_tokens_observed"] == 300
    assert summary["reasoning_tokens_subset"] == 80
    assert summary["cached_read_tokens_subset"] == 150
    assert summary["cached_write_tokens_subset"] == 20
    assert summary["precise_total_available"] is True


@pytest.mark.parametrize("response", [
    None, {}, {"usage": None},
    {"usage": {"prompt_tokens": 1}},
    {"usage": {"prompt_tokens": False, "completion_tokens": 4}},
])
def test_missing_usage_is_unknown_not_zero(response):
    record = usage_from_response(probe_id="p", stage="capability", response=response)
    assert record.source == "unknown"
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert summarize_usage([record])["precise_total_available"] is False


def test_incomplete_sse_never_claims_observed_total():
    record = usage_from_response(
        probe_id="p", stage="stream", stream_complete=False,
        response={"usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    )
    assert record.missing_reason == "incomplete_stream"
    assert record.source == "unknown"


def test_partial_usage_coverage_is_explicit():
    records = [
        usage_from_response(
            probe_id=str(i), stage="protocol",
            response={"usage": {"prompt_tokens": 10, "completion_tokens": 20}}
            if i < 136 else {},
        )
        for i in range(140)
    ]
    result = summarize_usage(records)
    assert result["observed_requests"] == 136
    assert result["unknown_requests"] == 4
    assert result["coverage"] == pytest.approx(136 / 140)
    assert result["precise_total_available"] is False


def test_invalid_subsets_fail_closed():
    with pytest.raises(ValidationError):
        UsageRecord(probe_id="p", stage="x", source="observed",
                    prompt_tokens=10, completion_tokens=2, reasoning_tokens=3)
    with pytest.raises(ValidationError):
        UsageRecord(probe_id="p", stage="x", source="unknown",
                    missing_reason="missing", prompt_tokens=0)

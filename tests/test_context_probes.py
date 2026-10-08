import asyncio
import json

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.context import _needle_probe


class FakeClient:
    def __init__(self, calls):
        self.calls = list(calls)
        self.payloads = []

    async def post_json(self, **kwargs):
        self.payloads.append(kwargs["payload"])
        if not self.calls:
            raise AssertionError("unexpected extra request")
        return self.calls.pop(0)


def response(
    content,
    *,
    finish_reason="stop",
    reasoning_content="",
    status=200,
    ev_id="ev_context",
):
    body = {
        "choices": [
            {
                "message": {
                    "content": content,
                    "reasoning_content": reasoning_content,
                },
                "finish_reason": finish_reason,
            }
        ]
    }
    return CallResult(
        evidence=Evidence(
            id=ev_id,
            probe_id="context.needle.8k",
            url="https://example.com/v1/chat/completions",
            response_status=status,
            response_headers={"content-type": "application/json"},
            response_body=body,
        ),
        json_body=body,
        text_body=json.dumps(body),
    )


def test_context_probe_retries_when_final_output_is_length_truncated():
    needle = "MD_NEEDLE_8192_7F3A"
    client = FakeClient(
        [
            response(
                "MD_NEEDLE_8192_7F",
                finish_reason="length",
                reasoning_content=f"Found {needle}",
                ev_id="ev_1",
            ),
            response(
                needle,
                finish_reason="stop",
                reasoning_content=f"Found {needle}",
                ev_id="ev_2",
            ),
        ]
    )

    result, evidence = asyncio.run(_needle_probe(client, "m", 8192))

    assert result.status == ProbeStatus.PASS
    assert result.metadata["retried_for_output_truncation"] is True
    assert result.metadata["retrieval_seen_in_reasoning"] is True
    assert [item["max_tokens"] for item in client.payloads] == [64, 256]
    assert len(evidence) == 2


def test_context_probe_does_not_fail_when_retry_is_still_length_truncated():
    client = FakeClient(
        [
            response("partial", finish_reason="length", ev_id="ev_1"),
            response("still partial", finish_reason="length", ev_id="ev_2"),
        ]
    )

    result, evidence = asyncio.run(_needle_probe(client, "m", 8192))

    assert result.status == ProbeStatus.INSUFFICIENT
    assert result.score is None
    assert len(evidence) == 2


def test_context_probe_accepts_reasoning_retrieval_even_if_final_stays_truncated():
    needle = "MD_NEEDLE_8192_7F3A"
    client = FakeClient(
        [
            response(
                "partial",
                finish_reason="length",
                reasoning_content=f"Retrieved {needle}",
                ev_id="ev_1",
            ),
            response(
                "partial again",
                finish_reason="length",
                reasoning_content=f"Retrieved {needle}",
                ev_id="ev_2",
            ),
        ]
    )

    result, _ = asyncio.run(_needle_probe(client, "m", 8192))

    assert result.status == ProbeStatus.PASS
    assert "final output remained truncated" in result.summary

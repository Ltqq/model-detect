"""Basic chat response shape must be checked, not just choices existence."""

import asyncio

import pytest

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.protocol import probe_basic


class StubClient:
    def __init__(self, payload):
        self.payload = payload

    async def post_json(self, *, probe_id, path, payload, **kwargs):
        assert probe_id == "protocol.chat.basic"
        return CallResult(
            evidence=Evidence(
                id="ev_basic",
                probe_id=probe_id,
                url="https://example.test/v1/chat/completions",
                response_status=200,
            ),
            json_body=self.payload,
        )


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        ({"choices": [{"message": {"role": "assistant", "content": "OK"}}]}, ProbeStatus.PASS),
        ({"choices": [{}]}, ProbeStatus.FAIL),
        ({"choices": [{"text": "OK"}]}, ProbeStatus.FAIL),
        ({"choices": ["not-an-object"]}, ProbeStatus.FAIL),
        ({"choices": []}, ProbeStatus.FAIL),
        ({"choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": "thinking"}, "finish_reason": "length"}]}, ProbeStatus.INSUFFICIENT),
    ],
)
def test_basic_probe_rejects_non_chat_completion_shapes(body, expected_status):
    results, _ = asyncio.run(probe_basic(StubClient(body), "kimi-k3"))
    assert results[0].probe_id == "protocol.chat.basic"
    assert results[0].status == expected_status

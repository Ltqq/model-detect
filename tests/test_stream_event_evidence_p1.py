"""SSE response must contain observable data events."""

import asyncio
import pytest

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.protocol import probe_stream


class StreamStub:
    def __init__(self, *, content_type, body, text=""):
        self.content_type = content_type
        self.body = body
        self.text = text

    async def post_json(self, *, probe_id, path, payload, **kwargs):
        assert kwargs["stream"] is True
        return CallResult(
            evidence=Evidence(
                id="ev_stream", probe_id=probe_id,
                url="https://provider.test/v1/chat/completions",
                response_status=200,
                response_headers={"content-type": self.content_type},
                response_body=self.body,
            ),
            json_body=self.body,
            text_body=self.text,
        )


@pytest.mark.parametrize(
    ("content_type", "body", "text", "status"),
    [
        ("text/event-stream", None, "", ProbeStatus.FAIL),
        ("text/event-stream", [], "", ProbeStatus.FAIL),
        ("text/event-stream", [{"choices": [{"delta": {"content": "ok"}}]}], "data: {}", ProbeStatus.PASS),
        ("text/html", "<!doctype html>", "data: unrelated", ProbeStatus.FAIL),
    ],
)
def test_stream_needs_events_not_just_sse_header(content_type, body, text, status):
    result, _ = asyncio.run(probe_stream(StreamStub(content_type=content_type, body=body, text=text), "glm-5.3"))
    assert result[0].status == status

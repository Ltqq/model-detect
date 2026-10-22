"""Offline regression: providers may reflect the configured API key.

Verify no reflected key reaches HTTP call previews, Evidence, report JSON/HTML,
or exported evidence files. These fixtures use an opaque *synthetic* secret.
"""
import asyncio
import json

import httpx
import pytest

from model_detect import http_client
from model_detect.models import AuditReport, ProbeResult, ProbeStatus
from model_detect.reporting import write_report

SECRET = "opaque-local-credential-583920"


def call_with_handler(monkeypatch, handler, *, stream=False, stream_full=False):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        http_client.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = http_client.AuditHttpClient(
        base_url="https://offline.invalid/v1", api_key=SECRET
    )
    return asyncio.run(
        client.post_json(
            probe_id="protocol.chat.basic",
            path="/chat/completions",
            payload={"model": "fixture", "messages": [{"role": "user", "content": "hi"}]},
            stream=stream,
            stream_full=stream_full,
        )
    )


@pytest.mark.parametrize("status", [200, 401, 429, 500])
def test_reflected_credential_is_removed_from_json_and_report(monkeypatch, tmp_path, status):
    def handler(request):
        assert request.headers["authorization"] == "Bearer " + SECRET
        return httpx.Response(
            status,
            json={
                "error": {"message": "reflected key " + SECRET},
                "choices": [{"message": {"content": SECRET + " quoted"}}],
            },
            headers={"x-debug-provider": SECRET},
        )

    call = call_with_handler(monkeypatch, handler)
    assert call.json_body["error"]["message"].endswith("***REDACTED***")
    assert call.json_body["choices"][0]["message"]["content"] == "***REDACTED*** quoted"
    assert call.evidence.response_headers["x-debug-provider"] == "***REDACTED***"
    assert call.evidence.request_headers["Authorization"] == "***REDACTED***"

    report = AuditReport(
        target={"base_url": "https://offline.invalid/v1", "model": "fixture"},
        evidences=[call.evidence],
        results=[
            ProbeResult(
                probe_id="protocol.chat.basic",
                category="protocol",
                status=ProbeStatus.ERROR,
                score=None,
                summary="synthetic response",
                observed=call.json_body,
                evidence_ids=[call.evidence.id],
            )
        ],
    )
    folder = write_report(report, tmp_path / "out")
    for path in (
        folder / "report.json",
        folder / "report.html",
        folder / "evidence" / (call.evidence.id + ".json"),
    ):
        assert path.is_file()
        assert SECRET not in path.read_text(encoding="utf-8"), path


@pytest.mark.parametrize("stream_full", [False, True])
def test_reflected_credential_is_removed_from_stream_preview(monkeypatch, stream_full):
    def handler(request):
        event = json.dumps({
            "choices": [
                {"index": 0, "delta": {"content": "reply " + SECRET}, "finish_reason": "stop"}
            ]
        })
        return httpx.Response(
            200,
            text=f"data: {event}\\n\\ndata: [DONE]\\n\\n",
            headers={"content-type": "text/event-stream"},
        )

    call = call_with_handler(monkeypatch, handler, stream=True, stream_full=stream_full)
    assert SECRET not in str(call.evidence.model_dump())
    assert SECRET not in str(call.json_body)
    assert SECRET not in call.text_body
    if stream_full:
        assert call.json_body["_sse_completed"] is True
        assert call.evidence.response_body["_sse_completed"] is True
    else:
        assert call.json_body[0]["choices"][0]["delta"]["content"] == "reply ***REDACTED***"


def test_reflected_credential_is_removed_from_unparseable_html(monkeypatch):
    call = call_with_handler(
        monkeypatch,
        lambda request: httpx.Response(
            502,
            text="<html>gateway rejected " + SECRET + "</html>",
            headers={"content-type": "text/html"},
        ),
    )
    assert call.json_body is None
    assert SECRET not in call.text_body
    assert SECRET not in str(call.evidence.model_dump())
    assert "***REDACTED***" in call.evidence.response_body

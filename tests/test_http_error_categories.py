import asyncio
import httpx
from model_detect import http_client


def _client_with_handler(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        http_client.httpx, "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    return http_client.AuditHttpClient(
        base_url="https://example.test/v1", api_key="sk-secret-never-report",
    )


def _request(client, *, stream=False):
    return asyncio.run(client.post_json(
        probe_id="protocol.test", path="/chat/completions",
        payload={"model": "test", "messages": [{"role": "user", "content": "x"}]},
        stream=stream, stream_full=stream,
    ))


def test_transport_timeout_has_structured_reason_no_secrets(monkeypatch):
    def handler(request):
        raise httpx.ConnectTimeout("Bearer sk-secret-never-report", request=request)
    client = _client_with_handler(monkeypatch, handler)
    output = _request(client)
    assert output.evidence.response_status is None
    assert output.evidence.error_category == "timeout"
    assert "sk-secret-never-report" not in str(output.evidence.model_dump())


def test_429_and_non_json_html_are_distinct(monkeypatch):
    client = _client_with_handler(
        monkeypatch, lambda request: httpx.Response(
            429, json={"error": {"message": "limit"}},
            headers={"Content-Type": "application/json"},
        ),
    )
    assert _request(client).evidence.error_category == "rate_limited"


def test_stream_without_done_is_marked_incomplete(monkeypatch):
    client = _client_with_handler(
        monkeypatch, lambda request: httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
            headers={"Content-Type": "text/event-stream"},
        ),
    )
    response = _request(client, stream=True)
    assert response.evidence.error_category == "stream_incomplete"
    assert response.json_body["_sse_completed"] is False

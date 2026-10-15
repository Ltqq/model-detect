"""G1.4: infrastructure and malformed responses are not capability failures."""
from types import SimpleNamespace

import pytest

from model_detect import glm53_qualification as module


@pytest.mark.asyncio
async def test_infrastructure_failures_are_inconclusive(monkeypatch):
    cases = module.capability_cases("smoke")[:1]
    responses = [
        (401, {"error": {"message": "unauthorized"}}, "application/json"),
        (429, {"error": {"message": "rate limited"}}, "application/json"),
        (200, "<html>gateway</html>", "text/html"),
        (200, {"not_choices": []}, "application/json"),
        (200, {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}, "application/json"),
    ]
    seen = []
    class FakeHttpClient:
        def __init__(self, **kwargs): pass
        async def post_json(self, **kwargs):
            status, body, content_type = responses[len(seen)]
            seen.append(status)
            return SimpleNamespace(
                json_body=body,
                evidence=SimpleNamespace(
                    response_status=status,
                    response_headers={"content-type": content_type},
                    elapsed_ms=1,
                ),
            )
    monkeypatch.setattr(module, "AuditHttpClient", FakeHttpClient)
    result = await module.run_endpoint(
        base_url="https://example.test/v1", api_key="test",
        cases=cases * len(responses), runs=1, label="customer",
    )
    assert [row["status"] for row in result] == ["insufficient"] * len(responses)
    assert all(row["normalized_answer_excerpt"] is None for row in result)
    assert all(row["answer_normalization"] is None for row in result)
    assert all("模型能力" in row["explanation"] or "HTTP 200" in row["explanation"] or "模型没有" in row["explanation"] for row in result)

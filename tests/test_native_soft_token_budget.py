import asyncio
from types import MethodType

from model_detect.http_client import AuditHttpClient, CallResult
from model_detect.models import Evidence
from model_detect.native_budget import NativeTokenBudget


def _response(index: int, usage: dict | None) -> CallResult:
    return CallResult(
        evidence=Evidence(
            id=f"ev_{index}", probe_id=f"test.{index}",
            url="https://example.test/v1/chat/completions", response_status=200,
        ),
        json_body={"usage": usage} if usage is not None else {},
    )


def test_observed_soft_cap_blocks_followup_requests_not_first_inflight():
    client = AuditHttpClient(
        base_url="https://example.test/v1", api_key="fake", model="glm-5.3",
        budget=NativeTokenBudget(20),
    )
    sent = []
    async def fake(self, **kwargs):
        sent.append(kwargs["probe_id"])
        return _response(len(sent), {"prompt_tokens": 14, "completion_tokens": 10})
    client._post_json_unmetered = MethodType(fake, client)
    async def run():
        first = await client.post_json(probe_id="a", path="/chat/completions",
                                       payload={"model": "glm-5.3", "messages": []})
        second = await client.post_json(probe_id="b", path="/chat/completions",
                                        payload={"model": "glm-5.3", "messages": []})
        return first, second
    first, second = asyncio.run(run())
    assert sent == ["a"]
    assert first.evidence.response_status == 200
    assert second.evidence.response_status is None
    assert "BudgetExceeded" in second.evidence.error
    status = client.budget.snapshot()
    assert status["observed_tokens"] == 24
    assert status["blocked_calls"] == 1
    assert status["hard_cost_cap"] is False


def test_unknown_usage_stops_before_second_http_call():
    client = AuditHttpClient(base_url="https://example.test/v1", api_key="fake",
                             budget=NativeTokenBudget(100, stop_on_unknown=True))
    sent = []
    async def fake(self, **kwargs):
        sent.append(True)
        return _response(len(sent), None)
    client._post_json_unmetered = MethodType(fake, client)
    async def run():
        await client.post_json(probe_id="a", path="/chat/completions", payload={})
        await client.post_json(probe_id="b", path="/chat/completions", payload={})
    asyncio.run(run())
    assert len(sent) == 1
    assert client.budget.snapshot()["stop_reason"] == "provider_usage_unknown"

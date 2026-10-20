"""Regression distilled from an authorized GLM-5.3-Flash Quick report.

No real prompt, private URL, API key or response content is committed.
"""
import asyncio

import pytest

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeStatus
from model_detect.probes.protocol import (
    probe_system, probe_multiturn, probe_json_mode,
)


class FakeThinkingClient:
    def __init__(self, *, complete=False):
        self.complete = complete
        self.calls = []

    async def post_json(self, *, probe_id, path, payload, **kwargs):
        self.calls.append(payload)
        if self.complete:
            content = (
                "SYS_MD_73A9" if probe_id == "protocol.system"
                else "TURN_MD_51C2" if probe_id == "protocol.multiturn"
                else '{"ok":true,"n":7}'
            )
            answer = {"content": content, "reasoning_content": "short thought"}
            reason = "stop"
        else:
            answer = {"content": "", "reasoning_content": "reasoning filled budget"}
            reason = "length"
        return CallResult(
            evidence=Evidence(
                id="ev1", probe_id=probe_id,
                url="https://placeholder.invalid/v1/chat/completions",
                response_status=200,
            ),
            json_body={
                "choices": [{"message": answer, "finish_reason": reason}],
                "usage": {"completion_tokens": payload["max_tokens"]},
            },
        )


@pytest.mark.parametrize("probe", [probe_system, probe_multiturn, probe_json_mode])
def test_truncated_reasoning_is_inconclusive_not_model_failure(probe):
    client = FakeThinkingClient()
    results, _ = asyncio.run(probe(client, "glm-5.3-flash"))
    assert results[0].status == ProbeStatus.INSUFFICIENT
    assert results[0].score is None
    assert "truncated" in results[0].summary.lower()
    assert client.calls[0]["max_tokens"] >= 256


@pytest.mark.parametrize("probe", [probe_system, probe_multiturn, probe_json_mode])
def test_complete_reasoning_model_answers_still_pass(probe):
    client = FakeThinkingClient(complete=True)
    results, _ = asyncio.run(probe(client, "glm-5.3-flash"))
    assert results[0].status == ProbeStatus.PASS


def test_other_models_keep_quick_output_budget():
    client = FakeThinkingClient()
    asyncio.run(probe_system(client, "a-custom-model-not-in-catalog"))
    assert client.calls[0]["max_tokens"] == 32

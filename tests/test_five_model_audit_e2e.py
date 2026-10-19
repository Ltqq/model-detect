"""Run the *real* audit pipeline against a local HTTP mock for all five models.

No paid endpoint and no fake claim of model capability: these fixtures only
exercise protocol dispatch, model selection and evidence persistence.
"""

import asyncio
import json

import httpx
import pytest

from model_detect.audit import run_audit
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget, ProbeStatus
from model_detect.reporting import write_report


@pytest.mark.parametrize(
    ("model", "rule_id"),
    [
        ("glm-5.3", "glm-5.3"),
        ("glm-5.3-flash", "glm-5.3-flash"),
        ("kimi-k3", "kimi-k3"),
        ("deepseek-v4-pro", "deepseek-v4"),
        ("deepseek-flash", "deepseek-v4.1"),
    ],
)
def test_five_models_run_single_provider_audit_pipeline(monkeypatch, tmp_path, model, rule_id):
    requests = []

    def response(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, payload))
        if str(payload.get("model", "")).startswith("md-invalid"):
            return httpx.Response(404, json={"error": {"message": "model not found"}})
        if payload.get("stream"):
            event = json.dumps({
                "id": "local-event",
                "choices": [{"index": 0, "delta": {"content": "OK"}, "finish_reason": "stop"}],
            })
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=f"data: {event}\\n\\ndata: [DONE]\\n\\n",
            )
        return httpx.Response(
            200,
            json={
                "id": "local-chat",
                "model": payload.get("model", model),
                "choices": [{
                    "index": 0, "message": {"role": "assistant", "content": "OK"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
            },
        )

    transport = httpx.MockTransport(response)
    original_async_client = httpx.AsyncClient

    def offline_client(*args, **kwargs):
        return original_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", offline_client)
    config = AuditConfig(
        target=AuditTarget(base_url="https://offline.test/v1", model=model),
        profile="quick",
        output_dir=str(tmp_path),
        proxy_sleuth_enabled=False,
    )
    report = asyncio.run(run_audit(config, api_key_override="test-secret"))
    assert requests, "real audit pipeline must send requests through MockTransport"
    assert report.adapters["model_rule"]["id"] == rule_id
    outcomes = {r.probe_id: r.status for r in report.results}
    assert outcomes["protocol.chat.basic"] == ProbeStatus.PASS
    assert outcomes["protocol.chat.stream"] == ProbeStatus.PASS
    assert report.summary.final_verdict not in {"mismatch", "invalid_target"}

    path = write_report(report, tmp_path / "report")
    rendered = (path / "report.html").read_text(encoding="utf-8")
    saved = (path / "report.json").read_text(encoding="utf-8")
    assert model in rendered
    assert "test-secret" not in saved
    assert "test-secret" not in rendered

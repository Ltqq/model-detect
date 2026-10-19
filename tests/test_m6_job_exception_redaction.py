"""M6 security: third-party exceptions can contain API keys and private prompts."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from model_detect import webapp


@pytest.mark.parametrize("kind", ["audit", "reference"])
def test_background_exception_never_leaks_to_sqlite_json_or_html(monkeypatch, tmp_path, kind):
    pending = []
    def intercept(coro):
        pending.append(coro)
        return None

    # Simulates an unsafe transport/subprocess exception containing secrets.
    secret = "sk-PRIVATE-M6-DO-NOT-SERIALIZE"
    private_prompt = "private: internal-financial-projection"
    async def crash(*args, **kwargs):
        raise RuntimeError(f"Third-party HTTP failed Authorization: Bearer {secret}; {private_prompt}")

    monkeypatch.setattr(webapp.asyncio, "create_task", intercept)
    monkeypatch.setattr(webapp, "run_audit", crash)
    app = webapp.create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "reports",
        regression_dir=tmp_path / "regressions",
    )
    client = TestClient(app)
    if kind == "audit":
        response = client.post("/api/audits", json={
            "base_url": "https://example.invalid/v1",
            "model": "kimi-k3", "api_key": secret,
            "profile": "quick", "proxy_sleuth": False,
        })
    else:
        response = client.post("/api/references", json={
            "id": "kimi-k3-untrusted", "model": "kimi-k3",
            "api_key": secret, "base_url": "https://example.invalid/v1",
            "quality_baseline": False, "fingerprint": False,
        })
    assert response.status_code == 200, response.text
    job_id = response.json()["id"]
    assert len(pending) == 1
    asyncio.run(pending.pop())

    job = client.get("/api/jobs/" + job_id)
    assert job.status_code == 200
    assert job.json()["status"] == "failed"
    assert "错误详情已隐藏" in job.json()["error"]
    payloads = (
        job.text,
        client.get("/api/jobs").text,
        client.get("/").text,
        (tmp_path / "state" / "jobs.sqlite3").read_bytes().decode("utf-8", errors="ignore"),
    )
    assert all(secret not in value for value in payloads)
    assert all(private_prompt not in value for value in payloads)
    assert all("Authorization: Bearer" not in value for value in payloads)


def test_sanitized_failure_messages_keep_actionable_categories():
    assert "超时" in webapp._safe_job_error(TimeoutError("sk-secret"))
    assert "配置" in webapp._safe_job_error(ValueError("sk-secret"))
    assert "文件" in webapp._safe_job_error(FileNotFoundError("sk-secret"))
    assert "sk-secret" not in webapp._safe_job_error(RuntimeError("sk-secret"))

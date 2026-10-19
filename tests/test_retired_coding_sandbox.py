"""Retired self-built coding sandbox must not execute or incur API costs."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from model_detect.audit import run_audit
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget
from model_detect.webapp import create_app


def test_legacy_coding_sandbox_config_is_rejected_before_any_api_request():
    config = AuditConfig(
        target=AuditTarget(base_url="https://example.invalid/v1", model="glm-5.3"),
        coding_sandbox_enabled=True,
    )
    with pytest.raises(ValueError, match="Coding Sandbox was removed"):
        asyncio.run(run_audit(config, api_key_override="dummy-key"))


def test_web_refuses_legacy_coding_flag_before_job_enqueue(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
        regression_dir=tmp_path / "regressions",
    )
    client = TestClient(app)
    reply = client.post(
        "/api/audits",
        json={
            "base_url": "https://example.invalid/v1",
            "api_key": "dummy-key",
            "model": "glm-5.3",
            "profile": "standard",
            "coding_sandbox": True,
        },
    )
    assert reply.status_code == 400
    assert "已移除" in reply.json()["detail"]

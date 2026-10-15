import asyncio
import json

from fastapi.testclient import TestClient

from model_detect import webapp
from model_detect.models import (
    AuditReport,
    AuditSummary,
    Evidence,
    ProbeResult,
    ProbeStatus,
)


def test_local_web_audit_history_report_filter_and_delete(
    monkeypatch,
    tmp_path,
):
    pending = []

    def capture_task(coro):
        pending.append(coro)
        return None

    async def fake_run_audit(
        config,
        *,
        progress=None,
        api_key_override=None,
        regression_output_dir=None,
        **kwargs,
    ):
        assert api_key_override == "sk-e2e-secret"
        assert config.target.model == "kimi-k3"
        assert config.profile == "standard"
        if progress:
            progress("protocol:basic", 1, 1)

        evidence = Evidence(
            id="ev_e2e",
            probe_id="protocol.chat.basic",
            url=config.target.base_url + "/chat/completions",
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body={"model": config.target.model},
        )
        result = ProbeResult(
            probe_id="protocol.chat.basic",
            category="protocol",
            status=ProbeStatus.PASS,
            score=1.0,
            confidence=1.0,
            summary="E2E protocol probe passed",
            evidence_ids=[evidence.id],
        )
        return AuditReport(
            profile=config.profile,
            target={
                "base_url": config.target.base_url,
                "model": config.target.model,
                "protocol": "openai",
            },
            results=[result],
            evidences=[evidence],
            summary=AuditSummary(
                overall_score=96.0,
                category_scores={"protocol": 100.0},
                coverage={"protocol": True},
                final_verdict="MATCH",
                confidence="high",
            ),
            adapters={
                "promptfoo_regression": {
                    "status": "not_configured",
                    "suites": [],
                },
                "model_rule": {
                    "id": "kimi-k3",
                    "schema_version": 2,
                    "sources": [],
                },
            },
        )

    monkeypatch.setattr(webapp.asyncio, "create_task", capture_task)
    monkeypatch.setattr(webapp, "run_audit", fake_run_audit)

    app = webapp.create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
        regression_dir=tmp_path / "regressions",
    )
    client = TestClient(app)

    created = client.post(
        "/api/audits",
        json={
            "base_url": "https://relay.example/v1",
            "api_key": "sk-e2e-secret",
            "model": "kimi-k3",
            "profile": "standard",
            "proxy_sleuth": False,
            "coding_sandbox": False,
            "regression_suites": [],
        },
    )
    assert created.status_code == 200
    job_id = created.json()["id"]
    assert created.json()["status"] == "queued"
    assert len(pending) == 1

    asyncio.run(pending.pop())

    job = client.get(f"/api/jobs/{job_id}")
    assert job.status_code == 200
    job_data = job.json()
    assert job_data["status"] == "done"
    assert job_data["meta"]["verdict"] == "MATCH"
    assert job_data["meta"]["score"] == 96.0
    assert "sk-e2e-secret" not in json.dumps(job_data)

    history = client.get(
        "/",
        params={
            "model": "kimi",
            "status": "done",
            "kind": "audit",
        },
    )
    assert history.status_code == 200
    assert job_id in history.text
    assert "MATCH" in history.text
    assert "96.0" in history.text

    html = client.get(f"/reports/{job_id}")
    assert html.status_code == 200
    assert "E2E protocol probe passed" in html.text

    report_json = client.get(f"/api/audits/{job_id}/report")
    assert report_json.status_code == 200
    assert report_json.json()["target"]["model"] == "kimi-k3"
    assert report_json.json()["summary"]["final_verdict"] == "MATCH"

    evidence = client.get(f"/api/audits/{job_id}/evidence/ev_e2e")
    assert evidence.status_code == 200
    assert evidence.json()["response_status"] == 200

    archive = client.get(f"/api/audits/{job_id}/download")
    assert archive.status_code == 200
    assert archive.headers["content-type"].startswith("application/zip")
    assert archive.content[:2] == b"PK"

    report_root = tmp_path / "out" / job_id
    archive_path = tmp_path / "state" / f"{job_id}-report.zip"
    assert report_root.exists()
    assert archive_path.exists()

    deleted = client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/reports/{job_id}").status_code == 404
    assert not report_root.exists()
    assert not archive_path.exists()

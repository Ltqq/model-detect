import asyncio

from fastapi.testclient import TestClient

from model_detect.models import AuditReport, AuditSummary
from model_detect.webapp import create_app


def test_web_pages_and_reference_api(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    assert "model-detect" in r.text

    r = client.get("/references")
    assert r.status_code == 200
    assert "Trusted References" in r.text

    r = client.get("/api/references")
    assert r.status_code == 200
    assert r.json() == {"references": []}


def test_audit_validation_rejects_bad_profile(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    client = TestClient(app)
    r = client.post(
        "/api/audits",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "secret",
            "model": "m",
            "profile": "bad",
        },
    )
    assert r.status_code == 400



def test_web_lists_controlled_regression_suites_and_knowledge(tmp_path):
    regression_dir = tmp_path / "regressions"
    regression_dir.mkdir()
    (regression_dir / "kimi.yaml").write_text(
        "version: 1\nsuite: kimi\nmodel_patterns: ['*']\ncases: []\n",
        encoding="utf-8",
    )
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
        regression_dir=regression_dir,
    )
    client = TestClient(app)

    page = client.get("/")
    assert page.status_code == 200
    assert "Regression Suites" in page.text
    assert "kimi.yaml" in page.text

    model = client.get(
        "/api/knowledge/model",
        params={"model": "kimi-k3"},
    )
    assert model.status_code == 200
    body = model.json()["rule"]
    assert body["id"] == "kimi-k3"
    assert body["schema_version"] == 2
    assert body["sources"]

    providers = client.get("/api/knowledge/providers")
    assert providers.status_code == 200
    provider_body = providers.json()
    assert provider_body["schema_version"] == 2
    assert provider_body["providers"]["fireworks"]["source_refs"]


def test_web_rejects_regression_suite_outside_catalog(tmp_path):
    regression_dir = tmp_path / "regressions"
    regression_dir.mkdir()
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
        regression_dir=regression_dir,
    )
    client = TestClient(app)

    r = client.post(
        "/api/audits",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "secret",
            "model": "m",
            "profile": "standard",
            "regression_suites": ["../outside.yaml"],
        },
    )

    assert r.status_code == 400
    assert "unknown regression suites" in r.json()["detail"]


def test_web_serves_persisted_regression_artifact_and_job_status(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
        regression_dir=tmp_path / "regressions",
    )
    report_root = tmp_path / "out" / "audit_test"
    artifact = report_root / "regression" / "01" / "promptfoo-result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"ok": true}', encoding="utf-8")
    (report_root / "report.html").write_text(
        '<a href="regression/01/promptfoo-result.json">artifact</a>',
        encoding="utf-8",
    )

    app.state.store.create(
        job_id="audit_test",
        kind="audit",
        model="kimi-k3",
        base_url="https://example.com/v1",
        profile="standard",
        meta={},
    )
    app.state.store.finish(
        "audit_test",
        report_path=str(report_root / "report.html"),
        meta={
            "regression_status": "completed",
            "regression_suites": ["kimi.yaml"],
            "model_rule": {
                "id": "kimi-k3",
                "sources": [
                    {
                        "type": "official_doc",
                        "title": "Kimi official docs",
                    }
                ],
            },
            "provider_provenance": [
                {
                    "provider": "fireworks",
                    "label": "Fireworks AI",
                    "sources": [
                        {
                            "type": "empirical",
                            "title": "header signals",
                        }
                    ],
                    "false_positive_notes": [],
                }
            ],
        },
    )
    client = TestClient(app)

    page = client.get("/")
    assert "completed" in page.text
    assert "Kimi official docs" in page.text
    assert "Fireworks AI" in page.text

    report = client.get("/reports/audit_test")
    assert (
        '/api/audits/audit_test/regression/01/promptfoo-result.json'
        in report.text
    )

    artifact_response = client.get(
        "/api/audits/audit_test/regression/01/promptfoo-result.json"
    )
    assert artifact_response.status_code == 200
    assert artifact_response.json() == {"ok": True}



def test_history_shows_verdict_score_and_all_report_links(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    report_root = tmp_path / "out" / "audit_history"
    report_root.mkdir(parents=True)
    (report_root / "report.html").write_text("<h1>report</h1>", encoding="utf-8")
    (report_root / "report.json").write_text('{"ok": true}', encoding="utf-8")

    app.state.store.create(
        job_id="audit_history",
        kind="audit",
        model="kimi-k3",
        base_url="https://example.com/v1",
        profile="standard",
        meta={},
    )
    app.state.store.finish(
        "audit_history",
        report_path=str(report_root / "report.html"),
        meta={
            "verdict": "MATCH",
            "score": 93.5,
            "regression_status": "completed",
        },
    )

    client = TestClient(app)
    page = client.get("/")

    assert page.status_code == 200
    assert "MATCH" in page.text
    assert "93.5" in page.text
    assert 'href="/reports/audit_history"' in page.text
    assert 'href="/api/audits/audit_history/report"' in page.text
    assert 'href="/api/audits/audit_history/download"' in page.text


def test_failed_history_keeps_error_reason_visible(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    app.state.store.create(
        job_id="audit_failed",
        kind="audit",
        model="bad-model",
        base_url="https://example.com/v1",
        profile="quick",
        meta={},
    )
    app.state.store.fail("audit_failed", "RuntimeError: upstream rejected request")

    page = TestClient(app).get("/")

    assert page.status_code == 200
    assert "RuntimeError: upstream rejected request" in page.text



def test_history_filters_apply_to_page_and_api(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    store = app.state.store

    store.create(
        job_id="audit_kimi",
        kind="audit",
        model="kimi-k3",
        base_url="https://example.com/v1",
        profile="standard",
        meta={},
    )
    store.finish(
        "audit_kimi",
        meta={"verdict": "MATCH", "score": 90},
    )

    store.create(
        job_id="audit_glm",
        kind="audit",
        model="glm-5.2",
        base_url="https://example.com/v1",
        profile="standard",
        meta={},
    )
    store.fail("audit_glm", "failed")

    store.create(
        job_id="ref_kimi",
        kind="reference",
        model="kimi-k3",
        base_url="https://official.example/v1",
        profile="standard",
        meta={},
    )

    client = TestClient(app)

    page = client.get(
        "/",
        params={
            "model": "kimi",
            "status": "done",
            "kind": "audit",
        },
    )
    assert page.status_code == 200
    assert "audit_kimi" in page.text
    assert "glm-5.2" not in page.text
    assert 'value="kimi"' in page.text
    assert 'value="done" selected' in page.text
    assert 'value="audit" selected' in page.text

    api = client.get(
        "/api/jobs",
        params={
            "model": "kimi",
            "kind": "reference",
        },
    )
    assert api.status_code == 200
    assert [job["id"] for job in api.json()["jobs"]] == ["ref_kimi"]



def test_delete_history_removes_audit_files_and_database_row(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    report_root = tmp_path / "out" / "audit_delete"
    report_root.mkdir(parents=True)
    report_html = report_root / "report.html"
    report_html.write_text("<h1>report</h1>", encoding="utf-8")

    archive = tmp_path / "state" / "audit_delete-report.zip"
    archive.write_bytes(b"zip")

    app.state.store.create(
        job_id="audit_delete",
        kind="audit",
        model="m",
        base_url="https://example.com/v1",
        profile="quick",
        meta={},
    )
    app.state.store.finish(
        "audit_delete",
        report_path=str(report_html),
        meta={"verdict": "MATCH", "score": 90},
    )

    client = TestClient(app)
    response = client.delete("/api/jobs/audit_delete")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert not report_root.exists()
    assert not archive.exists()
    assert client.get("/api/jobs/audit_delete").status_code == 404


def test_delete_history_rejects_running_job(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    app.state.store.create(
        job_id="audit_running",
        kind="audit",
        model="m",
        base_url="https://example.com/v1",
        profile="quick",
        meta={},
    )
    app.state.store.update(
        "audit_running",
        status="running",
        progress=0.5,
    )

    client = TestClient(app)
    response = client.delete("/api/jobs/audit_running")

    assert response.status_code == 409
    assert app.state.store.get("audit_running")["status"] == "running"


def test_delete_reference_history_does_not_delete_reference_artifacts(tmp_path):
    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    reference_root = tmp_path / "refs" / "trusted-ref"
    reference_root.mkdir(parents=True)
    report_html = reference_root / "report.html"
    report_html.write_text("<h1>reference</h1>", encoding="utf-8")

    app.state.store.create(
        job_id="ref_history",
        kind="reference",
        model="m",
        base_url="https://official.example/v1",
        profile="standard",
        meta={},
    )
    app.state.store.finish(
        "ref_history",
        report_path=str(report_html),
        meta={"reference_id": "trusted-ref"},
    )

    response = TestClient(app).delete("/api/jobs/ref_history")

    assert response.status_code == 200
    assert reference_root.exists()
    assert report_html.exists()



def test_local_e2e_audit_history_reports_filter_and_delete(tmp_path, monkeypatch):
    pending = []
    real_create_task = asyncio.create_task

    async def fake_run_audit(config, **kwargs):
        return AuditReport(
            profile=config.profile,
            target={
                "base_url": config.target.base_url,
                "model": config.target.model,
                "protocol": config.target.protocol,
            },
            summary=AuditSummary(
                overall_score=97.5,
                final_verdict="MATCH",
                confidence="high",
            ),
            adapters={
                "model_rule": {
                    "id": "kimi-k3",
                    "sources": [],
                },
                "promptfoo_regression": {
                    "status": "not_configured",
                    "suites": [],
                },
            },
        )

    def capture_task(coro):
        pending.append(coro)
        return None

    monkeypatch.setattr("model_detect.webapp.run_audit", fake_run_audit)
    monkeypatch.setattr(
        "model_detect.webapp.asyncio.create_task",
        capture_task,
    )

    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "out",
    )
    client = TestClient(app)

    submitted = client.post(
        "/api/audits",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "secret",
            "model": "kimi-k3",
            "profile": "quick",
            "proxy_sleuth": False,
        },
    )
    assert submitted.status_code == 200
    job_id = submitted.json()["id"]
    assert submitted.json()["status"] == "queued"
    assert len(pending) == 1

    monkeypatch.setattr(
        "model_detect.webapp.asyncio.create_task",
        real_create_task,
    )
    asyncio.run(pending.pop())

    completed = client.get(f"/api/jobs/{job_id}")
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"
    assert completed.json()["meta"]["verdict"] == "MATCH"
    assert completed.json()["meta"]["score"] == 97.5

    history = client.get("/")
    assert history.status_code == 200
    assert job_id in history.text
    assert "MATCH" in history.text
    assert "97.5" in history.text

    html_report = client.get(f"/reports/{job_id}")
    assert html_report.status_code == 200
    assert "MATCH" in html_report.text

    json_report = client.get(f"/api/audits/{job_id}/report")
    assert json_report.status_code == 200
    assert json_report.json()["summary"]["final_verdict"] == "MATCH"
    assert json_report.json()["summary"]["overall_score"] == 97.5

    zip_report = client.get(f"/api/audits/{job_id}/download")
    assert zip_report.status_code == 200
    assert zip_report.headers["content-type"].startswith("application/zip")
    assert zip_report.content.startswith(b"PK")

    filtered = client.get(
        "/",
        params={
            "model": "kimi-k3",
            "status": "done",
            "kind": "audit",
        },
    )
    assert filtered.status_code == 200
    assert job_id in filtered.text

    report_root = tmp_path / "out" / job_id
    archive = tmp_path / "state" / f"{job_id}-report.zip"
    assert report_root.exists()
    assert archive.exists()

    deleted = client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True, "id": job_id}
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert not report_root.exists()
    assert not archive.exists()

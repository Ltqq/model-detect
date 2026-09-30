from fastapi.testclient import TestClient

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

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

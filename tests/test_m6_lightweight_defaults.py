"""M6: solo-user default does not start optional external scanners."""
from fastapi.testclient import TestClient
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget
from model_detect.webapp import WebAuditRequest, create_app


def test_optional_oss_off_by_default_but_explicit_override_kept():
    target = AuditTarget(base_url="https://example.invalid/v1", model="glm-5.3")
    cfg = AuditConfig(target=target)
    assert cfg.proxy_sleuth_enabled is False
    assert cfg.benchmark_profile is None
    assert cfg.coding_sandbox_enabled is False

    enabled = AuditConfig(target=target, proxy_sleuth_enabled=True)
    assert enabled.proxy_sleuth_enabled is True


def test_web_request_and_page_default_optional_oss_off(tmp_path):
    base = {
        "base_url": "https://example.invalid/v1",
        "api_key": "secret-fixture-do-not-output",
        "model": "kimi-k3",
    }
    default = WebAuditRequest.model_validate(base)
    assert default.proxy_sleuth is False
    assert WebAuditRequest.model_validate({**base, "proxy_sleuth": True}).proxy_sleuth is True

    app = create_app(
        state_dir=tmp_path / "state",
        reference_dir=tmp_path / "refs",
        output_dir=tmp_path / "output",
        regression_dir=tmp_path / "regressions",
    )
    html = TestClient(app).get("/")
    assert html.status_code == 200
    assert 'id="proxy" type="checkbox" checked' not in html.text
    assert 'id="proxy" type="checkbox"' in html.text
    assert "secret-fixture-do-not-output" not in html.text

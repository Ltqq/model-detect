"""M6: no hidden optional subprocess on routine detection."""
from fastapi.testclient import TestClient

from model_detect.config import AuditConfig
from model_detect.models import AuditTarget
from model_detect.webapp import WebAuditRequest, create_app


def test_native_audit_and_web_default_do_not_enable_external_oss():
    target = AuditTarget(base_url="http://localhost:5000/v1", model="glm-5.3")
    assert AuditConfig(target=target).proxy_sleuth_enabled is False
    payload = WebAuditRequest(
        base_url="http://localhost:5000/v1", api_key="test-only", model="glm-5.3"
    )
    assert payload.proxy_sleuth is False
    assert AuditConfig(target=target, proxy_sleuth_enabled=True).proxy_sleuth_enabled
    assert WebAuditRequest(
        base_url=payload.base_url, api_key="test-only", model=payload.model,
        proxy_sleuth=True,
    ).proxy_sleuth


def test_single_web_page_proxy_checkbox_is_opt_in(tmp_path):
    client = TestClient(create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"output",
    ))
    html = client.get("/").text
    assert 'id="proxy" type="checkbox" style="width:auto"' in html

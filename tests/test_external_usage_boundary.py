from model_detect.external_usage import external_usage_boundary
from model_detect.models import AuditReport
from model_detect.reporting import _usage_cost_section


def test_ran_external_adapters_are_unknown_never_free():
    result = external_usage_boundary({
        "lm_eval_benchmark": {"status": "done"},
        "fingerprint": {"engine": "llm-fingerprint-detector", "returncode": 0},
        "proxy_sleuth": {"status": "disabled"},
        "promptfoo_regression": {"status": "not_configured"},
    })
    assert result["unknown_usage_adapters"] == 2
    assert result["complete_total_known"] is False
    assert all(item["actual_cost"] is None for item in result["adapters"])
    assert all(item["observed_tokens"] is None for item in result["adapters"])


def test_report_displays_external_unknown_count():
    report = AuditReport(target={"model": "test"})
    report.adapters["token_usage"] = {"summary": {
        "requests": 1, "observed_requests": 1, "unknown_requests": 0}}
    report.adapters["external_token_usage"] = external_usage_boundary({
        "lm_eval_benchmark": {"status": "done"},
    })
    html = _usage_cost_section(report)
    assert "外部工具无法计量的适配器数" in html
    assert "1" in html

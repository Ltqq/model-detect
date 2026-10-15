from decimal import Decimal

from model_detect.config import AuditConfig
from model_detect.models import AuditReport
from model_detect.reporting import _usage_cost_section
from model_detect.usage_pricing import TokenPrices, summarize_cost
from model_detect.usage_meter import usage_from_response


def test_pricing_config_roundtrip():
    cfg = AuditConfig.model_validate({
        "target": {"base_url": "http://localhost:1234/v1", "model": "test"},
        "token_prices": {"currency": "CNY", "input_per_million": "5",
                         "output_per_million": "30", "cache_read_per_million": "0.5",
                         "cache_write_per_million": "6.25"},
    })
    assert cfg.token_prices.currency == "CNY"
    assert cfg.token_prices.cache_write_per_million == Decimal("6.25")


def test_report_section_shows_unknown_usage_without_claiming_exact_cost():
    record = usage_from_response(probe_id="p", stage="native", response=None)
    pricing = TokenPrices(input_per_million=5, output_per_million=30)
    report = AuditReport(target={"model": "test"})
    report.adapters["token_usage"] = {
        "summary": {"requests": 1, "observed_requests": 0,
                    "unknown_requests": 1}
    }
    report.adapters["token_cost"] = summarize_cost([record], pricing)
    html = _usage_cost_section(report)
    assert "Token 与费用" in html
    assert "partial_or_unknown" in html
    assert "缺失 Usage" in html
    assert "未知" in html

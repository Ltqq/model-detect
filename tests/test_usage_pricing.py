from decimal import Decimal

from model_detect.usage_meter import UsageRecord
from model_detect.usage_pricing import TokenPrices, price_usage, summarize_cost


def prices(**kwargs):
    return TokenPrices(
        input_per_million=Decimal("5"), output_per_million=Decimal("30"),
        cache_read_per_million=Decimal("0.5"), cache_write_per_million=Decimal("6.25"),
        **kwargs,
    )


def observed(**kwargs):
    return UsageRecord(
        probe_id="case", stage="native", source="observed",
        prompt_tokens=1000000, completion_tokens=100000,
        **kwargs,
    )


def test_cache_split_no_double_billing():
    record = observed(
        cached_read_tokens=500000, cached_write_tokens=100000,
        reasoning_tokens=40000,
    )
    charge = price_usage(record, prices())
    assert charge["status"] == "observed_usage_priced"
    # 400k uncached x 5 + 500k read x .5 + 100k write x 6.25 + 100k out x 30
    assert Decimal(charge["amount"]) == Decimal("5.875")


def test_absent_cache_breakdown_cannot_claim_precise_bill():
    amount = price_usage(observed(), prices())
    assert amount["status"] == "estimated"
    assert amount["reason"] == "cache_breakdown_incomplete"


def test_unknown_usage_and_unpriced_cache_are_not_free():
    unknown = UsageRecord(probe_id="bad", stage="native",
                          missing_reason="usage_not_reported")
    result = summarize_cost([observed(cached_read_tokens=0, cached_write_tokens=0),
                             unknown], prices())
    assert result["unknown_cost_requests"] == 1
    assert result["precise_total_available"] is False
    assert result["status"] == "partial_or_unknown"

    missing_read_rate = TokenPrices(
        input_per_million=5, output_per_million=30,
    )
    assert price_usage(observed(cached_read_tokens=100, cached_write_tokens=0),
                       missing_read_rate)["reason"] == "cache_read_price_missing"

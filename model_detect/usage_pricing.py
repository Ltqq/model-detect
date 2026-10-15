"""Conservative per-request pricing; no unknown cost is silently zeroed."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from .usage_meter import UsageRecord


class TokenPrices(BaseModel):
    currency: str = "USD"
    input_per_million: Decimal = Field(ge=0)
    output_per_million: Decimal = Field(ge=0)
    cache_read_per_million: Decimal | None = Field(default=None, ge=0)
    cache_write_per_million: Decimal | None = Field(default=None, ge=0)


def price_usage(record: UsageRecord, prices: TokenPrices) -> dict[str, Any]:
    """Only claim a complete charge when measured counts and rates suffice."""
    if record.source != "observed" or record.prompt_tokens is None or record.completion_tokens is None:
        return {"status": "unknown", "amount": None, "currency": prices.currency,
                "reason": record.missing_reason or "unobserved_usage"}
    read = record.cached_read_tokens or 0
    write = record.cached_write_tokens or 0
    if record.cached_read_tokens is not None and prices.cache_read_per_million is None:
        return {"status": "unknown", "amount": None, "currency": prices.currency,
                "reason": "cache_read_price_missing"}
    if record.cached_write_tokens is not None and prices.cache_write_per_million is None:
        return {"status": "unknown", "amount": None, "currency": prices.currency,
                "reason": "cache_write_price_missing"}
    if read + write > record.prompt_tokens:
        return {"status": "unknown", "amount": None, "currency": prices.currency,
                "reason": "cache_count_exceeds_prompt"}
    # An absent cache read/write usage subfield does not prove there were zero
    # cached tokens; the quote is an ordinary-rate scenario, not exact billing.
    uncertain_cache = record.cached_read_tokens is None or record.cached_write_tokens is None
    uncached = record.prompt_tokens - read - write
    subtotal = (
        Decimal(uncached) * prices.input_per_million
        + Decimal(record.completion_tokens) * prices.output_per_million
        + Decimal(read) * (prices.cache_read_per_million or Decimal(0))
        + Decimal(write) * (prices.cache_write_per_million or Decimal(0))
    ) / Decimal(1_000_000)
    return {
        "status": "estimated" if uncertain_cache else "observed_usage_priced",
        "amount": str(subtotal),
        "currency": prices.currency,
        "reason": "cache_breakdown_incomplete" if uncertain_cache else None,
        "note": "Price is configured, not a verified provider invoice.",
    }


def summarize_cost(records: list[UsageRecord], prices: TokenPrices) -> dict[str, Any]:
    charges = [price_usage(r, prices) for r in records]
    available = [c for c in charges if c["amount"] is not None]
    unknown = len(charges) - len(available)
    total = sum((Decimal(c["amount"]) for c in available), Decimal("0"))
    return {
        "currency": prices.currency,
        "requests": len(records),
        "costed_requests": len(available),
        "unknown_cost_requests": unknown,
        "partial_amount": str(total),
        "precise_total_available": bool(records) and unknown == 0
            and all(c["status"] == "observed_usage_priced" for c in charges),
        "status": "complete_estimate" if not unknown and records else "partial_or_unknown",
        "unknown_reasons": sorted({c["reason"] for c in charges if c["reason"]}),
        "warning": "Configured unit prices are not provider invoices; unknown charges are excluded from partial_amount.",
    }

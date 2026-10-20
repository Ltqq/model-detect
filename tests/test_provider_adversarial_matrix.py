"""Model-agnostic adversarial fixtures for provider attribution.

These are synthetic protocol examples, never copied from a supplier audit.
A brand in model-generated text, reasoning, structured JSON strings or error
prose is not evidence of the actual model weights or upstream provider.
"""
import pytest

from model_detect.models import Evidence
from model_detect.probes.provider import (
    detect_provider_hypotheses,
    evaluate_upstream_policy,
)

BRANDS = ("ark", "openai", "fireworks", "anthropic", "volcengine", "siliconflow")


def evidence(body, *, headers=None, status=200):
    return Evidence(
        id="synthetic-provider-negative",
        probe_id="protocol.chat.basic",
        url="https://example.invalid/v1/chat/completions",
        response_status=status,
        response_headers=headers or {"content-type": "application/json"},
        response_body=body,
    )


@pytest.mark.parametrize("brand", BRANDS)
@pytest.mark.parametrize(
    "location",
    ("answer", "reasoning", "json_string", "error_message"),
)
def test_brand_in_untrusted_text_never_attributed(brand, location):
    if location == "answer":
        body = {"choices": [{"message": {"content": f"example: {brand}"}}]}
    elif location == "reasoning":
        body = {"choices": [{"message": {"content": "ok", "reasoning": brand}}]}
    elif location == "json_string":
        body = {"choices": [{"message": {"content": '{"vendor": "' + brand + '"}'}}]}
    else:
        body = {"error": {"message": f"example: {brand}"}}

    item = evidence(body, status=400 if location == "error_message" else 200)
    assert detect_provider_hypotheses([item]) == []
    policy = evaluate_upstream_policy(
        [item], [], disallowed=["fireworks", "openai", "volcengine", "anthropic"]
    )
    assert policy.status.value == "insufficient"
    assert policy.metadata["policy_violation"] is False
    assert policy.confidence is None


@pytest.mark.parametrize("status", [200, 401, 429, 500])
def test_generic_request_id_and_errors_are_not_identity_evidence(status):
    item = evidence(
        {"error": {"message": "Fireworks OpenAI Ark"}},
        headers={"x-request-id": "req-1", "request-id": "req-2"},
        status=status,
    )
    assert detect_provider_hypotheses([item]) == []
    result = evaluate_upstream_policy(
        [item], [], disallowed=["openai", "anthropic", "fireworks"]
    )
    assert result.status.value == "insufficient"
    assert not result.metadata["policy_violation"]


def test_explicit_header_is_only_a_metadata_hint_not_model_identity():
    item = evidence(
        {"choices": [{"message": {"content": "unrelated"}}]},
        headers={"X-Fireworks-Request-ID": "synthetic-123"},
    )
    hints = detect_provider_hypotheses([item])
    assert [h.provider for h in hints] == ["fireworks"]
    assert hints[0].confidence is None
    result = evaluate_upstream_policy([item], hints, disallowed=["fireworks"])
    assert result.status.value == "fail"
    assert result.confidence is None
    assert result.observed["detected"][0]["not_model_identity_proof"] is True


def test_no_policy_configuration_is_skipped_not_passed():
    item = evidence({"choices": []})
    result = evaluate_upstream_policy([item], [], disallowed=[])
    assert result.status.value == "skipped"
    assert result.confidence is None

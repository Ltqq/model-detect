"""Model-agnostic adversarial fixtures for provider attribution.

Synthetic protocol examples only; no real supplier outputs or credentials.
"""
import pytest

from model_detect.models import Evidence
from model_detect.probes.provider import detect_provider_hypotheses, evaluate_upstream_policy

BRANDS = ("ark", "openai", "fireworks", "anthropic", "volcengine", "siliconflow")


def evidence(body, *, headers=None, status=200):
    return Evidence(
        id="synthetic-provider-negative",
        probe_id="protocol.chat.basic",
        url="https://example.invalid/v1/chat/completions",
        response_status=status,
        response_headers={"content-type": "application/json"} if headers is None else headers,
        response_body=body,
    )


@pytest.mark.parametrize("brand", BRANDS)
@pytest.mark.parametrize("location", ("answer", "reasoning", "json_string", "error_message"))
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


@pytest.mark.parametrize("headers", [{}, {"x-unrecognized-gateway": "fireworks"}, {"server": "openai"}])
def test_absent_unknown_or_generic_headers_do_not_identify_provider(headers):
    item = evidence({"choices": [{"message": {"content": "ok"}}]}, headers=headers)
    assert detect_provider_hypotheses([item]) == []
    result = evaluate_upstream_policy([item], [], disallowed=["fireworks", "openai"])
    assert result.status.value == "insufficient"
    assert result.observed["detected"] == []


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
    assert result.observed["detected"][0]["decision_basis"] == "configured_response_header_rule"


def test_spoofable_provider_header_does_not_create_identity_probability():
    item = evidence({}, headers={"x-fireworks-request-id": "attacker-controlled"})
    hints = detect_provider_hypotheses([item])
    assert len(hints) == 1
    assert hints[0].confidence is None
    result = evaluate_upstream_policy([item], hints, disallowed=["fireworks"])
    # Legacy upstream *header policy* may fail, but that is not a verified
    # weight-identity verdict; even an injected header looks the same.
    assert result.status.value == "fail"
    assert result.observed["detected"][0]["not_model_identity_proof"] is True
    assert result.confidence is None


def test_no_policy_configuration_is_skipped_not_passed():
    item = evidence({"choices": []})
    result = evaluate_upstream_policy([item], [], disallowed=[])
    assert result.status.value == "skipped"
    assert result.confidence is None

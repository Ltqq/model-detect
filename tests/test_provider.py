import pytest

from model_detect.models import Evidence
from model_detect.probes.provider import (
    detect_provider_hypotheses,
    evaluate_upstream_policy,
    load_provider_rule_set,
    normalize_provider_rule_set,
)


def test_detect_azure_apim_and_fireworks_from_evidence():
    evidences = [
        Evidence(
            id="ev1",
            probe_id="provider.error.invalid_model",
            url="https://example.com/v1/chat/completions",
            response_status=400,
            response_headers={
                "apim-request-id": "abc",
                "x-ms-request-id": "def",
                "x-fireworks-request-id": "fw-123",
            },
            response_body={
                "error": {
                    "message": "Fireworks upstream rejected model FW-Kimi-K3"
                }
            },
        )
    ]

    got = detect_provider_hypotheses(evidences)
    by_name = {x.provider: x for x in got}
    assert "azure_apim" in by_name
    assert "fireworks" in by_name
    assert by_name["fireworks"].confidence > 0.5
    assert by_name["azure_apim"].evidence


def test_no_provider_without_signals():
    evidences = [
        Evidence(
            id="ev1",
            probe_id="protocol.chat.basic",
            url="https://example.com/v1/chat/completions",
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body={"choices": []},
        )
    ]
    assert detect_provider_hypotheses(evidences) == []


def test_v1_provider_rule_set_is_backward_compatible():
    rules = normalize_provider_rule_set(
        {
            "version": 1,
            "providers": {
                "demo": {
                    "label": "Demo",
                    "headers": {"x-demo": 0.8},
                    "patterns": {"demo": 0.5},
                }
            },
        }
    )

    assert rules.schema_version == 1
    assert rules.sources == []
    assert rules.providers["demo"].headers["x-demo"] == 0.8
    assert rules.providers["demo"].source_refs == []


def test_v2_provider_rule_set_loads_provenance_metadata():
    rules = normalize_provider_rule_set(
        {
            "schema_version": 2,
            "sources": [
                {
                    "id": "demo-doc",
                    "type": "provider_doc",
                    "title": "Demo provider documentation",
                    "url": "https://example.com/docs",
                    "confidence": "high",
                }
            ],
            "providers": {
                "demo": {
                    "label": "Demo",
                    "headers": {"x-demo-request-id": 0.9},
                    "patterns": {"demo": 0.5},
                    "source_refs": ["demo-doc"],
                    "false_positive_notes": [
                        "Generic request-id headers are weak signals."
                    ],
                    "confidence_calibration": {
                        "single_header_cap": 0.8,
                        "notes": "Use multiple signals for high confidence.",
                    },
                }
            },
        }
    )

    rule = rules.providers["demo"]
    assert rules.schema_version == 2
    assert rule.source_refs == ["demo-doc"]
    assert rule.false_positive_notes
    assert rule.confidence_calibration["single_header_cap"] == 0.8


def test_v2_provider_rule_rejects_unknown_source_ref():
    with pytest.raises(ValueError, match="unknown sources"):
        normalize_provider_rule_set(
            {
                "schema_version": 2,
                "sources": [],
                "providers": {
                    "demo": {
                        "label": "Demo",
                        "source_refs": ["missing"],
                    }
                },
            }
        )


def test_v2_provider_rule_rejects_duplicate_source_ids():
    with pytest.raises(ValueError, match="source ids must be unique"):
        normalize_provider_rule_set(
            {
                "schema_version": 2,
                "sources": [
                    {
                        "id": "same",
                        "type": "provider_doc",
                    },
                    {
                        "id": "same",
                        "type": "empirical",
                    },
                ],
                "providers": {},
            }
        )


def test_v2_provider_rule_rejects_invalid_source_enum():
    with pytest.raises(ValueError):
        normalize_provider_rule_set(
            {
                "schema_version": 2,
                "sources": [
                    {
                        "id": "bad",
                        "type": "unknown",
                    }
                ],
                "providers": {},
            }
        )



def test_bundled_provider_db_is_v2_and_every_provider_has_provenance():
    rules = load_provider_rule_set()

    assert rules.schema_version == 2
    assert len(rules.providers) == 19
    assert rules.sources
    assert all(rule.source_refs for rule in rules.providers.values())
    assert all(
        rule.confidence_calibration.get("behavior") == "legacy-v1-weights"
        for rule in rules.providers.values()
    )


def test_provider_v2_migration_preserves_legacy_signal_weights():
    rules = load_provider_rule_set()

    assert rules.providers["fireworks"].headers == {
        "x-fireworks-request-id": 0.95,
        "fireworks-request-id": 0.95,
    }
    assert rules.providers["fireworks"].patterns == {
        "fireworks": 0.90,
        "fw-kimi": 0.80,
    }
    assert rules.providers["openai"].headers["x-request-id"] == 0.10
    assert rules.providers["volcengine"].patterns["ark"] == 0.20


def test_provider_v2_migration_preserves_detection_confidence():
    evidences = [
        Evidence(
            id="ev1",
            probe_id="provider.error.invalid_model",
            url="https://example.com/v1/chat/completions",
            response_status=400,
            response_headers={
                "apim-request-id": "abc",
                "x-ms-request-id": "def",
                "x-fireworks-request-id": "fw-123",
            },
            response_body={
                "error": {
                    "message": "Fireworks upstream rejected model FW-Kimi-K3"
                }
            },
        )
    ]

    by_name = {
        item.provider: item
        for item in detect_provider_hypotheses(evidences)
    }

    assert by_name["fireworks"].confidence == 0.841
    assert by_name["azure_apim"].confidence == 0.533



def test_detect_new_api_gateway_from_response_headers():
    evidences = [
        Evidence(
            id="ev-new-api",
            probe_id="provider.error.invalid_model",
            url="https://example.com/v1/chat/completions",
            response_status=503,
            response_headers={
                "x-new-api-version": "v0.9",
                "x-oneapi-request-id": "req-123",
            },
            response_body={
                "error": {
                    "type": "new_api_error",
                    "message": "No available channel for model",
                }
            },
        )
    ]

    by_name = {
        item.provider: item
        for item in detect_provider_hypotheses(evidences)
    }
    assert "new_api" in by_name
    assert by_name["new_api"].confidence > 0.8



def test_upstream_policy_rejects_disallowed_provider_on_strong_signal():
    evidences = [
        Evidence(
            id="ev-fw",
            probe_id="protocol.chat.basic",
            url="https://example.com/v1/chat/completions",
            response_status=200,
            response_headers={"x-fireworks-request-id": "fw-123"},
            response_body={"choices": []},
        )
    ]
    hypotheses = detect_provider_hypotheses(evidences)

    result = evaluate_upstream_policy(
        evidences,
        hypotheses,
        disallowed=["fireworks"],
    )

    assert result.status.value == "fail"
    assert result.metadata["policy_violation"] is True
    assert result.observed["detected"][0]["provider"] == "fireworks"
    assert result.evidence_ids == ["ev-fw"]


def test_upstream_policy_does_not_treat_429_as_provider_identity():
    evidences = [
        Evidence(
            id="ev-429",
            probe_id="protocol.chat.basic",
            url="https://example.com/v1/chat/completions",
            response_status=429,
            response_headers={"content-type": "application/json"},
            response_body={"error": {"message": "rate limited"}},
        )
    ]
    hypotheses = detect_provider_hypotheses(evidences)

    result = evaluate_upstream_policy(
        evidences,
        hypotheses,
        disallowed=["fireworks"],
    )

    assert result.status.value == "pass"
    assert result.metadata["policy_violation"] is False
    assert result.observed["http_429_count"] == 1
    assert result.observed["detected"] == []

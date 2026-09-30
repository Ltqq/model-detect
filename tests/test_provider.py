from model_detect.models import Evidence
from model_detect.probes.provider import detect_provider_hypotheses


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

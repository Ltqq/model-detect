from model_detect.redaction import redact_headers, redact_payload


def test_redact_headers():
    got = redact_headers(
        {
            "Authorization": "Bearer sk-secret",
            "X-API-Key": "abc",
            "Content-Type": "application/json",
        }
    )
    assert got["Authorization"] == "***REDACTED***"
    assert got["X-API-Key"] == "***REDACTED***"
    assert got["Content-Type"] == "application/json"


def test_redact_nested_payload():
    got = redact_payload(
        {
            "api_key": "secret",
            "nested": {"authorization": "secret2", "ok": True},
            "items": [{"x-api-key": "secret3"}],
        }
    )
    assert got["api_key"] == "***REDACTED***"
    assert got["nested"]["authorization"] == "***REDACTED***"
    assert got["nested"]["ok"] is True
    assert got["items"][0]["x-api-key"] == "***REDACTED***"

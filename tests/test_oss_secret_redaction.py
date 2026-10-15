from types import SimpleNamespace
import pytest
from model_detect.redaction import redact_headers, redact_payload, redact_text, redact_url
from model_detect.adapters import fingerprint, proxy_sleuth


def test_redact_nested_and_inline_secrets():
    secret = "sk-abcdefgh123456789"
    assert secret not in redact_text("Bearer " + secret)
    assert secret not in redact_text(secret)
    assert redact_headers({"Cookie": secret})["Cookie"] == "***REDACTED***"
    assert redact_payload({"nested": {"access_token": secret}, "content": secret}) == {
        "nested": {"access_token": "***REDACTED***"},
        "content": "***REDACTED***",
    }
    url = redact_url("https://user:password@host.test/v1?api_key=" + secret)
    assert "password" not in url and secret not in url and "?" not in url


def test_fingerprint_subprocess_does_not_expose_secret_logs(monkeypatch):
    secret = "sk-abcdefgh123456789"
    monkeypatch.setattr(fingerprint.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=2, stdout="Bearer " + secret, stderr=secret))
    with pytest.raises(RuntimeError) as error:
        fingerprint._run_json(["fake"])
    assert secret not in str(error.value)


def test_fingerprint_success_suppresses_stderr(monkeypatch):
    secret = "sk-abcdefgh123456789"
    monkeypatch.setattr(fingerprint.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr=secret))
    data, meta = fingerprint._run_json(["fake"])
    assert data["ok"]
    assert secret not in str(meta)
    assert meta["stderr_present"] is True

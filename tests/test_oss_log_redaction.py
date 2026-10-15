"""Third-party process data is untrusted and must not enter persisted audit evidence."""
import json
from types import SimpleNamespace
import pytest
from model_detect.adapters import fingerprint, proxy_sleuth


def test_fingerprint_failure_does_not_echo_secrets(monkeypatch):
    monkeypatch.setattr(fingerprint.subprocess, "run", lambda *a, **k:
        SimpleNamespace(returncode=1, stdout="Bearer sk-secret-123", stderr="https://example/?key=secret"))
    with pytest.raises(RuntimeError) as error:
        fingerprint._run_json(["llm-fingerprint"], api_key="sk-secret-123")
    assert "sk-secret" not in str(error.value)
    assert "key=secret" not in str(error.value)


def test_fingerprint_invalid_json_does_not_echo_output(monkeypatch):
    monkeypatch.setattr(fingerprint.subprocess, "run", lambda *a, **k:
        SimpleNamespace(returncode=0, stdout="sk-secret-not-json", stderr="Bearer sk-secret"))
    with pytest.raises(RuntimeError) as error:
        fingerprint._run_json(["llm-fingerprint"])
    assert "sk-secret" not in str(error.value)


def test_proxy_metadata_never_contains_raw_output(monkeypatch):
    monkeypatch.setattr(proxy_sleuth.shutil, "which", lambda name: "/bin/proxy-sleuth")
    monkeypatch.setattr(proxy_sleuth.subprocess, "run", lambda *a, **k:
        SimpleNamespace(returncode=1, stdout="Bearer sk-secret", stderr="key=secret"))
    results, meta = proxy_sleuth.run(base_url="https://example.test/v1",model="test",api_key="sk-secret")
    serialized = json.dumps(meta) + json.dumps([x.model_dump(mode="json") for x in results])
    assert "sk-secret" not in serialized
    assert "key=secret" not in serialized
    assert meta["subprocess_logs_suppressed"] is True

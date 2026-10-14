"""Regression tests: external lm-eval logs must not expose caller credentials."""
import subprocess
from types import SimpleNamespace

import pytest

from model_detect.adapters import lm_eval


def test_lm_eval_diagnostics_redacted(monkeypatch, tmp_path):
    secret = "sk-verysecretkey123456"
    endpoint = "https://example.test/v1?access_token=hidden-token"
    def fake_run(*args, **kwargs):
        assert kwargs["env"]["OPENAI_API_KEY"] == secret
        return SimpleNamespace(
            returncode=1,
            stdout=f"request {endpoint}, key={secret}",
            stderr=(
                "Authorization: Bearer other-secret; "
                "api_key=another-private-value "
                "unexpected sk-anotherverylongsecret"
            ),
        )
    monkeypatch.setattr(lm_eval.subprocess, "run", fake_run)
    result = lm_eval.run_endpoint(
        base_url=endpoint, model="glm-5.3", api_key=secret,
        tasks=["gsm8k"], output_path=tmp_path, binary="lm_eval",
    )
    rendered = result["stdout_tail"] + result["stderr_tail"]
    for item in (secret, endpoint, "hidden-token", "other-secret",
                 "another-private-value", "sk-anotherverylongsecret"):
        assert item not in rendered
    assert result["returncode"] == 1
    assert "[REDACTED]" in rendered


def test_lm_eval_timeout_never_leaks_raw_subprocess_logs(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd="lm_eval", timeout=1,
            output="sk-secretfromtimeout",
            stderr="Bearer secretfromtimeout",
        )
    monkeypatch.setattr(lm_eval.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out") as caught:
        lm_eval.run_endpoint(
            base_url="https://example.test/v1",
            model="glm-5.3", api_key="sk-secretfromtimeout",
            tasks=["gsm8k"], output_path=tmp_path, binary="lm_eval",
        )
    assert "secretfromtimeout" not in str(caught.value)
    assert caught.value.__cause__ is None

from types import SimpleNamespace

import pytest

from model_detect import glm53_task_cache as probe


def test_offline_task_probe_uses_flags_and_never_exports_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("HF_TOKEN", "test-not-a-real-key")
    seen = {}
    def fake_run(args, **kwargs):
        seen.update(kwargs)
        assert "sk-secret" not in str(kwargs)
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["env"]["HF_DATASETS_OFFLINE"] == "1"
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert args[0] == probe.sys.executable
        return SimpleNamespace(returncode=0, stdout="warning\nMODEL_DETECT_TASK_CACHE_OK\n")
    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    result = probe.verify_offline_task_cache("smoke")
    assert result["verified"]
    assert result["tasks"] == ["gsm8k", "ifeval"]
    assert result["model_api_calls"] == 0


def test_failed_and_timed_out_tasks_fail_closed(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=1, stdout="MODEL_DETECT_TASK_CACHE_OK\n"))
    assert probe.verify_offline_task_cache("standard")["status"] == "unverified"
    def timeout(*args, **kwargs):
        raise probe.subprocess.TimeoutExpired(args[0], 10, output="sk-secret")
    monkeypatch.setattr(probe.subprocess, "run", timeout)
    assert probe.verify_offline_task_cache("smoke")["status"] == "timeout"


def test_invalid_args_never_launch_subprocess(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("must not launch")
    monkeypatch.setattr(probe.subprocess, "run", forbid)
    with pytest.raises(ValueError):
        probe.verify_offline_task_cache("other")
    with pytest.raises(ValueError):
        probe.verify_offline_task_cache("smoke", timeout_seconds=1)

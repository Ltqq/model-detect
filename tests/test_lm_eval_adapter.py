import subprocess

import pytest

from model_detect.adapters import lm_eval


def test_normalize_chat_endpoint():
    assert (
        lm_eval.normalize_chat_endpoint("https://relay.example/v1")
        == "https://relay.example/v1/chat/completions"
    )
    assert (
        lm_eval.normalize_chat_endpoint(
            "https://relay.example/v1/chat/completions"
        )
        == "https://relay.example/v1/chat/completions"
    )
    assert (
        lm_eval.normalize_chat_endpoint("https://relay.example")
        == "https://relay.example/v1/chat/completions"
    )


def test_build_command_for_openai_compatible_chat(tmp_path):
    cmd = lm_eval.build_command(
        base_url="https://relay.example/v1",
        model="kimi-k3",
        tasks=["gsm8k"],
        output_path=tmp_path,
        num_concurrent=2,
        max_retries=4,
        limit=5,
        binary="/usr/bin/lm_eval",
    )

    assert cmd[:3] == [
        "/usr/bin/lm_eval",
        "--model",
        "local-chat-completions",
    ]
    model_args = cmd[cmd.index("--model_args") + 1]
    assert "model=kimi-k3" in model_args
    assert "base_url=https://relay.example/v1/chat/completions" in model_args
    assert "num_concurrent=2" in model_args
    assert "max_retries=4" in model_args
    assert "tokenized_requests=False" in model_args
    assert "--apply_chat_template" in cmd
    assert cmd[cmd.index("--tasks") + 1] == "gsm8k"
    assert cmd[cmd.index("--limit") + 1] == "5"


def test_build_command_requires_tasks(tmp_path):
    with pytest.raises(ValueError):
        lm_eval.build_command(
            base_url="https://relay.example/v1",
            model="m",
            tasks=[],
            output_path=tmp_path,
            binary="/usr/bin/lm_eval",
        )


def test_run_endpoint_passes_key_only_via_environment(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = lm_eval.run_endpoint(
        base_url="https://relay.example/v1",
        model="m",
        api_key="sk-secret",
        tasks=["gsm8k"],
        output_path=tmp_path / "results",
        binary="/usr/bin/lm_eval",
    )

    assert result["returncode"] == 0
    assert seen["env"]["OPENAI_API_KEY"] == "sk-secret"
    assert all("sk-secret" not in arg for arg in seen["cmd"])

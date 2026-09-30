import subprocess

import yaml

from model_detect.adapters import promptfoo


def test_build_http_provider_uses_env_key():
    provider = promptfoo.build_http_provider(
        base_url="https://relay.example/v1",
        model="kimi-k3",
    )

    assert provider["id"] == "https"
    assert (
        provider["config"]["url"]
        == "https://relay.example/v1/chat/completions"
    )
    assert provider["config"]["body"]["model"] == "kimi-k3"
    assert provider["config"]["headers"]["Authorization"] == (
        "Bearer {{env.MODEL_DETECT_PROMPTFOO_KEY}}"
    )


def test_build_http_provider_supports_http():
    provider = promptfoo.build_http_provider(
        base_url="http://127.0.0.1:8000/v1",
        model="local-model",
    )
    assert provider["id"] == "http"


def test_write_eval_config_contains_no_api_key(tmp_path):
    provider = promptfoo.build_http_provider(
        base_url="https://relay.example/v1",
        model="m",
    )
    path = promptfoo.write_eval_config(
        tmp_path / "promptfooconfig.yaml",
        provider=provider,
        prompts=["{{question}}"],
        tests=[{"vars": {"question": "Reply OK"}}],
    )

    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)

    assert "sk-secret" not in raw
    assert parsed["providers"][0]["config"]["body"]["model"] == "m"
    assert parsed["tests"][0]["vars"]["question"] == "Reply OK"


def test_build_promptfoo_command(tmp_path):
    cmd = promptfoo.build_command(
        config_path=tmp_path / "config.yaml",
        output_path=tmp_path / "result.json",
        binary="/usr/bin/promptfoo",
    )

    assert cmd == [
        "/usr/bin/promptfoo",
        "eval",
        "-c",
        str(tmp_path / "config.yaml"),
        "--no-cache",
        "--no-progress-bar",
        "--no-table",
        "-o",
        str(tmp_path / "result.json"),
    ]


def test_run_eval_passes_key_only_in_environment(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="done",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = promptfoo.run_eval(
        config_path=tmp_path / "config.yaml",
        output_path=tmp_path / "result.json",
        api_key="sk-secret",
        binary="/usr/bin/promptfoo",
    )

    assert result["returncode"] == 0
    assert seen["env"]["MODEL_DETECT_PROMPTFOO_KEY"] == "sk-secret"
    assert all("sk-secret" not in arg for arg in seen["cmd"])

import json
from pathlib import Path
from urllib.request import Request, urlopen

from typer.testing import CliRunner

from model_detect import glm53_local_wire, glm53_cli
from model_detect.cli import app


def _fake_harness(**kwargs):
    assert kwargs["local_only"] is True
    assert kwargs["base_url"].startswith("http://127.0.0.1:")
    payload = {
        "model": "glm-5.3", "reasoning_effort": kwargs["reasoning_effort"],
        "max_tokens": kwargs["max_gen_toks"], "temperature": 0,
        "stop": [], "messages": [
            {"role": "user", "content": "sk-private-prompt-never-export"}
        ],
    }
    request = Request(
        kwargs["base_url"] + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        assert response.status == 200
    return {"returncode": 0}


def test_loopback_wire_capture_sees_actual_post_json_without_raw_prompts(monkeypatch):
    monkeypatch.setattr(glm53_local_wire.lm_eval, "run_endpoint", _fake_harness)
    captured = glm53_local_wire.capture_local_lm_eval_wire("smoke")
    assert captured["capture_count"] == 1
    assert captured["parameter_match"] is True
    assert captured["server_semantics_verified"] is False
    assert captured["external_model_api_calls"] == 0
    assert "sk-private-prompt-never-export" not in json.dumps(captured)
    assert captured["requests"][0]["reasoning_effort"] == "max"


def test_local_capture_cli_writes_redacted_file(monkeypatch, tmp_path):
    monkeypatch.setattr(glm53_local_wire.lm_eval, "run_endpoint", _fake_harness)
    path = tmp_path / "wire.json"
    result = CliRunner().invoke(app, [
        "glm53", "capture-local-wire", "--benchmark", "smoke",
        "--output-file", str(path),
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(path.read_text())["capture_count"] == 1
    assert "sk-private" not in path.read_text()
    assert CliRunner().invoke(app, [
        "glm53", "capture-local-wire", "--output-file", str(path),
    ]).exit_code != 0

import json

from typer.testing import CliRunner

from model_detect.cli import app


def test_verify_wire_cli_offline_and_redacted(tmp_path):
    payload = {
        "official": [{
            "model": "glm-5.3", "messages": [{"role": "user", "content": "private question"}],
            "reasoning_effort": "max", "max_tokens": 1280, "temperature": 0, "stop": [],
            "authorization": "sk-private-123456",
        }],
    }
    payload["customer"] = list(payload["official"])
    source = tmp_path / "sensitive.json"
    dest = tmp_path / "summary.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    args = ["glm53", "verify-wire", "--captured-json", str(source),
            "--output-file", str(dest)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    summary = dest.read_text(encoding="utf-8")
    assert json.loads(summary)["status"] == "request_payload_matched"
    assert "private question" not in summary
    assert "sk-private" not in summary
    second = CliRunner().invoke(app, args)
    assert second.exit_code != 0


def test_verify_wire_cli_rejects_malformed_evidence_without_leak(tmp_path):
    source = tmp_path / "sensitive.json"
    source.write_text('{"official":"sk-secret-not-list","customer":[]}', encoding="utf-8")
    dest = tmp_path / "summary.json"
    result = CliRunner().invoke(app, [
        "glm53", "verify-wire", "--captured-json", str(source),
        "--output-file", str(dest),
    ])
    assert result.exit_code != 0
    assert "sk-secret-not-list" not in result.output
    assert not dest.exists()

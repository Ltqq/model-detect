from typer.testing import CliRunner

from model_detect.cli import app
from model_detect import oss_readiness


def test_readiness_distinguishes_executable_from_validated_results(monkeypatch):
    monkeypatch.setattr(oss_readiness, "version", lambda package: "0.4.13")
    monkeypatch.setattr(oss_readiness.lm_eval, "availability",
                        lambda: {"available": True, "binary": "/bin/lm_eval"})
    monkeypatch.setattr(oss_readiness.promptfoo, "availability",
                        lambda: {"available": False, "binary": None})
    monkeypatch.setattr(oss_readiness.proxy_sleuth, "availability",
                        lambda: {"available": False, "binary": None})
    monkeypatch.setattr(oss_readiness.fingerprint, "availability",
                        lambda: {"available": True, "npx": "/bin/npx"})
    result = oss_readiness.local_oss_readiness()
    checks = result["checks"]
    assert len(checks) == 4
    assert checks["lm-evaluation-harness"]["version_compatible"] is True
    assert checks["lm-evaluation-harness"]["result_trust_verified"] is False
    assert checks["llm-fingerprint-detector"]["runtime_verified"] is False
    assert checks["promptfoo"]["readiness"] == "dependency_missing"
    assert result["api_calls"] == 0


def test_oss_status_json_lists_all_four_adapters():
    result = CliRunner().invoke(app, ["oss-status", "--json"])
    assert result.exit_code == 0, result.output
    for name in ("promptfoo", "lm-evaluation-harness", "proxy-sleuth",
                 "llm-fingerprint-detector"):
        assert name in result.output

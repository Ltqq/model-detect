"""G1.1: offline preflight must fail BEFORE any billable model calls."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.glm53_preflight import benchmark_preflight


def _mock_installed(monkeypatch, *, missing=frozenset(), version_value="0.4.13",
                    missing_nltk=frozenset()):
    from model_detect import glm53_preflight as preflight
    monkeypatch.setattr(preflight, "version", lambda name: version_value)
    monkeypatch.setattr(preflight, "resolve_lm_eval_executable",
                        lambda: "/example/venv/bin/lm_eval")
    monkeypatch.setattr(preflight, "_installed",
                        lambda name: name not in missing)
    monkeypatch.setattr(preflight, "_nltk_resource",
                        lambda name: name not in missing_nltk)


def test_preflight_requires_supported_harness_nltk_and_math_modules(monkeypatch):
    _mock_installed(monkeypatch)
    report = benchmark_preflight("standard")
    assert report["ready"] is True
    assert report["api_calls"] == 0
    assert report["network_calls"] == 0
    assert report["dataset_cache_verified"] is False
    assert next(x for x in report["checks"] if x["name"] == "dataset-cache")[
        "status"
    ] == "unverified"

    _mock_installed(monkeypatch, missing={"math_verify", "antlr4"})
    assert benchmark_preflight("smoke")["ready"] is True
    standard = benchmark_preflight("standard")
    assert standard["ready"] is False
    assert {"python:math_verify", "python:antlr4"} <= {
        x["name"] for x in standard["checks"] if x["status"] == "fail"
    }

    _mock_installed(monkeypatch, missing_nltk={"punkt_tab"})
    assert benchmark_preflight("standard")["ready"] is False
    _mock_installed(monkeypatch, version_value="0.4.12")
    assert benchmark_preflight("smoke")["ready"] is False


def test_doctor_runs_without_keys_and_never_calls_native_model(monkeypatch):
    from model_detect import glm53_cli
    _mock_installed(monkeypatch)
    monkeypatch.delenv("GLM53_OFFICIAL_KEY", raising=False)
    monkeypatch.delenv("GLM53_CUSTOMER_KEY", raising=False)

    def refuse(**kwargs):
        raise AssertionError("doctor must never execute native model API")

    monkeypatch.setattr(glm53_cli, "run_endpoint", refuse)
    result = CliRunner().invoke(app, ["glm53", "doctor", "--benchmark", "standard"])
    assert result.exit_code == 0, result.output
    assert "未调用模型" in result.output
    _mock_installed(monkeypatch, missing={"langdetect"})
    failure = CliRunner().invoke(app, ["glm53", "doctor", "--benchmark", "smoke"])
    assert failure.exit_code == 1
    assert "langdetect" in failure.output


def test_paid_cli_preflight_fails_before_native_calls(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "demo-off")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "demo-customer")
    _mock_installed(monkeypatch, missing={"immutabledict"})

    async def refuse(**kwargs):
        raise AssertionError("Paid API cannot be called without preflight")

    monkeypatch.setattr(glm53_cli, "run_endpoint", refuse)
    command = [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://provider.example/v1",
        "--mode", "protocol", "--official-runs", "1",
        "--customer-runs", "1", "--benchmark", "smoke",
        "--max-requests", "40",
        "--execute", "--output-dir", str(tmp_path / "out"),
    ]
    result = CliRunner().invoke(app, command)
    assert result.exit_code != 0
    assert "immutabledict" in result.output
    assert not (tmp_path / "out").exists()


def test_direct_benchmark_guard_blocks_before_subprocess(monkeypatch):
    from model_detect import glm53_benchmark as benchmark
    _mock_installed(monkeypatch, missing={"langdetect"})

    def refuse(**kwargs):
        raise AssertionError("benchmark subprocess must not start")

    monkeypatch.setattr(benchmark.lm_eval, "run_endpoint", refuse)
    with pytest.raises(RuntimeError, match="langdetect"):
        benchmark.run_standard_benchmark(
            level="smoke",
            official_url="https://api.z.ai/api/paas/v4",
            customer_url="https://provider.example/v1",
            official_key="fake-official",
            customer_key="fake-provider",
            official_runs=1,
            customer_runs=1,
        )


def test_generic_adapter_prefers_local_virtualenv_command(monkeypatch, tmp_path):
    from model_detect.adapters import lm_eval
    scripts = tmp_path / "env" / "Scripts"
    scripts.mkdir(parents=True)
    local = scripts / "lm_eval"
    local.write_text("placeholder")
    monkeypatch.setattr(lm_eval.sysconfig, "get_path", lambda name: str(scripts))
    monkeypatch.setattr(lm_eval.shutil, "which",
                        lambda name: "/some/other/global/bin/lm_eval")
    assert Path(lm_eval.resolve_lm_eval_executable()) == local
    cmd = lm_eval.build_command(
        base_url="https://provider.example/v1",
        model="glm-5.3", tasks=["gsm8k"], output_path=tmp_path,
    )
    assert cmd[0] == str(local)

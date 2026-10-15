"""G1.1: opt-in cache check must execute before any potentially billable call."""
from typer.testing import CliRunner
from model_detect.cli import app


def _args(tmp_path):
    return [
        "glm53", "compare", "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://provider.example/v1", "--official-runs", "1",
        "--customer-runs", "1", "--mode", "protocol", "--benchmark", "smoke",
        "--max-requests", "40", "--execute", "--require-offline-task-cache",
        "--output-dir", str(tmp_path / "evidence"),
    ]


def test_offline_cache_failure_prevents_paid_calls(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "fake1")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "fake2")
    monkeypatch.setattr(glm53_cli, "verify_offline_task_cache",
                        lambda level: {"verified": False})
    async def forbidden(**kwargs):
        raise AssertionError("must not send any model request")
    monkeypatch.setattr(glm53_cli, "run_endpoint", forbidden)
    result = CliRunner().invoke(app, _args(tmp_path))
    assert result.exit_code != 0
    assert "no paid requests were started" in result.output
    assert not (tmp_path / "evidence").exists()


def test_cache_preflight_not_triggered_in_preview(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    def forbidden(level):
        raise AssertionError("preview should not instantiate benchmark tasks")
    monkeypatch.setattr(glm53_cli, "verify_offline_task_cache", forbidden)
    args = _args(tmp_path)
    args.remove("--execute")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "预览完成" in result.output


def test_offline_cache_guard_requires_benchmark(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    async def forbidden(**kwargs):
        raise AssertionError("must not call paid endpoints")
    monkeypatch.setattr(glm53_cli, "run_endpoint", forbidden)
    args = _args(tmp_path)
    args[args.index("--benchmark") + 1] = "none"
    result = CliRunner().invoke(app, args)
    assert result.exit_code != 0
    assert "needs --benchmark" in result.output

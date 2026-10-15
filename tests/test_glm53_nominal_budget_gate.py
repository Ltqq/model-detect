"""B3: budget guards block execution before touching paid API keys."""
from typer.testing import CliRunner
from model_detect.cli import app


def _args():
    return [
        "glm53", "compare", "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://provider.example/v1",
        "--official-runs", "1", "--customer-runs", "1",
        "--mode", "protocol", "--benchmark", "none",
        "--max-requests", "60", "--execute",
    ]


def test_nominal_token_limit_fails_before_native_requests(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    async def no_paid_api(**kwargs):
        raise AssertionError("must fail before paid requests")
    monkeypatch.setattr(glm53_cli, "run_endpoint", no_paid_api)
    result = CliRunner().invoke(app, _args() + [
        "--max-nominal-output-tokens", "1",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code != 0
    assert not (tmp_path / "out").exists()


def test_estimated_input_limit_is_visible_in_dry_run(tmp_path):
    result = CliRunner().invoke(app, [
        arg for arg in _args() if arg != "--execute"
    ] + ["--max-estimated-input-tokens", "1",
         "--output-dir", str(tmp_path / "out")])
    assert result.exit_code != 0
    assert not (tmp_path / "out").exists()

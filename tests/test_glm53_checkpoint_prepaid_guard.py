"""Guard against duplicate paid native calls after an interrupted benchmark."""
from typer.testing import CliRunner
from model_detect.cli import app


def test_existing_benchmark_checkpoint_blocks_all_paid_calls(monkeypatch, tmp_path):
    from model_detect import glm53_cli
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "test-official")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "test-customer")
    monkeypatch.setattr(
        glm53_cli, "benchmark_preflight",
        lambda level: {"ready": True, "checks": []},
    )

    async def forbidden_native(**kwargs):
        raise AssertionError("native paid calls must not start")

    monkeypatch.setattr(glm53_cli, "run_endpoint", forbidden_native)
    output_dir = tmp_path / "existing-run"
    checkpoint = output_dir / "benchmark-evidence" / "benchmark-checkpoint.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text('{"schema":"glm53-benchmark-checkpoint-v1"}', encoding="utf-8")
    run = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://supplier.example/v1",
        "--official-runs", "1", "--customer-runs", "1",
        "--mode", "protocol", "--benchmark", "smoke",
        "--benchmark-runs", "1", "--max-requests", "40",
        "--execute", "--output-dir", str(output_dir),
    ])
    assert run.exit_code != 0
    assert "existing benchmark checkpoint" in run.output

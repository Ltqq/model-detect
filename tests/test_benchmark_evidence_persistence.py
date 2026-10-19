"""M2: allow evidence capture without ever re-running a paid benchmark by accident."""
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from model_detect.adapters import lm_eval
from model_detect.audit import run_audit
from model_detect.cli import app
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget


def _config(evidence):
    return AuditConfig(
        target=AuditTarget(
            base_url="https://example.invalid/v1", model="glm-5.3",
            api_key_env="DO_NOT_SET_FOR_THIS_TEST",
        ),
        benchmark_profile="smoke",
        benchmark_evidence_dir=str(evidence),
    )


def test_preflight_refuses_existing_output_before_reading_key_or_network(tmp_path):
    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(run_audit(_config(tmp_path)))


def test_preflight_requires_benchmark_profile(tmp_path):
    cfg = _config(tmp_path/"new")
    cfg.benchmark_profile = None
    with pytest.raises(ValueError, match="requires benchmark_profile"):
        asyncio.run(run_audit(cfg))
    assert not (tmp_path/"new").exists()


def test_profile_forwards_sample_logging_to_real_lm_eval_adapter(tmp_path):
    with patch.object(lm_eval, "run_endpoint", return_value={"returncode": 0}) as run:
        lm_eval.run_builtin_profile(
            profile_name="smoke", base_url="http://127.0.0.1:1/v1",
            model="glm-5.3", api_key="local-fake", output_path=tmp_path,
            log_samples=True,
        )
        assert run.call_args.kwargs["log_samples"] is True
        lm_eval.run_builtin_profile(
            profile_name="smoke", base_url="http://127.0.0.1:1/v1",
            model="glm-5.3", api_key="local-fake", output_path=tmp_path,
        )
        assert run.call_args.kwargs["log_samples"] is False


def test_cli_registers_evidence_capture_option():
    from typer.main import get_command
    params = get_command(app).commands["audit"].params
    assert any("--benchmark-evidence-dir" in param.opts for param in params)

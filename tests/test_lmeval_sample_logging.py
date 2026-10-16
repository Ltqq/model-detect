from pathlib import Path
from unittest.mock import patch

from model_detect.adapters import lm_eval


def test_log_samples_opt_in_does_not_change_default_command(tmp_path):
    base = dict(base_url="http://127.0.0.1:7788/v1", model="glm-5.3",
                tasks=["gsm8k"], output_path=tmp_path, binary="lm_eval")
    default = lm_eval.build_command(**base)
    logged = lm_eval.build_command(**base, log_samples=True)
    assert "--log_samples" not in default
    assert logged.count("--log_samples") == 1
    assert [x for x in logged if x != "--log_samples"] == default


def test_runner_passes_logging_flag_only_when_requested(tmp_path):
    base = dict(base_url="http://127.0.0.1:7788/v1", model="glm-5.3",
                tasks=["gsm8k"], output_path=tmp_path, binary="lm_eval",
                api_key="offline-only", local_only=True, timeout_seconds=10)
    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""
    with patch.object(lm_eval.subprocess, "run", return_value=Completed()) as fake:
        lm_eval.run_endpoint(**base, log_samples=True)
        assert "--log_samples" in fake.call_args.args[0]
        lm_eval.run_endpoint(**base)
        assert "--log_samples" not in fake.call_args.args[0]

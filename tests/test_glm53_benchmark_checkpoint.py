"""G1 checkpoint regression: no API calls, no secrets, no automatic paid retry."""
import json
from types import SimpleNamespace

import pytest

from model_detect import glm53_benchmark as benchmark


def test_checkpoint_retains_official_run_when_customer_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "benchmark_preflight",
                        lambda level: {"ready": True, "checks": []})
    monkeypatch.setattr(benchmark, "version", lambda package: "0.4.13")
    calls = []

    def fake_run_endpoint(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            return {"returncode": 1, "stderr_tail": "sk-private12345"}
        root = kwargs["output_path"]
        root.mkdir(parents=True)
        tasks = kwargs["tasks"]
        payload = {
            "results": {t: {"acc": 0.9} for t in tasks},
            "versions": {t: 3 for t in tasks},
            "n-samples": {t: {"effective": 5} for t in tasks},
            "configs": {
                t: {
                    "task": t,
                    "output_type": "generate_until",
                    "generation_kwargs": {"reasoning_effort": "max"},
                }
                for t in tasks
            },
        }
        (root / "results.json").write_text(json.dumps(payload), encoding="utf-8")
        return {"returncode": 0}

    monkeypatch.setattr(benchmark.lm_eval, "run_endpoint", fake_run_endpoint)
    evidence = tmp_path / "checkpoint"
    with pytest.raises(RuntimeError, match="customer benchmark run 1 failed"):
        benchmark.run_standard_benchmark(
            level="smoke", official_url="https://official.example/v1",
            customer_url="https://vendor.example/v1",
            official_key="sk-officialprivate", customer_key="sk-vendorprivate",
            official_runs=1, customer_runs=1, checkpoint_dir=evidence,
        )
    path = evidence / "benchmark-checkpoint.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["resume_supported"] is False
    assert len(data["runs"]["official"]) == 1
    assert data["runs"]["customer"] == []
    assert data["failures"][0]["endpoint"] == "customer"
    rendered = path.read_text(encoding="utf-8")
    for secret in ("sk-officialprivate", "sk-vendorprivate",
                   "official.example", "vendor.example", "sk-private12345"):
        assert secret not in rendered
    # Guard against silently repeating completed, paid work.
    with pytest.raises(RuntimeError, match="already exists"):
        benchmark.run_standard_benchmark(
            level="smoke", official_url="https://official.example/v1",
            customer_url="https://vendor.example/v1",
            official_key="sk-officialprivate", customer_key="sk-vendorprivate",
            official_runs=1, customer_runs=1, checkpoint_dir=evidence,
        )
    assert len(calls) == 2


def test_checkpoint_save_is_atomic_and_preserves_previous_on_serialization_failure(
        tmp_path):
    root = tmp_path / "evidence"
    plan = benchmark.benchmark_plan("smoke", official_runs=1, customer_runs=1)
    benchmark._save_checkpoint(root, plan=plan, harness_version="0.4.13",
                               runs={"official": [], "customer": []},
                               failures=[])
    previous = (root / "benchmark-checkpoint.json").read_bytes()
    with pytest.raises(TypeError):
        benchmark._save_checkpoint(root, plan=plan, harness_version="0.4.13",
                                   runs={"official": [object()]}, failures=[])
    assert (root / "benchmark-checkpoint.json").read_bytes() == previous

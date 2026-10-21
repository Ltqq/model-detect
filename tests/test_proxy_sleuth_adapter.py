import json
import subprocess
from pathlib import Path

from model_detect.adapters import proxy_sleuth
from model_detect.models import ProbeStatus


def _run_with_payload(monkeypatch, payload):
    monkeypatch.setattr(
        proxy_sleuth.shutil,
        "which",
        lambda name: "/usr/bin/proxy-sleuth" if name == "proxy-sleuth" else None,
    )

    def fake_run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output-file") + 1])
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(proxy_sleuth.subprocess, "run", fake_run)
    return proxy_sleuth.run(
        base_url="https://example.invalid/v1",
        model="example-model",
        api_key="test-key",
    )


def test_proxy_sleuth_mismatch_is_review_signal_not_identity_failure(monkeypatch):
    results, _ = _run_with_payload(
        monkeypatch,
        {
            "verdict": "MISMATCH",
            "overall_score": 0.12,
            "layers": [
                {"layer": "statistical", "verdict": "MISMATCH", "score": 0.12},
                {"layer": "param_integrity", "verdict": "MISMATCH", "score": 0.3},
            ],
        },
    )

    by_id = {result.probe_id: result for result in results}
    statistical = by_id["oss.proxy_sleuth.statistical"]
    assert statistical.status == ProbeStatus.WARN
    assert statistical.score is None
    assert statistical.confidence is None
    assert statistical.observed["external_score"] == 0.12
    assert statistical.metadata["identity_strength"] == "weak"
    assert statistical.metadata["weight_identity_proof"] is False
    assert statistical.metadata["not_calibrated_for_model_detect_targets"] is True

    parameter = by_id["oss.proxy_sleuth.param_integrity"]
    assert parameter.status == ProbeStatus.WARN
    assert parameter.score is None
    assert parameter.observed["external_score"] == 0.3


def test_proxy_sleuth_overall_verdict_is_not_promoted_to_identity_strength(monkeypatch):
    results, _ = _run_with_payload(
        monkeypatch,
        {"verdict": "MISMATCH", "overall_score": 0.2, "layers": []},
    )
    result = results[0]
    assert result.probe_id == "oss.proxy_sleuth.overall"
    assert result.status == ProbeStatus.WARN
    assert result.score is None
    assert result.observed["external_score"] == 0.2
    assert result.metadata["identity_strength"] == "weak"
    assert result.metadata["weight_identity_proof"] is False


def test_proxy_sleuth_match_remains_uncalibrated_unknown_not_pass(monkeypatch):
    results, meta = _run_with_payload(
        monkeypatch,
        {
            "verdict": "MATCH",
            "overall_score": 0.99,
            "layers": [{"layer": "statistical", "verdict": "MATCH", "score": 0.99}],
        },
    )
    assert meta["returncode"] == 0
    assert len(results) == 1
    row = results[0]
    assert row.status == ProbeStatus.INSUFFICIENT
    assert row.score is None
    assert row.confidence is None
    assert row.observed["verdict"] == "MATCH"
    assert row.observed["external_score"] == 0.99
    assert row.metadata["weight_identity_proof"] is False


def test_proxy_sleuth_failed_subprocess_discards_partial_positive_json(monkeypatch):
    monkeypatch.setattr(proxy_sleuth.shutil, "which", lambda _: "/fake/proxy-sleuth")

    def fake_run(cmd, **kwargs):
        path = Path(cmd[cmd.index("--output-file") + 1])
        path.write_text(
            json.dumps({"verdict": "MATCH", "overall_score": 1.0}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            cmd, 2, stdout="PRIVATE PROMPT", stderr="secret sk-12345678"
        )

    monkeypatch.setattr(proxy_sleuth.subprocess, "run", fake_run)
    results, meta = proxy_sleuth.run(
        base_url="https://supplier.example/v1",
        model="synthetic",
        api_key="private-placeholder",
    )
    assert len(results) == 1
    assert results[0].status == ProbeStatus.ERROR
    assert results[0].score is None
    assert results[0].confidence is None
    assert meta["returncode"] == 2
    assert meta["subprocess_logs_suppressed"] is True
    assert "PRIVATE PROMPT" not in json.dumps(meta)
    assert "sk-12345678" not in json.dumps(meta)

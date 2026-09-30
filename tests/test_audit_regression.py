import asyncio

from model_detect import audit
from model_detect.config import AuditConfig
from model_detect.models import (
    AuditReport,
    AuditTarget,
    ProbeResult,
    ProbeStatus,
)


def test_regression_suites_are_added_to_audit_results(
    monkeypatch,
    tmp_path,
):
    seen = []

    def fake_run_regression_file(
        regression_file,
        *,
        base_url,
        model,
        api_key,
        output_dir,
        **kwargs,
    ):
        seen.append(
            {
                "file": str(regression_file),
                "base_url": base_url,
                "model": model,
                "api_key": api_key,
                "output_dir": str(output_dir),
            }
        )
        return (
            [
                ProbeResult(
                    probe_id="regression.smoke.case-1",
                    category="protocol",
                    status=ProbeStatus.PASS,
                    score=1.0,
                    confidence=0.95,
                    summary="ok",
                    metadata={
                        "engine": "promptfoo",
                        "identity_strength": "none",
                    },
                )
            ],
            {
                "engine": "promptfoo",
                "suite": "smoke",
                "mapped_result_count": 1,
            },
        )

    monkeypatch.setattr(
        audit,
        "run_regression_file",
        fake_run_regression_file,
    )

    cfg = AuditConfig(
        target=AuditTarget(
            base_url="https://relay.example/v1",
            model="kimi-k3",
        ),
        output_dir=str(tmp_path / "audit-output"),
    )
    report = AuditReport(
        target={
            "base_url": cfg.target.base_url,
            "model": cfg.target.model,
        }
    )

    asyncio.run(
        audit._run_regression_suites(
            report,
            cfg,
            "sk-secret",
            [tmp_path / "regression.yaml"],
            output_dir=tmp_path / "regression-run",
        )
    )

    assert len(seen) == 1
    assert seen[0]["api_key"] == "sk-secret"
    assert report.results[0].probe_id == "regression.smoke.case-1"
    assert report.adapters["promptfoo_regression"]["status"] == "completed"
    assert report.adapters["promptfoo_regression"]["suites"][0][
        "mapped_result_count"
    ] == 1


def test_regression_failure_does_not_abort_audit(
    monkeypatch,
    tmp_path,
):
    def fail(*args, **kwargs):
        raise RuntimeError("promptfoo unavailable")

    monkeypatch.setattr(audit, "run_regression_file", fail)

    cfg = AuditConfig(
        target=AuditTarget(
            base_url="https://relay.example/v1",
            model="kimi-k3",
        ),
        output_dir=str(tmp_path),
    )
    report = AuditReport(
        target={
            "base_url": cfg.target.base_url,
            "model": cfg.target.model,
        }
    )

    asyncio.run(
        audit._run_regression_suites(
            report,
            cfg,
            "sk-secret",
            ["missing.yaml"],
            output_dir=tmp_path / "regression-run",
        )
    )

    assert report.results[0].status == ProbeStatus.ERROR
    assert report.results[0].probe_id == "internal.regression.1"
    assert report.adapters["promptfoo_regression"]["status"] == "partial"


def test_no_regression_suites_records_not_configured(tmp_path):
    cfg = AuditConfig(
        target=AuditTarget(
            base_url="https://relay.example/v1",
            model="m",
        )
    )
    report = AuditReport(
        target={
            "base_url": cfg.target.base_url,
            "model": cfg.target.model,
        }
    )

    asyncio.run(
        audit._run_regression_suites(
            report,
            cfg,
            "sk-secret",
            [],
            output_dir=tmp_path,
        )
    )

    assert report.results == []
    assert report.adapters["promptfoo_regression"] == {
        "status": "not_configured",
        "suites": [],
    }

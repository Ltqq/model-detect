import asyncio

from model_detect.baseline_collection import collect_quality_baseline
from model_detect.models import (
    AuditReport,
    AuditSummary,
    AuditTarget,
    ProbeResult,
    ProbeStatus,
)


def make_report(model, score):
    return AuditReport(
        target={
            "base_url": "https://official.example/v1",
            "model": model,
            "protocol": "openai",
        },
        profile="standard",
        results=[
            ProbeResult(
                probe_id="capability.reasoning",
                category="capability",
                status=ProbeStatus.PASS,
                score=score,
                summary="ok",
                observed={"tasks": [{"matched": True}, {"matched": score == 1.0}]},
            )
        ],
        summary=AuditSummary(
            overall_score=score * 100,
            category_scores={"capability": score * 100},
            coverage={"capability": True},
        ),
    )


def test_collect_quality_baseline_repeats_same_native_suite(monkeypatch):
    calls = []
    scores = iter([1.0, 0.5, 1.0])

    async def fake_run_audit(config, **kwargs):
        calls.append((config, kwargs))
        return make_report(config.target.model, next(scores))

    monkeypatch.setattr(
        "model_detect.baseline_collection.run_audit",
        fake_run_audit,
    )
    progress = []

    reports, baseline = asyncio.run(
        collect_quality_baseline(
            target=AuditTarget(
                base_url="https://official.example/v1",
                model="kimi-k3",
                api_key_env="IGNORED",
            ),
            api_key="secret",
            runs=3,
            progress=lambda current, total, phase: progress.append(
                (current, total, phase)
            ),
        )
    )

    assert len(reports) == 3
    assert len(calls) == 3
    assert all(call[0].profile == "standard" for call in calls)
    assert all(call[0].capability_enabled is True for call in calls)
    assert all(call[0].proxy_sleuth_enabled is False for call in calls)
    assert all(call[1]["api_key_override"] == "secret" for call in calls)
    assert baseline.runs == 3
    assert baseline.dimensions["reasoning"].samples == [1.0, 0.5, 1.0]
    assert progress[0] == (1, 3, "running")
    assert progress[-1] == (3, 3, "completed")


def test_collect_quality_baseline_limits_repeat_count():
    target = AuditTarget(
        base_url="https://official.example/v1",
        model="m",
    )

    try:
        asyncio.run(
            collect_quality_baseline(
                target=target,
                api_key="secret",
                runs=6,
            )
        )
    except ValueError as exc:
        assert "capped at 5" in str(exc)
    else:
        raise AssertionError("expected baseline run cap validation")

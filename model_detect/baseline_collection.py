from __future__ import annotations

from collections.abc import Callable

from .audit import run_audit
from .baseline import OfficialBaseline, aggregate_baseline_reports
from .config import AuditConfig
from .models import AuditReport, AuditTarget
from .rules import match_model_rule


BaselineProgress = Callable[[int, int, str], None]


async def collect_quality_baseline(
    *,
    target: AuditTarget,
    api_key: str,
    runs: int = 3,
    profile: str = "standard",
    coding_sandbox_enabled: bool = False,
    progress: BaselineProgress | None = None,
) -> tuple[list[AuditReport], OfficialBaseline]:
    """Run the same native audit suite repeatedly against one trusted endpoint.

    The collector is deliberately sequential. Its purpose is to estimate normal
    black-box variation on a trusted endpoint, not to benchmark throughput.
    """
    if runs < 1:
        raise ValueError("baseline runs must be at least 1")
    if runs > 5:
        raise ValueError("baseline runs are capped at 5 for the lightweight collector")
    if profile not in {"standard", "deep"}:
        raise ValueError("quality baseline profile must be standard or deep")

    reports: list[AuditReport] = []
    for index in range(1, runs + 1):
        if progress:
            progress(index, runs, "running")
        cfg = AuditConfig(
            target=target,
            profile=profile,
            capability_enabled=True,
            proxy_sleuth_enabled=False,
            coding_sandbox_enabled=coding_sandbox_enabled,
        )
        report = await run_audit(
            cfg,
            use_proxy_sleuth=False,
            api_key_override=api_key,
        )
        reports.append(report)
        if progress:
            progress(index, runs, "completed")

    rule = match_model_rule(target.model)
    baseline = aggregate_baseline_reports(
        reports,
        model_rule_id=rule.id,
        model_rule_updated_at=rule.updated_at,
    )
    baseline.metadata.update(
        {
            "collector": "model-detect-native",
            "collector_profile": profile,
            "coding_sandbox_enabled": coding_sandbox_enabled,
            "sequential_collection": True,
        }
    )
    return reports, baseline

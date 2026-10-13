from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable

from .audit import run_audit
from .config import AuditConfig, RegressionAuditConfig
from .models import AuditTarget
from .reporting import write_report
from .validation import ValidationSuite, evaluate_suite, write_validation


def execution_plan(suite: ValidationSuite) -> dict[str, Any]:
    plans = [
        {
            "case_id": case.id,
            "scenario": case.scenario,
            "runs": case.runs,
            "endpoint_configured": bool(case.base_url and case.model),
            "reference_configured": bool(case.reference_id),
            "benchmark_profile": case.benchmark_profile,
            "routing_fraction": case.routing_fraction,
        }
        for case in suite.cases
    ]
    return {
        "suite_id": suite.id,
        "total_audits": sum(item["runs"] for item in plans),
        "cases": plans,
        "notice": (
            "Each audit calls a real API. A mixed_routing percentage must already "
            "be enforced by an external controlled gateway."
        ),
    }


async def run_suite(
    suite: ValidationSuite,
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    max_audits: int = 16,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    plan = execution_plan(suite)
    total = int(plan["total_audits"])
    if not 1 <= max_audits <= 40:
        raise ValueError("max_audits must be between 1 and 40")
    if total > max_audits:
        raise ValueError(
            f"suite would execute {total} paid audits (max_audits={max_audits}); "
            "raise the explicit cap only after checking token usage"
        )

    root = Path(output_dir).resolve()
    manifest = Path(manifest_path).resolve()
    reference_dir = (manifest.parent / suite.reference_dir).resolve()
    # Preflight the entire suite before making any paid requests.
    for case in suite.cases:
        if not case.base_url or not case.model:
            raise ValueError(
                f"{case.id}: base_url and model are required to execute this case"
            )
        if not os.getenv(case.api_key_env):
            raise RuntimeError(
                f"{case.id}: environment variable {case.api_key_env!r} is unset"
            )
        for index in range(1, case.runs + 1):
            target = root / case.id / f"{index:02d}" / "report.json"
            if target.exists():
                raise FileExistsError(
                    f"{case.id} #{index}: report exists; use a new output directory"
                )
    outcomes: list[dict[str, Any]] = []
    position = 0
    for case in suite.cases:
        key = os.environ[case.api_key_env]
        for index in range(1, case.runs + 1):
            position += 1
            if progress:
                progress(case.id, position, total)
            target_dir = root / case.id / f"{index:02d}"
            try:
                cfg = AuditConfig(
                    target=AuditTarget(
                        base_url=case.base_url,
                        model=case.model,
                        api_key_env=case.api_key_env,
                    ),
                    profile=case.profile,
                    reference_id=case.reference_id,
                    reference_dir=str(reference_dir),
                    proxy_sleuth_enabled=False,
                    coding_sandbox_enabled=False,
                    benchmark_profile=case.benchmark_profile,
                    regression=RegressionAuditConfig(enabled=False),
                )
                report = await run_audit(
                    cfg,
                    use_proxy_sleuth=False,
                    api_key_override=key,
                )
                write_report(report, target_dir)
                outcomes.append({
                    "case_id": case.id,
                    "run": index,
                    "status": "completed",
                    "report": str(target_dir / "report.json"),
                })
            except Exception as exc:
                # Do not persist exception messages that may contain provider
                # request headers, tokens, URLs or account details.
                outcomes.append({
                    "case_id": case.id,
                    "run": index,
                    "status": "error",
                    "error_type": type(exc).__name__,
                })

    root.mkdir(parents=True, exist_ok=True)
    (root / "validation-run.json").write_text(
        json.dumps({
            "schema_version": 1,
            "suite_id": suite.id,
            "planned_audits": total,
            "outcomes": outcomes,
            "credentials_persisted": False,
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = evaluate_suite(suite, manifest_path=manifest, output_dir=root)
    write_validation(summary, root)
    return {"plan": plan, "outcomes": outcomes, "summary": summary}

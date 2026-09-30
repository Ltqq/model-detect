from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .adapters import fingerprint, proxy_sleuth
from .config import AuditConfig, get_api_key
from .http_client import AuditHttpClient
from .models import AuditReport, Evidence, ProbeResult
from .probes.protocol import QUICK_PROBES
from .probes.provider import detect_provider_hypotheses
from .scoring import build_summary


ProgressCallback = Callable[[str, int, int], None]


async def run_audit(
    config: AuditConfig,
    *,
    progress: ProgressCallback | None = None,
    use_proxy_sleuth: bool = False,
) -> AuditReport:
    if config.target.protocol != "openai":
        raise NotImplementedError("V0.1 currently implements native probes for OpenAI-compatible APIs")

    api_key = get_api_key(config.target)
    client = AuditHttpClient(
        base_url=config.target.base_url,
        api_key=api_key,
        timeout_seconds=config.target.timeout_seconds,
        extra_headers=config.extra_headers,
    )

    report = AuditReport(
        profile=config.profile,
        target={
            "base_url": config.target.base_url,
            "model": config.target.model,
            "protocol": config.target.protocol,
            "api_key_env": config.target.api_key_env,
        },
    )

    probes = list(QUICK_PROBES)
    total = len(probes)
    for index, probe in enumerate(probes, 1):
        if progress:
            progress(probe.__name__, index, total)
        try:
            results, evidences = await probe(client, config.target.model)
        except Exception as exc:
            results = [
                ProbeResult(
                    probe_id=f"internal.{probe.__name__}",
                    category="internal",
                    status="error",
                    score=None,
                    confidence=1.0,
                    summary=f"{type(exc).__name__}: {exc}",
                )
            ]
            evidences = []
        report.results.extend(results)
        report.evidences.extend(evidences)

    report.provider_hypotheses = detect_provider_hypotheses(report.evidences)

    # Optional OSS multi-layer detector. It never prevents the native audit from finishing.
    if use_proxy_sleuth:
        result, meta = await asyncio.to_thread(
            proxy_sleuth.run_quick,
            base_url=config.target.base_url,
            model=config.target.model,
            api_key=api_key,
            protocol=config.target.protocol,
        )
        report.results.append(result)
        report.adapters["proxy_sleuth"] = meta
    else:
        report.adapters["proxy_sleuth"] = proxy_sleuth.availability()

    # Statistical fingerprint comparison only runs when a trusted reference was supplied.
    if config.fingerprint_reference:
        try:
            result, meta = await asyncio.to_thread(
                fingerprint.verify,
                base_url=config.target.base_url,
                model=config.target.model,
                api_key=api_key,
                reference=config.fingerprint_reference,
            )
            report.results.append(result)
            report.adapters["fingerprint"] = meta
        except Exception as exc:
            report.results.append(
                ProbeResult(
                    probe_id="identity.fingerprint.reference_compare",
                    category="identity",
                    status="error",
                    score=None,
                    confidence=1.0,
                    summary=f"fingerprint adapter failed: {type(exc).__name__}: {exc}",
                    metadata={"engine": "llm-fingerprint-detector"},
                )
            )
            report.adapters["fingerprint"] = {
                **fingerprint.availability(),
                "error": f"{type(exc).__name__}: {exc}",
            }
    else:
        report.adapters["fingerprint"] = {
            **fingerprint.availability(),
            "status": "not_run",
            "reason": "no fingerprint_reference configured",
        }

    report.summary = build_summary(report.results)
    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report

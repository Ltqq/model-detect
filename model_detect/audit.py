from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from .adapters import fingerprint, proxy_sleuth
from .config import AuditConfig, get_api_key
from .http_client import AuditHttpClient
from .models import AuditReport, ProbeResult, ProbeStatus
from .probes.capability import derived_capability_results, run_capability_suite
from .probes.context import run_context_suite
from .probes.coding import run_coding_suite
from .probes.integrity import run_integrity_suite
from .probes.protocol import DEEP_PROBES, QUICK_PROBES, STANDARD_PROBES
from .probes.provider import detect_provider_hypotheses
from .probes.routing import finalize_routing_analysis, run_routing_suite
from .references import ReferenceRegistry, compare_protocol_signature
from .rules import evaluate_rule_expectations, match_model_rule
from .scoring import build_summary


ProgressCallback = Callable[[str, int, int], None]


def _protocol_probe_set(profile: str):
    if profile == "quick":
        return list(QUICK_PROBES)
    if profile == "standard":
        return list(STANDARD_PROBES)
    if profile == "deep":
        return list(DEEP_PROBES)
    raise ValueError(f"unsupported profile: {profile!r}; use quick, standard or deep")


def _rule_results(model: str, results: list[ProbeResult]) -> list[ProbeResult]:
    by_id = {r.probe_id: r for r in results}
    reasoning_values = [
        r.metadata.get("reasoning_effort_supported")
        for r in results
        if "reasoning_effort_supported" in r.metadata
    ]
    reasoning_observed = (
        True if any(x is True for x in reasoning_values)
        else (False if reasoning_values else None)
    )
    thinking_probe = by_id.get("protocol.thinking.disable")
    observations = {
        "reasoning_effort": reasoning_observed,
        "tools": (
            by_id.get("protocol.tools.basic").status == ProbeStatus.PASS
            if by_id.get("protocol.tools.basic")
            else None
        ),
        "json_schema": (
            by_id.get("protocol.json_schema").status == ProbeStatus.PASS
            if by_id.get("protocol.json_schema")
            else None
        ),
        "disable_thinking": (
            thinking_probe.metadata.get("disable_thinking_supported")
            if thinking_probe else None
        ),
    }
    out = []
    for item in evaluate_rule_expectations(model, observations):
        status = ProbeStatus(item["status"])
        score = {
            ProbeStatus.PASS: 1.0,
            ProbeStatus.WARN: 0.7,
            ProbeStatus.FAIL: 0.0,
        }.get(status)
        out.append(
            ProbeResult(
                probe_id=f"identity.family_features.{item['feature']}",
                category="identity",
                status=status,
                score=score,
                confidence=0.75,
                summary=(
                    f"model rule {item['rule_id']}: {item['feature']} "
                    f"expected={item['expected']} observed={item['observed']}"
                ),
                expected=item["expected"],
                observed=item["observed"],
                metadata={
                    "rule_id": item["rule_id"],
                    "strict": item["strict"],
                    "feature": item["feature"],
                    "identity_strength": "weak",
                },
            )
        )
    return out


async def run_audit(
    config: AuditConfig,
    *,
    progress: ProgressCallback | None = None,
    use_proxy_sleuth: bool | None = None,
    api_key_override: str | None = None,
) -> AuditReport:
    if config.target.protocol != "openai":
        raise NotImplementedError(
            "V1 native probes currently target OpenAI-compatible APIs; "
            "other protocols can still be inspected through proxy-sleuth."
        )

    profile = (config.profile or "quick").lower()
    api_key = get_api_key(config.target, api_key_override)
    client = AuditHttpClient(
        base_url=config.target.base_url,
        api_key=api_key,
        timeout_seconds=config.target.timeout_seconds,
        extra_headers=config.extra_headers,
    )
    report = AuditReport(
        profile=profile,
        target={
            "base_url": config.target.base_url,
            "model": config.target.model,
            "protocol": config.target.protocol,
            "api_key_env": config.target.api_key_env,
            "declared_context_tokens": config.declared_context_tokens,
        },
    )

    phase_names = [
        "protocol",
        "integrity",
        "context",
        "routing",
        "capability",
        "reference",
        "oss",
    ]
    phase_no = 0

    # 1. Native protocol probes.
    probes = _protocol_probe_set(profile)
    for index, probe in enumerate(probes, 1):
        if progress:
            progress(f"protocol:{probe.__name__}", index, len(probes))
        try:
            results, evidences = await probe(client, config.target.model)
        except Exception as exc:
            results = [
                ProbeResult(
                    probe_id=f"internal.{probe.__name__}",
                    category="internal",
                    status=ProbeStatus.ERROR,
                    score=None,
                    confidence=1.0,
                    summary=f"{type(exc).__name__}: {exc}",
                )
            ]
            evidences = []
        report.results.extend(results)
        report.evidences.extend(evidences)

    # 2. Parameter integrity.
    if progress:
        progress("integrity-suite", 2, len(phase_names))
    rs, evs = await run_integrity_suite(
        client, config.target.model, profile=profile
    )
    report.results.extend(rs)
    report.evidences.extend(evs)

    # 3. Context integrity.
    if progress:
        progress("context-suite", 3, len(phase_names))
    rs, evs = await run_context_suite(
        client,
        config.target.model,
        profile=profile,
        declared_context_tokens=config.declared_context_tokens,
    )
    report.results.extend(rs)
    report.evidences.extend(evs)

    # 4. Routing stability.
    if progress:
        progress("routing-suite", 4, len(phase_names))
    rs, evs = await run_routing_suite(
        client, config.target.model, profile=profile
    )
    report.results.extend(rs)
    report.evidences.extend(evs)

    # 5. Capability Lite.
    if config.capability_enabled:
        if progress:
            progress("capability-suite", 5, len(phase_names))
        rs, evs = await run_capability_suite(
            client, config.target.model, profile=profile
        )
        report.results.extend(rs)
        report.evidences.extend(evs)
        if profile != "quick":
            report.results.extend(derived_capability_results(report.results))

        if config.coding_sandbox_enabled and profile != "quick":
            if progress:
                progress("coding-sandbox", 6, 8)
            coding_results, coding_evidence, coding_meta = await run_coding_suite(
                client,
                config.target.model,
                profile=profile,
                auto_pull=config.coding_sandbox_auto_pull,
            )
            report.results.extend(coding_results)
            report.evidences.extend(coding_evidence)
            report.adapters["coding_sandbox"] = coding_meta
        else:
            report.adapters["coding_sandbox"] = {
                "status": "disabled",
                "reason": (
                    "quick profile"
                    if profile == "quick"
                    else "coding_sandbox_enabled=false"
                ),
            }

    # Provider inference uses all native raw responses.
    report.provider_hypotheses = detect_provider_hypotheses(report.evidences)

    # Model-family rule comparison.
    rule = match_model_rule(config.target.model)
    report.adapters["model_rule"] = rule.model_dump(mode="json")
    report.results.extend(_rule_results(config.target.model, report.results))

    # 6. Reference Registry and statistical fingerprint.
    reference_fingerprint = config.fingerprint_reference
    if config.reference_id:
        registry = ReferenceRegistry(config.reference_dir)
        manifest = registry.get(config.reference_id)
        report.adapters["reference"] = manifest.model_dump(mode="json")
        report.results.append(
            compare_protocol_signature(
                report.results,
                registry.signature(manifest),
            )
        )
        fp_reference = registry.fingerprint_reference_value(manifest)
        if fp_reference:
            reference_fingerprint = fp_reference
    else:
        report.adapters["reference"] = {"status": "not_configured"}

    if reference_fingerprint:
        try:
            if progress:
                progress("fingerprint-reference", 6, len(phase_names))
            fingerprint_preset = (
                "quick" if profile == "quick"
                else ("standard" if profile == "standard" else "strict")
            )
            fingerprint_results, meta = await asyncio.to_thread(
                fingerprint.verify,
                base_url=config.target.base_url,
                model=config.target.model,
                api_key=api_key,
                reference=reference_fingerprint,
                preset=fingerprint_preset,
            )
            report.results.extend(fingerprint_results)
            report.adapters["fingerprint"] = meta
        except Exception as exc:
            report.results.append(
                ProbeResult(
                    probe_id="identity.fingerprint.reference_compare",
                    category="identity",
                    status=ProbeStatus.ERROR,
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
            "reason": "no trusted fingerprint reference configured",
        }

    # 7. proxy-sleuth multi-layer OSS augmentation.
    effective_proxy_sleuth = (
        config.proxy_sleuth_enabled
        if use_proxy_sleuth is None
        else use_proxy_sleuth
    )
    if effective_proxy_sleuth:
        if progress:
            progress("proxy-sleuth", 7, len(phase_names))
        mode = "quick" if profile == "quick" else ("standard" if profile == "standard" else "full")
        oss_results, meta = await asyncio.to_thread(
            proxy_sleuth.run,
            base_url=config.target.base_url,
            model=config.target.model,
            api_key=api_key,
            protocol=config.target.protocol,
            mode=mode,
        )
        report.results.extend(oss_results)
        report.adapters["proxy_sleuth"] = meta
    else:
        report.adapters["proxy_sleuth"] = {
            **proxy_sleuth.availability(),
            "status": "disabled",
        }

    # Final routing verdict is computed after fingerprint/proxy-sleuth signals exist.
    report.results.append(finalize_routing_analysis(report.results))

    report.summary = build_summary(report.results)
    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report

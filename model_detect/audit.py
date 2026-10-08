from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Callable

from .adapters import fingerprint, proxy_sleuth
from .config import AuditConfig, get_api_key
from .http_client import AuditHttpClient
from .models import AuditReport, AuditSummary, ProbeResult, ProbeStatus
from .probes.capability import derived_capability_results, run_capability_suite
from .probes.context import run_context_suite
from .probes.coding import run_coding_suite
from .probes.integrity import run_integrity_suite
from .probes.protocol import DEEP_PROBES, QUICK_PROBES, STANDARD_PROBES
from .probes.provider import detect_provider_hypotheses, evaluate_upstream_policy
from .probes.routing import finalize_routing_analysis, run_routing_suite
from .references import ReferenceRegistry, compare_protocol_signature
from .regression_promptfoo import run_regression_file
from .rules import evaluate_rule_expectations, match_model_rule
from .scoring import build_summary


ProgressCallback = Callable[[str, int, int], None]


def _invalid_target_reason(evidences) -> str | None:
    for evidence in evidences:
        if evidence.response_status != 200:
            continue
        content_type = str(
            evidence.response_headers.get("content-type", "")
        ).lower()
        body = evidence.response_body
        body_text = body if isinstance(body, str) else ""
        looks_html = (
            "text/html" in content_type
            or body_text.lstrip().lower().startswith("<!doctype html")
            or body_text.lstrip().lower().startswith("<html")
        )
        if looks_html:
            return (
                "target returned HTML instead of a model API response; "
                "check that Base URL includes the API prefix such as /v1"
            )
    return None



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


async def _run_regression_suites(
    report: AuditReport,
    config: AuditConfig,
    api_key: str,
    regression_files: list[str | Path],
    *,
    output_dir: str | Path | None = None,
    progress: ProgressCallback | None = None,
) -> None:
    if not regression_files:
        report.adapters["promptfoo_regression"] = {
            "status": "not_configured",
            "suites": [],
        }
        return

    root = Path(
        output_dir
        or (
            Path(config.output_dir)
            / "_regression_runs"
            / uuid.uuid4().hex
        )
    )
    root.mkdir(parents=True, exist_ok=True)

    suites: list[dict[str, object]] = []
    for index, regression_file in enumerate(regression_files, 1):
        if progress:
            progress("regression-suite", index, len(regression_files))
        suite_dir = root / f"{index:02d}"
        try:
            results, meta = await asyncio.to_thread(
                run_regression_file,
                regression_file,
                base_url=config.target.base_url,
                model=config.target.model,
                api_key=api_key,
                output_dir=suite_dir,
            )
            report.results.extend(results)
            suites.append(
                {
                    **meta,
                    "status": "completed",
                }
            )
        except Exception as exc:
            suites.append(
                {
                    "status": "error",
                    "regression_file": str(regression_file),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            report.results.append(
                ProbeResult(
                    probe_id=f"internal.regression.{index}",
                    category="internal",
                    status=ProbeStatus.ERROR,
                    score=None,
                    confidence=1.0,
                    summary=(
                        "regression suite failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    metadata={
                        "engine": "promptfoo",
                        "regression_file": str(regression_file),
                    },
                )
            )

    report.adapters["promptfoo_regression"] = {
        "status": (
            "completed"
            if all(item.get("status") == "completed" for item in suites)
            else "partial"
        ),
        "artifact_root": str(root),
        "suites": suites,
    }


async def run_audit(
    config: AuditConfig,
    *,
    progress: ProgressCallback | None = None,
    use_proxy_sleuth: bool | None = None,
    api_key_override: str | None = None,
    regression_files: list[str | Path] | None = None,
    regression_output_dir: str | Path | None = None,
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
        model=config.target.model,
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

        if index == 1:
            invalid_target = _invalid_target_reason(evidences)
            if invalid_target:
                report.results.append(
                    ProbeResult(
                        probe_id="target.api.preflight",
                        category="target",
                        status=ProbeStatus.FAIL,
                        score=None,
                        confidence=1.0,
                        summary=invalid_target,
                        evidence_ids=[e.id for e in evidences],
                        metadata={"invalid_target": True},
                    )
                )
                report.adapters["target_validation"] = {
                    "status": "invalid_target",
                    "reason": invalid_target,
                }
                report.summary = AuditSummary(
                    overall_score=None,
                    final_verdict="invalid_target",
                    confidence="high",
                    warnings=[invalid_target],
                )
                report.finished_at = datetime.now(timezone.utc).isoformat()
                return report

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

    if config.upstream_policy.disallowed:
        policy_result = evaluate_upstream_policy(
            report.evidences,
            report.provider_hypotheses,
            disallowed=config.upstream_policy.disallowed,
            min_confidence=config.upstream_policy.min_confidence,
            strong_signal_weight=config.upstream_policy.strong_signal_weight,
        )
        report.results.append(policy_result)
        report.adapters["upstream_policy"] = {
            "status": (
                "violation"
                if policy_result.metadata.get("policy_violation")
                else "clear"
            ),
            "config": config.upstream_policy.model_dump(mode="json"),
            "observed": policy_result.observed,
        }
    else:
        report.adapters["upstream_policy"] = {
            "status": "not_configured",
            "config": config.upstream_policy.model_dump(mode="json"),
        }

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

    # 8. Declarative regression suites. These are supporting protocol/integrity
    # checks only; mapped results explicitly carry identity_strength=none.
    effective_regression_files = (
        list(regression_files)
        if regression_files is not None
        else config.regression.suites_for(profile)
    )
    await _run_regression_suites(
        report,
        config,
        api_key,
        effective_regression_files,
        output_dir=regression_output_dir,
        progress=progress,
    )

    # Final routing verdict is computed after fingerprint/proxy-sleuth signals exist.
    report.results.append(finalize_routing_analysis(report.results))

    report.summary = build_summary(report.results)
    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report

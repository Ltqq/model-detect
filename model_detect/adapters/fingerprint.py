from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..models import ProbeResult, ProbeStatus


PINNED_FINGERPRINT_VERSION = "0.1.0"
MIN_COMPARABLE_CELLS = 4


def _installed_version(binary: str) -> str | None:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def availability() -> dict[str, Any]:
    direct = shutil.which("llm-fingerprint")
    npx = shutil.which("npx")
    direct_version = _installed_version(direct) if direct else None
    direct_compatible = bool(direct and direct_version == PINNED_FINGERPRINT_VERSION)
    can_use_pinned_npx = bool(not direct and npx)
    return {
        "available": direct_compatible or can_use_pinned_npx,
        "executable_found": bool(direct or npx),
        "direct_binary": direct,
        "installed_version": direct_version,
        "version_compatible": direct_compatible if direct else None,
        "npx": npx,
        "engine": "ToseaAI/llm-fingerprint-detector",
        "pinned_package_version": PINNED_FINGERPRINT_VERSION,
        "requires_network_if_downloaded": can_use_pinned_npx,
        "structured_json": True,
    }


def _prefix() -> list[str]:
    direct = shutil.which("llm-fingerprint")
    if direct:
        installed_version = _installed_version(direct)
        if installed_version != PINNED_FINGERPRINT_VERSION:
            raise RuntimeError(
                "llm-fingerprint CLI version mismatch; "
                f"required {PINNED_FINGERPRINT_VERSION}, found "
                f"{installed_version or 'unknown'}"
            )
        return [direct]
    npx = shutil.which("npx")
    if npx:
        # Pin the package explicitly; never resolve an unversioned latest release.
        return [
            npx,
            "--yes",
            f"llm-fingerprint-detector@{PINNED_FINGERPRINT_VERSION}",
        ]
    raise RuntimeError(
        "llm-fingerprint-detector is unavailable; install Node.js/npm or "
        f"the llm-fingerprint CLI version {PINNED_FINGERPRINT_VERSION}"
    )


def _run_json(
    cmd: list[str],
    *,
    api_key: str | None = None,
    timeout_seconds: float = 900,
    accepted_codes: set[int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    env = dict(os.environ)
    if api_key:
        env["LLM_FINGERPRINT_API_KEY"] = api_key
    proc = subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    accepted = accepted_codes or {0}
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if proc.returncode not in accepted:
        raise RuntimeError(
            f"llm-fingerprint failed (exit {proc.returncode}); subprocess logs hidden"
        )
    try:
        data = json.loads(stdout)
    except Exception as exc:
        raise RuntimeError(
            "llm-fingerprint returned invalid JSON; subprocess text hidden"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError("llm-fingerprint JSON root is not an object")
    return data, {
        "returncode": proc.returncode,
        "stderr_tail": "",
        "stderr_present": bool(stderr),
    }


def fingerprint_metadata_from_data(data: dict[str, Any]) -> dict[str, Any]:
    cells = data.get("cells") if isinstance(data.get("cells"), dict) else {}
    return {
        "format_version": data.get("formatVersion"),
        "protocol": data.get("protocol"),
        "model": data.get("model"),
        "collected_at": data.get("collectedAt"),
        "samples_per_cell": data.get("samplesPerCell"),
        "cell_count": len(cells),
        "post_reasoning": bool(data.get("postReasoning", False)),
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
    }


def fingerprint_metadata(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fingerprint artifact root must be an object")
    return fingerprint_metadata_from_data(raw)


def collect(
    *,
    base_url: str,
    model: str,
    api_key: str,
    output: str | Path,
    timeout_seconds: float = 1200,
    preset: str = "standard",
) -> dict[str, Any]:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = _prefix() + [
        "fingerprint",
        "--base-url", base_url,
        "--model", model,
        "--out", str(out),
        "--api-key-env", "LLM_FINGERPRINT_API_KEY",
        "--preset", preset,
        "--json",
        "--quiet",
    ]
    data, process_meta = _run_json(
        cmd,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        accepted_codes={0},
    )
    if not out.exists():
        raise RuntimeError("fingerprint collection succeeded but output artifact is missing")

    fp = data.get("fingerprint")
    run = data.get("run")
    if not isinstance(fp, dict) or not isinstance(run, dict):
        raise RuntimeError("fingerprint JSON is missing fingerprint/run fields")

    return {
        "engine": "llm-fingerprint-detector",
        **process_meta,
        "path": str(out),
        "fingerprint": fingerprint_metadata_from_data(fp),
        "split_half_jsd": run.get("splitHalfJsd"),
        "adapter": run.get("adapter"),
        "error_count": run.get("errorCount"),
        "duration_ms": run.get("durationMs"),
        "warning_count": len(run.get("warnings") or []),
        "warnings": [],
    }


def list_bundled_references(timeout_seconds: float = 60) -> dict[str, Any]:
    cmd = _prefix() + ["references", "--json", "--quiet"]
    data, process_meta = _run_json(
        cmd,
        timeout_seconds=timeout_seconds,
        accepted_codes={0},
    )
    return {
        **process_meta,
        "source": data.get("source"),
        "references": data.get("references") or [],
    }


def _self_consistency_result(split_half_jsd: Any) -> ProbeResult:
    """Preserve split-half JSD as a raw statistic; no local threshold is calibrated."""
    probe_id = "identity.self_consistency"
    try:
        value = float(split_half_jsd)
        if not math.isfinite(value) or value < 0:
            raise ValueError("split-half JSD must be finite and non-negative")
    except (TypeError, ValueError):
        return ProbeResult(
            probe_id=probe_id,
            category="identity",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            confidence=None,
            summary="fingerprint split-half JSD unavailable; no consistency conclusion",
            observed={"split_half_jsd": split_half_jsd},
            metadata={
                "identity_strength": "weak",
                "signal": "split-half-jsd",
                "not_calibrated": True,
                "mixed_routing_proof": False,
            },
        )

    return ProbeResult(
        probe_id=probe_id,
        category="identity",
        status=ProbeStatus.INSUFFICIENT,
        score=None,
        confidence=None,
        summary=(
            f"split-half JSD={value:.3f} is retained as a raw statistic; "
            "this project has no calibrated cutoff for it"
        ),
        observed={"split_half_jsd": value},
        metadata={
            "identity_strength": "weak",
            "signal": "split-half-jsd",
            "not_calibrated": True,
            "mixed_routing_proof": False,
        },
    )


def parse_verify_payload(
    data: dict[str, Any],
    *,
    returncode: int = 0,
) -> tuple[list[ProbeResult], dict[str, Any]]:
    raw_verdict = str(data.get("verdict") or "insufficient").lower()
    verdict = raw_verdict
    comparison = data.get("comparison") if isinstance(data.get("comparison"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    target_fp = target.get("fingerprint") if isinstance(target.get("fingerprint"), dict) else {}
    reference = data.get("reference") if isinstance(data.get("reference"), dict) else {}
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []

    mean_jsd = data.get("meanJsd", comparison.get("meanJsd"))
    cells = comparison.get("cells") if isinstance(comparison.get("cells"), list) else []
    comparable_raw = comparison.get("comparableCellCount")
    try:
        comparable = int(comparable_raw)
    except (TypeError, ValueError):
        comparable = 0
    split_half = target.get("splitHalfJsd")

    target_protocol = target_fp.get("protocol")
    reference_protocol = reference.get("protocol")
    protocol_mismatch = (
        comparison.get("protocolMismatch") is True
        or not isinstance(target_protocol, str)
        or not target_protocol
        or not isinstance(reference_protocol, str)
        or not reference_protocol
        or target_protocol != reference_protocol
    )

    try:
        numeric_mean_jsd = float(mean_jsd)
        valid_mean_jsd = math.isfinite(numeric_mean_jsd) and 0 <= numeric_mean_jsd <= 1
    except (TypeError, ValueError):
        numeric_mean_jsd = None
        valid_mean_jsd = False

    validation_reasons: list[str] = []
    if raw_verdict in {"match", "mismatch", "uncertain"}:
        if protocol_mismatch:
            validation_reasons.append("target/reference fingerprint protocols are missing or incompatible")
        if comparable < MIN_COMPARABLE_CELLS or len(cells) < MIN_COMPARABLE_CELLS:
            validation_reasons.append(
                f"fewer than {MIN_COMPARABLE_CELLS} comparable fingerprint cells"
            )
        if not valid_mean_jsd:
            validation_reasons.append("mean JSD is missing or invalid")
        if validation_reasons:
            verdict = "insufficient"

    status_map = {
        "match": ProbeStatus.PASS,
        # A distribution mismatch may reflect model replacement, version drift,
        # hidden prompts, sampling conditions, or serving changes. It is a review
        # signal, not proof of fraud or wrong weights.
        "mismatch": ProbeStatus.WARN,
        "uncertain": ProbeStatus.WARN,
        "insufficient": ProbeStatus.INSUFFICIENT,
    }
    status = status_map.get(verdict, ProbeStatus.ERROR)
    mean_text = (
        f", mean JSD={numeric_mean_jsd:.3f}"
        if valid_mean_jsd and numeric_mean_jsd is not None
        else ""
    )
    summaries = {
        "match": (
            "behavioral output distribution is close to the selected reference"
            f"{mean_text}; this does not prove model-weight identity"
        ),
        "mismatch": (
            "behavioral output distribution differs from the selected reference"
            f"{mean_text}; review reference age, prompt, sampling, model update, "
            "quantization, and routing before drawing conclusions"
        ),
        "uncertain": (
            "behavioral fingerprint comparison is uncertain"
            f"{mean_text}; repeat with more valid samples and a compatible reference"
        ),
        "insufficient": (
            "behavioral fingerprint evidence is insufficient"
            + (": " + "; ".join(validation_reasons) if validation_reasons else "")
        ),
    }
    summary = summaries.get(verdict, "fingerprint tool returned an unknown verdict")

    primary = ProbeResult(
        probe_id="identity.fingerprint.reference_compare",
        category="identity",
        status=status,
        # Do not turn the external verdict into an invented 0–100 capability score.
        score=None,
        confidence=None,
        summary=summary,
        observed={
            "verdict": verdict,
            "raw_verdict": raw_verdict,
            "mean_jsd": numeric_mean_jsd if valid_mean_jsd else mean_jsd,
            "comparable_cell_count": comparable,
            "cells": cells,
            "protocol_mismatch": protocol_mismatch,
            "validation_reasons": validation_reasons,
            "thresholds": comparison.get("thresholds"),
            "baselines": comparison.get("baselines"),
            "target_split_half_jsd": split_half,
            "target_adapter": target.get("adapter"),
            "target_fingerprint": fingerprint_metadata_from_data(target_fp),
            "reference_fingerprint": fingerprint_metadata_from_data(reference),
            "warnings": warnings,
        },
        metadata={
            "verdict": verdict,
            "raw_verdict": raw_verdict,
            "engine": "llm-fingerprint-detector",
            "identity_strength": "weak",
            "evidence_type": "behavioral_distribution_comparison",
            "weight_identity_proof": False,
            "not_calibrated_for_model_detect_targets": True,
            "per_cell_jsd": True,
        },
    )
    # Split-half JSD is the same statistic used to assess endpoint self-consistency.
    # Do not duplicate it as an independent routing detector or apply an uncalibrated
    # routing threshold.
    results = [primary, _self_consistency_result(split_half)]
    meta = {
        "available": True,
        "engine": "llm-fingerprint-detector",
        "returncode": returncode,
        "verdict": verdict,
        "raw_verdict": raw_verdict,
        "mean_jsd": numeric_mean_jsd if valid_mean_jsd else mean_jsd,
        "comparable_cell_count": comparable,
        "per_cell": cells,
        "split_half_jsd": split_half,
        "adapter": target.get("adapter"),
        "warnings": warnings,
        "validation_reasons": validation_reasons,
        "target_fingerprint": fingerprint_metadata_from_data(target_fp),
        "reference_fingerprint": fingerprint_metadata_from_data(reference),
        "protocol_mismatch": protocol_mismatch,
        "thresholds": comparison.get("thresholds"),
        "baselines": comparison.get("baselines"),
        "weight_identity_proof": False,
    }
    return results, meta


def verify(
    *,
    base_url: str,
    model: str,
    api_key: str,
    reference: str,
    timeout_seconds: float = 1200,
    preset: str = "standard",
) -> tuple[list[ProbeResult], dict[str, Any]]:
    cmd = _prefix() + [
        "verify",
        "--base-url", base_url,
        "--model", model,
        "--reference", reference,
        "--api-key-env", "LLM_FINGERPRINT_API_KEY",
        "--preset", preset,
        "--json",
        "--quiet",
    ]
    data, process_meta = _run_json(
        cmd,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        accepted_codes={0, 2, 3, 4},
    )
    results, meta = parse_verify_payload(
        data,
        returncode=int(process_meta["returncode"]),
    )
    meta["stderr_suppressed"] = process_meta.get("stderr_suppressed", False)
    return results, meta

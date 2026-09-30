from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..models import ProbeResult, ProbeStatus


SELF_MATCH_THRESHOLD = 0.25
SELF_WARN_THRESHOLD = 0.35


def availability() -> dict[str, Any]:
    direct = shutil.which("llm-fingerprint")
    npx = shutil.which("npx")
    return {
        "available": bool(direct or npx),
        "direct_binary": direct,
        "npx": npx,
        "engine": "ToseaAI/llm-fingerprint-detector",
        "structured_json": True,
    }


def _prefix() -> list[str]:
    direct = shutil.which("llm-fingerprint")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "llm-fingerprint-detector"]
    raise RuntimeError(
        "llm-fingerprint-detector is unavailable; install Node.js/npm or the llm-fingerprint CLI"
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
            f"llm-fingerprint failed (exit {proc.returncode}): {(stdout + chr(10) + stderr)[-1800:]}"
        )
    try:
        data = json.loads(stdout)
    except Exception as exc:
        raise RuntimeError(
            f"llm-fingerprint returned invalid JSON: {exc}; stdout={stdout[-1200:]!r}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError("llm-fingerprint JSON root is not an object")
    return data, {
        "returncode": proc.returncode,
        "stderr_tail": stderr[-4000:],
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
        "warnings": run.get("warnings") or [],
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
    probe_id = "identity.self_consistency"
    try:
        value = float(split_half_jsd)
    except (TypeError, ValueError):
        return ProbeResult(
            probe_id=probe_id,
            category="identity",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            confidence=0.0,
            summary="fingerprint split-half JSD is unavailable",
            observed={"split_half_jsd": split_half_jsd},
            metadata={"identity_strength": "weak"},
        )

    if value <= SELF_MATCH_THRESHOLD:
        status = ProbeStatus.PASS
        score = 1.0
        label = "stable"
    elif value <= SELF_WARN_THRESHOLD:
        status = ProbeStatus.WARN
        score = 0.6
        label = "suspicious"
    else:
        status = ProbeStatus.WARN
        score = 0.3
        label = "unstable"

    return ProbeResult(
        probe_id=probe_id,
        category="identity",
        status=status,
        score=score,
        confidence=0.75,
        summary=f"fingerprint self-consistency={label}, split-half JSD={value:.3f}",
        observed={
            "split_half_jsd": value,
            "thresholds": {
                "stable_max": SELF_MATCH_THRESHOLD,
                "suspicious_max": SELF_WARN_THRESHOLD,
            },
        },
        metadata={
            "identity_strength": "weak",
            "self_consistency": label,
            "does_not_imply_identity_mismatch": True,
        },
    )


def _routing_consistency_result(split_half_jsd: Any) -> ProbeResult:
    probe_id = "routing.fingerprint.consistency"
    try:
        value = float(split_half_jsd)
    except (TypeError, ValueError):
        return ProbeResult(
            probe_id=probe_id,
            category="routing",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            confidence=0.0,
            summary="fingerprint split-half JSD is unavailable for routing analysis",
            observed={"split_half_jsd": split_half_jsd},
        )

    if value <= SELF_MATCH_THRESHOLD:
        status = ProbeStatus.PASS
        score = 1.0
        verdict = "stable"
    elif value <= SELF_WARN_THRESHOLD:
        status = ProbeStatus.WARN
        score = 0.6
        verdict = "suspicious"
    else:
        status = ProbeStatus.WARN
        score = 0.3
        verdict = "unstable"

    return ProbeResult(
        probe_id=probe_id,
        category="routing",
        status=status,
        score=score,
        confidence=0.7,
        summary=f"fingerprint routing consistency={verdict}, split-half JSD={value:.3f}",
        observed={
            "split_half_jsd": value,
            "thresholds": {
                "stable_max": SELF_MATCH_THRESHOLD,
                "suspicious_max": SELF_WARN_THRESHOLD,
            },
        },
        metadata={
            "verdict": verdict,
            "signal": "split-half-jsd",
            "mixed_routing_proof": False,
        },
    )


def parse_verify_payload(
    data: dict[str, Any],
    *,
    returncode: int = 0,
) -> tuple[list[ProbeResult], dict[str, Any]]:
    verdict = str(data.get("verdict") or "insufficient").lower()
    comparison = data.get("comparison") if isinstance(data.get("comparison"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    target_fp = target.get("fingerprint") if isinstance(target.get("fingerprint"), dict) else {}
    reference = data.get("reference") if isinstance(data.get("reference"), dict) else {}
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []

    mean_jsd = data.get("meanJsd", comparison.get("meanJsd"))
    cells = comparison.get("cells") if isinstance(comparison.get("cells"), list) else []
    comparable = comparison.get("comparableCellCount")
    split_half = target.get("splitHalfJsd")

    status_map = {
        "match": ProbeStatus.PASS,
        "mismatch": ProbeStatus.FAIL,
        "uncertain": ProbeStatus.WARN,
        "insufficient": ProbeStatus.INSUFFICIENT,
    }
    score_map = {
        "match": 1.0,
        "uncertain": 0.5,
        "mismatch": 0.0,
        "insufficient": None,
    }
    status = status_map.get(verdict, ProbeStatus.ERROR)
    mean_text = ""
    try:
        mean_text = f", mean JSD={float(mean_jsd):.3f}"
    except (TypeError, ValueError):
        pass

    primary = ProbeResult(
        probe_id="identity.fingerprint.reference_compare",
        category="identity",
        status=status,
        score=score_map.get(verdict),
        confidence=0.9 if verdict in {"match", "mismatch"} else 0.6,
        summary=f"statistical fingerprint verdict={verdict}{mean_text}",
        observed={
            "verdict": verdict,
            "mean_jsd": mean_jsd,
            "comparable_cell_count": comparable,
            "cells": cells,
            "protocol_mismatch": comparison.get("protocolMismatch"),
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
            "engine": "llm-fingerprint-detector",
            "identity_strength": "strong",
            "per_cell_jsd": True,
        },
    )
    results = [
        primary,
        _self_consistency_result(split_half),
        _routing_consistency_result(split_half),
    ]
    meta = {
        "available": True,
        "engine": "llm-fingerprint-detector",
        "returncode": returncode,
        "verdict": verdict,
        "mean_jsd": mean_jsd,
        "comparable_cell_count": comparable,
        "per_cell": cells,
        "split_half_jsd": split_half,
        "adapter": target.get("adapter"),
        "warnings": warnings,
        "target_fingerprint": fingerprint_metadata_from_data(target_fp),
        "reference_fingerprint": fingerprint_metadata_from_data(reference),
        "protocol_mismatch": comparison.get("protocolMismatch"),
        "thresholds": comparison.get("thresholds"),
        "baselines": comparison.get("baselines"),
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
    meta["stderr_tail"] = process_meta.get("stderr_tail", "")
    return results, meta

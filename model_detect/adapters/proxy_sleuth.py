from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..models import ProbeResult, ProbeStatus


LAYER_CATEGORY = {
    "param_integrity": "integrity",
    "context_truncation": "context",
    "api_features": "protocol",
    "knowledge_probes": "identity",
    "statistical": "identity",
    "capability": "capability",
    "mixed_routing": "routing",
}


def availability() -> dict:
    binary = shutil.which("proxy-sleuth")
    return {
        "available": bool(binary),
        "binary": binary,
        "engine": "Babapei/proxy-sleuth",
    }


def _status(verdict: str) -> ProbeStatus:
    value = verdict.upper()
    if value == "MATCH":
        return ProbeStatus.PASS
    if value == "MISMATCH":
        return ProbeStatus.FAIL
    if value in {"SUSPICIOUS", "INCONCLUSIVE"}:
        return ProbeStatus.WARN
    if value in {"NOT_RUN", "NOT_AVAILABLE"}:
        return ProbeStatus.SKIPPED
    return ProbeStatus.INSUFFICIENT


def run(
    *,
    base_url: str,
    model: str,
    api_key: str,
    protocol: str = "openai",
    mode: str = "quick",
    timeout_seconds: float = 900,
) -> tuple[list[ProbeResult], dict]:
    binary = shutil.which("proxy-sleuth")
    if not binary:
        return (
            [
                ProbeResult(
                    probe_id="oss.proxy_sleuth",
                    category="identity",
                    status=ProbeStatus.SKIPPED,
                    score=None,
                    confidence=0.0,
                    summary="proxy-sleuth is not installed; optional OSS layers skipped",
                    metadata={"engine": "proxy-sleuth"},
                )
            ],
            availability(),
        )

    env = dict(os.environ)
    env["PROXY_SLEUTH_KEY"] = api_key
    with tempfile.TemporaryDirectory(prefix="model-detect-") as tmp:
        out = Path(tmp) / "proxy-sleuth.json"
        cmd = [
            binary,
            "detect",
            "--endpoint",
            base_url,
            "--model",
            model,
            "--protocol",
            protocol,
            "--mode",
            mode,
            "--output",
            "json",
            "--output-file",
            str(out),
        ]
        proc = subprocess.run(
            cmd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        data: dict[str, Any] | None = None
        if out.exists():
            try:
                data = json.loads(out.read_text(encoding="utf-8"))
            except Exception:
                data = None

    stream_text = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-6000:]
    if not isinstance(data, dict):
        return (
            [
                ProbeResult(
                    probe_id="oss.proxy_sleuth",
                    category="identity",
                    status=ProbeStatus.ERROR,
                    score=None,
                    confidence=0.4,
                    summary=f"proxy-sleuth did not produce parseable JSON (exit {proc.returncode})",
                    metadata={"engine": "proxy-sleuth"},
                )
            ],
            {
                **availability(),
                "returncode": proc.returncode,
                "stdout_tail": stream_text,
            },
        )

    results: list[ProbeResult] = []
    for layer in data.get("layers", []) or []:
        if not isinstance(layer, dict):
            continue
        name = str(layer.get("layer") or layer.get("name") or "unknown")
        category = LAYER_CATEGORY.get(name, "identity")
        verdict = str(layer.get("verdict") or "INCONCLUSIVE")
        score = layer.get("overall_score", layer.get("score"))
        try:
            score = float(score) if score is not None else None
        except Exception:
            score = None
        results.append(
            ProbeResult(
                probe_id=f"oss.proxy_sleuth.{name}",
                category=category,
                status=_status(verdict),
                score=score,
                confidence=0.75,
                summary=f"proxy-sleuth {name}: {verdict}",
                observed=layer,
                metadata={
                    "engine": "proxy-sleuth",
                    "layer": name,
                    "verdict": verdict.lower(),
                    "identity_strength": (
                        "strong" if name == "statistical"
                        else ("medium" if name == "knowledge_probes" else "weak")
                    ),
                },
            )
        )

    if not results:
        verdict = str(data.get("verdict") or "INCONCLUSIVE")
        score = data.get("overall_score")
        try:
            score = float(score) if score is not None else None
        except Exception:
            score = None
        results.append(
            ProbeResult(
                probe_id="oss.proxy_sleuth.overall",
                category="identity",
                status=_status(verdict),
                score=score,
                confidence=0.65,
                summary=f"proxy-sleuth overall verdict={verdict}",
                observed=data,
                metadata={"engine": "proxy-sleuth", "verdict": verdict.lower(), "identity_strength": "medium"},
            )
        )

    return (
        results,
        {
            **availability(),
            "returncode": proc.returncode,
            "mode": mode,
            "verdict": data.get("verdict"),
            "overall_score": data.get("overall_score"),
            "raw": data,
            "stdout_tail": stream_text,
        },
    )


def run_quick(**kwargs):
    kwargs["mode"] = "quick"
    results, meta = run(**kwargs)
    return results[0], meta

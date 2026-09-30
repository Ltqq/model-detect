from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..models import ProbeResult, ProbeStatus


def availability() -> dict:
    binary = shutil.which("proxy-sleuth")
    return {
        "available": bool(binary),
        "binary": binary,
        "engine": "Babapei/proxy-sleuth",
    }


def run_quick(
    *,
    base_url: str,
    model: str,
    api_key: str,
    protocol: str = "openai",
    timeout_seconds: float = 300,
) -> tuple[ProbeResult, dict]:
    binary = shutil.which("proxy-sleuth")
    if not binary:
        return (
            ProbeResult(
                probe_id="identity.proxy_sleuth.quick",
                category="identity",
                status=ProbeStatus.SKIPPED,
                score=None,
                confidence=0.0,
                summary="proxy-sleuth is not installed; optional adapter skipped",
                metadata={"engine": "proxy-sleuth"},
            ),
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
            "quick",
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
        data = None
        if out.exists():
            try:
                data = json.loads(out.read_text(encoding="utf-8"))
            except Exception:
                data = None

    if not isinstance(data, dict):
        return (
            ProbeResult(
                probe_id="identity.proxy_sleuth.quick",
                category="identity",
                status=ProbeStatus.ERROR,
                score=None,
                confidence=0.4,
                summary=f"proxy-sleuth did not produce parseable JSON (exit {proc.returncode})",
                metadata={"engine": "proxy-sleuth"},
            ),
            {
                **availability(),
                "returncode": proc.returncode,
                "stdout_tail": ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-4000:],
            },
        )

    verdict = str(data.get("verdict") or "INCONCLUSIVE").upper()
    score = data.get("overall_score")
    try:
        score = float(score) if score is not None else None
    except Exception:
        score = None

    if verdict == "MATCH":
        status = ProbeStatus.PASS
    elif verdict == "MISMATCH":
        status = ProbeStatus.FAIL
    elif verdict == "SUSPICIOUS":
        status = ProbeStatus.WARN
    else:
        status = ProbeStatus.INSUFFICIENT

    return (
        ProbeResult(
            probe_id="identity.proxy_sleuth.quick",
            category="identity",
            status=status,
            score=score,
            confidence=0.75,
            summary=f"proxy-sleuth quick verdict={verdict}",
            observed={
                "verdict": verdict,
                "overall_score": score,
                "layers": data.get("layers", []),
            },
            metadata={"engine": "proxy-sleuth", "verdict": verdict.lower()},
        ),
        {
            **availability(),
            "returncode": proc.returncode,
            "verdict": verdict,
            "overall_score": score,
            "raw": data,
        },
    )

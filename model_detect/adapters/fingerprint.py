from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from ..models import ProbeResult, ProbeStatus


VERDICT_RE = re.compile(r"Verdict:\s*([A-Z_]+)", re.I)
JSD_RE = re.compile(r"Mean JSD:\s*([0-9.]+)", re.I)


def availability() -> dict:
    direct = shutil.which("llm-fingerprint")
    npx = shutil.which("npx")
    return {
        "available": bool(direct or npx),
        "direct_binary": direct,
        "npx": npx,
        "engine": "ToseaAI/llm-fingerprint-detector",
    }


def _command(base_url: str, model: str, reference: str) -> list[str]:
    direct = shutil.which("llm-fingerprint")
    if direct:
        return [
            direct,
            "verify",
            "--base-url",
            base_url,
            "--model",
            model,
            "--reference",
            reference,
            "--api-key-env",
            "LLM_FINGERPRINT_API_KEY",
        ]
    npx = shutil.which("npx")
    if npx:
        return [
            npx,
            "--yes",
            "llm-fingerprint-detector",
            "verify",
            "--base-url",
            base_url,
            "--model",
            model,
            "--reference",
            reference,
            "--api-key-env",
            "LLM_FINGERPRINT_API_KEY",
        ]
    raise RuntimeError(
        "llm-fingerprint-detector is unavailable; install Node.js/npm or the llm-fingerprint CLI"
    )


def verify(
    *,
    base_url: str,
    model: str,
    api_key: str,
    reference: str,
    timeout_seconds: float = 900,
) -> tuple[ProbeResult, dict]:
    ref = Path(reference)
    if not ref.exists():
        raise FileNotFoundError(f"fingerprint reference not found: {reference}")

    env = dict(os.environ)
    env["LLM_FINGERPRINT_API_KEY"] = api_key
    cmd = _command(base_url, model, str(ref))
    proc = subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    verdict_match = VERDICT_RE.search(output)
    jsd_match = JSD_RE.search(output)
    verdict = verdict_match.group(1).lower() if verdict_match else "insufficient"
    mean_jsd = float(jsd_match.group(1)) if jsd_match else None

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
    status = status_map.get(verdict, ProbeStatus.ERROR if proc.returncode == 1 else ProbeStatus.INSUFFICIENT)
    result = ProbeResult(
        probe_id="identity.fingerprint.reference_compare",
        category="identity",
        status=status,
        score=score_map.get(verdict),
        confidence=0.9 if verdict in {"match", "mismatch"} else 0.6,
        summary=(
            f"statistical fingerprint verdict={verdict}"
            + (f", mean JSD={mean_jsd:.3f}" if mean_jsd is not None else "")
        ),
        observed={"verdict": verdict, "mean_jsd": mean_jsd, "returncode": proc.returncode},
        metadata={"verdict": verdict, "engine": "llm-fingerprint-detector"},
    )
    meta = {
        "available": True,
        "engine": "llm-fingerprint-detector",
        "returncode": proc.returncode,
        "verdict": verdict,
        "mean_jsd": mean_jsd,
        "stdout_tail": output[-4000:],
    }
    return result, meta

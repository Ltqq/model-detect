"""Guarded Kimi official verifier subprocess runner.

Never imports or modifies Moonshot's rules, and never echoes subprocess logs.
Use only a pinned checkout and a separate Python >=3.12 environment.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from .kimi_official import OFFICIAL_CASES, OFFICIAL_COMMIT, import_official_junit


def run_official_subset(
    *,
    repo_dir: Path, python_executable: Path, suite: str,
    model: str, base_url: str, api_key: str,
    output_xml: Path, timeout_seconds: int = 1800,
    max_cases: int = 10,
) -> dict[str, Any]:
    if suite not in OFFICIAL_CASES:
        raise ValueError("suite not in pinned official subset")
    if not 10 <= timeout_seconds <= 3600:
        raise ValueError("invalid timeout")
    if not 1 <= max_cases <= 20:
        raise ValueError("max_cases must be 1..20")
    repo_dir = Path(repo_dir).resolve()
    path = repo_dir / OFFICIAL_CASES[suite]["path"]
    if not path.is_dir() or not (repo_dir / "pyproject.toml").is_file():
        raise ValueError("official suite not available in checked-out source")
    try:
        check = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        raise RuntimeError("cannot verify local official source commit") from None
    if check.returncode != 0 or check.stdout.strip() != OFFICIAL_COMMIT:
        raise RuntimeError("official verifier source commit is not pinned")
    if output_xml.exists():
        raise FileExistsError("JUnit evidence already exists")
    output_xml.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "KIMI_API_KEY": api_key,
        "KIMI_BASE_URL": base_url,
        "MODEL_NAME": model,
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    # No --api-key on argv: command line arguments are visible to other users.
    command = [
        str(python_executable), "-m", "pytest", "-q",
        OFFICIAL_CASES[suite]["path"],
        "--smoke-model", model,
        "--junitxml", str(output_xml),
    ]
    if suite == "params":
        command += ["--think-mode", "kimi"]
    if suite == "tool_call_json_schema":
        command += ["--thinking", "--think-mode", "kimi",
                    "--max-cases", str(max_cases)]
    try:
        result = subprocess.run(
            command, cwd=repo_dir, env=env,
            capture_output=True, text=True, timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "suite": suite, "xml_saved": output_xml.is_file(),
                "report": None}
    except OSError:
        return {"status": "execution_error", "suite": suite,
                "xml_saved": output_xml.is_file(), "report": None}
    # Preserve sanitized structured evidence even when pytest exit status != 0.
    try:
        report = import_official_junit(output_xml, suite=suite, model=model)
    except (ValueError, OSError):
        return {
            "status": "invalid_junit", "suite": suite,
            "pytest_exit_code": result.returncode, "report": None,
        }
    return {
        "status": "finished" if result.returncode == 0 else "pytest_failed",
        "suite": suite,
        "pytest_exit_code": result.returncode,
        "report": report,
        "warning": "Results require later real environment provenance verification.",
    }

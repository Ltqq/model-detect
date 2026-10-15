"""Safe offline inspection of an existing paid GLM53 benchmark checkpoint.

An inspection is never a resume operation and cannot authorize rerunning tests.
No stored raw task output is displayed or copied to terminal.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def inspect_checkpoint(path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink checkpoint is not trusted")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("checkpoint is too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "glm53-benchmark-checkpoint-v1":
        raise ValueError("invalid benchmark checkpoint schema")
    runs = data.get("runs")
    failures = data.get("failures")
    if not isinstance(runs, dict) or not isinstance(failures, list):
        raise ValueError("invalid checkpoint runs or failures")
    summary: dict[str, Any] = {}
    for source in ("official", "customer"):
        items = runs.get(source, [])
        if not isinstance(items, list):
            raise ValueError("invalid run list")
        summary[source] = {"stored_run_groups": len(items)}
    sha = data.get("suite_sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid suite digest")
    return {
        "schema": "glm53-checkpoint-inspection-v1",
        "suite_sha256": sha,
        "recorded_sources": summary,
        "failure_count": len(failures),
        "resume_supported": False,
        "paid_api_calls": 0,
        "decision": "inspect_and_start_a_new_output_directory_if_explicitly_authorized",
        "warning": "Original tasks were not resumed, verified or re-executed; no raw prompts or responses shown.",
    }

"""Attach only sanitized official Kimi verifier summary to a copied audit report.

The original audit and its identity scoring stay unchanged. This is not
independent evidence that user-supplied JUnit was produced by Moonshot code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .kimi_official import OFFICIAL_CASES, OFFICIAL_COMMIT
from .models import AuditReport
from .reporting import write_report


def _validated_summary(raw: Any, model: str, *, include_case_index: bool = False) -> dict[str, Any]:
    if isinstance(raw, dict) and "report" in raw:
        raw = raw["report"]
    if not isinstance(raw, dict):
        raise ValueError("official verifier summary missing")
    if raw.get("schema") != "kimi-official-junit-import-v1":
        raise ValueError("unsupported official verifier summary")
    if raw.get("source_commit") != OFFICIAL_COMMIT:
        raise ValueError("unrecognized official source commit")
    if raw.get("suite") not in OFFICIAL_CASES:
        raise ValueError("unknown official suite")
    if raw.get("model") != model:
        raise ValueError("model mismatch; refusing unrelated evidence")
    counts = raw.get("counts")
    if not isinstance(counts, dict) or any(
        type(counts.get(k)) is not int or counts[k] < 0
        for k in ("pass", "fail", "error", "skipped")
    ):
        raise ValueError("invalid official suite counts")
    total = sum(counts[k] for k in ("pass", "fail", "error", "skipped"))
    cases = raw.get("cases")
    if not isinstance(cases, list) or len(cases) != total or total < 1:
        raise ValueError("inconsistent official testcase count")
    # Case index is only used for cross-endpoint protocol comparisons.
    # Attachment reports intentionally omit even hashed testcase identifiers.
    index: dict[str, str] = {}
    if include_case_index:
        import re
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError("invalid official testcase")
            key, status = case.get("testcase_sha256"), case.get("status")
            if not isinstance(key, str) or not re.fullmatch("[0-9a-f]{64}", key):
                raise ValueError("invalid official testcase digest")
            if key in index or status not in {"pass", "fail", "error", "skipped"}:
                raise ValueError("duplicate or invalid official testcase")
            index[key] = status
        if any(sum(v == k for v in index.values()) != counts[k] for k in ("pass", "fail", "error", "skipped")):
            raise ValueError("official testcase count mismatch")
    # Reconstruct an allow-listed payload, not raw user-supplied paths/messages.
    normalized = {
        "source_repository": "MoonshotAI/Kimi-Vendor-Verifier",
        "source_commit": OFFICIAL_COMMIT,
        "suite": raw["suite"],
        "model": model,
        "counts": {k: counts[k] for k in ("pass", "fail", "error", "skipped")},
        "evidence_source": "user_supplied_unattested_junit",
        "identity_strength": "none",
        "result": (
            "inconclusive" if counts["error"] or counts["skipped"]
            else "failure_observed" if counts["fail"]
            else "all_cases_passed_in_import"
        ),
        "warning": "Official test outcomes are separate from model identity and audit score.",
    }
    if include_case_index:
        normalized["case_index"] = index
    return normalized


def merge_official_summary(
    audit_path: Path, verifier_summary_path: Path, output_dir: Path,
) -> Path:
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError("refusing to overwrite an existing report directory")
    if audit_path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("audit too large")
    if verifier_summary_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("official summary too large")
    original = AuditReport.model_validate_json(audit_path.read_text(encoding="utf-8"))
    raw = json.loads(verifier_summary_path.read_text(encoding="utf-8"))
    summary = _validated_summary(raw, str(original.target.get("model") or ""))
    amended = original.model_copy(deep=True)
    amended.adapters["kimi_official_verifier"] = summary
    # The original final_verdict and per-probe scores must not be modified.
    return write_report(amended, out)

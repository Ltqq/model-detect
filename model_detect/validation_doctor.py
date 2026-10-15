"""No-network validation manifest doctor for independently labelled audit cases."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .validation import ValidationSuite, _find_report_paths


def validation_manifest_readiness(
    suite: ValidationSuite, *, manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    labels: dict[str, dict[str, int]] = {
        signal: {"positive": 0, "negative": 0, "unlabelled": 0}
        for signal in ("identity", "routing", "quality")
    }
    rows = []
    missing_files = 0
    for case in suite.cases:
        truth = case.truth
        tag = {
            "identity": None if truth.identity is None else truth.identity == "different",
            "routing": truth.routing_mixed,
            "quality": truth.quality_regressed,
        }
        for signal, positive in tag.items():
            labels[signal][
                "unlabelled" if positive is None else
                ("positive" if positive else "negative")
            ] += 1
        expected = _find_report_paths(
            case, manifest=manifest_path, output_dir=output_dir
        )
        found = sum(file.is_file() for file in expected)
        missing_files += len(expected) - found
        rows.append({
            "case_id": case.id, "scenario": case.scenario,
            "declared_runs": case.runs, "reports_found": found,
            "reports_missing": len(expected) - found,
            "truth_source_present": bool(case.truth_source.strip()),
            "truth_source_verified": False,
        })
    detectable = [
        signal for signal, entry in labels.items()
        if entry["positive"] and entry["negative"]
    ]
    return {
        "schema": "validation-manifest-readiness-v1",
        "suite_id": suite.id,
        "case_count": len(suite.cases),
        "expected_runs": sum(case.runs for case in suite.cases),
        "missing_report_files": missing_files,
        "independent_case_labels": labels,
        "signals_with_both_classes": detectable,
        "cases": rows,
        "status": (
            "missing_reports" if missing_files else
            "needs_truth_and_source_attestation"
        ),
        "api_calls": 0,
        "limitations": [
            "Truth sources are user-declared; their correctness is NOT verified.",
            "Repeated runs of one case are not independent negative/positive cases.",
            "Positive and negative cases are needed before claiming performance.",
            "Report presence does not establish model identity or ground truth.",
        ],
    }

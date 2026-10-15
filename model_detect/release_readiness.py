"""Offline release readiness inspection. Never asserts live acceptance.

All real-provider and external tool acceptance evidence is intentionally a
separate mandatory release gate, not inferred from local files or CI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_DOCS = (
    "README.md",
    "CHANGELOG.md",
    "docs/release-checklist.md",
    "docs/upgrade-and-restore.md",
    "docs/oss-compatibility.md",
    "docs/kimi-official-verifier.md",
)
REQUIRED_TESTS = (
    "tests/test_usage_meter.py",
    "tests/test_usage_pricing.py",
    "tests/test_kimi_official_import.py",
    "tests/test_web_e2e.py",
    "tests/test_validation_doctor.py",
)


def inspect_release_tree(repository: Path) -> dict[str, Any]:
    """Verify packaging/docs/test presence, not whether tests passed."""
    root = Path(repository).resolve()
    present = {}
    for relative in ("pyproject.toml", *REQUIRED_DOCS, *REQUIRED_TESTS):
        present[relative] = (root / relative).is_file()
    missing = sorted(name for name, found in present.items() if not found)
    return {
        "schema": "release-readiness-v1",
        "files_checked": present,
        "missing_files": missing,
        "offline_engineering_files_present": not missing,
        "ci_verified_here": False,
        "live_model_verified": False,
        "external_adapters_verified": False,
        "controlled_ground_truth_verified": False,
        "publish_ready": False,
        "reason": (
            "missing engineering files" if missing
            else "engineering files present, but real acceptance remains mandatory"
        ),
        "api_calls": 0,
    }

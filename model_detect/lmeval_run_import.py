"""Discover a single matching lm-eval logged-samples file for a saved run."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters.lm_eval import discover_result_file
from .lmeval_snapshot_import import import_lmeval_snapshot


def import_run_directory(*, run_dir: Path, task: str, output: Path,
                         model: str, provider_role: str,
                         dataset_revision: str, scorer_revision: str) -> Any:
    root = Path(run_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("invalid run directory")
    result = discover_result_file(root)
    # lm-eval uses samples_<task>_*.jsonl, but installations may also emit JSON.
    # No guesswork when the task-specific sample artifact is missing/ambiguous.
    matches = []
    for ext in ("jsonl", "json"):
        for path in root.rglob(f"samples_{task}_*.{ext}"):
            if path.is_symlink() or not path.is_file():
                continue
            if path.resolve().is_relative_to(root.resolve()):
                matches.append(path)
    if len(matches) != 1:
        raise ValueError("expected exactly one task-specific logged sample artifact")
    return import_lmeval_snapshot(
        result_file=result, samples_file=matches[0], task=task, output=output,
        model=model, provider_role=provider_role,
        dataset_revision=dataset_revision, scorer_revision=scorer_revision,
    )

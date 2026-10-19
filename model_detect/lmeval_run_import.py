"""Discover a single matching lm-eval logged-samples file for a saved run."""
from __future__ import annotations

from pathlib import Path
import re
from collections.abc import Mapping
import yaml
from typing import Any

from .adapters.lm_eval import discover_result_file
from .lmeval_snapshot_import import import_lmeval_snapshot, snapshot_from_lmeval
from .evaluation_snapshots import save_snapshot


def import_run_directory(*, run_dir: Path, task: str, output: Path,
                         model: str, provider_role: str,
                         dataset_revision: str, scorer_revision: str) -> Any:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", task):
        raise ValueError("invalid task name")
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


def load_revision_manifest(path: Path, *, expected_tasks: list[str]) -> dict:
    """Require explicit per-task source labels; these are NOT independently attested."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ValueError("invalid revisions manifest")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "benchmark-revisions-v1":
        raise ValueError("unsupported revisions manifest")
    if data.get("provider_role") not in {"official", "vendor"}:
        raise ValueError("provider_role must be official or vendor")
    tasks = data.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != set(expected_tasks):
        raise ValueError("manifest task set must exactly match benchmark task set")
    for task, spec in tasks.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", task) or not isinstance(spec, dict):
            raise ValueError("invalid manifest task")
        for key in ("dataset_revision", "scorer_revision"):
            value = spec.get(key)
            if not isinstance(value, str) or not (1 <= len(value.strip()) <= 256):
                raise ValueError("missing or invalid per-task revision")
    return data


def import_run_snapshots(
    *, run_dir: Path, output_dir: Path, model: str,
    manifest: Mapping[str, object],
) -> dict:
    """Promote saved run artifacts to derived snapshots, never certify the source."""
    root = Path(run_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("invalid run directory")
    target = Path(output_dir)
    if target.exists() or target.is_symlink():
        raise FileExistsError("snapshots already exist")
    result = discover_result_file(root)
    tasks = manifest["tasks"]
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError("manifest tasks missing")
    snapshots = {}
    for task, spec in sorted(tasks.items()):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(task)):
            raise ValueError("invalid task")
        candidates = []
        for ext in ("jsonl", "json"):
            for path in root.rglob(f"samples_{task}_*.{ext}"):
                if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()):
                    candidates.append(path)
        if len(candidates) != 1:
            raise ValueError("expected exactly one sample log per task")
        snapshots[task] = snapshot_from_lmeval(
            result_file=result, samples_file=candidates[0], task=task,
            model=model, provider_role=manifest["provider_role"],
            dataset_revision=spec["dataset_revision"],
            scorer_revision=spec["scorer_revision"],
        )
    # Validate *all* tasks before exposing any derived Reference file.
    target.mkdir(parents=True, exist_ok=False)
    for task, snapshot in snapshots.items():
        save_snapshot(snapshot, target / f"{task}.json")
    return {
        "status": "completed", "task_count": len(snapshots),
        "source_verified": False, "revisions": "user_declared_unverified",
    }

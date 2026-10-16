"""Import lm-eval results into a reusable evidence snapshot, without model calls.

Sample IDs are only trusted when a companion logged-samples artifact includes
one explicit integer doc_id per evaluated sample. Metadata supplied by users
is recorded as unverified, never claimed as official attestation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters.lm_eval import parse_result_payload
from .benchmark_contract import task_contract_sha256
from .evaluation_snapshots import EvaluationSnapshot, save_snapshot


def _read_json(path: Path) -> tuple[dict[str, Any] | list[Any], bytes]:
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("invalid or oversized evidence file")
    raw = path.read_bytes()
    parsed = json.loads(raw)
    if not isinstance(parsed, (dict, list)):
        raise ValueError("invalid lm-eval artifact")
    return parsed, raw


def snapshot_from_lmeval(
    *, result_file: Path, samples_file: Path, task: str, model: str,
    provider_role: str, dataset_revision: str, scorer_revision: str,
) -> EvaluationSnapshot:
    report, raw = _read_json(result_file)
    samples, _ = _read_json(samples_file)
    if not isinstance(report, dict) or not isinstance(samples, list):
        raise ValueError("expected lm-eval result object and samples list")
    configs = report.get("configs")
    if not isinstance(configs, dict) or not isinstance(configs.get(task), dict):
        raise ValueError("task configuration missing")
    cfg = configs[task]
    rows = [r for r in parse_result_payload(report) if r.metadata.get("task") == task]
    if len(rows) != 1 or rows[0].score is None:
        raise ValueError("task score missing or unsupported")
    count = rows[0].observed.get("effective_samples")
    if type(count) is not int or count < 1 or len(samples) != count:
        raise ValueError("logged sample count does not equal effective task count")
    ids = []
    for row in samples:
        if not isinstance(row, dict) or type(row.get("doc_id")) is not int or row["doc_id"] < 0:
            raise ValueError("logged samples require unambiguous integer doc_id")
        ids.append(row["doc_id"])
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate doc_id makes comparison ambiguous")
    if not dataset_revision.strip() or not scorer_revision.strip():
        raise ValueError("dataset and scorer revisions must be declared")
    engine = str(report.get("lm_eval_version") or "").strip()
    if not engine:
        raise ValueError("lm-eval version missing")
    # Preserve task options as hashed contract without leaking prompts or URLs.
    contract = task_contract_sha256(task, cfg, report)
    samples_sha = hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()
    return EvaluationSnapshot(
        model=model, provider_role=provider_role, task_id=task,
        engine_revision=engine,
        dataset_revision=dataset_revision.strip(),
        scorer_revision=scorer_revision.strip(),
        sample_ids_sha256=samples_sha,
        generation_parameters_sha256=contract,
        sample_count=count,
        score=rows[0].score,
        metric_name=rows[0].metadata["primary_metric"],
        source_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        source_verified=False,
    )


def import_lmeval_snapshot(*, output: Path, **kwargs: Any) -> EvaluationSnapshot:
    snapshot = snapshot_from_lmeval(**kwargs)
    save_snapshot(snapshot, output)
    return snapshot

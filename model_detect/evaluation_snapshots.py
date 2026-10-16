"""Reusable, immutable-by-default benchmark result snapshots.

A snapshot is measured evidence supplied by the user, never a fabricated
official score. Compares only identically versioned/sampled test contracts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .evaluation_catalog import benchmark_comparability


class EvaluationSnapshot(BaseModel):
    schema_version: str = "evaluation-snapshot-v1"
    model: str = Field(min_length=1)
    provider_role: str
    task_id: str = Field(min_length=1)
    engine_revision: str = Field(min_length=1)
    dataset_revision: str = Field(min_length=1)
    scorer_revision: str = Field(min_length=1)
    sample_ids_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_parameters_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_count: int = Field(gt=0)
    score: float = Field(ge=0, le=1)
    metric_name: str = Field(min_length=1)
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_verified: bool = False


def save_snapshot(snapshot: EvaluationSnapshot, path: Path) -> None:
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise FileExistsError("snapshot exists; preserving old evidence")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = snapshot.model_dump_json(indent=2)
    with target.open("x", encoding="utf-8") as handle:
        handle.write(data)


def compare_snapshots(official: EvaluationSnapshot, vendor: EvaluationSnapshot) -> dict[str, Any]:
    contract = benchmark_comparability(
        official.model_dump(mode="json"), vendor.model_dump(mode="json")
    )
    extra = []
    if official.model != vendor.model:
        extra.append("model")
    if official.metric_name != vendor.metric_name:
        extra.append("metric_name")
    if official.sample_count != vendor.sample_count:
        extra.append("sample_count")
    compatible = contract["comparable"] and not extra
    return {
        "schema": "evaluation-snapshot-compare-v1",
        "comparable": compatible,
        "mismatch_fields": sorted(contract["mismatched_fields"] + extra),
        "missing_fields": contract["missing_fields"],
        "official_score": official.score if compatible else None,
        "vendor_score": vendor.score if compatible else None,
        "score_delta_vendor_minus_official": (
            round(vendor.score - official.score, 8) if compatible else None
        ),
        "sample_count": official.sample_count if compatible else None,
        "ceiling_warning": (
            "both_scores_above_90_percent_not_discriminating"
            if compatible and official.score >= .9 and vendor.score >= .9 else None
        ),
        "identity_proven": False,
        "provenance_verified": official.source_verified and vendor.source_verified,
        "warning": (
            "Supplied benchmark scores are user-provided evidence. Matching scores "
            "never proves that the same model weights were used."
        ),
    }

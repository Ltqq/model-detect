"""Compatibility view of the ONE canonical test catalog (test_catalog.py).

Never register evaluation tasks here. No catalog is evidence of actual execution.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel

from .test_catalog import build_test_catalog

EvidenceAuthority = Literal["official_suite", "community_benchmark", "candidate_unverified"]
Difficulty = Literal["protocol", "foundation", "intermediate", "advanced", "unverified"]


class EvaluationEntry(BaseModel):
    id: str
    engine: str
    authority: EvidenceAuthority
    dimension: str
    difficulty: Difficulty
    source: str
    source_revision: str | None = None
    task_version: str | None = None
    scorer_revision: str | None = None
    verified_on_live_model: bool = False
    integration: str
    coverage_note: str


def evaluation_catalog() -> dict[str, Any]:
    """Maintain old CLI shape while reading the authoritative registry."""
    items: list[EvaluationEntry] = []
    for row in build_test_catalog()["entries"]:
        provenance = row["provenance"]
        if provenance == "vendor_official_source_pinned":
            authority: EvidenceAuthority = "official_suite"
            engine = "kimi-vendor-verifier"
            name = row["id"].removeprefix("kimi.official.")
            legacy_id = f"kimi:{name}"
        elif provenance == "community_benchmark_adapter":
            authority = "community_benchmark"
            engine = "lm-evaluation-harness"
            name = row["id"].removeprefix("lm_eval.")
            legacy_id = f"lm_eval:{name}"
        else:
            # In particular a mentioned, unintegrated vendor benchmark
            # must not appear as executable or validated official coverage.
            authority = "candidate_unverified"
            engine = "not_integrated"
            legacy_id = row["id"].replace("kimi.benchmark.", "kimi:benchmark:")
        items.append(EvaluationEntry(
            id=legacy_id, engine=engine, authority=authority,
            dimension=row["title"],
            difficulty=row["difficulty"] if row["difficulty"] in {
                "protocol", "foundation", "intermediate", "advanced"
            } else "unverified",
            source=row["source_url"], source_revision=row["source_revision"],
            verified_on_live_model=bool(row["run_verified"]),
            integration=row["integration"],
            coverage_note=row["authority_note"],
        ))
    return {
        "schema": "evaluation-catalog-v1",
        "source_schema": "model-detect-test-catalog-v1",
        "entries": [item.model_dump(mode="json") for item in items],
        "difficulty_policy": {
            "quick": "Protocol and cheap discriminators only; cannot certify intelligence.",
            "standard": "Representative public benchmarks; avoid ceiling effects.",
            "deep": "Require deliberately harder, independently scored tasks; not simply more easy samples.",
        },
        "ceiling_effect_rule": {
            "trigger": "When two models both nearly saturate a task, that task is non-discriminating.",
            "action": "Mark non-discriminating and move to a validated harder or different task.",
            "do_not": "Infer model identity or equal reasoning quality from matching easy-task scores.",
        },
        "official_results_embedded": False,
        "live_verified": False,
    }


def benchmark_comparability(
    official: dict[str, Any], vendor: dict[str, Any],
) -> dict[str, Any]:
    required = (
        "task_id", "engine_revision", "dataset_revision",
        "scorer_revision", "sample_ids_sha256", "generation_parameters_sha256",
    )
    missing = sorted(k for k in required if not official.get(k) or not vendor.get(k))
    different = sorted(
        k for k in required if k not in missing and official[k] != vendor[k]
    )
    return {
        "comparable": not missing and not different,
        "missing_fields": missing,
        "mismatched_fields": different,
        "reason": "comparable" if not missing and not different else "insufficient_or_mismatched_contract",
    }

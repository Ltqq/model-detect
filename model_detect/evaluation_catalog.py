"""Source-aware evaluation catalog; planning metadata, not certified scores.

The catalog deliberately distinguishes official verification suites from
community benchmark tasks and native probes. It does not download datasets,
execute models or pretend a task is a validated high-difficulty benchmark.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .adapters.lm_eval import load_builtin_profiles
from .kimi_official import OFFICIAL_CASES, OFFICIAL_COMMIT, OFFICIAL_REPOSITORY

EvidenceAuthority = Literal["official_suite", "community_benchmark", "local_probe"]
Difficulty = Literal["protocol", "foundation", "intermediate", "advanced", "unverified"]

# Difficulty descriptions are editorial labels, NOT psychometric calibrations.
_TASK_DIFFICULTY = {
    "truthfulqa_gen": "foundation",
    "gsm8k": "foundation",
    "ifeval": "intermediate",
}


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
    samples_configured: int | None = Field(default=None, ge=1)
    verified_on_live_model: bool = False
    coverage_note: str


def evaluation_catalog() -> dict[str, Any]:
    profiles = load_builtin_profiles()
    task_names = profiles["tasks"]
    entries: list[EvaluationEntry] = []
    for name, cfg in sorted(task_names.items()):
        entries.append(EvaluationEntry(
            id=f"lm_eval:{name}", engine="lm-evaluation-harness",
            authority="community_benchmark",
            dimension=str(cfg.get("dimension") or "unknown"),
            difficulty=_TASK_DIFFICULTY.get(name, "unverified"),
            source="https://github.com/EleutherAI/lm-evaluation-harness",
            source_revision=None, task_version=None, scorer_revision=None,
            coverage_note=(
                "Task exists in configured lm-eval profiles; actual dataset "
                "revision, sample IDs and scorer hash must be recorded at execution."
            ),
        ))
    for suite, cfg in OFFICIAL_CASES.items():
        entries.append(EvaluationEntry(
            id=f"kimi:{suite}", engine="kimi-vendor-verifier",
            authority="official_suite", dimension=str(cfg["local_mapping"]),
            difficulty="protocol", source=f"https://github.com/{OFFICIAL_REPOSITORY}",
            source_revision=OFFICIAL_COMMIT,
            coverage_note=(
                "Pinned official source path " + cfg["path"] +
                "; real execution and original-provenance confirmation pending."
            ),
        ))
    return {
        "schema": "evaluation-catalog-v1",
        "entries": [entry.model_dump(mode="json") for entry in entries],
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

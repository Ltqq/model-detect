"""Canonical test catalog: source authority, coverage and difficulty are distinct.

This is a registry of *declared* tests, not proof that an upstream suite ran.
All external source pins and local profiles remain explicitly unverified until
their real execution environment is attested.
"""
from __future__ import annotations

from typing import Any

from .adapters.lm_eval import load_builtin_profiles
from .kimi_official import OFFICIAL_CASES, OFFICIAL_COMMIT, OFFICIAL_REPOSITORY

CATALOG_SCHEMA = "model-detect-test-catalog-v1"

# Editorial task tiers only; do not imply independently calibrated difficulty.
_TASK_DIFFICULTY = {"truthfulqa_gen": "foundation", "gsm8k": "foundation", "ifeval": "intermediate"}

# Cost class expresses qualitative planning only, not a billed token estimate.
_OFFICIAL_KIMI_BENCHMARKS: tuple[tuple[str, str, str], ...] = (
    ("ocrbench", "vision_ocr", "high"),
    ("mmmu", "vision_reasoning", "high"),
    ("beam_1m", "long_context", "very_high"),
    ("deepswe", "agentic_coding", "very_high"),
)


def _entry(
    *, id: str, title: str, owner: str, source_url: str,
    provenance: str, difficulty: str, cost_class: str,
    integration: str, task_path: str | None = None,
    source_revision: str | None = None,
    models: list[str] | None = None,
    authority_note: str,
) -> dict[str, Any]:
    return {
        "id": id, "title": title, "owner": owner, "source_url": source_url,
        "source_revision": source_revision,
        "provenance": provenance, "integration": integration,
        "models": models or [],
        "difficulty": difficulty, "cost_class": cost_class,
        "task_path": task_path, "authority_note": authority_note,
        "run_verified": False, "results_attested": False,
    }


def build_test_catalog() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for name, spec in OFFICIAL_CASES.items():
        items.append(_entry(
            id=f"kimi.official.{name}",
            title=str(spec["purpose"]), owner=OFFICIAL_REPOSITORY,
            source_url=f"https://github.com/{OFFICIAL_REPOSITORY}/tree/{OFFICIAL_COMMIT}/{spec['path']}",
            source_revision=OFFICIAL_COMMIT,
            provenance="vendor_official_source_pinned",
            difficulty="protocol", cost_class="variable",
            integration="runner_and_junit_import_implemented",
            task_path=spec["path"], models=["kimi-k3"],
            authority_note="Official source code is pinned; executing it and provider compliance are not attested.",
        ))
    for name, dimension, cost in _OFFICIAL_KIMI_BENCHMARKS:
        items.append(_entry(
            id=f"kimi.benchmark.{name}",
            title=dimension, owner=OFFICIAL_REPOSITORY,
            source_url=f"https://github.com/{OFFICIAL_REPOSITORY}/tree/{OFFICIAL_COMMIT}/tests",
            source_revision=OFFICIAL_COMMIT,
            provenance="vendor_benchmark_named_not_verified",
            difficulty="advanced", cost_class=cost,
            integration="not_integrated",
            models=["kimi-k3"],
            authority_note="Scope is a candidate; verify exact upstream test paths and scoring before claiming official coverage.",
        ))
    profiles = load_builtin_profiles()
    for name, spec in profiles["tasks"].items():
        items.append(_entry(
            id=f"lm_eval.{name}", title=str(spec.get("dimension") or name),
            owner="EleutherAI/lm-evaluation-harness",
            source_url="https://github.com/EleutherAI/lm-evaluation-harness",
            provenance="community_benchmark_adapter", difficulty=_TASK_DIFFICULTY.get(name, "unverified"),
            cost_class="variable", integration="local_lm_eval_adapter",
            task_path=name, authority_note=(
                "Open-source benchmark adapter is not a model vendor's official verification suite; "
                "pin package revision and dataset revision per evaluation."
            ),
        ))
    return {
        "schema": CATALOG_SCHEMA, "entries": items,
        "authority_verified_at_runtime": False,
        "warning": (
            "Catalog presence/pinned source is not proof of an actual authoritative evaluation. "
            "Unintegrated high-cost suites cannot be marked passed."
        ),
    }


def select_catalog(*, model: str | None = None, provenance: str | None = None) -> dict[str, Any]:
    catalog = build_test_catalog()
    catalog["entries"] = [
        item for item in catalog["entries"]
        if (model is None or not item["models"] or model in item["models"])
        and (provenance is None or item["provenance"] == provenance)
    ]
    return catalog

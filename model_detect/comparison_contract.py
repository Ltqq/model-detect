from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import AuditReport, ProbeResult

CONTRACT_VERSION = 1
_SENSITIVE = {"authorization", "api_key", "apikey", "secret", "password", "token"}


def _clean(value: Any) -> Any:
    """Normalize inputs for hashing. Never persist raw prompt or secret values."""
    if isinstance(value, dict):
        return {
            str(k): _clean(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
            if str(k).casefold() not in _SENSITIVE and k != "model"
        }
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _clean(value), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest()


def _native_contract(report: AuditReport, result: ProbeResult) -> dict[str, Any] | None:
    related = set(result.evidence_ids)
    prefix = None
    if result.probe_id == "context.summary":
        prefix = "context."
    elif result.probe_id == "routing.summary":
        prefix = "routing."
    evidence = [
        item for item in report.evidences
        if item.id in related or (prefix and item.probe_id.startswith(prefix))
    ]
    # Inputs must be from actual evidence. A synthetic or incomplete report is
    # not sufficient evidence for a scientifically comparable quality verdict.
    if not evidence or any(item.request_body is None for item in evidence):
        return None

    scenarios = result.observed.get("scenarios") if isinstance(result.observed, dict) else None
    tasks = result.observed.get("tasks") if isinstance(result.observed, dict) else None
    manifest = {
        "probe_id": result.probe_id,
        "scenario_ids": (
            [item.get("probe_id") for item in scenarios if isinstance(item, dict)]
            if isinstance(scenarios, list) else []
        ),
        "task_ids": (
            [item.get("id") for item in tasks if isinstance(item, dict)]
            if isinstance(tasks, list) else []
        ),
        "requests": [
            {"probe_id": item.probe_id, "body": item.request_body}
            for item in evidence
        ],
    }
    return {
        "version": CONTRACT_VERSION,
        "kind": "native",
        "sha256": _digest(manifest),
        "request_count": len(evidence),
        "task_count": len(manifest["task_ids"]) or len(manifest["scenario_ids"]),
    }


def _benchmark_contract(result: ProbeResult) -> dict[str, Any] | None:
    meta = result.metadata
    obs = result.observed if isinstance(result.observed, dict) else {}
    # A published score with unknown metric/dataset/harness/limit is NOT
    # comparable, even if the user chose a profile with the same label.
    required = (
        meta.get("benchmark_profile"),
        meta.get("benchmark_limit"),
        meta.get("benchmark_harness_version"),
        obs.get("version"),
        meta.get("primary_metric"),
        meta.get("benchmark_task_metadata"),
    )
    if any(value is None for value in required):
        return None
    manifest = {
        "task": meta.get("task"),
        "profile": meta["benchmark_profile"],
        "limit": meta["benchmark_limit"],
        "harness_version": meta["benchmark_harness_version"],
        "dataset_version": obs["version"],
        "primary_metric": meta["primary_metric"],
        "task_metadata": meta["benchmark_task_metadata"],
        "model_type": meta.get("benchmark_model_type"),
        "apply_chat_template": meta.get("benchmark_apply_chat_template"),
        "num_fewshot": meta.get("benchmark_num_fewshot"),
        "config": meta.get("benchmark_run_config"),
    }
    return {
        "version": CONTRACT_VERSION,
        "kind": "benchmark",
        "sha256": _digest(manifest),
        "request_count": 0,
        "task_count": int(meta["benchmark_limit"]),
    }


def build_dimension_contracts(report: AuditReport) -> dict[str, dict[str, Any]]:
    from .baseline import BASELINE_DIMENSIONS

    by_id = {r.probe_id: r for r in report.results}
    contracts: dict[str, dict[str, Any]] = {}
    for dimension, probe_id in BASELINE_DIMENSIONS.items():
        result = by_id.get(probe_id)
        if result is None or result.score is None:
            continue
        contract = _native_contract(report, result)
        if contract:
            contracts[dimension] = contract

    for result in report.results:
        if (
            result.score is not None
            and result.metadata.get("engine") == "lm-evaluation-harness"
            and result.metadata.get("task")
        ):
            contract = _benchmark_contract(result)
            if contract:
                contracts[f"benchmark:{result.metadata['task']}"] = contract
    return contracts

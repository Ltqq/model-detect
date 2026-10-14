from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .adapters import lm_eval
from .benchmark_contract import CONTRACT_VERSION
from .glm53_preflight import benchmark_preflight

# Only generation-based suites; local-chat-completions does not implement
# multiple-choice loglikelihood (so default MMLU-Pro cannot run here).
BENCHMARK_PROFILES = {
    "smoke": {"tasks": ["gsm8k", "ifeval"], "limit": 5},
    "standard": {"tasks": ["gsm8k", "ifeval", "minerva_math500"], "limit": 25},
    "deep": {"tasks": ["gsm8k", "ifeval", "minerva_math500"], "limit": 100},
}
BENCHMARK_SUITE = "glm53-lm-eval-generative-v2"


def benchmark_plan(level: str, *, official_runs: int, customer_runs: int,
                   max_gen_toks: int = 8192,
                   reasoning_effort: str = "max") -> dict[str, Any]:
    if level not in BENCHMARK_PROFILES:
        raise ValueError("unknown benchmark level")
    if not (1 <= official_runs <= 5 and 1 <= customer_runs <= 5):
        raise ValueError("benchmark runs must be between 1 and 5")
    if not (256 <= max_gen_toks <= 32768):
        raise ValueError("benchmark max generation tokens must be 256..32768")
    if reasoning_effort not in {"low", "high", "max"}:
        raise ValueError("reasoning_effort must be low, high or max")
    profile = BENCHMARK_PROFILES[level]
    count = len(profile["tasks"]) * profile["limit"] * (
        official_runs + customer_runs
    )
    contract = {
        "suite": BENCHMARK_SUITE,
        "level": level,
        "tasks": profile["tasks"],
        "limit": profile["limit"],
        "max_gen_toks": max_gen_toks,
        "reasoning_effort": reasoning_effort,
        "apply_chat_template": True,
        "num_concurrent": 1,
        "max_retries": 0,
    }
    digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True).encode()
    ).hexdigest()
    return {
        **contract, "suite_sha256": digest,
        "nominal_samples": count,
        "nominal_max_output_tokens": count * max_gen_toks,
        "warning": (
            "This is a task sample count, NOT guaranteed request count or actual "
            "tokens. lm-eval subprocess usage is not metered here; endpoint "
            "must support generation tasks and follow task default generation."
        ),
    }


def _check_task(
    row: Any, *, expected_reasoning_effort: str | None = None
) -> dict[str, Any]:
    obs = row.observed if isinstance(row.observed, dict) else {}
    meta = row.metadata
    score = row.score
    task_generation = obs.get("task_generation_settings") or {}
    effort_recorded = task_generation.get("reasoning_effort")
    effort_valid = (
        expected_reasoning_effort is None
        or effort_recorded == expected_reasoning_effort
    )
    # Only scored metrics, never sample_len / stderr / bookkeeping numbers.
    metrics = {
        str(key): float(value)
        for key, value in (obs.get("metrics") or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        and 0 <= value <= 1
    }
    if not metrics and score is not None and meta.get("primary_metric"):
        metrics = {meta["primary_metric"]: float(score)}
    good = bool(
        effort_valid
        and score is not None
        and meta.get("primary_metric")
        and obs.get("version") is not None
        and isinstance(obs.get("effective_samples"), int)
        and obs["effective_samples"] > 0
        and isinstance(obs.get("task_config_hash"), str)
        and len(obs["task_config_hash"]) == 64
        and obs.get("task_contract_version") == CONTRACT_VERSION
    )
    return {
        "task": meta.get("task"),
        "score": score if good else None,
        "metric": meta.get("primary_metric"),
        "metrics": metrics,
        "dataset_version": obs.get("version"),
        "sample_count": obs.get("effective_samples"),
        "config_sha256": obs.get("task_config_hash"),
        "contract_version": obs.get("task_contract_version"),
        "valid": good,
        "requested_reasoning_effort": expected_reasoning_effort,
        "task_reasoning_effort": effort_recorded,
        "reasoning_config_verified": effort_valid if expected_reasoning_effort else None,
    }


def compare_benchmark_runs(
    official: list[list[dict[str, Any]]],
    customer: list[list[dict[str, Any]]],
    *,
    plan: dict[str, Any],
    harness_version: str,
) -> dict[str, Any]:
    """Compare complete scored metrics; no averaging dissimilar metrics.

    Result describes paired observed sample means, not significance/equivalence
    or the authenticity of either model.
    """
    tasks: list[dict[str, Any]] = []
    for name in plan["tasks"]:
        off = [next((r for r in run if r["task"] == name), None) for run in official]
        ven = [next((r for r in run if r["task"] == name), None) for run in customer]
        entries = off + ven
        first = entries[0] if entries else None
        validity = (
            bool(first)
            and all(r and r.get("valid") and r.get("score") is not None for r in entries)
            and all(
                (r["dataset_version"], r["sample_count"], r["config_sha256"],
                 r.get("contract_version"), r["metric"])
                == (first["dataset_version"], first["sample_count"],
                    first["config_sha256"], first.get("contract_version"), first["metric"])
                for r in entries if r
            )
        )
        def metric_values(row):
            # Existing integrations may still supply only a primary metric;
            # newer adapters preserve every numeric scored metric.
            metrics = row.get("metrics") or {}
            return metrics if metrics else {row["metric"]: row["score"]}
        if validity:
            keys = set(metric_values(first))
            validity = (
                bool(keys)
                and first["metric"] in keys
                and all(set(metric_values(r)) == keys for r in entries)
            )
        metric_rows = []
        if validity:
            for metric in sorted(keys, key=lambda k: (k != first["metric"], k)):
                om = [metric_values(r)[metric] for r in off]
                cm = [metric_values(r)[metric] for r in ven]
                official_mean = sum(om) / len(om)
                customer_mean = sum(cm) / len(cm)
                metric_rows.append({
                    "metric": metric,
                    "primary": metric == first["metric"],
                    "official_scores": om,
                    "customer_scores": cm,
                    "official_mean": official_mean,
                    "customer_mean": customer_mean,
                    "delta": customer_mean - official_mean,
                    "status": "measured_difference",
                })
        primary = next((row for row in metric_rows if row["primary"]), None)
        tasks.append({
            "task": name,
            "status": "measured_difference" if validity else "incomparable",
            "reason": (
                "同配置任务的观测差值，不构成统计显著性或等价证明"
                if validity else
                "任务/评分指标/有效样本/版本/参数契约缺失或不一致"
            ),
            "official_mean": primary["official_mean"] if primary else None,
            "customer_mean": primary["customer_mean"] if primary else None,
            "delta": primary["delta"] if primary else None,
            "official_scores": [r["score"] if r else None for r in off],
            "customer_scores": [r["score"] if r else None for r in ven],
            "metrics": metric_rows,
            "sample_count": first.get("sample_count") if first else None,
            "metric": first.get("metric") if first else None,
            "dataset_version": first.get("dataset_version") if first else None,
            "task_config_sha256": first.get("config_sha256") if first else None,
            "task_contract_version": first.get("contract_version") if first else None,
        })
    return {
        "suite": BENCHMARK_SUITE,
        "suite_sha256": plan["suite_sha256"],
        "harness_version": harness_version,
        "official_runs": len(official), "customer_runs": len(customer),
        "tasks": tasks,
        "result": (
            "measured" if tasks and all(t["status"] == "measured_difference" for t in tasks)
            else "partial_or_incomparable"
        ),
        "provenance": "EleutherAI/lm-evaluation-harness",
        "limitations": [
            "Only generate_until tasks are selected for Chat Completions; "
            "this is not GLM-5.3's official published evaluation configuration.",
            "The SDK sends its own task-default messages and generation config; "
            "Reasoning effort is checked in the emitted task config, but "
            "on-wire payload and server-side adherence remain unverified.",
            "lm-eval network usage is not captured by native request accounting.",
            "No model authenticity, statistical equivalence or significant "
            "regression is inferred from small samples.",
        ],
    }


def run_standard_benchmark(
    *,
    level: str,
    official_url: str,
    customer_url: str,
    official_key: str,
    customer_key: str,
    official_runs: int,
    customer_runs: int,
    max_gen_toks: int = 8192,
    reasoning_effort: str = "max",
) -> dict[str, Any]:
    """Explicit paid workflow. Keep all raw benchmark artifacts ephemeral."""
    plan = benchmark_plan(
        level, official_runs=official_runs,
        customer_runs=customer_runs, max_gen_toks=max_gen_toks,
        reasoning_effort=reasoning_effort,
    )
    local_check = benchmark_preflight(level)
    if not local_check["ready"]:
        failures = ", ".join(
            item["name"] for item in local_check["checks"]
            if item["status"] == "fail"
        )
        raise RuntimeError(
            "local Benchmark preflight failed: " + failures
            + "; run model-detect glm53 doctor before executing"
        )
    try:
        harness_version = version("lm-eval")
    except PackageNotFoundError:
        raise RuntimeError("cannot determine installed lm-eval version") from None

    all_runs: dict[str, list[list[dict[str, Any]]]] = {}
    with tempfile.TemporaryDirectory(prefix="model-detect-glm53-benchmark-") as tmp:
        for label, url, key, count in (
            ("official", official_url, official_key, official_runs),
            ("customer", customer_url, customer_key, customer_runs),
        ):
            collected = []
            for index in range(1, count + 1):
                output = Path(tmp) / label / str(index)
                result = lm_eval.run_endpoint(
                    base_url=url, model="glm-5.3", api_key=key,
                    tasks=plan["tasks"], output_path=output,
                    limit=plan["limit"], num_concurrent=1, max_retries=0,
                    max_gen_toks=plan["max_gen_toks"],
                    reasoning_effort=plan["reasoning_effort"],
                    timeout_seconds=3600,
                )
                if result["returncode"] != 0:
                    raise RuntimeError(
                        f"{label} benchmark failed in run {index}: "
                        "check local lm_eval installation and endpoint logs"
                    )
                parsed = lm_eval.parse_result_file(lm_eval.discover_result_file(output))
                collected.append([
                    _check_task(
                        row, expected_reasoning_effort=plan["reasoning_effort"]
                    ) for row in parsed
                ])
            all_runs[label] = collected
    compared = compare_benchmark_runs(
        all_runs["official"], all_runs["customer"],
        plan=plan, harness_version=harness_version,
    )
    compared["requested_reasoning_effort"] = plan["reasoning_effort"]
    compared["generation_parameter_provenance"] = (
        "requested via lm-eval 0.4.13 --gen_kwargs; no captured wire "
        "request or server-side reasoning-setting verification"
    )
    return compared

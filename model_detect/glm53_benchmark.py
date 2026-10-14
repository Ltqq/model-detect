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

# Only generation-based suites; local-chat-completions does not implement
# multiple-choice loglikelihood (so default MMLU-Pro cannot run here).
BENCHMARK_PROFILES = {
    "smoke": {"tasks": ["gsm8k", "ifeval"], "limit": 5},
    "standard": {"tasks": ["gsm8k", "ifeval", "minerva_math500"], "limit": 25},
    "deep": {"tasks": ["gsm8k", "ifeval", "minerva_math500"], "limit": 100},
}
BENCHMARK_SUITE = "glm53-lm-eval-generative-v1"


def benchmark_plan(level: str, *, official_runs: int, customer_runs: int,
                   max_gen_toks: int = 8192) -> dict[str, Any]:
    if level not in BENCHMARK_PROFILES:
        raise ValueError("unknown benchmark level")
    if not (1 <= official_runs <= 5 and 1 <= customer_runs <= 5):
        raise ValueError("benchmark runs must be between 1 and 5")
    if not (256 <= max_gen_toks <= 32768):
        raise ValueError("benchmark max generation tokens must be 256..32768")
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


def _check_task(row: Any) -> dict[str, Any]:
    obs = row.observed if isinstance(row.observed, dict) else {}
    meta = row.metadata
    score = row.score
    good = bool(
        score is not None
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
        "dataset_version": obs.get("version"),
        "sample_count": obs.get("effective_samples"),
        "config_sha256": obs.get("task_config_hash"),
        "contract_version": obs.get("task_contract_version"),
        "valid": good,
    }


def compare_benchmark_runs(
    official: list[list[dict[str, Any]]],
    customer: list[list[dict[str, Any]]],
    *,
    plan: dict[str, Any],
    harness_version: str,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for name in plan["tasks"]:
        off = [next((r for r in run if r["task"] == name), None) for run in official]
        ven = [next((r for r in run if r["task"] == name), None) for run in customer]
        entries = off + ven
        validity = (
            bool(entries)
            and all(r and r.get("valid") and r.get("score") is not None for r in entries)
            and all(
                (r["dataset_version"], r["sample_count"], r["config_sha256"],
                 r["contract_version"], r["metric"])
                == (entries[0]["dataset_version"], entries[0]["sample_count"],
                    entries[0]["config_sha256"], entries[0]["contract_version"],
                    entries[0]["metric"])
                for r in entries if r
            )
        )
        if validity:
            official_mean = sum(r["score"] for r in off) / len(off)
            customer_mean = sum(r["score"] for r in ven) / len(ven)
            delta = customer_mean - official_mean
            status = "measured_difference"
            reason = "分数是同配置客观任务的观测差异，未验证统计显著性或身份"
        else:
            official_mean = customer_mean = delta = None
            status = "incomparable"
            reason = "任务缺失、评分指标、样本量、任务配置或数据集版本不一致"
        tasks.append({
            "task": name, "status": status, "reason": reason,
            "official_mean": official_mean,
            "customer_mean": customer_mean, "delta": delta,
            "official_scores": [r["score"] if r else None for r in off],
            "customer_scores": [r["score"] if r else None for r in ven],
            "sample_count": entries[0].get("sample_count") if entries[0] else None,
            "metric": entries[0].get("metric") if entries[0] else None,
            "dataset_version": entries[0].get("dataset_version") if entries[0] else None,
            "task_config_sha256": entries[0].get("config_sha256") if entries[0] else None,
            "task_contract_version": entries[0].get("contract_version") if entries[0] else None,
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
            "reasoning_effort equivalence across providers remains unverified.",
            "lm-eval network usage is not captured by native request accounting.",
            "No model authenticity or statistically significant regression claim "
            "is derived from a small benchmark sample.",
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
) -> dict[str, Any]:
    """Explicit paid workflow. Keep all raw benchmark artifacts ephemeral."""
    plan = benchmark_plan(
        level, official_runs=official_runs,
        customer_runs=customer_runs, max_gen_toks=max_gen_toks,
    )
    if not lm_eval.availability()["available"]:
        raise RuntimeError(
            "lm-eval is unavailable; install pip install 'lm_eval[api]'"
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
                    timeout_seconds=3600,
                )
                if result["returncode"] != 0:
                    raise RuntimeError(
                        f"{label} benchmark failed in run {index}: "
                        "check local lm_eval installation and endpoint logs"
                    )
                parsed = lm_eval.parse_result_file(lm_eval.discover_result_file(output))
                collected.append([_check_task(row) for row in parsed])
            all_runs[label] = collected
    return compare_benchmark_runs(
        all_runs["official"], all_runs["customer"],
        plan=plan, harness_version=harness_version,
    )

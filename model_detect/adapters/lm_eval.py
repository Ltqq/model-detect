from __future__ import annotations

import json
import os
import shutil
import subprocess

import yaml
from pathlib import Path
from typing import Any

from ..models import ProbeResult, ProbeStatus


def availability() -> dict[str, Any]:
    binary = shutil.which("lm_eval")
    return {
        "available": bool(binary),
        "binary": binary,
        "engine": "EleutherAI/lm-evaluation-harness",
        "model_type": "local-chat-completions",
    }


def normalize_chat_endpoint(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("base_url is required")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return value + "/chat/completions"
    return value + "/v1/chat/completions"


def build_command(
    *,
    base_url: str,
    model: str,
    tasks: list[str],
    output_path: str | Path,
    num_concurrent: int = 1,
    max_retries: int = 3,
    limit: int | None = None,
    binary: str | None = None,
) -> list[str]:
    if not model.strip():
        raise ValueError("model is required")
    clean_tasks = [task.strip() for task in tasks if task.strip()]
    if not clean_tasks:
        raise ValueError("at least one lm-eval task is required")
    executable = binary or shutil.which("lm_eval")
    if not executable:
        raise RuntimeError(
            "lm-evaluation-harness is unavailable; install it so the lm_eval CLI is on PATH"
        )

    endpoint = normalize_chat_endpoint(base_url)
    model_args = ",".join(
        [
            f"model={model}",
            f"base_url={endpoint}",
            f"num_concurrent={max(1, int(num_concurrent))}",
            f"max_retries={max(0, int(max_retries))}",
            "tokenized_requests=False",
        ]
    )
    cmd = [
        executable,
        "--model",
        "local-chat-completions",
        "--model_args",
        model_args,
        "--tasks",
        ",".join(clean_tasks),
        "--apply_chat_template",
        "--output_path",
        str(output_path),
    ]
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        cmd.extend(["--limit", str(limit)])
    return cmd


def run_endpoint(
    *,
    base_url: str,
    model: str,
    api_key: str,
    tasks: list[str],
    output_path: str | Path,
    num_concurrent: int = 1,
    max_retries: int = 3,
    limit: int | None = None,
    timeout_seconds: float = 1800,
    binary: str | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    cmd = build_command(
        base_url=base_url,
        model=model,
        tasks=tasks,
        output_path=output,
        num_concurrent=num_concurrent,
        max_retries=max_retries,
        limit=limit,
        binary=binary,
    )
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = api_key
    proc = subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "engine": "EleutherAI/lm-evaluation-harness",
        "model_type": "local-chat-completions",
        "returncode": proc.returncode,
        "output_path": str(output),
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
    }



def load_builtin_profiles() -> dict[str, Any]:
    from importlib.resources import files

    import yaml

    path = files("model_detect").joinpath("data/lm_eval_profiles.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = raw.get("tasks") or {}
    profiles = raw.get("profiles") or {}
    if not isinstance(tasks, dict) or not isinstance(profiles, dict):
        raise ValueError("invalid lm-eval profile data")
    return {
        "version": raw.get("version"),
        "tasks": tasks,
        "profiles": profiles,
    }


def get_builtin_profile(name: str) -> dict[str, Any]:
    data = load_builtin_profiles()
    profile = data["profiles"].get(name)
    if not isinstance(profile, dict):
        raise KeyError(f"unknown lm-eval profile: {name}")
    task_names = profile.get("tasks") or []
    if not isinstance(task_names, list) or not task_names:
        raise ValueError(f"lm-eval profile {name!r} has no tasks")
    missing = [task for task in task_names if task not in data["tasks"]]
    if missing:
        raise ValueError(
            f"lm-eval profile {name!r} references unknown tasks: {missing}"
        )
    return {
        "name": name,
        "tasks": list(task_names),
        "limit": profile.get("limit"),
        "task_metadata": {
            task: data["tasks"][task]
            for task in task_names
        },
    }


def resolve_builtin_profile(
    name: str,
    *,
    include_native_overlap: bool = False,
) -> dict[str, Any]:
    profile = get_builtin_profile(name)
    original_tasks = list(profile["tasks"])
    if include_native_overlap:
        selected_tasks = original_tasks
        skipped_tasks: list[str] = []
    else:
        selected_tasks = [
            task
            for task in original_tasks
            if not bool(profile["task_metadata"][task].get("native_overlap"))
        ]
        skipped_tasks = [
            task
            for task in original_tasks
            if task not in selected_tasks
        ]

    if not selected_tasks:
        raise ValueError(
            f"lm-eval profile {name!r} has no non-overlapping tasks to run"
        )

    return {
        **profile,
        "tasks": selected_tasks,
        "candidate_tasks": original_tasks,
        "skipped_tasks": skipped_tasks,
        "include_native_overlap": include_native_overlap,
    }


def run_builtin_profile(
    *,
    profile_name: str,
    base_url: str,
    model: str,
    api_key: str,
    output_path: str | Path,
    include_native_overlap: bool = False,
    num_concurrent: int = 1,
    max_retries: int = 3,
    timeout_seconds: float = 1800,
    binary: str | None = None,
) -> dict[str, Any]:
    profile = resolve_builtin_profile(
        profile_name,
        include_native_overlap=include_native_overlap,
    )
    result = run_endpoint(
        base_url=base_url,
        model=model,
        api_key=api_key,
        tasks=profile["tasks"],
        output_path=output_path,
        num_concurrent=num_concurrent,
        max_retries=max_retries,
        limit=profile["limit"],
        timeout_seconds=timeout_seconds,
        binary=binary,
    )
    return {
        **result,
        "profile": profile_name,
        "tasks": profile["tasks"],
        "skipped_tasks": profile["skipped_tasks"],
        "deduplicated_against_capability_lite": not include_native_overlap,
    }





_SENSITIVE_PROFILE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "password",
}


def _reject_profile_secrets(value: Any, *, path: str = "profile") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SENSITIVE_PROFILE_KEYS:
                raise ValueError(
                    f"lm-eval profile must not contain secrets: {path}.{key}"
                )
            _reject_profile_secrets(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_profile_secrets(nested, path=f"{path}[{index}]")


def load_profile_file(
    path: str | Path,
    profile_name: str,
) -> dict[str, Any]:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("lm-eval profile YAML root must be an object")
    _reject_profile_secrets(raw)

    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("lm-eval profile YAML must contain a profiles object")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise KeyError(f"unknown lm-eval profile: {profile_name}")

    tasks = profile.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"lm-eval profile {profile_name!r} has no tasks")

    clean_tasks: list[str] = []
    for task in tasks:
        if not isinstance(task, str) or not task.strip():
            raise ValueError(
                f"lm-eval profile {profile_name!r} contains an invalid task"
            )
        task_name = task.strip()
        if task_name not in clean_tasks:
            clean_tasks.append(task_name)

    limit = profile.get("limit")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("lm-eval profile limit must be a positive integer")

    include_overlap = profile.get("include_native_overlap", False)
    if not isinstance(include_overlap, bool):
        raise ValueError("include_native_overlap must be boolean")

    builtin_tasks = load_builtin_profiles()["tasks"]
    selected_tasks = list(clean_tasks)
    skipped_tasks: list[str] = []
    if not include_overlap:
        selected_tasks = [
            task
            for task in clean_tasks
            if not bool((builtin_tasks.get(task) or {}).get("native_overlap"))
        ]
        skipped_tasks = [
            task for task in clean_tasks if task not in selected_tasks
        ]

    if not selected_tasks:
        raise ValueError(
            f"lm-eval profile {profile_name!r} has no tasks after overlap filtering"
        )

    return {
        "name": profile_name,
        "source": str(config_path),
        "tasks": selected_tasks,
        "candidate_tasks": clean_tasks,
        "skipped_tasks": skipped_tasks,
        "limit": limit,
        "include_native_overlap": include_overlap,
    }


def run_profile_file(
    *,
    profile_file: str | Path,
    profile_name: str,
    base_url: str,
    model: str,
    api_key: str,
    output_path: str | Path,
    num_concurrent: int = 1,
    max_retries: int = 3,
    timeout_seconds: float = 1800,
    binary: str | None = None,
) -> dict[str, Any]:
    profile = load_profile_file(profile_file, profile_name)
    result = run_endpoint(
        base_url=base_url,
        model=model,
        api_key=api_key,
        tasks=profile["tasks"],
        output_path=output_path,
        num_concurrent=num_concurrent,
        max_retries=max_retries,
        limit=profile["limit"],
        timeout_seconds=timeout_seconds,
        binary=binary,
    )
    return {
        **result,
        "profile": profile["name"],
        "profile_source": profile["source"],
        "tasks": profile["tasks"],
        "skipped_tasks": profile["skipped_tasks"],
        "deduplicated_against_capability_lite": (
            not profile["include_native_overlap"]
        ),
    }

_PRIMARY_METRICS: dict[str, list[str]] = {
    "gsm8k": [
        "exact_match,flexible-extract",
        "exact_match,strict-match",
        "exact_match",
    ],
    "ifeval": [
        "prompt_level_strict_acc",
        "inst_level_strict_acc",
        "prompt_level_loose_acc",
    ],
    "truthfulqa_gen": [
        "bleu_acc",
        "rougeL_acc",
        "rouge1_acc",
    ],
}


def _numeric_metrics(values: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in values.items():
        if "stderr" in key.lower() or key == "alias":
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            metrics[str(key)] = float(value)
    return metrics


def _select_primary_metric(
    task: str,
    metrics: dict[str, float],
) -> tuple[str | None, float | None]:
    for key in _PRIMARY_METRICS.get(task, []):
        if key in metrics:
            return key, metrics[key]

    generic_priority = ["acc", "acc_norm", "exact_match", "f1"]
    for preferred in generic_priority:
        if preferred in metrics:
            return preferred, metrics[preferred]

    bounded = [
        (key, value)
        for key, value in metrics.items()
        if 0.0 <= value <= 1.0
    ]
    if bounded:
        return bounded[0]
    if metrics:
        key = next(iter(metrics))
        return key, metrics[key]
    return None, None


def parse_result_payload(
    data: dict[str, Any],
    *,
    source_path: str | None = None,
) -> list[ProbeResult]:
    raw_results = data.get("results")
    if not isinstance(raw_results, dict):
        raise ValueError("lm-eval result JSON is missing the results object")

    versions = data.get("versions") if isinstance(data.get("versions"), dict) else {}
    out: list[ProbeResult] = []
    for task, raw_metrics in raw_results.items():
        if not isinstance(raw_metrics, dict):
            continue
        metrics = _numeric_metrics(raw_metrics)
        metric_name, metric_value = _select_primary_metric(str(task), metrics)

        score = None
        if metric_value is not None and 0.0 <= metric_value <= 1.0:
            score = metric_value

        status = ProbeStatus.PASS if metric_name is not None else ProbeStatus.INSUFFICIENT
        summary = (
            f"lm-eval {task}: {metric_name}={metric_value:.4f}"
            if metric_name is not None and metric_value is not None
            else f"lm-eval {task}: no numeric metric found"
        )
        safe_task = "".join(
            char if char.isalnum() or char in {"_", "-", "."} else "_"
            for char in str(task)
        )
        out.append(
            ProbeResult(
                probe_id=f"capability.external.lm_eval.{safe_task}",
                category="capability",
                status=status,
                score=score,
                confidence=0.8 if score is not None else 0.4,
                summary=summary,
                observed={
                    "task": task,
                    "primary_metric": metric_name,
                    "primary_value": metric_value,
                    "metrics": metrics,
                    "version": versions.get(task),
                },
                metadata={
                    "engine": "lm-evaluation-harness",
                    "task": task,
                    "primary_metric": metric_name,
                    "benchmark_score_only": True,
                    "threshold_interpretation": False,
                    "source_path": source_path,
                },
            )
        )
    return out


def parse_result_file(path: str | Path) -> list[ProbeResult]:
    result_path = Path(path)
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("lm-eval result JSON root must be an object")
    return parse_result_payload(raw, source_path=str(result_path))

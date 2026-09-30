from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


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

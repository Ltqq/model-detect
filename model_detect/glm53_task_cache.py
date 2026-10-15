"""Optional, isolated and strictly offline lm-eval task/data cache probe.

The basic dependency preflight remains a fast, non-executing check. This opt-in
verification actually instantiates every selected task in a subprocess with
Hugging Face offline flags, no API key, and an execution time limit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from .glm53_benchmark import BENCHMARK_PROFILES

_CHILD = r"""
import json
from lm_eval.tasks import TaskManager, get_task_dict
tasks = json.loads(__import__('sys').argv[1])
manager = TaskManager()
for name in tasks:
    loaded = get_task_dict([name], task_manager=manager)
    if not loaded:
        raise RuntimeError('task not loaded')
print('MODEL_DETECT_TASK_CACHE_OK')
"""


def verify_offline_task_cache(level: str, *, timeout_seconds: int = 180) -> dict[str, Any]:
    if level not in BENCHMARK_PROFILES:
        raise ValueError("invalid benchmark level")
    if not 5 <= timeout_seconds <= 600:
        raise ValueError("timeout must be 5..600 seconds")
    tasks = list(BENCHMARK_PROFILES[level]["tasks"])
    env = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "WANDB_DISABLED": "true",
    }
    # No secrets are needed to initialize local datasets.
    for name in tuple(env):
        if any(term in name.upper() for term in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")):
            env.pop(name, None)
    try:
        result = subprocess.run(
            [sys.executable, "-c", _CHILD, json.dumps(tasks)],
            env=env, capture_output=True, text=True, timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        status = "timeout"
    except OSError:
        status = "subprocess_unavailable"
    else:
        status = (
            "verified" if result.returncode == 0
            and "MODEL_DETECT_TASK_CACHE_OK" in result.stdout.splitlines()
            else "unverified"
        )
    return {
        "status": status,
        "verified": status == "verified",
        "tasks": tasks,
        "offline_flags_enforced": True,
        "model_api_calls": 0,
        "warning": (
            "Offline task instantiation does not prove all future input data, "
            "generation settings, grading code and models remain unchanged. "
            "Third-party task custom code may ignore the HF offline flags."
        ),
    }

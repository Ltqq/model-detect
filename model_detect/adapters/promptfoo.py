from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


API_KEY_ENV = "MODEL_DETECT_PROMPTFOO_KEY"


def availability() -> dict[str, Any]:
    binary = shutil.which("promptfoo")
    return {
        "available": bool(binary),
        "binary": binary,
        "engine": "promptfoo/promptfoo",
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


def build_http_provider(
    *,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    if not model.strip():
        raise ValueError("model is required")

    endpoint = normalize_chat_endpoint(base_url)
    provider_id = "http" if endpoint.startswith("http://") else "https"
    return {
        "id": provider_id,
        "label": f"model-detect:{model}",
        "config": {
            "url": endpoint,
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {{{{env.{API_KEY_ENV}}}}}",
            },
            "body": {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "{{prompt}}",
                    }
                ],
            },
            "transformResponse": (
                "({ output: json.choices?.[0]?.message?.content ?? '', "
                "metadata: { model: json.model, "
                "finish_reason: json.choices?.[0]?.finish_reason, "
                "tool_calls: json.choices?.[0]?.message?.tool_calls } })"
            ),
        },
    }


def write_eval_config(
    path: str | Path,
    *,
    provider: dict[str, Any],
    prompts: list[Any],
    tests: list[dict[str, Any]],
) -> Path:
    if not prompts:
        raise ValueError("promptfoo config requires at least one prompt")
    if not tests:
        raise ValueError("promptfoo config requires at least one test")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "providers": [provider],
        "prompts": prompts,
        "tests": tests,
    }
    target.write_text(
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return target


def build_command(
    *,
    config_path: str | Path,
    output_path: str | Path,
    binary: str | None = None,
) -> list[str]:
    executable = binary or shutil.which("promptfoo")
    if not executable:
        raise RuntimeError(
            "promptfoo is unavailable; install the promptfoo CLI and ensure it is on PATH"
        )

    return [
        executable,
        "eval",
        "-c",
        str(config_path),
        "--no-cache",
        "--no-progress-bar",
        "--no-table",
        "-o",
        str(output_path),
    ]


def run_eval(
    *,
    config_path: str | Path,
    output_path: str | Path,
    api_key: str,
    timeout_seconds: float = 900,
    binary: str | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(
        config_path=config_path,
        output_path=output,
        binary=binary,
    )
    env = dict(os.environ)
    env[API_KEY_ENV] = api_key
    proc = subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "engine": "promptfoo",
        "returncode": proc.returncode,
        "config_path": str(config_path),
        "output_path": str(output),
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-4000:],
    }

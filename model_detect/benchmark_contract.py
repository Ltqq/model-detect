"""Stable, versioned lm-eval task contract for cross-endpoint comparison.

Task configs are evidence, not URLs. Only known transport-only fields may be
removed; all other fields (including prompts, seeds, metrics and generation
options) must remain part of the comparison. Never hash Python object addresses.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from typing import Any

CONTRACT_VERSION = "lm-eval-task-v2"
_FUNCTION_RE = re.compile(r"^<function ([A-Za-z_][\w.]*) at 0x[0-9a-fA-F]+>$")
_ADDRESS_RE = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")
_TRANSPORT_ONLY = frozenset({
    "base_url", "api_key", "token", "authorization", "num_concurrent", "max_retries",
})
_RUN_CONFIG_FIELDS = (
    "model", "limit", "gen_kwargs", "random_seed", "numpy_seed",
    "torch_seed", "fewshot_seed",
)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, str):
        found = _FUNCTION_RE.fullmatch(value)
        if found:
            # The function identity is still tied to the harness version and
            # task version; identical names alone are NOT proof of same code.
            return {"callable_name": found.group(1)}
        if _ADDRESS_RE.search(value):
            raise ValueError("unrecognized runtime memory address in task contract")
        return value
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise ValueError("unsupported non-JSON task contract value")


def _normalize_config_source(value: Any) -> Any:
    if not isinstance(value, str):
        return _normalize_value(value)
    path = value.replace("\\", "/")
    marker = "/lm_eval/tasks/"
    if marker in path:
        return "lm_eval/tasks/" + path.split(marker, 1)[1]
    # Custom task configurations are NOT normalized by basename: different
    # absolute paths might really be different custom task code.
    return _normalize_value(value)


def _clean_model_args(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("{"):
            try:
                value = ast.literal_eval(raw)
            except (SyntaxError, ValueError) as exc:
                raise ValueError("unparseable lm-eval model_args") from exc
        else:
            parts = raw.split(",")
            if not all("=" in entry for entry in parts):
                raise ValueError("unparseable lm-eval model_args")
            value = dict(entry.split("=", 1) for entry in parts)
    if not isinstance(value, dict):
        raise ValueError("unparseable lm-eval model_args")
    return {
        str(k): _normalize_value(v)
        for k, v in value.items()
        if str(k).lower() not in _TRANSPORT_ONLY
    }


def task_contract(task: str, config: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Produce a strict canonical subset: strip only transport / machine noise.

    Missing task config or unknown object representations fail closed.
    """
    if not isinstance(config, dict) or not config:
        raise ValueError("task config missing")
    normalized = _normalize_value(config)
    metadata = normalized.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("base_url", None)
        metadata.pop("api_key", None)
        metadata.pop("authorization", None)
        if "config_source" in metadata:
            metadata["config_source"] = _normalize_config_source(metadata["config_source"])
    globals_cfg = run.get("config")
    global_contract: dict[str, Any] = {}
    if isinstance(globals_cfg, dict):
        for key in _RUN_CONFIG_FIELDS:
            if key in globals_cfg:
                global_contract[key] = _normalize_value(globals_cfg[key])
        if "model_args" in globals_cfg:
            global_contract["model_args"] = _clean_model_args(globals_cfg["model_args"])
    for key in ("chat_template_sha", "system_instruction_sha", "fewshot_as_multiturn"):
        if key in run:
            global_contract[key] = _normalize_value(run[key])
    nshot = run.get("n-shot")
    if isinstance(nshot, dict) and task in nshot:
        global_contract["task_num_fewshot"] = _normalize_value(nshot[task])
    task_hashes = run.get("task_hashes")
    if isinstance(task_hashes, dict) and task in task_hashes:
        global_contract["task_source_hash"] = _normalize_value(task_hashes[task])
    return {
        "contract_version": CONTRACT_VERSION,
        "task": task,
        "harness_version": _normalize_value(run.get("lm_eval_version")),
        "harness_git_hash": _normalize_value(run.get("git_hash")),
        "task_version": _normalize_value((run.get("versions") or {}).get(task)),
        "task_config": normalized,
        "run_options": global_contract,
    }


def task_contract_sha256(task: str, config: dict[str, Any], run: dict[str, Any]) -> str:
    contract = task_contract(task, config, run)
    data = json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

"""Offline GLM-5.3 benchmark dependency preflight.

No subprocess benchmark execution, API request, dataset download, or secret
access is performed here. Only lm-eval 0.4.13 is an integration-tested target;
dataset cache availability cannot be inferred reliably from a Python import.
"""

from __future__ import annotations

import importlib.util
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .adapters.lm_eval import resolve_lm_eval_executable

VALID_LEVELS = {"smoke", "standard", "deep"}
VERIFIED_HARNESS = "0.4.13"


def _installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, AttributeError, ValueError):
        return False


def _nltk_resource(name: str) -> bool:
    if not _installed("nltk"):
        return False
    try:
        from nltk.data import find

        find(f"tokenizers/{name}")
        return True
    except (ImportError, LookupError, OSError):
        return False


def benchmark_preflight(level: str) -> dict[str, Any]:
    """Check known local prerequisites; fail closed for missing essentials.

    A successful preflight is not proof of downloaded dataset/revision, model
    parameter semantics, a runnable scoring task, or future API availability.
    """
    if level not in VALID_LEVELS:
        raise ValueError("benchmark level must be smoke, standard or deep")

    checks: list[dict[str, str]] = []

    def add(name: str, status: str, explanation: str) -> None:
        checks.append({
            "name": name,
            "status": status,
            "explanation": explanation,
        })

    try:
        installed_version = version("lm-eval")
    except PackageNotFoundError:
        installed_version = None
    if installed_version == VERIFIED_HARNESS:
        add("lm-eval-version", "pass", f"lm-eval {VERIFIED_HARNESS}")
    else:
        add(
            "lm-eval-version", "fail",
            f"需要经实测的 lm-eval=={VERIFIED_HARNESS}；"
            f"当前：{installed_version or '未安装'}。"
            f"安装：python -m pip install 'lm-eval[api,math]=={VERIFIED_HARNESS}'",
        )

    binary = resolve_lm_eval_executable()
    add(
        "lm-eval-entrypoint",
        "pass" if binary else "fail",
        "检测到当前 Python 环境的 lm_eval 命令"
        if binary else "未找到 lm_eval 可执行入口；检查当前虚拟环境安装",
    )

    required = ("lm_eval", "aiohttp", "datasets", "langdetect", "immutabledict", "nltk")
    if level in {"standard", "deep"}:
        required += ("math_verify", "antlr4")
    for package in required:
        installed = _installed(package)
        add(
            f"python:{package}", "pass" if installed else "fail",
            f"{package} 已安装" if installed else
            f"缺少 {package}；先安装/修复 lm-eval 及对应 task 的可选依赖",
        )
    for name in ("punkt", "punkt_tab"):
        found = _nltk_resource(name)
        add(
            f"nltk:{name}", "pass" if found else "fail",
            f"本机存在 NLTK {name}" if found else
            f"缺少 NLTK {name}；在预热步骤执行 "
            f"python -c \"import nltk; nltk.download('{name}')\"",
        )
    add(
        "dataset-cache", "unverified",
        "未访问 Hugging Face，也没有证明所选 task 的完整数据集已缓存。"
        "必须先在独立准备步骤预热/核对版本；切勿把依赖检查当作"
        "零网络、零付费的正式 Benchmark 运行保证。",
    )
    ready = all(item["status"] != "fail" for item in checks)
    return {
        "benchmark_level": level,
        "verified_harness_version": VERIFIED_HARNESS,
        "installed_harness_version": installed_version,
        "binary_found": bool(binary),
        "checks": checks,
        "ready": ready,
        "dataset_cache_verified": False,
        "network_calls": 0,
        "api_calls": 0,
        "warning": (
            "ready 表示本地已知基础依赖齐全；不代表题集缓存、"
            "task 注册、实际生效推理参数或第三方模型 API 已通过验收。"
        ),
    }

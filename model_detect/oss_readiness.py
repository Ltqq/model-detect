"""Offline-only OSS readiness matrix; process availability is not result trust."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .adapters import lm_eval, fingerprint, proxy_sleuth, promptfoo


def local_oss_readiness() -> dict[str, Any]:
    try:
        lm_version = version("lm-eval")
    except PackageNotFoundError:
        lm_version = None
    engines = {
        "lm-evaluation-harness": {
            **lm_eval.availability(), "installed_version": lm_version,
            "tested_version": "0.4.13",
            "version_compatible": lm_version == "0.4.13",
        },
        "promptfoo": {**promptfoo.availability(),
                      "installed_version": None, "version_compatible": None},
        "proxy-sleuth": {**proxy_sleuth.availability(),
                        "installed_version": None, "version_compatible": None},
        "llm-fingerprint-detector": {**fingerprint.availability(),
                                     "installed_version": None, "version_compatible": None},
    }
    for item in engines.values():
        item["adapter_exists"] = True
        item["executable_found"] = bool(item.pop("available", False))
        item["runtime_verified"] = False
        item["result_trust_verified"] = False
        item["readiness"] = (
            "binary_detected_not_tested" if item["executable_found"]
            else "dependency_missing"
        )
    return {
        "schema": "oss-readiness-v1",
        "checks": engines,
        "api_calls": 0,
        "network_calls_by_model_detect": 0,
        "warning": (
            "Binary presence is not an integration test. "
            "No external process executed or model API called. "
            "npx presence may still require network package download."
        ),
    }

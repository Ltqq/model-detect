"""Pinned official Kimi Vendor Verifier scope and local JUnit evidence importer.

Import never executes pytest or calls a model. Original failure logs, prompts,
keys, request URLs and testcase names are deliberately not persisted.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any

OFFICIAL_REPOSITORY = "MoonshotAI/Kimi-Vendor-Verifier"
OFFICIAL_COMMIT = "66092cf444c97356c0e11c5078c67116390615d9"
OFFICIAL_LICENSE = "MIT"
OFFICIAL_CASES: dict[str, dict[str, str]] = {
    "params": {
        "path": "tests/params",
        "purpose": "temperature/top_p/penalty/n fixed parameters",
        "local_mapping": "protocol.parameter_constraints",
    },
    "k3_features": {
        "path": "tests/k3_features",
        "purpose": "dynamic tools, response_format, tool_choice, thinking effort",
        "local_mapping": "protocol/tools/routing",
    },
    "tool_call_json_schema": {
        "path": "tests/tool_call_json_schema",
        "purpose": "tool_calls[].function.arguments JSON Schema verification",
        "local_mapping": "protocol.tools",
    },
    "prompt_tokens": {
        "path": "tests/prompt_tokens",
        "purpose": "vendor reported prompt token count against fixed official cases",
        "local_mapping": "usage.prompt_tokens",
    },
}


def plan_official_subset(names: list[str]) -> dict[str, Any]:
    chosen = list(dict.fromkeys(names))
    if not chosen:
        raise ValueError("at least one official case suite is required")
    unknown = sorted(set(chosen) - OFFICIAL_CASES.keys())
    if unknown:
        raise ValueError("unknown official Kimi suite(s): " + ", ".join(unknown))
    return {
        "source_repository": OFFICIAL_REPOSITORY,
        "source_commit": OFFICIAL_COMMIT,
        "license": OFFICIAL_LICENSE,
        "suites": [{"name": name, **OFFICIAL_CASES[name]} for name in chosen],
        "estimated_requests": None,
        "paid_run_requested": False,
        "warning": (
            "Pytest parametrization and test data determine request counts; "
            "the tool deliberately does not invent a fixed token budget. "
            "Vision, BEAM 1M, DeepSWE and OCRBench/MMMU are excluded."
        ),
    }


def import_official_junit(
    xml_file: str | Path, *, suite: str, model: str,
) -> dict[str, Any]:
    if suite not in OFFICIAL_CASES:
        raise ValueError("unrecognized pinned official suite")
    if not model.strip():
        raise ValueError("model must not be empty")
    path = Path(xml_file)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("JUnit evidence exceeds 16MB limit")
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML entity declarations not permitted")
    root = ET.fromstring(raw)
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("expected JUnit testsuite or testsuites root")
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError("empty JUnit report must not count as tested")
    results = []
    for case in cases:
        name = (case.get("classname") or "") + "::" + (case.get("name") or "")
        if not name.strip(":"):
            raise ValueError("JUnit case missing identifier")
        # Never persist raw testcase names, which can contain prompts/keys/URLs.
        key = hashlib.sha256(name.encode("utf-8")).hexdigest()
        if case.find("error") is not None:
            state = "error"
        elif case.find("failure") is not None:
            state = "fail"
        elif case.find("skipped") is not None:
            state = "skipped"
        else:
            state = "pass"
        results.append({"testcase_sha256": key, "status": state})
    tally = {key: sum(x["status"] == key for x in results)
             for key in ("pass", "fail", "error", "skipped")}
    return {
        "schema": "kimi-official-junit-import-v1",
        "source_repository": OFFICIAL_REPOSITORY,
        "source_commit": OFFICIAL_COMMIT,
        "suite": suite, "model": model.strip(),
        "scope_path": OFFICIAL_CASES[suite]["path"],
        "original_junit_sha256": hashlib.sha256(raw).hexdigest(),
        "evidence_source": "user_supplied_unattested_junit",
        "result": "inconclusive" if tally["error"] or tally["skipped"]
                  else ("failure_observed" if tally["fail"] else "all_cases_passed_in_import"),
        "counts": tally,
        "cases": results,
        "identity_strength": "none",
        "limitations": [
            "Import is not proof that pinned official code actually produced the XML.",
            "No model API calls were made during import.",
            "A pass means supplied JUnit cases passed, NOT genuine model identity.",
        ],
    }

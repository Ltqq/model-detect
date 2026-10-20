import subprocess

import pytest

from model_detect.adapters import fingerprint as fingerprint_adapter
from model_detect.adapters.fingerprint import (
    fingerprint_metadata_from_data,
    parse_verify_payload,
)
from model_detect.models import ProbeStatus


def sample_payload(split_half=0.12, verdict="match"):
    return {
        "verdict": verdict,
        "meanJsd": 0.18 if verdict == "match" else 0.48,
        "comparison": {
            "meanJsd": 0.18 if verdict == "match" else 0.48,
            "verdict": verdict,
            "comparableCellCount": 2,
            "protocolMismatch": False,
            "thresholds": {"match": 0.25, "mismatch": 0.35},
            "baselines": {
                "sameModelSelf": 0.14,
                "sameModelCrossProvider": 0.227,
                "differentModel": 0.463,
            },
            "cells": [
                {
                    "cellId": "random-number-1-100:en",
                    "jsd": 0.11,
                    "validA": 25,
                    "validB": 25,
                },
                {
                    "cellId": "random-color:zh",
                    "jsd": 0.25,
                    "validA": 24,
                    "validB": 25,
                },
            ],
        },
        "target": {
            "fingerprint": {
                "formatVersion": 1,
                "protocol": "one-token/v1",
                "model": "kimi-k3",
                "collectedAt": "2026-09-30T00:00:00Z",
                "samplesPerCell": 25,
                "postReasoning": False,
                "cells": {
                    "random-number-1-100:en": {},
                    "random-color:zh": {},
                },
                "meta": {"tool": "llm-fingerprint-detector"},
            },
            "adapter": {
                "strategy": "openai-effort",
                "postReasoning": False,
            },
            "splitHalfJsd": split_half,
            "warnings": [],
        },
        "reference": {
            "formatVersion": 1,
            "protocol": "one-token/v1",
            "model": "kimi-k3",
            "collectedAt": "2026-09-29T00:00:00Z",
            "samplesPerCell": 25,
            "postReasoning": False,
            "cells": {
                "random-number-1-100:en": {},
                "random-color:zh": {},
            },
        },
        "warnings": [],
    }


def test_parse_verify_payload_returns_identity_and_routing_results():
    results, meta = parse_verify_payload(sample_payload(), returncode=0)
    by_id = {x.probe_id: x for x in results}

    primary = by_id["identity.fingerprint.reference_compare"]
    assert primary.status == ProbeStatus.PASS
    assert primary.metadata["identity_strength"] == "strong"
    assert len(primary.observed["cells"]) == 2
    assert primary.observed["target_fingerprint"]["protocol"] == "one-token/v1"

    self_result = by_id["identity.self_consistency"]
    assert self_result.status == ProbeStatus.PASS
    assert self_result.observed["split_half_jsd"] == 0.12

    routing = by_id["routing.fingerprint.consistency"]
    assert routing.status == ProbeStatus.PASS
    assert meta["split_half_jsd"] == 0.12
    assert len(meta["per_cell"]) == 2


def test_high_split_half_is_warning_not_identity_mismatch():
    results, _ = parse_verify_payload(sample_payload(split_half=0.42), returncode=0)
    by_id = {x.probe_id: x for x in results}
    assert by_id["identity.self_consistency"].status == ProbeStatus.WARN
    assert by_id["routing.fingerprint.consistency"].status == ProbeStatus.WARN
    assert by_id["identity.self_consistency"].metadata["does_not_imply_identity_mismatch"] is True


def test_fingerprint_metadata_shape():
    got = fingerprint_metadata_from_data(
        {
            "formatVersion": 1,
            "protocol": "one-token/v1",
            "model": "m",
            "collectedAt": "now",
            "samplesPerCell": 25,
            "postReasoning": True,
            "cells": {"a": {}, "b": {}},
            "meta": {"source": "test"},
        }
    )
    assert got["format_version"] == 1
    assert got["cell_count"] == 2
    assert got["post_reasoning"] is True


def test_fingerprint_npx_fallback_pins_exact_package_version(monkeypatch):
    monkeypatch.setattr(
        fingerprint_adapter.shutil,
        "which",
        lambda name: "/usr/bin/npx" if name == "npx" else None,
    )
    assert fingerprint_adapter._prefix() == [
        "/usr/bin/npx",
        "--yes",
        "llm-fingerprint-detector@0.1.0",
    ]


def test_fingerprint_global_binary_must_match_pinned_version(monkeypatch):
    monkeypatch.setattr(
        fingerprint_adapter.shutil,
        "which",
        lambda name: "/usr/local/bin/llm-fingerprint" if name == "llm-fingerprint" else None,
    )
    monkeypatch.setattr(
        fingerprint_adapter.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 0, stdout="0.1.0\n", stderr=""
        ),
    )
    assert fingerprint_adapter._prefix() == ["/usr/local/bin/llm-fingerprint"]


def test_fingerprint_global_binary_rejects_unknown_or_different_version(monkeypatch):
    monkeypatch.setattr(
        fingerprint_adapter.shutil,
        "which",
        lambda name: "/usr/local/bin/llm-fingerprint" if name == "llm-fingerprint" else None,
    )
    monkeypatch.setattr(
        fingerprint_adapter.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 0, stdout="0.9.9\n", stderr=""
        ),
    )
    with pytest.raises(RuntimeError, match="version mismatch"):
        fingerprint_adapter._prefix()


def test_fingerprint_availability_reports_version_mismatch(monkeypatch):
    monkeypatch.setattr(
        fingerprint_adapter.shutil,
        "which",
        lambda name: "/usr/local/bin/llm-fingerprint" if name == "llm-fingerprint" else None,
    )
    monkeypatch.setattr(
        fingerprint_adapter.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 0, stdout="0.9.9\n", stderr=""
        ),
    )
    status = fingerprint_adapter.availability()
    assert status["executable_found"] is True
    assert status["available"] is False
    assert status["installed_version"] == "0.9.9"
    assert status["version_compatible"] is False


def test_fingerprint_availability_marks_pinned_npx_as_network_dependent(monkeypatch):
    monkeypatch.setattr(
        fingerprint_adapter.shutil,
        "which",
        lambda name: "/usr/bin/npx" if name == "npx" else None,
    )
    status = fingerprint_adapter.availability()
    assert status["available"] is True
    assert status["executable_found"] is True
    assert status["version_compatible"] is None
    assert status["pinned_package_version"] == "0.1.0"
    assert status["requires_network_if_downloaded"] is True

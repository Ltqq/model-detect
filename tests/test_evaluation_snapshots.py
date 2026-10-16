from model_detect.evaluation_snapshots import (
    EvaluationSnapshot, compare_snapshots, save_snapshot,
)
import pytest


def snapshot(role, **overrides):
    data = {
        "model": "kimi-k3", "provider_role": role,
        "task_id": "ifeval", "engine_revision": "pinned-lm-eval",
        "dataset_revision": "pinned-dataset", "scorer_revision": "pinned-scorer",
        "sample_ids_sha256": "a" * 64,
        "generation_parameters_sha256": "b" * 64,
        "sample_count": 25, "metric_name": "prompt_strict_accuracy",
        "source_artifact_sha256": "c" * 64, "score": .96,
    }
    data.update(overrides)
    return EvaluationSnapshot(**data)


def test_identical_contract_can_compare_but_not_prove_identity():
    official = snapshot("official")
    supplier = snapshot("supplier", score=.92)
    result = compare_snapshots(official, supplier)
    assert result["comparable"]
    assert result["score_delta_vendor_minus_official"] == -0.04
    assert result["ceiling_warning"]
    assert result["identity_proven"] is False
    assert result["provenance_verified"] is False


def test_mismatched_dataset_or_sample_is_not_comparable():
    official = snapshot("official")
    supplier = snapshot("supplier", sample_ids_sha256="d" * 64)
    result = compare_snapshots(official, supplier)
    assert not result["comparable"]
    assert result["official_score"] is None
    assert "sample_ids_sha256" in result["mismatch_fields"]


def test_snapshot_never_overwrites_existing_reference(tmp_path):
    path = tmp_path / "reference.json"
    save_snapshot(snapshot("official"), path)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_snapshot(snapshot("supplier", score=.01), path)
    assert path.read_bytes() == original


def test_self_asserted_provenance_flag_is_never_official_attestation():
    official = snapshot("official", source_verified=True)
    vendor = snapshot("vendor", source_verified=True)
    result = compare_snapshots(official, vendor)
    assert result["claimed_source_verified"] is True
    assert result["provenance_verified"] is False
    assert result["identity_proven"] is False

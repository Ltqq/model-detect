"""A1: Reference persistence must not destroy paid trusted baselines."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_detect.references import ReferenceRegistry


def fake_report():
    return SimpleNamespace(
        target={"base_url": "https://example.test/v1", "model": "glm-5.3"},
        profile="standard",
        summary=SimpleNamespace(model_dump=lambda **_: {"overall_score": 0.75}),
        results=[],
    )


def create(registry, reference_id="official"):
    return registry.create_from_report(
        reference_id=reference_id, model="glm-5.3",
        provider="official", protocol="openai",
        report=fake_report(),
    )


def test_atomic_reference_creation_and_duplicate_preserves_bytes(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    saved = create(registry)
    root = registry.path_for("official")
    before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    assert saved.id == "official"
    assert set(before) == {"manifest.json", "protocol-signature.json"}
    with pytest.raises(FileExistsError):
        create(registry)
    assert {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()} == before
    assert not list(registry.root.glob(".reference-stage-*"))


def test_failed_stage_write_does_not_publish_or_leave_partial(tmp_path, monkeypatch):
    from model_detect import references
    registry = ReferenceRegistry(tmp_path / "refs")
    original_write = Path.write_text
    def fail_manifest(self, data, *args, **kwargs):
        if self.name == "manifest.json" and self.parent.name.startswith(".reference-stage-"):
            raise OSError("injected write failure")
        return original_write(self, data, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_manifest)
    with pytest.raises(OSError, match="injected"):
        create(registry, "new")
    assert not registry.path_for("new").exists()
    assert not list(registry.root.glob(".reference-stage-*"))


def test_missing_optional_fingerprint_does_not_leak_reference_directory(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    manifest = registry.create_from_report(
        reference_id="no-fingerprint", model="glm-5.3", provider="trusted",
        protocol="openai", report=fake_report(),
        fingerprint_path=tmp_path / "not-there.json",
    )
    assert manifest.fingerprint_artifact is None
    assert registry.get("no-fingerprint").id == "no-fingerprint"


@pytest.mark.parametrize("unsafe", [
    "../outside", "..", "a/b", "a\\\\b", "a b", "🚀", "a..b", "",
])
def test_invalid_reference_ids_rejected(tmp_path, unsafe):
    registry = ReferenceRegistry(tmp_path / "refs")
    with pytest.raises(ValueError, match="invalid reference ID"):
        registry.path_for(unsafe)


def test_reference_symlink_is_rejected(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    external = tmp_path / "external"
    external.mkdir()
    (registry.root / "alias").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        registry.path_for("alias")


def test_reference_validation_fails_closed_on_missing_artifacts_and_wrong_model(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    manifest = create(registry)
    assert registry.validate(manifest, expected_model="glm-5.3") == []
    assert registry.validate(manifest, expected_model="kimi-k3") == ["model_mismatch"]
    (registry.path_for("official") / "protocol-signature.json").unlink()
    assert "protocol_signature_missing" in registry.validate(
        manifest, expected_model="glm-5.3"
    )


def test_malicious_manifest_artifact_paths_cannot_escape_registry(tmp_path):
    from model_detect.references import ReferenceManifest
    registry = ReferenceRegistry(tmp_path / "refs")
    source = create(registry)
    tampered = source.model_copy(update={
        "protocol_signature": "../../secret.json",
        "fingerprint_artifact": "../../secret.json",
        "baseline_artifact": "../../secret.json",
    })
    assert registry.signature(tampered) is None
    assert registry.fingerprint_path(tampered) is None
    assert registry.baseline_path(tampered) is None
    issues = registry.validate(tampered, expected_model="glm-5.3")
    assert "protocol_signature_missing" in issues
    assert "fingerprint_artifact_missing" in issues
    assert "baseline_artifact_missing" in issues


def test_registry_listing_rejects_symlink_and_mismatched_manifest(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    create(registry, "official")
    target = registry.path_for("official")
    alias = registry.root / "alias"
    alias.symlink_to(target, target_is_directory=True)
    assert [x.id for x in registry.list()] == ["official"]
    content = (target / "manifest.json").read_text(encoding="utf-8")
    (target / "manifest.json").write_text(
        content.replace('"id": "official"', '"id": "another"'), encoding="utf-8"
    )
    assert registry.list() == []


def test_reference_checksum_detects_post_collection_tampering(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    manifest = create(registry)
    assert manifest.artifact_sha256["protocol-signature.json"]
    assert registry.validate(manifest, expected_model="glm-5.3") == []
    path = registry.path_for("official") / "protocol-signature.json"
    path.write_text('{"model":"glm-5.3","probes":{}}', encoding="utf-8")
    assert "artifact_checksum_mismatch:protocol-signature.json" in registry.validate(
        manifest, expected_model="glm-5.3"
    )


def test_historical_reference_without_hashes_is_unverified(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    manifest = create(registry)
    historical = manifest.model_copy(update={"artifact_sha256": {}})
    assert "legacy_unverified_artifacts" in registry.validate(
        historical, expected_model="glm-5.3"
    )

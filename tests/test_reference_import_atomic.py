from pathlib import Path

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.references import ReferenceManifest, ReferenceRegistry


def test_import_fingerprint_atomic_success_duplicate_and_hash(tmp_path):
    registry = ReferenceRegistry(tmp_path / "references")
    original = tmp_path / "fingerprint.json"
    original.write_text('{"provider":"trusted"}', encoding="utf-8")
    manifest = ReferenceManifest(id="imported", model="glm-5.3",
                                 fingerprint_source="imported")
    target = registry.create_imported_fingerprint(manifest, original)
    assert target.exists()
    saved = registry.get("imported")
    assert saved.fingerprint_artifact == "fingerprint.json"
    assert registry.validate(saved, expected_model="glm-5.3") == []
    previous = target.read_bytes()
    with pytest.raises(FileExistsError):
        registry.create_imported_fingerprint(manifest, original)
    assert target.read_bytes() == previous


def test_import_failure_cleans_staging_without_partial_reference(tmp_path, monkeypatch):
    registry = ReferenceRegistry(tmp_path / "references")
    original = tmp_path / "fingerprint.json"
    original.write_text("{}", encoding="utf-8")
    manifest = ReferenceManifest(id="imported", model="glm-5.3")
    old = Path.write_text
    def injected(self, *args, **kwargs):
        if self.name == "manifest.json" and self.parent.name.startswith(".reference-import-"):
            raise OSError("injected failure")
        return old(self, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", injected)
    with pytest.raises(OSError, match="injected failure"):
        registry.create_imported_fingerprint(manifest, original)
    assert not registry.path_for("imported").exists()
    assert not list(registry.root.glob(".reference-import-*"))

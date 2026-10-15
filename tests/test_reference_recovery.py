import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.reference_recovery import inspect_reference_backups, restore_missing_reference
from model_detect.references import ReferenceRegistry, ReferenceManifest


def _backup(root: Path, reference_id="official") -> str:
    name = f".reference-backup-{reference_id}-abc123"
    folder = root / name
    folder.mkdir()
    content = b'{"model":"glm-5.3","probes":{}}'
    (folder / "protocol-signature.json").write_bytes(content)
    manifest = ReferenceManifest(
        id=reference_id, model="glm-5.3",
        protocol_signature="protocol-signature.json",
        artifact_sha256={"protocol-signature.json": hashlib.sha256(content).hexdigest()},
    )
    (folder / "manifest.json").write_text(manifest.model_dump_json())
    return name


def test_recovery_preview_and_explicit_missing_target_only(tmp_path):
    registry = ReferenceRegistry(tmp_path)
    name = _backup(tmp_path)
    status = inspect_reference_backups(registry, "official")
    assert status["target_exists"] is False
    assert status["candidates"][0]["verified"] is True
    cli = CliRunner().invoke(app, ["reference", "recover", "--id", "official",
                                   "--reference-dir", str(tmp_path)])
    assert cli.exit_code == 0, cli.output
    assert not (tmp_path / "official").exists()
    done = restore_missing_reference(registry, "official", name)
    assert done["restored"] is True
    assert (tmp_path / "official" / "manifest.json").is_file()
    with pytest.raises(RuntimeError):
        restore_missing_reference(registry, "official", name)


def test_bad_hash_and_stale_lock_never_restore(tmp_path):
    registry = ReferenceRegistry(tmp_path)
    name = _backup(tmp_path)
    (tmp_path / name / "protocol-signature.json").write_text("tampered")
    with pytest.raises(ValueError):
        restore_missing_reference(registry, "official", name)
    assert not (tmp_path / "official").exists()
    (tmp_path / f".official.write.lock").write_text("stale")
    with pytest.raises(RuntimeError):
        restore_missing_reference(registry, "official", name)

from pathlib import Path
from types import SimpleNamespace

import pytest

from model_detect.references import ReferenceRegistry


def report():
    return SimpleNamespace(
        target={"model": "glm-5.3", "base_url": "https://example.test/v1"},
        profile="standard",
        summary=SimpleNamespace(model_dump=lambda **_: {"overall_score": 0.9}),
        results=[],
    )


def create(registry, *, replace=False):
    return registry.create_from_report(
        reference_id="trusted", model="glm-5.3", provider="official",
        protocol="openai", report=report(), replace_existing=replace,
    )


def test_explicit_replace_retains_versioned_backup(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    create(registry)
    original = (registry.path_for("trusted") / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        create(registry)
    replacement = create(registry, replace=True)
    backup_name = replacement.metadata["previous_backup_directory"]
    backup = registry.root / backup_name
    assert backup.is_dir()
    assert (backup / "manifest.json").read_bytes() == original
    assert registry.validate(replacement, expected_model="glm-5.3") == []
    assert not list(registry.root.glob(".trusted.write.lock"))


def test_replacement_failure_restores_old_reference(tmp_path, monkeypatch):
    from model_detect import references as module
    registry = ReferenceRegistry(tmp_path / "refs")
    create(registry)
    old_path = registry.path_for("trusted") / "manifest.json"
    original = old_path.read_bytes()
    real_rename = module.os.rename
    def fail_new_publish(src, dst):
        if (Path(src).name.startswith(".reference-stage-")
                and Path(dst).name == "trusted"):
            raise OSError("simulated swap failure")
        return real_rename(src, dst)
    monkeypatch.setattr(module.os, "rename", fail_new_publish)
    with pytest.raises(OSError, match="simulated"):
        create(registry, replace=True)
    assert old_path.read_bytes() == original
    assert not list(registry.root.glob(".reference-stage-*"))
    assert not list(registry.root.glob(".trusted.write.lock"))


def test_stale_lock_refuses_replace_without_touching_existing_reference(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    create(registry)
    old_path = registry.path_for("trusted") / "manifest.json"
    original = old_path.read_bytes()
    (registry.root / ".trusted.write.lock").write_text("stale")
    with pytest.raises(RuntimeError, match="lock"):
        create(registry, replace=True)
    assert old_path.read_bytes() == original

"""Recovery of a missing Reference from a verified, preserved backup.

Never overwrites a healthy target. A stale writer lock requires independent
operator diagnosis and removal before recovery; the tool never deletes it.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .references import ReferenceManifest, ReferenceRegistry

_ALLOWED = {"protocol-signature.json", "fingerprint.json", "baseline.json"}


def inspect_reference_backups(registry: ReferenceRegistry, reference_id: str) -> dict:
    target = registry.path_for(reference_id)
    candidates = []
    for path in sorted(registry.root.glob(f".reference-backup-{reference_id}-*")):
        if not path.is_dir() or path.is_symlink():
            continue
        reason = []
        manifest_path = path / "manifest.json"
        try:
            if manifest_path.is_symlink():
                raise ValueError("symlink manifest")
            manifest = ReferenceManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            if manifest.id != reference_id:
                reason.append("reference_id_mismatch")
            if not manifest.artifact_sha256:
                reason.append("missing_artifact_checksums")
            for name, digest in manifest.artifact_sha256.items():
                if name not in _ALLOWED:
                    reason.append("unexpected_artifact")
                    continue
                artifact = path / name
                if artifact.is_symlink() or not artifact.is_file():
                    reason.append("artifact_missing_or_symlink")
                elif hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
                    reason.append("artifact_checksum_mismatch")
            if manifest.protocol_signature and manifest.protocol_signature not in manifest.artifact_sha256:
                reason.append("signature_checksum_missing")
        except (ValueError, OSError, TypeError):
            reason.append("manifest_invalid")
        candidates.append({"backup_name": path.name,
                           "verified": not reason, "reasons": sorted(set(reason))})
    lock = registry.root / f".{reference_id}.write.lock"
    return {
        "reference_id": reference_id,
        "target_exists": target.exists() or target.is_symlink(),
        "write_lock_exists": lock.exists(),
        "candidates": candidates,
        "restore_requires_explicit_action": True,
    }


def restore_missing_reference(
    registry: ReferenceRegistry, reference_id: str, backup_name: str,
) -> dict:
    status = inspect_reference_backups(registry, reference_id)
    if status["target_exists"] or status["write_lock_exists"]:
        raise RuntimeError("target present or writer lock present; refusing recovery")
    valid = [r for r in status["candidates"]
             if r["backup_name"] == backup_name and r["verified"]]
    if len(valid) != 1:
        raise ValueError("requested backup missing or invalid")
    backup = registry.root / backup_name
    target = registry.path_for(reference_id)
    lock_path = registry.root / f".{reference_id}.write.lock"
    try:
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError("concurrent Reference writer detected") from None
    os.close(fd)
    try:
        # Revalidate while holding lock; never rename onto an existing target.
        check = inspect_reference_backups(registry, reference_id)
        current = [r for r in check["candidates"]
                   if r["backup_name"] == backup_name and r["verified"]]
        if target.exists() or target.is_symlink() or len(current) != 1:
            raise RuntimeError("reference backup changed during recovery")
        os.rename(backup, target)
        return {"restored": True, "reference_id": reference_id,
                "original_backup_name": backup_name}
    finally:
        lock_path.unlink(missing_ok=True)

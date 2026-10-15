from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .baseline import OfficialBaseline
from .models import AuditReport, ProbeResult, ProbeStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_.")[:96] or "reference"


class ReferenceManifest(BaseModel):
    id: str
    model: str
    provider: str = "trusted"
    protocol: str = "openai"
    base_url_hint: str | None = None
    collected_at: str = Field(default_factory=_now)
    fingerprint_artifact: str | None = None
    fingerprint_source: str | None = None
    fingerprint_reference: str | None = None
    fingerprint_metadata: dict[str, Any] = Field(default_factory=dict)
    protocol_signature: str | None = None
    baseline_schema_version: int | None = None
    baseline_suite_version: str | None = None
    baseline_runs: int = 0
    baseline_artifact: str | None = None
    model_rule_id: str | None = None
    model_rule_updated_at: str | None = None
    baseline_metadata: dict[str, Any] = Field(default_factory=dict)
    artifact_sha256: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceRegistry:
    def __init__(self, root: str | Path = "references") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, reference_id: str) -> Path:
        # Never silently alias two logical IDs to the same storage directory.
        # The former _safe() transform could collide and overwrite evidence.
        if (not isinstance(reference_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", reference_id)
                or reference_id in {".", ".."}
                or ".." in reference_id):
            raise ValueError("invalid reference ID: use 1-96 safe ASCII characters")
        path = self.root / reference_id
        if path.is_symlink():
            raise ValueError("reference path must not be a symbolic link")
        return path

    def exists(self, reference_id: str) -> bool:
        return (self.path_for(reference_id) / "manifest.json").exists()

    def list(self) -> list[ReferenceManifest]:
        out: list[ReferenceManifest] = []
        for manifest in sorted(self.root.glob("*/manifest.json")):
            if manifest.parent.is_symlink() or manifest.is_symlink():
                continue
            try:
                parsed = ReferenceManifest.model_validate_json(
                    manifest.read_text(encoding="utf-8")
                )
                if parsed.id != manifest.parent.name:
                    continue
                self.path_for(parsed.id)
                out.append(parsed)
            except (OSError, ValueError, TypeError):
                continue
        return out

    def get(self, reference_id: str) -> ReferenceManifest:
        path = self.path_for(reference_id) / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"reference not found: {reference_id}")
        return ReferenceManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def delete(self, reference_id: str) -> bool:
        root = self.path_for(reference_id)
        if not root.exists():
            return False
        shutil.rmtree(root)
        return True

    def save_manifest(self, manifest: ReferenceManifest) -> Path:
        root = self.path_for(manifest.id)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "manifest.json"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root,
            prefix=".manifest-", suffix=".tmp", delete=False
        ) as handle:
            pending = Path(handle.name)
            try:
                handle.write(manifest.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                pending.unlink(missing_ok=True)
                raise
        try:
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)
        return path

    def create_imported_fingerprint(
        self, manifest: ReferenceManifest, fingerprint_file: str | Path
    ) -> Path:
        """Import an existing fingerprint without exposing partial state."""
        root = self.path_for(manifest.id)
        if root.exists() or root.is_symlink():
            raise FileExistsError(f"reference already exists: {manifest.id}")
        source = Path(fingerprint_file)
        if not source.is_file():
            raise FileNotFoundError("fingerprint input missing")
        stage = Path(tempfile.mkdtemp(prefix=".reference-import-", dir=self.root))
        try:
            dst = stage / "fingerprint.json"
            shutil.copy2(source, dst)
            payload = manifest.model_copy(deep=True)
            payload.fingerprint_artifact = "fingerprint.json"
            payload.fingerprint_reference = "fingerprint.json"
            payload.artifact_sha256 = {
                "fingerprint.json": hashlib.sha256(dst.read_bytes()).hexdigest()
            }
            (stage / "manifest.json").write_text(
                payload.model_dump_json(indent=2), encoding="utf-8"
            )
            if root.exists() or root.is_symlink():
                raise FileExistsError(f"reference already exists: {manifest.id}")
            os.rename(stage, root)
            return root / "manifest.json"
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def create_from_report(
        self,
        *,
        reference_id: str,
        model: str,
        provider: str,
        protocol: str,
        report: AuditReport,
        fingerprint_path: str | Path | None = None,
        fingerprint_metadata: dict[str, Any] | None = None,
        fingerprint_source: str | None = None,
        baseline: OfficialBaseline | None = None,
        notes: list[str] | None = None,
        replace_existing: bool = False,
    ) -> ReferenceManifest:
        root = self.path_for(reference_id)
        if root.exists() and not replace_existing:
            raise FileExistsError(f"reference already exists: {reference_id}")
        lock_path = self.root / f".{reference_id}.write.lock"
        try:
            lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise RuntimeError("reference write already in progress or stale lock") from None
        os.close(lock_fd)
        stage: Path | None = None
        backup_name = f".reference-backup-{reference_id}-{uuid.uuid4().hex}" if replace_existing else None
        try:
            stage = Path(tempfile.mkdtemp(prefix=".reference-stage-", dir=self.root))
            signature_path = stage / "protocol-signature.json"
            signature = protocol_signature_from_report(report)
            signature_path.write_text(
                json.dumps(signature, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            fp_name = None
            if fingerprint_path:
                src = Path(fingerprint_path)
                if src.is_file():
                    shutil.copy2(src, stage / "fingerprint.json")
                    fp_name = "fingerprint.json"
            baseline_name = None
            if baseline is not None:
                (stage / "baseline.json").write_text(
                    baseline.model_dump_json(indent=2), encoding="utf-8"
                )
                baseline_name = "baseline.json"
            artifact_hashes = {
                file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                for file in stage.iterdir() if file.is_file()
            }
            manifest = ReferenceManifest(
                id=reference_id,
                model=model,
                provider=provider,
                protocol=protocol,
                base_url_hint=_base_url_hint(str(report.target.get("base_url", ""))),
                fingerprint_artifact=fp_name,
                fingerprint_source=(
                    fingerprint_source or ("collected" if fp_name else None)
                ),
                fingerprint_reference=fp_name,
                fingerprint_metadata=fingerprint_metadata or {},
                protocol_signature=signature_path.name,
                baseline_schema_version=(
                    baseline.schema_version if baseline is not None else None
                ),
                baseline_suite_version=(
                    baseline.suite_version if baseline is not None else None
                ),
                baseline_runs=baseline.runs if baseline is not None else 0,
                baseline_artifact=baseline_name,
                artifact_sha256=artifact_hashes,
                model_rule_id=(
                    baseline.model_rule_id if baseline is not None else None
                ),
                model_rule_updated_at=(
                    baseline.model_rule_updated_at if baseline is not None else None
                ),
                baseline_metadata=(
                    dict(baseline.metadata) if baseline is not None else {}
                ),
                notes=notes or [],
                metadata={
                    "profile": report.profile,
                    "summary": report.summary.model_dump(mode="json"),
                    **({"previous_backup_directory": backup_name} if backup_name and root.exists() else {}),
                },
            )
            (stage / "manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
            if root.exists() and not replace_existing:
                raise FileExistsError(f"reference already exists: {reference_id}")
            backup = self.root / backup_name if (replace_existing and root.exists()) else None
            if backup is not None:
                os.rename(root, backup)
            try:
                os.rename(stage, root)
            except BaseException:
                if backup is not None and not root.exists():
                    os.rename(backup, root)
                raise
            return manifest
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)
            lock_path.unlink(missing_ok=True)


    def validate(self, manifest: ReferenceManifest, *, expected_model: str | None = None) -> list[str]:
        """Return explicit reasons a selected Reference is not fully trustworthy."""
        reasons: list[str] = []
        if expected_model is not None and manifest.model != expected_model:
            reasons.append("model_mismatch")
        if manifest.protocol_signature:
            try:
                signature = self.signature(manifest)
                if signature is None:
                    reasons.append("protocol_signature_missing")
                elif not isinstance(signature, dict) or not isinstance(
                    signature.get("probes"), dict
                ):
                    reasons.append("protocol_signature_invalid")
                elif signature.get("model") != manifest.model:
                    reasons.append("protocol_signature_model_mismatch")
            except (OSError, ValueError, TypeError):
                reasons.append("protocol_signature_invalid")
        if manifest.fingerprint_artifact and self.fingerprint_path(manifest) is None:
            reasons.append("fingerprint_artifact_missing")
        if manifest.baseline_artifact:
            try:
                baseline = self.baseline(manifest)
                if baseline is None:
                    reasons.append("baseline_artifact_missing")
                elif manifest.baseline_runs < 1 or baseline.runs != manifest.baseline_runs:
                    reasons.append("baseline_runs_mismatch")
                elif manifest.baseline_suite_version != baseline.suite_version:
                    reasons.append("baseline_suite_mismatch")
                elif (manifest.baseline_schema_version is not None
                      and manifest.baseline_schema_version != baseline.schema_version):
                    reasons.append("baseline_schema_mismatch")
            except (OSError, ValueError, TypeError):
                reasons.append("baseline_invalid")
        local_artifacts = (
            (manifest.protocol_signature, "protocol-signature.json"),
            (manifest.fingerprint_artifact, "fingerprint.json"),
            (manifest.baseline_artifact, "baseline.json"),
        )
        for artifact, expected_name in local_artifacts:
            if not artifact:
                continue
            path = self._artifact_path(manifest, artifact, expected_name)
            expected_hash = manifest.artifact_sha256.get(expected_name)
            if path is not None and expected_hash:
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    reasons.append("artifact_checksum_mismatch:" + expected_name)
        if not manifest.artifact_sha256 and any(name for name, _ in local_artifacts):
            reasons.append("legacy_unverified_artifacts")
        if not (manifest.protocol_signature or manifest.fingerprint_reference
                or manifest.baseline_artifact):
            reasons.append("reference_empty")
        return reasons

    def _artifact_path(self, manifest: ReferenceManifest,
                       filename: str | None, allowed: str) -> Path | None:
        # A modified manifest must never read arbitrary files from the host.
        if filename != allowed:
            return None
        target = self.path_for(manifest.id) / allowed
        if target.is_symlink():
            return None
        return target if target.is_file() else None

    def fingerprint_path(self, manifest: ReferenceManifest) -> Path | None:
        if not manifest.fingerprint_artifact:
            return None
        return self._artifact_path(manifest, manifest.fingerprint_artifact, "fingerprint.json")

    def fingerprint_reference_value(self, manifest: ReferenceManifest) -> str | None:
        path = self.fingerprint_path(manifest)
        if path:
            return str(path)
        if manifest.fingerprint_source == "bundled" and manifest.fingerprint_reference:
            return manifest.fingerprint_reference
        return None

    def signature(self, manifest: ReferenceManifest) -> dict[str, Any] | None:
        if not manifest.protocol_signature:
            return None
        path = self._artifact_path(manifest, manifest.protocol_signature, "protocol-signature.json")
        if path is None:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def baseline_path(self, manifest: ReferenceManifest) -> Path | None:
        if not manifest.baseline_artifact:
            return None
        return self._artifact_path(manifest, manifest.baseline_artifact, "baseline.json")

    def baseline(self, manifest: ReferenceManifest) -> OfficialBaseline | None:
        path = self.baseline_path(manifest)
        if path is None:
            return None
        return OfficialBaseline.model_validate_json(
            path.read_text(encoding="utf-8")
        )


def _base_url_hint(base_url: str) -> str | None:
    if not base_url:
        return None
    match = re.match(r"^(https?://[^/]+)", base_url)
    return match.group(1) if match else None


def protocol_signature_from_report(report: AuditReport) -> dict[str, Any]:
    signature: dict[str, Any] = {
        "model": report.target.get("model"),
        "profile": report.profile,
        "probes": {},
    }
    for result in report.results:
        if result.category not in {"protocol", "integrity", "context", "routing"}:
            continue
        signature["probes"][result.probe_id] = {
            "status": result.status.value,
            "score": result.score,
            "metadata": result.metadata,
        }
    return signature


def compare_protocol_signature(
    current_results: list[ProbeResult],
    reference_signature: dict[str, Any] | None,
) -> ProbeResult:
    probe_id = "identity.reference.protocol_signature"
    if not reference_signature:
        return ProbeResult(
            probe_id=probe_id,
            category="identity",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            confidence=0.0,
            summary="reference does not contain a protocol signature",
        )

    expected = reference_signature.get("probes") or {}
    current = {
        r.probe_id: r for r in current_results
        if r.category in {"protocol", "integrity", "context", "routing"}
    }
    common = sorted(set(expected) & set(current))
    if not common:
        return ProbeResult(
            probe_id=probe_id,
            category="identity",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            confidence=0.0,
            summary="no comparable probes between current run and reference",
        )

    matches = 0
    details = []
    for key in common:
        exp_status = str((expected.get(key) or {}).get("status") or "")
        cur_status = current[key].status.value
        same = exp_status == cur_status
        matches += int(same)
        details.append(
            {"probe_id": key, "expected": exp_status, "observed": cur_status, "match": same}
        )

    ratio = matches / len(common)
    if ratio >= 0.90:
        status = ProbeStatus.PASS
    elif ratio >= 0.70:
        status = ProbeStatus.WARN
    else:
        status = ProbeStatus.FAIL
    return ProbeResult(
        probe_id=probe_id,
        category="identity",
        status=status,
        score=ratio,
        confidence=min(0.95, 0.5 + len(common) / 40),
        summary=f"protocol signature matched {matches}/{len(common)} comparable probes",
        observed={"match_ratio": ratio, "details": details},
        metadata={
            "verdict": "match" if status == ProbeStatus.PASS else ("mismatch" if status == ProbeStatus.FAIL else "uncertain"),
            "identity_strength": "medium",
        },
    )

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

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
    protocol_signature: str | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceRegistry:
    def __init__(self, root: str | Path = "references") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, reference_id: str) -> Path:
        return self.root / _safe(reference_id)

    def exists(self, reference_id: str) -> bool:
        return (self.path_for(reference_id) / "manifest.json").exists()

    def list(self) -> list[ReferenceManifest]:
        out: list[ReferenceManifest] = []
        for manifest in sorted(self.root.glob("*/manifest.json")):
            try:
                out.append(
                    ReferenceManifest.model_validate_json(
                        manifest.read_text(encoding="utf-8")
                    )
                )
            except Exception:
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
        path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def create_from_report(
        self,
        *,
        reference_id: str,
        model: str,
        provider: str,
        protocol: str,
        report: AuditReport,
        fingerprint_path: str | Path | None = None,
        notes: list[str] | None = None,
    ) -> ReferenceManifest:
        root = self.path_for(reference_id)
        root.mkdir(parents=True, exist_ok=True)
        signature_path = root / "protocol-signature.json"
        signature = protocol_signature_from_report(report)
        signature_path.write_text(
            json.dumps(signature, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        fp_name = None
        if fingerprint_path:
            src = Path(fingerprint_path)
            if src.exists():
                dst = root / "fingerprint.json"
                if src.resolve() != dst.resolve():
                    shutil.copy2(src, dst)
                fp_name = dst.name

        manifest = ReferenceManifest(
            id=reference_id,
            model=model,
            provider=provider,
            protocol=protocol,
            base_url_hint=_base_url_hint(str(report.target.get("base_url", ""))),
            fingerprint_artifact=fp_name,
            protocol_signature=signature_path.name,
            notes=notes or [],
            metadata={
                "profile": report.profile,
                "summary": report.summary.model_dump(mode="json"),
            },
        )
        self.save_manifest(manifest)
        return manifest

    def fingerprint_path(self, manifest: ReferenceManifest) -> Path | None:
        if not manifest.fingerprint_artifact:
            return None
        path = self.path_for(manifest.id) / manifest.fingerprint_artifact
        return path if path.exists() else None

    def signature(self, manifest: ReferenceManifest) -> dict[str, Any] | None:
        if not manifest.protocol_signature:
            return None
        path = self.path_for(manifest.id) / manifest.protocol_signature
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


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

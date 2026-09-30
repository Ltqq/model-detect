from model_detect.models import AuditReport, ProbeResult, ProbeStatus
from model_detect.references import ReferenceManifest, ReferenceRegistry, compare_protocol_signature


def make_report():
    return AuditReport(
        target={"base_url": "https://official.example/v1", "model": "kimi-k3", "protocol": "openai"},
        profile="standard",
        results=[
            ProbeResult(
                probe_id="protocol.chat.basic",
                category="protocol",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="ok",
            ),
            ProbeResult(
                probe_id="integrity.max_tokens",
                category="integrity",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="ok",
            ),
        ],
    )


def test_reference_roundtrip_and_signature_compare(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    report = make_report()
    manifest = registry.create_from_report(
        reference_id="kimi-official",
        model="kimi-k3",
        provider="official",
        protocol="openai",
        report=report,
    )

    loaded = registry.get("kimi-official")
    assert loaded.id == manifest.id
    assert registry.exists("kimi-official")
    signature = registry.signature(loaded)
    result = compare_protocol_signature(report.results, signature)
    assert result.status == ProbeStatus.PASS
    assert result.score == 1.0


def test_reference_delete(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    registry.create_from_report(
        reference_id="x",
        model="m",
        provider="trusted",
        protocol="openai",
        report=make_report(),
    )
    assert registry.delete("x") is True
    assert registry.delete("x") is False


def test_bundled_reference_preserves_source(tmp_path):
    registry = ReferenceRegistry(tmp_path / "refs")
    manifest = ReferenceManifest(
        id="bundled-kimi",
        model="kimi-k2",
        provider="bundled-sample",
        protocol="openai",
        fingerprint_source="bundled",
        fingerprint_reference="moonshot/kimi-k2",
        fingerprint_metadata={
            "source": {"dataset": "paper sample"},
            "bundled": {"id": "moonshot/kimi-k2"},
        },
    )
    registry.save_manifest(manifest)
    loaded = registry.get("bundled-kimi")
    assert loaded.fingerprint_source == "bundled"
    assert loaded.fingerprint_reference == "moonshot/kimi-k2"
    assert registry.fingerprint_reference_value(loaded) == "moonshot/kimi-k2"


def test_old_reference_manifest_remains_compatible(tmp_path):
    root = tmp_path / "refs" / "old"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        '{"id":"old","model":"m","provider":"trusted","protocol":"openai"}',
        encoding="utf-8",
    )
    loaded = ReferenceRegistry(tmp_path / "refs").get("old")
    assert loaded.id == "old"
    assert loaded.fingerprint_source is None
    assert loaded.fingerprint_metadata == {}

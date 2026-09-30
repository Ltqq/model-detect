from model_detect.models import AuditReport, ProbeResult, ProbeStatus
from model_detect.references import ReferenceRegistry, compare_protocol_signature


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

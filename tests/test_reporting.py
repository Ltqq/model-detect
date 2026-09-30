from model_detect.models import AuditReport, Evidence, ProbeResult, ProbeStatus
from model_detect.reporting import write_report


def test_report_contains_evidence_links(tmp_path):
    ev = Evidence(
        id="ev_test",
        probe_id="protocol.chat.basic",
        url="https://example.com/v1/chat/completions",
        response_status=200,
    )
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        results=[
            ProbeResult(
                probe_id="protocol.chat.basic",
                category="protocol",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="ok",
                evidence_ids=[ev.id],
            )
        ],
        evidences=[ev],
    )
    root = write_report(report, tmp_path / "out")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert 'evidence/ev_test.json' in html
    assert (root / "evidence" / "ev_test.json").exists()

from model_detect.models import AuditReport, ProbeResult, ProbeStatus
from model_detect.reporting import write_report

def test_evidence_first_report_layout(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.test/v1", "model": "glm-5.3-flash"},
        results=[ProbeResult(
            probe_id="protocol.system",
            category="protocol",
            status=ProbeStatus.INSUFFICIENT,
            score=None,
            summary="output truncated",
        )],
    )
    root = write_report(report, tmp_path / "out")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert html.index("风险与异常解读") < html.index("官方已发布成绩")
    assert "证据不足（非模型失败）" in html
    assert "完整检测明细与原始证据" in html

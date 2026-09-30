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


def test_report_renders_fingerprint_cells(tmp_path):
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "kimi-k3"},
        results=[
            ProbeResult(
                probe_id="identity.fingerprint.reference_compare",
                category="identity",
                status=ProbeStatus.PASS,
                score=1.0,
                summary="match",
                observed={
                    "verdict": "match",
                    "mean_jsd": 0.18,
                    "comparable_cell_count": 1,
                    "target_split_half_jsd": 0.12,
                    "target_adapter": {"strategy": "openai-effort"},
                    "target_fingerprint": {
                        "model": "kimi-k3",
                        "protocol": "one-token/v1",
                        "collected_at": "now",
                        "cell_count": 1,
                    },
                    "reference_fingerprint": {
                        "model": "kimi-k3",
                        "protocol": "one-token/v1",
                        "collected_at": "before",
                        "cell_count": 1,
                    },
                    "warnings": [],
                    "cells": [
                        {
                            "cellId": "random-number-1-100:en",
                            "jsd": 0.18,
                            "validA": 25,
                            "validB": 25,
                        }
                    ],
                },
                metadata={"identity_strength": "strong", "verdict": "match"},
            )
        ],
        adapters={
            "reference": {
                "fingerprint_source": "collected",
                "fingerprint_reference": "fingerprint.json",
            }
        },
    )
    root = write_report(report, tmp_path / "fp-report")
    html = (root / "report.html").read_text(encoding="utf-8")
    assert "Statistical Fingerprint" in html
    assert "Per-cell JSD" in html
    assert "random-number-1-100:en" in html
    assert "collected" in html

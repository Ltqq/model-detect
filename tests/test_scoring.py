from model_detect.models import ProbeResult, ProbeStatus
from model_detect.scoring import build_summary


def r(probe_id, category, score, status=ProbeStatus.PASS, **metadata):
    return ProbeResult(
        probe_id=probe_id,
        category=category,
        status=status,
        score=score,
        summary="test",
        metadata=metadata,
    )


def test_category_score_and_pass():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r("protocol.chat.stream", "protocol", 1.0),
            r("identity.fp", "identity", 0.9),
        ]
    )
    assert summary.category_scores["protocol"] == 100.0
    assert summary.category_scores["identity"] == 90.0
    assert summary.overall_score is not None
    assert summary.final_verdict == "pass"


def test_identity_mismatch_hard_caps_total():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r(
                "identity.fingerprint.reference_compare",
                "identity",
                0.0,
                status=ProbeStatus.FAIL,
                verdict="mismatch",
            ),
        ]
    )
    assert summary.hard_cap == 40.0
    assert summary.overall_score <= 40.0
    assert summary.final_verdict == "mismatch"


def test_critical_protocol_failure_caps_score():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 0.0, status=ProbeStatus.FAIL),
            r("identity.other", "identity", 1.0),
        ]
    )
    assert summary.hard_cap == 60.0

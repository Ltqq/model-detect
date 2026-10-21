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



def test_probe_confidence_defaults_to_unknown_without_calibration():
    result = ProbeResult(
        probe_id="protocol.chat.basic",
        category="protocol",
        status=ProbeStatus.PASS,
        score=1.0,
        summary="deterministic protocol assertion passed",
    )
    assert result.confidence is None

def test_category_score_and_pass():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r("protocol.chat.stream", "protocol", 1.0),
            r("identity.fp", "identity", 0.9, identity_strength="strong"),
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
                identity_strength="strong",
            ),
        ]
    )
    assert summary.hard_cap == 40.0
    assert summary.overall_score <= 40.0
    assert summary.final_verdict == "review"


def test_critical_protocol_failure_caps_score():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 0.0, status=ProbeStatus.FAIL),
            r("identity.other", "identity", 1.0),
        ]
    )
    assert summary.hard_cap == 60.0


def test_weak_identity_does_not_block_protocol_admission():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r("identity.family_features.x", "identity", 1.0, identity_strength="weak"),
            r("integrity.max_tokens", "integrity", 1.0),
            r("context.summary", "context", 1.0),
        ]
    )
    assert summary.overall_score is not None
    assert summary.final_verdict == "pass"
    assert summary.confidence in {"medium", "low"}


def test_weak_identity_failure_does_not_trigger_mismatch():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r(
                "identity.self_consistency",
                "identity",
                0.3,
                status=ProbeStatus.FAIL,
                identity_strength="weak",
            ),
            r("integrity.max_tokens", "integrity", 1.0),
        ]
    )
    assert summary.hard_cap is None
    assert summary.final_verdict != "mismatch"




def test_header_only_upstream_suspicion_requires_review_not_hard_fail():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r(
                "provider.upstream_policy",
                "provider",
                None,
                status=ProbeStatus.WARN,
                policy_violation=False,
                policy_suspected=True,
                evidence_strength="weak",
            ),
        ]
    )
    assert summary.hard_cap is None
    assert summary.final_verdict == "review"

def test_disallowed_upstream_policy_violation_fails_admission():
    summary = build_summary(
        [
            r("protocol.chat.basic", "protocol", 1.0),
            r(
                "identity.fingerprint.reference_compare",
                "identity",
                1.0,
                identity_strength="strong",
            ),
            r(
                "provider.upstream_policy",
                "provider",
                0.0,
                status=ProbeStatus.FAIL,
                policy_violation=True,
            ),
        ]
    )

    assert summary.hard_cap == 40.0
    assert summary.final_verdict == "fail"



def test_benchmark_scores_do_not_change_authenticity_admission_score():
    native = [
        r("protocol.chat.basic", "protocol", 1.0),
        r("identity.fp", "identity", 0.9, identity_strength="strong"),
        r("capability.reasoning", "capability", 0.4),
    ]
    original = build_summary(native)
    with_benchmark = build_summary([
        *native,
        r("capability.external.lm_eval.gsm8k", "benchmark", 1.0),
    ])
    assert with_benchmark.overall_score == original.overall_score
    assert with_benchmark.final_verdict == original.final_verdict


def test_no_protocol_evidence_is_insufficient_even_with_high_identity_score():
    summary = build_summary([
        r("identity.fp", "identity", 1.0, identity_strength="strong")
    ])
    assert summary.final_verdict == "insufficient"


def test_protocol_transport_error_cannot_be_admitted():
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 0.0, ProbeStatus.ERROR),
        r("identity.fp", "identity", 1.0, identity_strength="strong"),
    ])
    assert summary.final_verdict == "insufficient"


def test_critical_protocol_failure_is_not_masked_by_capability():
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 0.0, ProbeStatus.FAIL),
        r("capability.reasoning", "capability", 1.0),
    ])
    assert summary.final_verdict == "fail"


def test_noncritical_protocol_failure_requires_review():
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 1.0),
        r("protocol.json_mode", "protocol", 0.0, ProbeStatus.FAIL),
    ])
    assert summary.final_verdict == "review"


def test_glm_flash_weak_tool_support_is_not_perfect_model_identity():
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 1.0),
        r("protocol.chat.stream", "protocol", 1.0),
        r("identity.family_features.tools", "identity", 1.0, identity_strength="weak"),
        r("identity.family_features.reasoning_effort", "identity", None,
          status=ProbeStatus.INSUFFICIENT, identity_strength="weak"),
    ])
    assert summary.category_scores.get("identity") is None
    assert summary.coverage["identity"] is False
    assert summary.category_scores["protocol"] == 100.0
    assert summary.final_verdict == "pass"


def test_quick_without_reference_is_not_automatic_review():
    """Untested identity/routing features are coverage gaps, not supplier defects."""
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 1.0),
        r("protocol.chat.stream", "protocol", 1.0),
        r("identity.family_features.reasoning_effort", "identity", None,
          status=ProbeStatus.INSUFFICIENT, identity_strength="weak"),
        r("routing.summary", "routing", None, status=ProbeStatus.INSUFFICIENT),
    ])
    assert summary.final_verdict == "pass"


def test_truncated_protocol_behavior_is_still_inconclusive():
    summary = build_summary([
        r("protocol.chat.basic", "protocol", 1.0),
        r("protocol.chat.stream", "protocol", 1.0),
        r("protocol.json_mode", "protocol", None, status=ProbeStatus.INSUFFICIENT),
    ])
    assert summary.final_verdict == "review"

from model_detect.interpretation import (
    build_report_interpretation,
    probe_title,
    status_label,
)
from model_detect.models import (
    AuditReport,
    AuditSummary,
    ProbeResult,
    ProbeStatus,
    ProviderHypothesis,
)


def result(probe_id, category, status=ProbeStatus.PASS, score=1.0, **metadata):
    return ProbeResult(
        probe_id=probe_id,
        category=category,
        status=status,
        score=score,
        summary="technical summary",
        metadata=metadata,
    )


def test_review_without_strong_identity_explains_reference_gap():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "kimi-k3"},
        summary=AuditSummary(
            overall_score=88.0,
            final_verdict="review",
            confidence="medium",
            category_scores={"protocol": 100.0, "integrity": 90.0},
            coverage={"protocol": True, "integrity": True},
        ),
        results=[
            result("protocol.chat.basic", "protocol"),
            result(
                "identity.family_features.reasoning_effort",
                "identity",
                identity_strength="weak",
            ),
        ],
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "人工复核"
    assert human["identity"]["state"] == "missing"
    assert human["identity"]["label"] == "缺少强身份依据"
    assert any("Reference" in action for action in human["actions"])


def test_strong_identity_match_can_be_explained_as_pass():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "kimi-k3"},
        summary=AuditSummary(
            overall_score=96.0,
            final_verdict="pass",
            confidence="high",
            category_scores={"identity": 100.0, "protocol": 100.0},
            coverage={"identity": True, "protocol": True},
        ),
        results=[
            result(
                "identity.fingerprint.reference_compare",
                "identity",
                verdict="match",
                identity_strength="strong",
            )
        ],
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "可通过"
    assert human["identity"]["state"] == "match"
    assert "统计行为指纹" in human["identity"]["text"]


def test_upstream_policy_violation_becomes_plain_chinese_rejection():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        summary=AuditSummary(
            overall_score=40.0,
            final_verdict="fail",
            confidence="medium",
        ),
        results=[
            result(
                "provider.upstream_policy",
                "provider",
                status=ProbeStatus.FAIL,
                score=0.0,
                policy_violation=True,
            )
        ],
        provider_hypotheses=[
            ProviderHypothesis(
                provider="fireworks",
                confidence=0.95,
                evidence=["protocol.chat.basic: response header x-fireworks-request-id"],
            )
        ],
        adapters={
            "upstream_policy": {
                "status": "violation",
                "config": {"disallowed": ["fireworks"]},
                "observed": {
                    "detected": [{"provider": "fireworks"}],
                    "http_429_count": 2,
                },
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "拒绝准入"
    assert human["provider"]["state"] == "violation"
    assert human["provider"]["http_429_count"] == 2
    assert human["provider"]["hypotheses"][0]["label"] == "Fireworks AI"


def test_429_is_explained_as_auxiliary_only_when_policy_clear():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        summary=AuditSummary(final_verdict="review", confidence="low"),
        adapters={
            "upstream_policy": {
                "status": "clear",
                "config": {"disallowed": ["fireworks"]},
                "observed": {"detected": [], "http_429_count": 3},
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["provider"]["state"] == "clear"
    assert human["provider"]["http_429_count"] == 3
    assert "未观察到" in human["provider"]["text"]
    assert any("429" in item for item in human["limitations"])


def test_probe_and_status_labels_are_human_readable():
    assert probe_title("routing.cluster") == "路由特征聚类"
    assert status_label(ProbeStatus.INSUFFICIENT) == "证据不足"

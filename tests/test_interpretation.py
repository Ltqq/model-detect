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


def result(probe_id, category, status=ProbeStatus.PASS, score=1.0, confidence=1.0, **metadata):
    return ProbeResult(
        probe_id=probe_id,
        category=category,
        status=status,
        score=score,
        confidence=confidence,
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
    assert human["identity"]["label"] == "未运行可用的参考对比"
    assert any("不影响已支持的协议与能力测试" in action for action in human["actions"])


def test_behavioral_fingerprint_match_is_not_strong_identity_proof():
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
                score=None,
                confidence=None,
                verdict="match",
                identity_strength="weak",
                weight_identity_proof=False,
            )
        ],
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "可通过"
    assert human["identity"]["state"] == "behavioral_match"
    assert "不能证明模型权重身份" in human["identity"]["text"]


def test_upstream_header_match_is_explained_as_suspicion_for_review():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        summary=AuditSummary(
            overall_score=None,
            final_verdict="review",
            confidence="low",
        ),
        results=[
            result(
                "provider.upstream_policy",
                "provider",
                status=ProbeStatus.WARN,
                score=None,
                policy_violation=False,
                policy_suspected=True,
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
                "status": "warn",
                "config": {"disallowed": ["fireworks"]},
                "metadata": {"policy_suspected": True},
                "observed": {
                    "detected": [{"provider": "fireworks"}],
                    "http_429_count": 2,
                },
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "人工复核"
    assert human["provider"]["state"] == "suspected"
    assert human["provider"]["label"] == "疑似命中上游标记，需复核"
    assert human["provider"]["http_429_count"] == 2
    assert human["provider"]["hypotheses"][0]["label"] == "Fireworks AI"
    assert human["provider"]["hypotheses"][0]["confidence"] is None
    assert human["confidence_is_probability"] is False
    assert "不是统计置信度" in human["confidence_text"]
    assert any("生成正文" in item for item in human["limitations"])


def test_429_is_explained_as_auxiliary_only_when_no_header_signal_is_observed():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "m"},
        summary=AuditSummary(final_verdict="review", confidence="low"),
        adapters={
            "upstream_policy": {
                "status": "insufficient",
                "config": {"disallowed": ["fireworks"]},
                "observed": {"detected": [], "http_429_count": 3},
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["provider"]["state"] == "unknown"
    assert human["provider"]["http_429_count"] == 3
    assert "未观察到" in human["provider"]["text"]
    assert "不能排除" in human["provider"]["label"]
    assert any("429" in item for item in human["limitations"])


def test_probe_and_status_labels_are_human_readable():
    assert probe_title("routing.cluster") == "路由特征聚类"
    assert status_label(ProbeStatus.INSUFFICIENT) == "证据不足"



def test_quality_regression_is_explained_without_claiming_quantization():
    report = AuditReport(
        target={"base_url": "https://supplier.example/v1", "model": "kimi-k3"},
        summary=AuditSummary(
            overall_score=90.0,
            final_verdict="review",
            confidence="medium",
        ),
        adapters={
            "official_baseline_comparison": {
                "suite_version": "official-baseline-v1",
                "model": "kimi-k3",
                "profile": "standard",
                "verdict": "quality_regression",
                "comparable_dimensions": 2,
                "statistically_evaluable_dimensions": 2,
                "regression_dimensions": ["tool_use"],
                "dimensions": {
                    "reasoning": {
                        "baseline_mean": 1.0,
                        "baseline_stddev": 0.0,
                        "baseline_runs": 3,
                        "target_score": 1.0,
                        "delta": 0.0,
                        "retention_ratio": 1.0,
                        "lower_bound": 0.5,
                        "verdict": "match",
                        "explanation": "within range",
                    },
                    "tool_use": {
                        "baseline_mean": 1.0,
                        "baseline_stddev": 0.0,
                        "baseline_runs": 3,
                        "target_score": 0.0,
                        "delta": -1.0,
                        "retention_ratio": 0.0,
                        "lower_bound": 0.5,
                        "verdict": "regression",
                        "explanation": "below range",
                    },
                },
                "warnings": [],
                "metadata": {"baseline_runs": 3},
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["decision"] == "人工复核"
    assert human["quality"]["state"] == "regression"
    assert human["quality"]["label"] == "检测到质量退化"
    assert "工具调用" in human["quality"]["text"]
    assert "量化" in human["quality"]["text"]
    assert any("不能据此确定" in item for item in human["limitations"])


def test_quality_baseline_match_is_kept_separate_from_identity():
    report = AuditReport(
        target={"base_url": "https://supplier.example/v1", "model": "kimi-k3"},
        summary=AuditSummary(
            overall_score=90.0,
            final_verdict="review",
            confidence="medium",
        ),
        adapters={
            "official_baseline_comparison": {
                "suite_version": "official-baseline-v1",
                "model": "kimi-k3",
                "profile": "standard",
                "verdict": "baseline_match",
                "comparable_dimensions": 1,
                "statistically_evaluable_dimensions": 1,
                "regression_dimensions": [],
                "dimensions": {},
                "warnings": [],
                "metadata": {"baseline_runs": 3},
            }
        },
    )

    human = build_report_interpretation(report)

    assert human["quality"]["state"] == "match"
    assert human["identity"]["state"] == "missing"
    assert human["decision"] == "人工复核"


def test_fingerprint_mismatch_is_not_automatic_model_rejection():
    report = AuditReport(
        target={"base_url": "https://example.com/v1", "model": "kimi-k3"},
        summary=AuditSummary(final_verdict="mismatch", confidence="high"),
        results=[
            result(
                "identity.fingerprint.reference_compare",
                "identity",
                status=ProbeStatus.WARN,
                score=None,
                confidence=None,
                identity_strength="weak",
                weight_identity_proof=False,
                verdict="mismatch",
            )
        ],
    )
    human = build_report_interpretation(report)
    assert human["identity"]["state"] == "behavioral_mismatch"
    assert human["decision"] == "人工复核"
    assert "不以此单项证明换模" in human["headline"]

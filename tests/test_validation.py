import json

import pytest
from pydantic import ValidationError

from model_detect.models import AuditReport, AuditSummary, ProbeResult, ProbeStatus
from model_detect.validation import (
    ValidationSuite,
    classify_report,
    evaluate_suite,
    load_suite,
    write_validation,
)


def audit_report(
    *,
    identity=None,
    routing=None,
    quality=None,
    model="kimi-k3",
):
    results = []
    if identity is not None:
        results.append(ProbeResult(
            probe_id="identity.fingerprint.reference_compare",
            category="identity",
            status={
                "same": ProbeStatus.PASS,
                "different": ProbeStatus.FAIL,
                "uncertain": ProbeStatus.WARN,
            }[identity],
            score=1.0 if identity == "same" else 0.0,
            summary="trusted fingerprint",
            metadata={
                "identity_strength": "strong",
                "verdict": {
                    "same": "match",
                    "different": "mismatch",
                    "uncertain": "uncertain",
                }[identity],
            },
        ))
    if routing is not None:
        is_mixed = routing == "mixed"
        is_suspicious = routing == "suspicious"
        results.extend([
            ProbeResult(
                probe_id="routing.repeat.same_probe",
                category="routing",
                status=ProbeStatus.WARN if is_suspicious else (
                    ProbeStatus.FAIL if is_mixed else ProbeStatus.PASS
                ),
                score=0.0 if is_mixed else 1.0,
                summary="repeated requests",
                observed={"samples": 6},
            ),
            ProbeResult(
                probe_id="routing.cluster",
                category="routing",
                status=ProbeStatus.WARN if is_suspicious else (
                    ProbeStatus.FAIL if is_mixed else ProbeStatus.PASS
                ),
                score=0.0 if is_mixed else 1.0,
                summary="cluster",
            ),
            ProbeResult(
                probe_id="routing.summary",
                category="routing",
                status=ProbeStatus.WARN if is_suspicious else (
                    ProbeStatus.FAIL if is_mixed else ProbeStatus.PASS
                ),
                score=0.0 if is_mixed else 1.0,
                summary="routing fusion",
                metadata={
                    "verdict": (
                        "mixed-routing-likely" if is_mixed
                        else "suspicious" if is_suspicious else "stable"
                    )
                },
            ),
        ])
    comparison = (
        {"status": "not_configured"}
        if quality is None
        else {
            "verdict": "quality_regression" if quality else "baseline_match",
            "regression_dimensions": ["reasoning"] if quality else [],
            "incomparable_dimensions": [],
            "statistically_evaluable_dimensions": 2,
        }
    )
    return AuditReport(
        target={"model": model, "base_url": "https://test.example/v1"},
        profile="standard",
        results=results,
        summary=AuditSummary(final_verdict="review"),
        adapters={"official_baseline_comparison": comparison},
    )


def suite(cases):
    return ValidationSuite.model_validate({
        "id": "controlled-test",
        "cases": cases,
    })


def validation_case(case_id, scenario, truth, **other):
    return {
        "id": case_id,
        "scenario": scenario,
        "truth_source": "controlled-test-config-2026",
        "truth": truth,
        **other,
    }


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def test_truth_labels_are_required_and_extra_secrets_rejected():
    with pytest.raises(ValidationError, match="at least one known truth"):
        suite([validation_case("a", "same_model", {})])
    with pytest.raises(ValidationError):
        suite([validation_case(
            "a", "same_model", {"identity": "same"},
            api_key="sk-do-not-save",
        )])
    with pytest.raises(ValidationError, match="case ids must be unique"):
        suite([
            validation_case("a", "same_model", {"identity": "same"}),
            validation_case("a", "same_model", {"identity": "same"}),
        ])


def test_mixed_routing_requires_declared_ratio_consistency():
    with pytest.raises(ValidationError, match="requires routing_fraction"):
        suite([validation_case(
            "route30", "mixed_routing", {"routing_mixed": True}
        )])
    with pytest.raises(ValidationError, match="contradicts"):
        suite([validation_case(
            "route0", "mixed_routing", {"routing_mixed": True},
            routing_fraction=0.0,
        )])


def test_signal_classifier_abstains_without_strong_evidence():
    assert classify_report(audit_report()) == {
        "identity": None, "routing": None, "quality": None
    }
    assert classify_report(audit_report(
        identity="uncertain", routing="suspicious"
    )) == {"identity": None, "routing": None, "quality": None}
    assert classify_report(audit_report(
        identity="different", routing="mixed", quality=True
    )) == {"identity": "different", "routing": True, "quality": True}


def test_confusion_matrix_counts_real_reports_and_abstentions(tmp_path):
    cases = [
        validation_case(
            "official", "same_model",
            {"identity": "same", "routing_mixed": False, "quality_regressed": False},
        ),
        validation_case(
            "switched", "different_model",
            {"identity": "different", "routing_mixed": False, "quality_regressed": True},
        ),
        validation_case(
            "route30", "mixed_routing",
            {"identity": "same", "routing_mixed": True},
            routing_fraction=0.3,
        ),
        validation_case(
            "loweffort", "different_effort",
            {"quality_regressed": True},
        ),
        validation_case(
            "unknown", "different_provider",
            {"identity": "same"},
        ),
    ]
    manifest = tmp_path / "experiment.yaml"
    manifest.write_text("id: controlled-test\n", encoding="utf-8")
    root = tmp_path / "results"
    examples = [
        ("official", audit_report(identity="same", routing="stable", quality=False)),
        ("switched", audit_report(identity="different", routing="stable", quality=True)),
        ("route30", audit_report(identity="same", routing="mixed")),
        ("loweffort", audit_report(quality=False)),
        ("unknown", audit_report(identity="uncertain")),
    ]
    for case_id, report in examples:
        write_report(root / case_id / "01" / "report.json", report)

    outcome = evaluate_suite(
        suite(cases), manifest_path=manifest, output_dir=root,
    )
    assert outcome["observed_reports"] == 5
    ident = outcome["metrics"]["identity"]
    assert (ident["tp"], ident["tn"], ident["fp"], ident["fn"]) == (1, 2, 0, 0)
    assert ident["labelled"] == 4
    assert ident["abstained"] == 1
    routing = outcome["metrics"]["routing"]
    assert (routing["tp"], routing["tn"], routing["fp"], routing["fn"]) == (1, 2, 0, 0)
    quality = outcome["metrics"]["quality"]
    assert (quality["tp"], quality["tn"], quality["fp"], quality["fn"]) == (1, 1, 0, 1)
    assert quality["sensitivity"] == 0.5

    json_path, md_path = write_validation(outcome, root)
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    text = md_path.read_text(encoding="utf-8")
    assert saved["metrics"]["identity"]["abstained"] == 1
    assert "受控鉴别实验" in text
    assert "30%（仅配置目标）" in text


def test_missing_reports_produce_no_fabricated_accuracy(tmp_path):
    case = validation_case(
        "official", "same_model", {"identity": "same"}, runs=3
    )
    manifest = tmp_path / "experiment.yaml"
    manifest.write_text("id: controlled-test\n", encoding="utf-8")
    outcome = evaluate_suite(
        suite([case]), manifest_path=manifest, output_dir=tmp_path / "out",
    )
    assert outcome["observed_reports"] == 0
    assert len(outcome["missing"]) == 3
    assert outcome["metrics"]["identity"]["accuracy"] is None
    assert outcome["metrics"]["identity"]["coverage"] is None
    assert outcome["metrics"]["identity"]["false_positive_rate"] is None


def test_rejects_wrong_model_and_profile_report(tmp_path):
    manifest = tmp_path / "experiment.yaml"
    manifest.write_text("id: controlled-test\n", encoding="utf-8")
    report = audit_report(identity="same", model="other-model")
    path = tmp_path / "mismatch.json"
    write_report(path, report)
    selected = suite([validation_case(
        "official", "same_model", {"identity": "same"},
        model="kimi-k3", reports=["mismatch.json"],
    )])
    outcome = evaluate_suite(
        selected, manifest_path=manifest, output_dir=tmp_path / "out"
    )
    assert outcome["observed_reports"] == 0
    assert "invalid report" in outcome["missing"][0]

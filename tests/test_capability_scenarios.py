from model_detect.models import ProbeResult, ProbeStatus
from model_detect.probes.capability import derived_capability_results


def _result(probe_id, score, status, evidence_id):
    return ProbeResult(
        probe_id=probe_id,
        category="protocol",
        status=status,
        score=score,
        confidence=0.8,
        summary=probe_id,
        evidence_ids=[evidence_id],
    )


def test_tool_use_capability_aggregates_multiple_scenarios():
    existing = [
        _result("protocol.tools.basic", 1.0, ProbeStatus.PASS, "ev1"),
        _result("protocol.tools.arguments_schema", 1.0, ProbeStatus.PASS, "ev2"),
        _result("protocol.tools.tool_choice", 0.5, ProbeStatus.WARN, "ev3"),
        _result("protocol.tools.parallel", 0.5, ProbeStatus.WARN, "ev4"),
    ]

    results = derived_capability_results(existing)
    tool = next(item for item in results if item.probe_id == "capability.tool_use")

    assert tool.score == 0.75
    assert tool.status == ProbeStatus.WARN
    assert tool.metadata["scenario_count"] == 4
    assert tool.metadata["derived_from"] == [
        "protocol.tools.basic",
        "protocol.tools.arguments_schema",
        "protocol.tools.tool_choice",
        "protocol.tools.parallel",
    ]
    assert tool.evidence_ids == ["ev1", "ev2", "ev3", "ev4"]
    assert len(tool.observed["scenarios"]) == 4


def test_tool_use_ignores_non_capability_validation_probe():
    existing = [
        _result("protocol.tools.basic", 1.0, ProbeStatus.PASS, "ev1"),
        _result("protocol.tools.invalid_schema", 0.0, ProbeStatus.FAIL, "ev2"),
    ]

    results = derived_capability_results(existing)
    tool = next(item for item in results if item.probe_id == "capability.tool_use")

    assert tool.score == 1.0
    assert tool.status == ProbeStatus.PASS
    assert tool.metadata["scenario_count"] == 1

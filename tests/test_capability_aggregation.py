from model_detect.models import ProbeResult, ProbeStatus
from model_detect.probes.capability import derived_capability_results


def r(probe_id, score, status=ProbeStatus.PASS):
    return ProbeResult(
        probe_id=probe_id,
        category="protocol" if probe_id.startswith("protocol.") else "integrity",
        status=status,
        score=score,
        confidence=0.8,
        summary="test",
        evidence_ids=[f"ev_{probe_id.replace('.', '_')}"],
    )


def test_tool_use_dimension_aggregates_multiple_scenarios():
    got = derived_capability_results(
        [
            r("protocol.tools.basic", 1.0),
            r("protocol.tools.arguments_schema", 1.0),
            r("protocol.tools.tool_choice", 0.5, ProbeStatus.WARN),
            r("integrity.tool_definitions", 1.0),
            r("integrity.tools.preserved", 1.0),
        ]
    )
    tool = next(x for x in got if x.probe_id == "capability.tool_use")
    assert len(tool.metadata["derived_from"]) == 5
    assert tool.score is not None
    assert tool.score > 0.8
    assert len(tool.evidence_ids) == 5


def test_structured_output_dimension_aggregates_json_scenarios():
    got = derived_capability_results(
        [
            r("protocol.json_mode", 1.0),
            r("protocol.json_schema", 1.0),
            r("integrity.json_schema.preserved", 0.5, ProbeStatus.WARN),
        ]
    )
    structured = next(
        x for x in got if x.probe_id == "capability.structured_output"
    )
    assert structured.score is not None
    assert round(structured.score, 2) == 0.83
    assert structured.status == ProbeStatus.PASS

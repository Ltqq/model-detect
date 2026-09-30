import asyncio
import json

from model_detect.http_client import CallResult
from model_detect.models import Evidence, ProbeResult, ProbeStatus
from model_detect.probes.routing import (
    _fact_inversion,
    cluster_rows,
    finalize_routing_analysis,
)


def result(probe_id, status, score, **metadata):
    return ProbeResult(
        probe_id=probe_id,
        category="routing",
        status=status,
        score=score,
        summary="test",
        metadata=metadata,
    )


def test_cluster_rows_groups_explainable_features():
    base = {
        "model": "m",
        "id_prefix": "chatcmpl-",
        "signature": "sig",
        "finish_reason": "stop",
        "usage_signature": "usage",
        "header_signature": ["x-request-id"],
    }
    rows = [
        {**base, "answer": "95"},
        {**base, "answer": "95"},
        {**base, "model": "m2", "answer": "95"},
    ]
    clusters = cluster_rows(rows)
    assert len(clusters) == 2
    assert clusters[0]["count"] == 2


def test_routing_summary_strong_model_drift_fails():
    results = [
        result(
            "routing.repeat.same_probe",
            ProbeStatus.FAIL,
            0.0,
            verdict="mixed-routing-likely",
        ),
        result(
            "routing.cluster",
            ProbeStatus.FAIL,
            0.0,
            verdict="mixed-routing-likely",
            model_drift=True,
        ),
    ]
    summary = finalize_routing_analysis(results)
    assert summary.status == ProbeStatus.FAIL
    assert summary.metadata["verdict"] == "mixed-routing-likely"


def test_routing_summary_requires_multiple_weak_signals_for_suspicious():
    one = finalize_routing_analysis(
        [
            result(
                "routing.fact_inversion",
                ProbeStatus.WARN,
                0.6,
                verdict="suspicious",
            ),
            result("routing.repeat.same_probe", ProbeStatus.PASS, 1.0, verdict="stable"),
        ]
    )
    assert one.status == ProbeStatus.PASS

    two = finalize_routing_analysis(
        [
            result(
                "routing.fact_inversion",
                ProbeStatus.WARN,
                0.6,
                verdict="suspicious",
            ),
            result(
                "routing.fingerprint.consistency",
                ProbeStatus.WARN,
                0.6,
                verdict="suspicious",
            ),
        ]
    )
    assert two.status == ProbeStatus.WARN
    assert two.metadata["verdict"] == "suspicious"


class FakeClient:
    def __init__(self, calls):
        self.calls = list(calls)

    async def post_json(self, **kwargs):
        if not self.calls:
            raise AssertionError("unexpected request")
        return self.calls.pop(0)


def call(text, ev_id):
    body = {
        "choices": [
            {
                "message": {"content": text},
                "finish_reason": "stop",
            }
        ]
    }
    return CallResult(
        evidence=Evidence(
            id=ev_id,
            probe_id="routing.fact_inversion",
            url="https://example.com/v1/chat/completions",
            response_status=200,
            response_body=body,
        ),
        json_body=body,
        text_body=json.dumps(body),
    )


def test_fact_inversion_detects_inconsistent_same_fact():
    # 4 facts x 3 samples. First fact flips between expected and wrong.
    values = [
        "Au", "Ag", "Au",
        "Paris", "Paris", "Paris",
        "10", "10", "10",
        "H2O", "H2O", "H2O",
    ]
    calls = [call(value, f"ev_{i}") for i, value in enumerate(values)]
    probe, evidence = asyncio.run(_fact_inversion(FakeClient(calls), "m"))
    assert probe.status == ProbeStatus.WARN
    assert probe.observed["inversion_count"] == 1
    assert len(evidence) == 12

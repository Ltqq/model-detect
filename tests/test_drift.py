import json

from model_detect.drift import compare_reports


def test_compare_reports_detects_score_probe_and_provider_changes(tmp_path):
    old = {
        "target": {"model": "m"},
        "summary": {"final_verdict": "pass", "overall_score": 90, "category_scores": {"protocol": 100}},
        "results": [{"probe_id": "protocol.chat.basic", "status": "pass", "score": 1.0}],
        "provider_hypotheses": [{"provider": "fireworks", "confidence": 0.8}],
    }
    new = {
        "target": {"model": "m"},
        "summary": {"final_verdict": "review", "overall_score": 70, "category_scores": {"protocol": 70}},
        "results": [{"probe_id": "protocol.chat.basic", "status": "warn", "score": 0.7}],
        "provider_hypotheses": [{"provider": "azure_apim", "confidence": 0.9}],
    }
    p1 = tmp_path / "old.json"
    p2 = tmp_path / "new.json"
    p1.write_text(json.dumps(old), encoding="utf-8")
    p2.write_text(json.dumps(new), encoding="utf-8")

    got = compare_reports(p1, p2)
    assert got["category_deltas"]["protocol"]["delta"] == -30.0
    assert got["probe_changes"][0]["probe_id"] == "protocol.chat.basic"
    assert "azure_apim" in got["provider_changes"]["added"]
    assert "fireworks" in got["provider_changes"]["removed"]

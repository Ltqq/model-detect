"""M4-B: Web opt-in benchmark evidence capture, history reuse, no paid tests."""
import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from model_detect import webapp
from model_detect.models import AuditReport, AuditSummary, ProbeResult, ProbeStatus


def _app(tmp_path):
    return webapp.create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"reports", regression_dir=tmp_path/"regressions",
    )


def _payload(manifest=None, *, capture=True):
    return {
        "base_url": "https://relay.example/v1",
        "api_key": "sk-local-m4-secret",
        "model": "glm-5.3", "profile": "standard",
        "benchmark_profile": "smoke",
        "retain_benchmark_reference": capture,
        "benchmark_revisions_file": str(manifest) if manifest else None,
        "proxy_sleuth": False,
    }


def _manifest(path):
    path.write_text(
        "schema: benchmark-revisions-v1\n"
        "provider_role: official\n"
        "tasks:\n"
        "  truthfulqa_gen:\n"
        "    dataset_revision: fixture-dataset\n"
        "    scorer_revision: fixture-scorer\n"
    )
    return path


def test_web_benchmark_capture_preflight_without_model_calls(tmp_path):
    client = TestClient(_app(tmp_path))
    no_manifest = client.post("/api/audits", json=_payload())
    assert no_manifest.status_code == 400
    assert client.get("/api/jobs").json()["jobs"] == []
    bad = _manifest(tmp_path/"revisions.yaml")
    bad.write_text(bad.read_text().replace("truthfulqa_gen", "gsm8k"))
    mismatch = client.post("/api/audits", json=_payload(bad))
    assert mismatch.status_code == 400
    assert client.get("/api/jobs").json()["jobs"] == []
    assert "sk-local-m4-secret" not in mismatch.text


def test_web_audit_persists_reference_selection_and_removes_raw_on_delete(
    monkeypatch, tmp_path,
):
    pending = []

    def intercept(coro):
        pending.append(coro)
        return None

    async def fake_audit(cfg, *, api_key_override=None, **kwargs):
        assert api_key_override == "sk-local-m4-secret"
        assert cfg.benchmark_profile == "smoke"
        assert cfg.benchmark_revisions_file == str(manifest)
        evidence_root = Path(cfg.benchmark_evidence_dir)
        assert not evidence_root.exists()
        (evidence_root/"snapshots").mkdir(parents=True)
        (evidence_root/"samples_private.jsonl").write_text("private prompt")
        (evidence_root/"snapshots"/"truthfulqa_gen.json").write_text("{}")
        return AuditReport(
            profile="standard",
            target={"model":"glm-5.3","base_url":"https://relay.example/v1","protocol":"openai"},
            results=[ProbeResult(
                probe_id="protocol.chat.basic", category="protocol",
                status=ProbeStatus.PASS, score=1., confidence=1.,
                summary="Mock protocol valid",
            )],
            summary=AuditSummary(
                overall_score=95., category_scores={"protocol": 95.},
                coverage={"protocol": True}, final_verdict="MATCH",
                confidence="high",
            ),
            adapters={
                "lm_eval_benchmark": {
                    "status":"completed", "snapshot_import":{
                        "status":"completed", "source_verified":False,
                    },
                },
                "promptfoo_regression":{"status":"not_configured"},
                "model_rule":{"id":"default","sources":[]},
            },
        )

    manifest = _manifest(tmp_path/"revisions.yaml")
    monkeypatch.setattr(webapp.asyncio, "create_task", intercept)
    monkeypatch.setattr(webapp, "run_audit", fake_audit)
    client = TestClient(_app(tmp_path))
    posted = client.post("/api/audits", json=_payload(manifest))
    assert posted.status_code == 200, posted.text
    assert len(pending) == 1
    asyncio.run(pending.pop())
    jid = posted.json()["id"]
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "done"
    assert job["meta"]["benchmark_snapshot_status"] == "completed"
    snapshot_path = Path(job["meta"]["benchmark_snapshots_dir"])
    assert snapshot_path.exists()
    assert "sk-local-m4-secret" not in json.dumps(job)
    home = client.get("/").text
    assert "设为官方" in home and "设为供应商" in home
    assert str(snapshot_path) in home
    assert "private prompt" not in client.get(f"/reports/{jid}").text
    deleted = client.delete(f"/api/jobs/{jid}")
    assert deleted.status_code == 200
    assert not snapshot_path.parent.exists()

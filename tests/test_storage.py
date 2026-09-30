from model_detect.storage import JobStore


def test_job_store_roundtrip(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    created = store.create(
        job_id="audit_1",
        kind="audit",
        model="kimi-k3",
        base_url="https://example/v1",
        profile="standard",
        meta={"reference_id": "ref1"},
    )
    assert created["status"] == "queued"
    assert created["meta"]["reference_id"] == "ref1"

    running = store.update(
        "audit_1",
        status="running",
        progress=0.5,
        detail="context-suite",
    )
    assert running["progress"] == 0.5

    done = store.finish(
        "audit_1",
        report_path="/tmp/report.html",
        meta={"score": 90},
    )
    assert done["status"] == "done"
    assert done["meta"]["score"] == 90
    assert store.list()[0]["id"] == "audit_1"

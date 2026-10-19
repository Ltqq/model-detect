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



def test_job_store_filters_model_status_and_kind(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")

    store.create(
        job_id="audit_kimi",
        kind="audit",
        model="kimi-k3",
        base_url="https://example/v1",
        profile="standard",
    )
    store.finish("audit_kimi", meta={"verdict": "MATCH"})

    store.create(
        job_id="audit_glm",
        kind="audit",
        model="glm-5.2",
        base_url="https://example/v1",
        profile="quick",
    )
    store.fail("audit_glm", "failed")

    store.create(
        job_id="ref_kimi",
        kind="reference",
        model="kimi-k3",
        base_url="https://official/v1",
        profile="standard",
    )

    assert [x["id"] for x in store.list(model="KIMI")] == [
        "ref_kimi",
        "audit_kimi",
    ]
    assert [x["id"] for x in store.list(status="failed")] == [
        "audit_glm",
    ]
    assert [x["id"] for x in store.list(kind="reference")] == [
        "ref_kimi",
    ]
    assert [x["id"] for x in store.list(
        model="kimi",
        status="done",
        kind="audit",
    )] == ["audit_kimi"]



def test_job_store_delete(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create(
        job_id="audit_delete",
        kind="audit",
        model="m",
        base_url="https://example/v1",
        profile="quick",
    )

    assert store.delete("audit_delete") is True
    assert store.delete("audit_delete") is False

    try:
        store.get("audit_delete")
    except KeyError:
        pass
    else:
        raise AssertionError("deleted job should not exist")


def test_sqlite_backup_restore_preserves_legacy_history_and_json_metadata(tmp_path):
    """SQLite native backup is consistent even if a writer connection is open.

    Does not touch user files, external APIs or assume schema migrations.
    """
    import sqlite3

    original = JobStore(tmp_path / "active" / "jobs.sqlite3")
    original.create(
        job_id="legacy_1", kind="audit", model="glm-5.3",
        base_url="https://private.example/v1", profile="quick",
        meta={"score": 88.5, "provider_hypotheses": [{"provider": "unknown"}]},
    )
    original.finish("legacy_1", report_path="/old/report.html",
                    meta={"score": 88.5, "verdict": "review"})

    backup = tmp_path / "backup" / "jobs.sqlite3"
    backup.parent.mkdir(parents=True)
    with sqlite3.connect(original.path) as source:
        with sqlite3.connect(backup) as target:
            source.backup(target)
    assert backup.exists()

    recovered = JobStore(backup)
    assert len(recovered.list()) == 1
    row = recovered.get("legacy_1")
    assert row["model"] == "glm-5.3"
    assert row["status"] == "done"
    assert row["report_path"] == "/old/report.html"
    assert row["meta"]["score"] == 88.5
    assert row["meta"]["verdict"] == "review"
    assert recovered.delete("legacy_1") is True
    assert original.get("legacy_1")["status"] == "done"

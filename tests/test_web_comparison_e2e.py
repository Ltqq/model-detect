"""M4: saved official/vendor evidence -> existing Web, SQLite, report and ZIP."""
import io
import json
import zipfile

from fastapi.testclient import TestClient

from model_detect.evaluation_snapshots import EvaluationSnapshot, save_snapshot
from model_detect.kimi_official import OFFICIAL_COMMIT
from model_detect.webapp import create_app


def _snapshot(folder, role, score, *, marker="a"):
    folder.mkdir(parents=True)
    item = EvaluationSnapshot(
        model="kimi-k3", provider_role=role, task_id="gsm8k",
        engine_revision="0.4.13", dataset_revision="same-dataset",
        scorer_revision="same-scorer",
        sample_ids_sha256=marker*64,
        generation_parameters_sha256="b"*64, sample_count=25,
        score=score, metric_name="exact_match",
        source_artifact_sha256="c"*64,
    )
    save_snapshot(item, folder/"gsm8k.json")


def _kimi(path, statuses):
    path.write_text(json.dumps({
        "schema": "kimi-official-junit-import-v1",
        "source_commit": OFFICIAL_COMMIT, "suite": "params",
        "model": "kimi-k3",
        "counts": {x: sum(v == x for v in statuses)
                   for x in ("pass", "fail", "error", "skipped")},
        "cases": [
            {"testcase_sha256": chr(97+i)*64, "status": v}
            for i, v in enumerate(statuses)
        ],
    }))


def test_web_comparison_history_html_json_zip_delete(tmp_path):
    official, vendor = tmp_path/"official", tmp_path/"vendor"
    _snapshot(official, "official", .9)
    _snapshot(vendor, "vendor", .7)
    kp, kv = tmp_path/"official-kimi.json", tmp_path/"vendor-kimi.json"
    _kimi(kp, ["pass", "pass"])
    _kimi(kv, ["pass", "fail"])
    app = create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"reports",
        regression_dir=tmp_path/"regressions",
    )
    client = TestClient(app)
    payload = {
        "model": "kimi-k3", "official_snapshots_dir": str(official),
        "vendor_snapshots_dir": str(vendor),
        "kimi_official_summary": str(kp), "kimi_vendor_summary": str(kv),
    }
    result = client.post("/api/comparisons", json=payload)
    assert result.status_code == 200, result.text
    job = result.json()
    assert job["kind"] == "comparison"
    assert job["status"] == "done"
    assert job["meta"]["comparable_tasks"] == 1
    assert job["meta"]["kimi_protocol_status"] == "comparable"
    jid = job["id"]
    assert "api_key" not in json.dumps(job)
    assert str(official) not in json.dumps(job)

    html = client.get(f"/reports/{jid}")
    assert html.status_code == 200
    assert "Kimi 官方协议专项" in html.text
    assert "供应商" in html.text
    assert "来源未经独立认证" in html.text
    raw = client.get(f"/api/audits/{jid}/report")
    assert raw.status_code == 200
    doc = raw.json()
    assert doc["comparable_tasks"] == 1
    assert doc["kimi_official_protocol"]["newly_failed_cases"] == 1
    assert doc["model_identity_proven"] is False
    history = client.get("/", params={"kind":"comparison"})
    assert jid in history.text and "离线对照" in history.text
    zip_resp = client.get(f"/api/audits/{jid}/download")
    assert zip_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
        assert {"comparison.html","comparison.json","comparison.md"}.issubset(z.namelist())
        assert "api_key" not in z.read("comparison.json").decode()

    deleted = client.delete(f"/api/jobs/{jid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/jobs/{jid}").status_code == 404
    assert not (tmp_path/"reports"/jid).exists()
    assert not (tmp_path/"state"/f"{jid}-report.zip").exists()


def test_web_comparison_rejects_missing_pair_and_wrong_roles(tmp_path):
    a, b = tmp_path/"a", tmp_path/"b"
    _snapshot(a,"vendor",.95)
    _snapshot(b,"vendor",.8)
    client = TestClient(create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"out",
    ))
    incomplete = client.post("/api/comparisons", json={
        "model": "kimi-k3", "official_snapshots_dir": str(a),
    })
    assert incomplete.status_code == 400
    result = client.post("/api/comparisons", json={
        "model": "kimi-k3",
        "official_snapshots_dir": str(a), "vendor_snapshots_dir": str(b),
    })
    assert result.status_code == 200, result.text
    report = client.get(f'/api/audits/{result.json()["id"]}/report').json()
    assert report["comparable_tasks"] == 0
    assert report["tasks"][0]["status"] == "not_comparable"
    assert report["tasks"][0]["reason"] == "source_role_mismatch"


def test_web_comparison_kimi_only_and_html_escaping(tmp_path):
    kp, kv = tmp_path/"o.json", tmp_path/"v.json"
    _kimi(kp, ["pass"])
    _kimi(kv, ["fail"])
    client = TestClient(create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"out",
    ))
    # A UI label must not silently override the real model recorded in JUnit.
    invalid = client.post("/api/comparisons", json={
        "model": "kimi-k3<script>bad</script>",
        "kimi_official_summary": str(kp), "kimi_vendor_summary": str(kv),
    })
    assert invalid.status_code == 400
    assert client.get("/api/jobs").json()["jobs"] == []

    result = client.post("/api/comparisons", json={
        "model": "kimi-k3",
        "kimi_official_summary": str(kp), "kimi_vendor_summary": str(kv),
    })
    assert result.status_code == 200, result.text
    html = client.get(f'/reports/{result.json()["id"]}').text
    assert "官方协议专项" in html


def test_web_comparison_refuses_displayed_model_mismatch_in_benchmark(tmp_path):
    official, vendor = tmp_path/"official", tmp_path/"vendor"
    _snapshot(official,"official",.91)
    _snapshot(vendor,"vendor",.86)
    client = TestClient(create_app(
        state_dir=tmp_path/"state", reference_dir=tmp_path/"refs",
        output_dir=tmp_path/"out",
    ))
    result = client.post("/api/comparisons", json={
        "model": "glm-5.3",
        "official_snapshots_dir": str(official),
        "vendor_snapshots_dir": str(vendor),
    })
    assert result.status_code == 400
    assert client.get("/api/jobs").json()["jobs"] == []


def test_direct_comparison_cli_remains_backward_compatible(tmp_path):
    from model_detect.evaluation_batch_report import compare_directories
    official, vendor = tmp_path/"official", tmp_path/"vendor"
    _snapshot(official,"official",.91)
    _snapshot(vendor,"vendor",.86)
    assert compare_directories(official,vendor)["comparable_tasks"] == 1
    try:
        compare_directories(official,vendor,expected_model="glm-5.3")
        assert False, "mismatched actual model must fail"
    except ValueError:
        pass

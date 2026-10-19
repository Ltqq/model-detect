"""Existing local Web+SQLite comparison workflow; no paid model calls."""
import io
import json
import zipfile

from fastapi.testclient import TestClient

from model_detect.webapp import create_app
from model_detect.evaluation_snapshots import EvaluationSnapshot, save_snapshot
from model_detect.kimi_official import OFFICIAL_COMMIT


def _add_run(root, name, role, model="kimi-k3", score=0.8):
    folder = root / name
    snapshots = folder / "snapshots"
    snapshots.mkdir(parents=True)
    record = EvaluationSnapshot(
        model=model, provider_role=role, task_id="gsm8k",
        engine_revision="0.4.13", dataset_revision="same-data",
        scorer_revision="same-scorer",
        sample_ids_sha256="a"*64, generation_parameters_sha256="b"*64,
        sample_count=25, score=score, metric_name="exact_match",
        source_artifact_sha256="c"*64,
    )
    save_snapshot(record, snapshots / "gsm8k.json")
    return folder


def _kimi(folder, failed=False):
    cases = [
        {"testcase_sha256": "a"*64, "status": "pass"},
        {"testcase_sha256": "b"*64, "status": "fail" if failed else "pass"},
    ]
    data = {
        "schema": "kimi-official-junit-import-v1", "source_commit": OFFICIAL_COMMIT,
        "suite": "params", "model": "kimi-k3", "cases": cases,
        "counts": {key: sum(row["status"] == key for row in cases)
                   for key in ("pass", "fail", "error", "skipped")},
    }
    (folder / "kimi-summary.json").write_text(json.dumps(data))


def _client(tmp_path):
    app = create_app(state_dir=tmp_path/"state", output_dir=tmp_path/"out",
                     reference_dir=tmp_path/"refs", regression_dir=tmp_path/"regression")
    runs = tmp_path/"state"/"evaluation-runs"
    return TestClient(app), runs, app


def test_web_comparison_history_download_delete_and_zero_model_calls(tmp_path, monkeypatch):
    client, runs, app = _client(tmp_path)
    official = _add_run(runs,"official-01","official",score=.9)
    vendor = _add_run(runs,"vendor-01","vendor",score=.8)
    _kimi(official)
    _kimi(vendor,failed=True)

    def forbid_model_calls(*args, **kwargs):
        raise AssertionError("local snapshot comparison must never call a model")
    monkeypatch.setattr("model_detect.webapp.run_audit",forbid_model_calls)

    response = client.post("/api/evaluation-comparisons",json={
        "model":"kimi-k3","official_run":"official-01",
        "vendor_run":"vendor-01","include_kimi":True
    })
    assert response.status_code==200, response.text
    job = response.json()
    assert job["kind"]=="comparison" and job["status"]=="done"
    assert job["meta"]["comparable_tasks"]==1
    id=job["id"]
    detail=client.get("/api/jobs/"+id).json()
    assert detail["kind"]=="comparison" and detail["base_url"]==""
    home=client.get("/?kind=comparison")
    assert home.status_code==200 and id in home.text
    assert "模型能力对照" in home.text
    html=client.get("/reports/"+id)
    assert html.status_code==200 and "Kimi 官方协议专项" in html.text
    report=client.get("/api/audits/"+id+"/report").json()
    assert report["comparable_tasks"]==1
    assert report["kimi_official_protocol"]["newly_failed_cases"]==1
    assert report["official_provenance_attested"] is False
    assert report["model_identity_proven"] is False
    archive=client.get("/api/audits/"+id+"/download")
    assert archive.status_code==200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        assert set(z.namelist())=={"comparison.json","comparison.md"}
    assert client.delete("/api/jobs/"+id).status_code==200
    assert client.get("/api/jobs/"+id).status_code==404
    assert not (tmp_path/"out"/id).exists()


def test_comparison_refuses_swapped_roles_wrong_models_and_paths(tmp_path):
    client, runs, app = _client(tmp_path)
    _add_run(runs,"left","vendor")
    _add_run(runs,"right","official")
    payload={"model":"kimi-k3","official_run":"left","vendor_run":"right"}
    assert client.post("/api/evaluation-comparisons",json=payload).status_code==400
    assert client.post("/api/evaluation-comparisons",json={
        **payload,"official_run":"../outside"
    }).status_code==422
    assert client.post("/api/evaluation-comparisons",json={
        **payload,"official_run":"left","vendor_run":"left"
    }).status_code==400
    assert client.get("/api/jobs").json()["jobs"]==[]
    # Wrong model even if the source roles are correct.
    payload["official_run"]="right"
    payload["vendor_run"]="left"
    payload["model"]="glm-5.3"
    assert client.post("/api/evaluation-comparisons",json=payload).status_code==400


def test_kimi_only_comparison_and_html_escapes_local_input(tmp_path):
    client,runs,app=_client(tmp_path)
    o=runs/"official"
    v=runs/"vendor"
    o.mkdir(parents=True)
    v.mkdir(parents=True)
    _kimi(o)
    _kimi(v,failed=True)
    r=client.post("/api/evaluation-comparisons",json={
        "model":"kimi-k3", "official_run":"official","vendor_run":"vendor",
        "include_benchmark":False,"include_kimi":True,
    })
    assert r.status_code==200, r.text
    doc=client.get("/reports/"+r.json()["id"]).text
    assert "官方端点通过但供应商未通过：1" in doc
    assert "能力基准对照" in doc

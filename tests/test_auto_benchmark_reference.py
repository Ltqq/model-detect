"""M2: opt-in automatic snapshots from real logged lm-eval artifacts."""
import asyncio
import json

import pytest

from model_detect.audit import run_audit
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget
from model_detect.lmeval_run_import import load_revision_manifest, import_run_snapshots


def _fixture(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "results_20261019.json").write_text(json.dumps({
        "results": {"gsm8k": {"exact_match,strict-match": 0.75}},
        "n-samples": {"gsm8k": {"effective": 2}},
        "configs": {"gsm8k": {"task": "gsm8k", "output_type": "generate_until"}},
        "lm_eval_version": "0.4.13",
        "versions": {"gsm8k": 1},
        "config": {"model_args": "model=glm-5.3,base_url=http://127.0.0.1:9090/v1"},
    }))
    (root / "samples_gsm8k_20261019.jsonl").write_text(
        json.dumps({"doc_id": 17, "doc": {"secret": "hidden prompt"}}) + "\n" +
        json.dumps({"doc_id": 28, "resps": ["hidden answer"]}) + "\n"
    )
    manifest = tmp_path / "revisions.yaml"
    manifest.write_text(
        "schema: benchmark-revisions-v1\nprovider_role: official\n"
        "tasks:\n  gsm8k:\n    dataset_revision: user-declared-dataset\n"
        "    scorer_revision: user-declared-scorer\n"
    )
    return root, manifest


def test_saved_run_produces_reusable_snapshots_but_does_not_attest_source(tmp_path):
    root, file = _fixture(tmp_path)
    labels = load_revision_manifest(file, expected_tasks=["gsm8k"])
    out = root / "snapshots"
    result = import_run_snapshots(run_dir=root, output_dir=out, model="glm-5.3", manifest=labels)
    assert result["status"] == "completed" and result["task_count"] == 1
    snap = json.loads((out / "gsm8k.json").read_text())
    assert snap["score"] == .75
    assert snap["source_verified"] is False
    assert "hidden" not in (out / "gsm8k.json").read_text()
    with pytest.raises(FileExistsError):
        import_run_snapshots(run_dir=root, output_dir=out, model="glm-5.3", manifest=labels)


def test_manifest_wrong_task_or_role_rejected(tmp_path):
    root, file = _fixture(tmp_path)
    with pytest.raises(ValueError, match="task set"):
        load_revision_manifest(file, expected_tasks=["ifeval"])
    file.write_text(file.read_text().replace("official", "untrusted"))
    with pytest.raises(ValueError, match="provider_role"):
        load_revision_manifest(file, expected_tasks=["gsm8k"])


def test_invalid_revision_file_aborts_before_api_or_creating_output(tmp_path):
    root, file = _fixture(tmp_path)
    file.write_text("schema: wrong\n")
    output = tmp_path / "future-artifacts"
    cfg = AuditConfig(
        target=AuditTarget(base_url="https://unreachable.invalid/v1", model="glm-5.3",
                           api_key_env="M2_UNSET_KEY"),
        benchmark_profile="smoke",
        benchmark_evidence_dir=str(output),
        benchmark_revisions_file=str(file),
    )
    with pytest.raises(ValueError, match="revisions manifest"):
        asyncio.run(run_audit(cfg))
    assert not output.exists()

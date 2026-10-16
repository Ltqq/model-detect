from model_detect.evaluation_batch_report import compare_directories, write_comparison_report
from model_detect.evaluation_snapshots import EvaluationSnapshot, save_snapshot
from typer.testing import CliRunner
from model_detect.cli import app


def make(root, role, task="gsm8k", score=.8, samples="a"):
    root.mkdir(exist_ok=True)
    item = EvaluationSnapshot(model="glm-5.3", provider_role=role, task_id=task,
        engine_revision="0.4.13", dataset_revision="rev", scorer_revision="s",
        sample_ids_sha256=samples*64, generation_parameters_sha256="b"*64,
        sample_count=25, score=score, metric_name="exact_match",
        source_artifact_sha256="c"*64)
    save_snapshot(item, root / (task+".json"))


def test_batch_report_compatible_and_missing_tasks(tmp_path):
    official, vendor = tmp_path/"official", tmp_path/"vendor"
    make(official, "official", score=.95)
    make(vendor, "vendor", score=.92)
    make(official, "official", task="ifeval")
    report = compare_directories(official, vendor)
    assert report["comparable_tasks"] == 1
    assert report["unknown_or_incompatible_tasks"] == 1
    assert report["model_identity_proven"] is False
    out = tmp_path / "out"
    write_comparison_report(report, out)
    rendered = (out/"comparison.md").read_text()
    assert "glm" not in rendered
    assert "gsm8k" in rendered and "缺失配对" in rendered


def test_cli_batch_report_and_mismatched_samples(tmp_path):
    official, vendor = tmp_path/"a", tmp_path/"b"
    make(official,"official",samples="a")
    make(vendor,"vendor",samples="d")
    out = tmp_path/"report"
    r = CliRunner().invoke(app,[
        "compare-evaluation-dirs", "--official-dir",str(official),
        "--vendor-dir",str(vendor),"--output-dir",str(out)
    ])
    assert r.exit_code == 0, r.output
    assert '"comparable_tasks": 0' in r.output
    assert (out/"comparison.json").exists()
    repeated = CliRunner().invoke(app,[
        "compare-evaluation-dirs","--official-dir",str(official),
        "--vendor-dir",str(vendor),"--output-dir",str(out)
    ])
    assert repeated.exit_code != 0

import json
import pytest
from typer.testing import CliRunner
from model_detect.cli import app
from model_detect.lmeval_run_import import import_run_directory


def _saved_run(root):
    root.mkdir()
    (root / "results_20261016.json").write_text(json.dumps({
        "results": {"gsm8k": {"exact_match,strict-match": 0.75}},
        "n-samples": {"gsm8k": {"effective": 2}},
        "configs": {"gsm8k": {"task": "gsm8k", "output_type": "generate_until"}},
        "lm_eval_version": "0.4.13", "versions": {"gsm8k": 1},
        "config": {"model_args": "model=glm-5.3,base_url=http://127.0.0.1:6789/v1"}
    }))
    (root / "samples_gsm8k_20261016.jsonl").write_text(
        json.dumps({"doc_id": 5, "doc": {"text": "private prompt"}}) + "\n" +
        json.dumps({"doc_id": 9, "resps": ["private answer"]}) + "\n"
    )


def test_import_saved_run_one_command_without_raw_content(tmp_path):
    root = tmp_path / "run"
    _saved_run(root)
    argv = [
        "import-lmeval-run", "--run-dir", str(root),
        "--task", "gsm8k", "--model", "glm-5.3",
        "--provider-role", "official", "--dataset-revision", "declared",
        "--scorer-revision", "declared", "--output", str(tmp_path / "snapshot.json")
    ]
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 0, result.output
    content = (tmp_path / "snapshot.json").read_text()
    assert "private prompt" not in content and "private answer" not in content
    assert '"source_verified": false' in content


def test_ambiguous_logs_and_glob_tasks_fail_closed(tmp_path):
    root = tmp_path / "run"
    _saved_run(root)
    (root / "samples_gsm8k_duplicate.jsonl").write_text('{"doc_id":5}')
    kwargs = dict(run_dir=root, task="gsm8k", output=tmp_path/"o.json",
                  model="glm-5.3", provider_role="official",
                  dataset_revision="declared", scorer_revision="declared")
    with pytest.raises(ValueError, match="exactly one"):
        import_run_directory(**kwargs)
    assert not (tmp_path/"o.json").exists()
    with pytest.raises(ValueError, match="invalid task"):
        import_run_directory(**{**kwargs, "task": "../*"})

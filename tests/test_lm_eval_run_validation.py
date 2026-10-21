"""Synthetic, model-independent checks for the original lm-eval run contract.

These fixtures never call a supplier endpoint, download datasets, or replace
the upstream scoring algorithm. They validate that execution is reportable.
"""
import json

import pytest

from model_detect.adapters import lm_eval
from model_detect.models import ProbeStatus


def payload(*, score=0.8, samples=5, with_version=True, with_config=True):
    data = {
        "results": {"gsm8k": {"exact_match,flexible-extract": score}},
        "n-samples": {"gsm8k": {"original": 100, "effective": samples}},
    }
    if with_version:
        data["versions"] = {"gsm8k": 3}
    if with_config:
        data["configs"] = {
            "gsm8k": {"dataset_path": "gsm8k", "output_type": "generate_until"}
        }
    return data


def check(data, root, *, tasks=None, log_samples=False):
    rows = lm_eval.parse_result_payload(data)
    lm_eval._validate_profile_run_results(
        rows,
        requested_tasks=tasks or ["gsm8k"],
        output_path=root,
        log_samples=log_samples,
    )
    return rows


def test_complete_native_task_result_is_accepted(tmp_path):
    rows = check(payload(), tmp_path)
    assert rows[0].status == ProbeStatus.PASS
    assert rows[0].observed["effective_samples"] == 5
    assert rows[0].observed["task_config_hash"]


@pytest.mark.parametrize("tasks", [["gsm8k", "ifeval"], ["ifeval"]])
def test_missing_expected_task_never_reports_complete(tmp_path, tasks):
    with pytest.raises(RuntimeError, match="did not produce results for tasks"):
        check(payload(), tmp_path, tasks=tasks)


@pytest.mark.parametrize(
    "data",
    [
        payload(samples=0),
        payload(samples=None),
        payload(samples=True),
        payload(with_version=False),
        payload(with_config=False),
        payload(score=float("nan")),
        payload(score=float("inf")),
        payload(score=-0.2),
    ],
)
def test_invalid_score_samples_version_or_config_is_not_a_success(tmp_path, data):
    with pytest.raises(RuntimeError, match="cannot mark this benchmark run complete"):
        check(data, tmp_path)


def test_sample_log_is_required_only_when_explicitly_requested(tmp_path):
    check(payload(), tmp_path, log_samples=False)
    with pytest.raises(RuntimeError, match="has no non-empty samples JSONL"):
        check(payload(), tmp_path, log_samples=True)
    (tmp_path / "samples_gsm8k_20261021.jsonl").write_text(
        '{"doc_id":1,"resps":[["42"]]}\n', encoding="utf-8"
    )
    check(payload(), tmp_path, log_samples=True)


@pytest.mark.parametrize("installed", ["0.4.12", "0.4.14", "0.4.13.dev0"])
def test_unpinned_harness_version_is_rejected(installed, monkeypatch):
    monkeypatch.setattr(lm_eval, "version", lambda _: installed)
    with pytest.raises(RuntimeError, match="no benchmark was started"):
        lm_eval._require_pinned_harness_version()


def test_correct_harness_version_is_explicit(monkeypatch):
    monkeypatch.setattr(lm_eval, "version", lambda _: "0.4.13")
    assert lm_eval._require_pinned_harness_version() == "0.4.13"


def test_stale_result_json_cannot_be_reused_as_a_new_success(tmp_path, monkeypatch):
    output = tmp_path / "results"
    output.mkdir()
    (output / "results_older.json").write_text(
        json.dumps(payload()), encoding="utf-8"
    )
    monkeypatch.setattr(lm_eval, "_require_pinned_harness_version", lambda: "0.4.13")
    monkeypatch.setattr(
        lm_eval, "run_builtin_profile",
        lambda **kwargs: {"returncode": 0, "stderr_tail": ""},
    )
    with pytest.raises(RuntimeError, match="refusing to reuse"):
        lm_eval.run_builtin_profile_results(
            profile_name="smoke",
            base_url="https://supplier.example/v1",
            model="generic",
            api_key="fake-token",
            output_path=output,
        )


def test_unpinned_preflight_does_not_invoke_costly_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(lm_eval, "version", lambda _: "0.4.12")
    monkeypatch.setattr(
        lm_eval, "run_builtin_profile",
        lambda **kwargs: pytest.fail("API benchmark must not have started"),
    )
    with pytest.raises(RuntimeError, match="no benchmark was started"):
        lm_eval.run_builtin_profile_results(
            profile_name="smoke",
            base_url="https://supplier.example/v1",
            model="generic",
            api_key="fake-token",
            output_path=tmp_path,
        )


def test_fresh_complete_profile_run_is_reported_with_provenance(tmp_path, monkeypatch):
    output = tmp_path / "new-run"

    def fake_original_runner(**kwargs):
        root = kwargs["output_path"]
        root.mkdir(parents=True, exist_ok=True)
        data = {
            "results": {"truthfulqa_gen": {"bleu_acc": 0.5}},
            "versions": {"truthfulqa_gen": 2},
            "configs": {
                "truthfulqa_gen": {
                    "dataset_path": "truthful_qa",
                    "output_type": "generate_until",
                }
            },
            "n-samples": {"truthfulqa_gen": {"original": 100, "effective": 5}},
        }
        (root / "results_current.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(lm_eval, "version", lambda _: "0.4.13")
    monkeypatch.setattr(lm_eval, "run_builtin_profile", fake_original_runner)
    results, metadata = lm_eval.run_builtin_profile_results(
        profile_name="smoke",
        base_url="https://supplier.example/v1",
        model="generic",
        api_key="synthetic",
        output_path=output,
    )

    assert len(results) == 1
    assert results[0].score == 0.5
    assert results[0].metadata["benchmark_effective_samples"] == 5
    assert results[0].metadata["benchmark_task_config_sha256"]
    assert results[0].metadata["benchmark_harness_version"] == "0.4.13"
    assert metadata["result_file"].endswith("results_current.json")


def test_official_metric_filter_suffix_retains_expected_primary_priority(tmp_path):
    data = {
        "results": {
            "truthfulqa_gen": {
                "rouge1_acc,none": 0.4,
                "bleu_acc,none": 0.5,
                "rougeL_acc,none": 0.6,
            },
        },
        "versions": {"truthfulqa_gen": 2},
        "configs": {
            "truthfulqa_gen": {
                "dataset_path": "truthful_qa",
                "output_type": "generate_until",
            },
        },
        "n-samples": {"truthfulqa_gen": {"effective": 25, "original": 100}},
    }
    rows = lm_eval.parse_result_payload(data)
    assert rows[0].observed["primary_metric"] == "bleu_acc,none"
    lm_eval._validate_profile_run_results(
        rows,
        requested_tasks=["truthfulqa_gen"],
        output_path=tmp_path,
        log_samples=False,
    )


def test_extra_task_result_cannot_be_mixed_into_requested_profile(tmp_path):
    data = payload()
    data["results"]["ifeval"] = {"prompt_level_strict_acc,none": 0.7}
    with pytest.raises(RuntimeError, match="unrequested tasks"):
        check(data, tmp_path, tasks=["gsm8k"])


def test_preexisting_sample_log_cannot_satisfy_a_new_run(tmp_path):
    old_log = tmp_path / "samples_gsm8k_old.jsonl"
    old_log.write_text('{"doc_id":1}\n', encoding="utf-8")
    before = lm_eval._result_artifact_snapshot(tmp_path)
    rows = lm_eval.parse_result_payload(payload())
    with pytest.raises(RuntimeError, match="no non-empty samples JSONL"):
        lm_eval._validate_profile_run_results(
            rows, requested_tasks=["gsm8k"],
            output_path=tmp_path, log_samples=True,
            existing_artifacts=before,
        )
    (tmp_path / "samples_gsm8k_new.jsonl").write_text(
        '{"doc_id":2}\n', encoding="utf-8"
    )
    lm_eval._validate_profile_run_results(
        rows, requested_tasks=["gsm8k"],
        output_path=tmp_path, log_samples=True,
        existing_artifacts=before,
    )

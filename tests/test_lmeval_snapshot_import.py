import json
import pytest
from model_detect.lmeval_snapshot_import import snapshot_from_lmeval, import_lmeval_snapshot


def _fixtures(tmp_path):
    result = tmp_path / "results.json"
    result.write_text(json.dumps({
        "results": {"gsm8k": {"exact_match,strict-match": .8}},
        "n-samples": {"gsm8k": {"effective": 2}},
        "configs": {"gsm8k": {"task": "gsm8k", "output_type": "generate_until",
                               "generation_kwargs": {"max_gen_toks": 256}}},
        "versions": {"gsm8k": 1},
        "lm_eval_version": "0.4.13",
        "config": {"model": "local-chat-completions", "model_args": "model=glm-5.3,base_url=http://localhost:1234/v1"},
    }))
    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps([{"doc_id": 7, "resps": ["secret"]},
                                   {"doc_id": 2, "resps": ["secret"]}]))
    return result, samples


def _args(tmp_path):
    a,b = _fixtures(tmp_path)
    return {"result_file": a, "samples_file": b, "task": "gsm8k",
            "model": "glm-5.3", "provider_role": "official",
            "dataset_revision": "user-declared-rev", "scorer_revision": "user-declared-scorer"}


def test_import_scores_and_sample_ids_without_prompt_or_urls(tmp_path):
    args = _args(tmp_path)
    snapshot = import_lmeval_snapshot(output=tmp_path / "snapshot.json", **args)
    assert snapshot.score == .8
    assert snapshot.sample_count == 2
    assert snapshot.source_verified is False
    saved = (tmp_path / "snapshot.json").read_text()
    assert "secret" not in saved
    assert "localhost" not in saved
    with pytest.raises(FileExistsError):
        import_lmeval_snapshot(output=tmp_path / "snapshot.json", **args)


def test_missing_samples_and_duplicate_ids_fail_closed(tmp_path):
    args = _args(tmp_path)
    args["samples_file"].write_text(json.dumps([{"doc_id": 7}, {"doc_id": 7}]))
    with pytest.raises(ValueError, match="duplicate"):
        snapshot_from_lmeval(**args)
    args["samples_file"].write_text(json.dumps([{"doc_id": 7}]))
    with pytest.raises(ValueError, match="count"):
        snapshot_from_lmeval(**args)

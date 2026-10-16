from typer.testing import CliRunner
from model_detect.cli import app
from model_detect.evaluation_catalog import benchmark_comparability, evaluation_catalog
from model_detect.kimi_official import OFFICIAL_COMMIT


def test_catalog_distinguishes_official_from_community():
    entries = {entry["id"]: entry for entry in evaluation_catalog()["entries"]}
    assert entries["k imi:params".replace(" ", "")]["authority"] == "official_suite"
    assert entries["kimi:params"]["source_revision"] == OFFICIAL_COMMIT
    assert entries["lm_eval:gsm8k"]["authority"] == "community_benchmark"
    assert entries["lm_eval:gsm8k"]["difficulty"] == "foundation"
    assert all(item["verified_on_live_model"] is False for item in entries.values())


def test_comparison_requires_exact_dataset_and_sample_contract():
    baseline = {
        "task_id": "gsm8k", "engine_revision": "v", "dataset_revision": "d",
        "scorer_revision": "s", "sample_ids_sha256": "a"*64,
        "generation_parameters_sha256": "b"*64,
    }
    assert benchmark_comparability(baseline, dict(baseline))["comparable"]
    changed = dict(baseline, dataset_revision="other")
    outcome = benchmark_comparability(baseline, changed)
    assert not outcome["comparable"]
    assert "dataset_revision" in outcome["mismatched_fields"]
    outcome = benchmark_comparability({}, baseline)
    assert not outcome["comparable"]
    assert "sample_ids_sha256" in outcome["missing_fields"]


def test_catalog_cli_reports_no_verified_official_scores():
    result = CliRunner().invoke(app, ["evaluation-catalog"])
    assert result.exit_code == 0, result.output
    assert "official_suite" in result.output
    assert "community_benchmark" in result.output
    assert "ceiling_effect_rule" in result.output

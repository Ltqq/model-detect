"""Pinned interpretation checks for official published scores.

No external API or model evaluation. Only ensures source figures cannot silently
be treated as a same-sample vendor reference.
"""
from importlib.resources import files

import yaml


def test_published_aggregate_is_background_only():
    path = files("model_detect").joinpath("data/public_benchmarks.yaml")
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["entries"]
    for entry in manifest["entries"]:
        assert entry["evidence_type"] == "official_published_aggregate"
        assert entry["comparison_status"] == "background_only"
        assert entry["source"]["url"].startswith("https://")
        assert entry["source"]["retrieved_at"]
        assert entry["conditions"]["scorer_revision"] is None
        assert entry["conditions"]["sample_count"] is None
        assert entry["source"]["immutable_commit"] is None


def test_kimi_official_gpqa_aggregate_is_not_verification_result():
    path = files("model_detect").joinpath("data/public_benchmarks.yaml")
    items = yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]
    record = next(item for item in items if item["id"] == "kimi-k3-gpqa-diamond-max-published")
    assert record["model"] == "kimi-k3"
    assert record["benchmark"] == "GPQA Diamond"
    assert record["value"] == 93.5
    assert record["conditions"]["effort"] == "max"
    assert record["comparison_status"] == "background_only"


def test_deepseek_october_public_results_are_background_only():
    """Source-verified vendor aggregates are NOT same-sample model verification."""
    path = files("model_detect").joinpath("data/public_benchmarks.yaml")
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]
    expected = {
        "deepseek-v41-flash-1017-hle-without-tools-published": ("HLE (without tools)", 42.6),
        "deepseek-v41-flash-1017-terminal-bench-4-published": ("Terminal-Bench 4.0", 42.3),
    }
    for evidence_id, (benchmark, value) in expected.items():
        record = next(item for item in entries if item["id"] == evidence_id)
        assert record["model"] == "deepseek-v4.1"
        assert record["model_variant"] == "DeepSeek-V4.1-Flash-1017"
        assert record["benchmark"] == benchmark
        assert record["value"] == value
        assert record["comparison_status"] == "background_only"
        assert "2026-10-17" in record["source"]["section"]
        assert record["conditions"]["dataset_revision"] is None

from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.kimi_official import OFFICIAL_CASES, OFFICIAL_COMMIT
from model_detect.test_catalog import build_test_catalog, select_catalog


def test_catalog_preserves_authority_and_unsupported_boundaries():
    result = build_test_catalog()
    names = {row["id"]: row for row in result["entries"]}
    assert all(f"kimi.official.{suite}" in names for suite in OFFICIAL_CASES)
    official = names["kimi.official.params"]
    assert official["source_revision"] == OFFICIAL_COMMIT
    assert official["provenance"] == "vendor_official_source_pinned"
    assert official["run_verified"] is False
    assert names["kimi.benchmark.deepswe"]["integration"] == "not_integrated"
    assert names["lm_eval.gsm8k"]["provenance"] == "community_benchmark_adapter"
    assert names["lm_eval.gsm8k"]["results_attested"] is False


def test_model_filter_does_not_claim_kimi_official_suites_for_other_model():
    catalog = select_catalog(model="glm-5.3")
    assert not any(row["id"].startswith("kimi.") for row in catalog["entries"])
    assert any(row["id"].startswith("lm_eval.") for row in catalog["entries"])


def test_catalog_cli_offline():
    result = CliRunner().invoke(app, ["catalog", "--model", "kimi-k3"])
    assert result.exit_code == 0, result.output
    assert "vendor_official_source_pinned" in result.output
    assert "not_integrated" in result.output

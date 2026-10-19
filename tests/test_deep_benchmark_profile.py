"""M5: Deep suite must test harder math, without bypassing the source scorer."""
from model_detect.adapters.lm_eval import load_builtin_profiles, resolve_builtin_profile
from model_detect.test_catalog import build_test_catalog
from model_detect.config import AuditConfig
from model_detect.models import AuditTarget


def test_deep_profile_is_not_just_more_easy_standard_tasks():
    profiles = load_builtin_profiles()
    assert profiles["version"] == 2
    deep = resolve_builtin_profile("deep", include_native_overlap=True)
    standard = resolve_builtin_profile("standard", include_native_overlap=True)
    assert deep["tasks"] != standard["tasks"]
    assert "minerva_math500" in deep["tasks"]
    assert "minerva_math500" not in standard["tasks"]
    assert "gsm8k" not in deep["tasks"]
    task = deep["task_metadata"]["minerva_math500"]
    assert task["difficulty"] == "advanced"
    assert task["output_type"] == "generate_until"
    assert task["requires_extra"] == "lm-eval[math]"
    assert deep["limit"] == 100


def test_source_catalog_and_engine_share_task_difficulty():
    definitions = load_builtin_profiles()["tasks"]
    catalog = {entry["id"]: entry for entry in build_test_catalog()["entries"]}
    for name, item in definitions.items():
        row = catalog["lm_eval." + name]
        assert row["difficulty"] == item["difficulty"]
        assert row["provenance"] == "community_benchmark_adapter"
        assert not row["results_attested"]
    assert "lm_eval.minerva_math500" in catalog


def test_deep_engine_remains_opt_in_and_not_model_identity_proof():
    config = AuditConfig(target=AuditTarget(base_url="http://127.0.0.1/v1", model="glm-5.3"))
    assert config.benchmark_profile is None
    assert config.capability_enabled

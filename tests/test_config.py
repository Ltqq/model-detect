from pathlib import Path

import pytest
import yaml

from model_detect.config import AuditConfig, load_config
from model_detect.models import AuditTarget


def test_config_defaults():
    cfg = AuditConfig(
        target=AuditTarget(
            base_url="https://example.com/v1",
            model="kimi-k3",
        )
    )
    assert cfg.profile == "quick"
    assert cfg.target.api_key_env == "OPENAI_API_KEY"
    assert cfg.target.protocol == "openai"
    assert cfg.regression.suites_for("quick") == []


def test_regression_suites_are_profile_aware_and_deduplicated():
    cfg = AuditConfig.model_validate(
        {
            "target": {
                "base_url": "https://example.com/v1",
                "model": "m",
            },
            "regression": {
                "suites": ["common.yaml"],
                "profiles": {
                    "quick": ["quick.yaml"],
                    "standard": ["common.yaml", "standard.yaml"],
                    "deep": ["deep.yaml"],
                },
            },
        }
    )

    assert cfg.regression.suites_for("quick") == [
        "common.yaml",
        "quick.yaml",
    ]
    assert cfg.regression.suites_for("standard") == [
        "common.yaml",
        "standard.yaml",
    ]
    assert cfg.regression.suites_for("deep") == [
        "common.yaml",
        "deep.yaml",
    ]


def test_regression_can_be_disabled():
    cfg = AuditConfig.model_validate(
        {
            "target": {
                "base_url": "https://example.com/v1",
                "model": "m",
            },
            "regression": {
                "enabled": False,
                "suites": ["common.yaml"],
                "profiles": {
                    "deep": ["deep.yaml"],
                },
            },
        }
    )

    assert cfg.regression.suites_for("deep") == []


def test_regression_profile_rejects_unknown_name():
    with pytest.raises(ValueError, match="unsupported regression profile"):
        AuditConfig.model_validate(
            {
                "target": {
                    "base_url": "https://example.com/v1",
                    "model": "m",
                },
                "regression": {
                    "profiles": {
                        "turbo": ["x.yaml"],
                    }
                },
            }
        )


def test_load_config_resolves_regression_paths_relative_to_config(tmp_path):
    suites = tmp_path / "suites"
    suites.mkdir()
    config_path = tmp_path / "audit.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "target": {
                    "base_url": "https://example.com/v1",
                    "model": "m",
                },
                "profile": "standard",
                "regression": {
                    "suites": ["suites/common.yaml"],
                    "profiles": {
                        "standard": ["suites/standard.yaml"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(config_path)

    assert cfg.regression.suites_for("standard") == [
        str((suites / "common.yaml").resolve()),
        str((suites / "standard.yaml").resolve()),
    ]



def test_upstream_policy_normalizes_and_deduplicates_provider_ids():
    cfg = AuditConfig.model_validate(
        {
            "target": {
                "base_url": "https://example.com/v1",
                "model": "m",
            },
            "upstream_policy": {
                "disallowed": [" Fireworks ", "fireworks", "AZURE_APIM"],
            },
        }
    )

    assert cfg.upstream_policy.disallowed == ["fireworks", "azure_apim"]
    assert cfg.upstream_policy.min_confidence == 0.70
    assert cfg.upstream_policy.strong_signal_weight == 0.90

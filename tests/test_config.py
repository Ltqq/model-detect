from model_detect.config import AuditConfig
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

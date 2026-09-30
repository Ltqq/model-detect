import pytest

from model_detect.adapters import lm_eval


def test_load_user_profile_filters_known_native_overlap(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
version: 1
profiles:
  supplier:
    tasks:
      - truthfulqa_gen
      - gsm8k
      - ifeval
    limit: 12
    include_native_overlap: false
""",
        encoding="utf-8",
    )
    profile = lm_eval.load_profile_file(path, "supplier")
    assert profile["tasks"] == ["truthfulqa_gen"]
    assert profile["skipped_tasks"] == ["gsm8k", "ifeval"]
    assert profile["limit"] == 12


def test_load_user_profile_allows_explicit_overlap(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
profiles:
  cross-check:
    tasks: [gsm8k, ifeval]
    include_native_overlap: true
""",
        encoding="utf-8",
    )
    profile = lm_eval.load_profile_file(path, "cross-check")
    assert profile["tasks"] == ["gsm8k", "ifeval"]
    assert profile["skipped_tasks"] == []


@pytest.mark.parametrize(
    "secret_key",
    ["api_key", "authorization", "token", "secret", "password"],
)
def test_profile_file_rejects_secrets(tmp_path, secret_key):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        f"""
profiles:
  bad:
    tasks: [truthfulqa_gen]
    {secret_key}: do-not-store-me
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must not contain secrets"):
        lm_eval.load_profile_file(path, "bad")


def test_profile_file_validates_limit(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
profiles:
  bad:
    tasks: [truthfulqa_gen]
    limit: 0
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="positive integer"):
        lm_eval.load_profile_file(path, "bad")


def test_run_profile_file_uses_existing_endpoint_runner(monkeypatch, tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
profiles:
  supplier:
    tasks: [truthfulqa_gen, gsm8k]
    limit: 7
""",
        encoding="utf-8",
    )
    seen = {}

    def fake_run_endpoint(**kwargs):
        seen.update(kwargs)
        return {"returncode": 0, "engine": "fake"}

    monkeypatch.setattr(lm_eval, "run_endpoint", fake_run_endpoint)
    result = lm_eval.run_profile_file(
        profile_file=path,
        profile_name="supplier",
        base_url="https://relay.example/v1",
        model="model-x",
        api_key="sk-test",
        output_path=tmp_path / "out",
    )
    assert seen["tasks"] == ["truthfulqa_gen"]
    assert seen["limit"] == 7
    assert result["profile"] == "supplier"
    assert result["skipped_tasks"] == ["gsm8k"]

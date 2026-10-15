import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.kimi_official import OFFICIAL_COMMIT
from model_detect.kimi_runner import run_official_subset
from model_detect import kimi_runner


def make_official_repo(tmp_path):
    repo = tmp_path / "official"
    (repo / "tests" / "params").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='test'\n")
    return repo


def test_runner_verifies_sha_and_keeps_secret_out_of_argv(tmp_path, monkeypatch):
    repo = make_official_repo(tmp_path)
    xml = tmp_path / "output" / "junit.xml"
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        if args[0] == "git":
            return SimpleNamespace(returncode=0, stdout=OFFICIAL_COMMIT + "\n")
        assert "secret-api-key" not in " ".join(args)
        assert kwargs["env"]["KIMI_API_KEY"] == "secret-api-key"
        xml.write_text("<testsuite><testcase classname='x' name='y'/></testsuite>")
        return SimpleNamespace(returncode=0, stdout="do not save this", stderr="")
    monkeypatch.setattr(kimi_runner.subprocess, "run", fake_run)
    result = run_official_subset(
        repo_dir=repo, python_executable=Path("/usr/bin/python3"),
        suite="params", model="kimi-k3",
        base_url="https://example.test/v1", api_key="secret-api-key",
        output_xml=xml,
    )
    assert result["status"] == "finished"
    assert result["report"]["counts"]["pass"] == 1
    assert "secret-api-key" not in json.dumps(result)
    assert len(calls) == 3


def test_unpinned_source_never_executes_pytest(tmp_path, monkeypatch):
    repo = make_official_repo(tmp_path)
    called = []
    def fake_run(args, **kwargs):
        called.append(args)
        return SimpleNamespace(returncode=0, stdout="wrong-commit\n")
    monkeypatch.setattr(kimi_runner.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="not pinned"):
        run_official_subset(
            repo_dir=repo, python_executable=Path("/usr/bin/python3"),
            suite="params", model="kimi-k3", base_url="http://example.test/v1",
            api_key="secret", output_xml=tmp_path / "result.xml",
        )
    assert len(called) == 1


def test_cli_default_preview_never_executes(monkeypatch, tmp_path):
    from model_detect import kimi_cli
    def forbidden(**kwargs):
        raise AssertionError("no execution in preview")
    monkeypatch.setattr(kimi_cli, "run_official_subset", forbidden)
    repo = make_official_repo(tmp_path)
    python = tmp_path / "python"
    python.write_text("placeholder")
    result = CliRunner().invoke(app, [
        "kimi-verifier", "run", "--repo-dir", str(repo),
        "--python-executable", str(python),
        "--suite", "params", "--model", "kimi-k3",
        "--base-url", "https://example.test/v1",
    ])
    assert result.exit_code == 0, result.output
    assert "Preview only" in result.output


def test_dirty_official_checkout_blocks_pytest(tmp_path, monkeypatch):
    repo = make_official_repo(tmp_path)
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        if "rev-parse" in args:
            return SimpleNamespace(returncode=0, stdout=OFFICIAL_COMMIT + "\n")
        if "status" in args:
            return SimpleNamespace(returncode=0, stdout=" M tests/params/test_params.py\n")
        raise AssertionError("must not run dirty verifier tests")
    monkeypatch.setattr(kimi_runner.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="dirty"):
        run_official_subset(
            repo_dir=repo, python_executable=Path("/usr/bin/python3"),
            suite="params", model="kimi-k3",
            base_url="https://example.test/v1", api_key="secret",
            output_xml=tmp_path / "junit.xml",
        )
    assert len(calls) == 2

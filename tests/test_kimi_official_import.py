import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.kimi_official import (
    OFFICIAL_COMMIT, import_official_junit, plan_official_subset,
)


def test_pinned_plan_contains_only_supported_official_suites():
    plan = plan_official_subset(["params", "k3_features", "params"])
    assert plan["source_commit"] == OFFICIAL_COMMIT
    assert [x["name"] for x in plan["suites"]] == ["params", "k3_features"]
    assert plan["estimated_requests"] is None
    with pytest.raises(ValueError):
        plan_official_subset(["imaginary"])


def test_local_junit_import_redacts_case_names_and_failure_messages(tmp_path):
    raw = """<testsuite tests='4'>
      <testcase classname='params' name='temperature_secret_sk-private-test'/>
      <testcase classname='params' name='bad'><failure message='bearer sk-other-secret'/></testcase>
      <testcase classname='params' name='auth'><error message='Authorization: sk-leak'/></testcase>
      <testcase classname='params' name='skip'><skipped/></testcase>
    </testsuite>"""
    path = tmp_path / "report.xml"
    path.write_text(raw, encoding="utf-8")
    imported = import_official_junit(path, suite="params", model="kimi-k3")
    assert imported["counts"] == {"pass": 1, "fail": 1, "error": 1, "skipped": 1}
    assert imported["result"] == "inconclusive"
    text = json.dumps(imported)
    assert "sk-private-test" not in text
    assert "sk-leak" not in text
    assert "sk-other-secret" not in text
    assert imported["evidence_source"] == "user_supplied_unattested_junit"


def test_reject_empty_report_and_xml_entities(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text("<testsuite/>")
    with pytest.raises(ValueError, match="empty"):
        import_official_junit(path, suite="params", model="kimi-k3")
    path.write_text("<!DOCTYPE x [<!ENTITY leak SYSTEM 'file:///etc/passwd'>]><testsuite/>")
    with pytest.raises(ValueError, match="not permitted"):
        import_official_junit(path, suite="params", model="kimi-k3")


def test_cli_import_fails_closed_on_existing_result(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text("<testsuite><testcase classname='x' name='y'/></testsuite>")
    out = tmp_path / "summary.json"
    args = ["kimi-verifier", "import-junit", "--file", str(path),
            "--suite", "params", "--model", "kimi-k3", "--output-file", str(out)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["result"] == "all_cases_passed_in_import"
    assert CliRunner().invoke(app, args).exit_code != 0

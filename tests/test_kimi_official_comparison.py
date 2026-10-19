import json

from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.evaluation_batch_report import (
    compare_kimi_official_protocol_summaries,
    render_comparison_markdown,
)
from model_detect.kimi_official import OFFICIAL_COMMIT


def _summary(path, *, statuses=("pass", "pass"), suite="params"):
    data = {
        "schema": "kimi-official-junit-import-v1",
        "source_commit": OFFICIAL_COMMIT,
        "model": "kimi-k3", "suite": suite,
        "cases": [
            {"testcase_sha256": chr(97+i)*64, "status": status}
            for i, status in enumerate(statuses)
        ],
        "counts": {key: sum(status == key for status in statuses)
                   for key in ("pass", "fail", "error", "skipped")},
    }
    path.write_text(json.dumps({"status": "finished", "report": data}))


def test_official_protocol_comparison_is_separate_from_benchmark_score(tmp_path):
    official, vendor = tmp_path/"official.json", tmp_path/"vendor.json"
    _summary(official)
    _summary(vendor, statuses=("pass", "fail"))
    got = compare_kimi_official_protocol_summaries(official, vendor)
    assert got["status"] == "comparable"
    assert got["newly_failed_cases"] == 1
    assert got["official_source_attested"] is False
    assert got["model_identity_proven"] is False
    doc = render_comparison_markdown({
        "tasks": [], "comparable_tasks": 0, "unknown_or_incompatible_tasks": 0,
        "kimi_official_protocol": got,
    })
    assert "官方端点通过但供应商未通过：1" in doc
    assert "官方协议专项" in doc


def test_protocol_case_set_and_partial_results_fail_closed(tmp_path):
    official, vendor = tmp_path/"official.json", tmp_path/"vendor.json"
    _summary(official)
    _summary(vendor, suite="k3_features")
    assert compare_kimi_official_protocol_summaries(official, vendor)["status"] == "not_comparable"
    _summary(vendor, statuses=("pass", "skipped"))
    assert compare_kimi_official_protocol_summaries(official, vendor)["status"] == "incomplete"
    raw = json.loads(vendor.read_text())
    raw["report"]["cases"][0]["testcase_sha256"] = "x"*64
    vendor.write_text(json.dumps(raw))
    try:
        compare_kimi_official_protocol_summaries(official, vendor)
        assert False, "invalid digest must be rejected"
    except ValueError:
        pass


def test_existing_report_command_supports_protocol_only(tmp_path):
    official, vendor = tmp_path/"official.json", tmp_path/"vendor.json"
    _summary(official)
    _summary(vendor, statuses=("pass", "fail"))
    dest = tmp_path/"output"
    r = CliRunner().invoke(app,[
        "compare-evaluation-dirs", "--kimi-official", str(official),
        "--kimi-vendor",str(vendor),"--output-dir",str(dest),
    ])
    assert r.exit_code == 0, r.output
    assert json.loads((dest/"comparison.json").read_text())["kimi_official_protocol"]["newly_failed_cases"] == 1

import csv
import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.usage_export import export_usage_csv


def test_csv_records_and_unknown_fields_without_prompt(tmp_path):
    source = tmp_path / "report.json"
    source.write_text(json.dumps({
        "adapters": {"token_usage": {"records": [
            {"probe_id": "protocol.basic", "stage": "native", "source": "observed",
             "prompt_tokens": 25, "completion_tokens": 10},
            {"probe_id": "protocol.error", "stage": "native", "source": "unknown",
             "missing_reason": "usage_not_reported"},
        ]}},
        "sensitive_raw_prompt": "sk-do-not-export-1234567",
    }))
    output = tmp_path / "usage.csv"
    result = export_usage_csv(source, output)
    assert result["rows"] == 2
    content = output.read_text(encoding="utf-8-sig")
    assert "sk-do-not-export" not in content
    data = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert data[0]["prompt_tokens"] == "25"
    assert data[1]["source"] == "unknown"
    assert data[1]["prompt_tokens"] == ""
    with pytest.raises(FileExistsError):
        export_usage_csv(source, output)


def test_usage_csv_cli_does_not_reprocess_raw_evidence(tmp_path):
    source = tmp_path / "report.json"
    source.write_text('{"adapters":{"token_usage":{"records":[]}}}')
    output = tmp_path / "out.csv"
    result = CliRunner().invoke(app, ["usage-csv", "--report", str(source),
                                      "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert "rows" in result.output


def test_invalid_record_leaves_no_csv(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('{"adapters":{"token_usage":{"records":[{"probe_id":"x","stage":"y","source":"unknown"}]}}}')
    target = tmp_path / "out.csv"
    with pytest.raises(ValueError):
        export_usage_csv(source, target)
    assert not target.exists()

"""Export only versioned token evidence from an existing local report JSON."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .usage_meter import UsageRecord


_FIELDS = (
    "probe_id", "stage", "attempt", "http_status", "source",
    "prompt_tokens", "completion_tokens", "reasoning_tokens",
    "cached_read_tokens", "cached_write_tokens", "missing_reason",
)


def export_usage_csv(report_path: Path, output_path: Path) -> dict:
    source = Path(report_path)
    target = Path(output_path)
    if source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("report too large")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("report JSON root must be a mapping")
    adapters = data.get("adapters")
    token_usage = adapters.get("token_usage") if isinstance(adapters, dict) else None
    records = token_usage.get("records") if isinstance(token_usage, dict) else None
    if not isinstance(records, list):
        raise ValueError("report has no request usage records")
    validated = [UsageRecord.model_validate(row) for row in records]
    if target.exists() or target.is_symlink():
        raise FileExistsError("output already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDS)
            writer.writeheader()
            for record in validated:
                fields = record.model_dump(mode="json")
                writer.writerow({key: fields.get(key) for key in _FIELDS})
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {
        "rows": len(validated),
        "output": str(target),
        "warning": "Only already recorded native Usage is exported; external tools can be unmetered.",
    }

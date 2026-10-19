"""Zero-API-cost release-candidate handoff check.

Run: python scripts/acceptance_check.py
Only uses temporary files; never reads real API keys or persistent history.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from model_detect.models import AuditReport
from model_detect.reporting import write_report
from model_detect.rules import match_model_rule
from model_detect.storage import JobStore

TARGETS = {
    "glm-5.3": "glm-5.3",
    "glm-5.3-flash": "glm-5.3-flash",
    "kimi-k3": "kimi-k3",
    "deepseek-v4-pro": "deepseek-v4",
    "deepseek-flash": "deepseek-v4.1",
}


def main() -> int:
    checks: dict[str, bool] = {}
    for model, expected_rule in TARGETS.items():
        rule = match_model_rule(model)
        checks[f"model:{model}"] = (
            rule.id == expected_rule and bool(rule.sources) and bool(rule.updated_at)
        )

    with TemporaryDirectory(prefix="model-detect-acceptance-") as directory:
        root = Path(directory)
        store = JobStore(root / "history.sqlite3")
        row = store.create(
            job_id="smoke-audit",
            kind="audit",
            model="kimi-k3",
            base_url="https://test.invalid/v1",
            profile="quick",
        )
        checks["sqlite:create"] = row["status"] == "queued"
        report = AuditReport(
            target={"base_url": "https://test.invalid/v1", "model": "kimi-k3"},
        )
        output = write_report(report, root / "report")
        expected = ("report.html", "report.json")
        checks["report:files"] = all((output / name).is_file() for name in expected)
        document = (output / "report.html").read_text(encoding="utf-8")
        checks["report:html"] = "kimi-k3" in document
        checks["report:secret"] = "sk-not-a-real-key" not in document
        store.finish("smoke-audit", report_path=str(output / "report.html"))
        checks["sqlite:read"] = store.get("smoke-audit")["status"] == "done"
        checks["sqlite:delete"] = store.delete("smoke-audit") is True

    print(json.dumps(
        {"status": "pass" if all(checks.values()) else "fail",
         "checks": checks, "paid_api_calls": 0,
         "note": "Offline software handoff only; NOT a real vendor capability test"},
        ensure_ascii=False, indent=2,
    ))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

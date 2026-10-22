"""Offline v0.2.0 software handoff check (zero paid API calls).

All data lives in a temporary directory. This checks report/verdict semantics,
five model catalog mappings and SQLite history, not live-provider correctness.
Run: python scripts/acceptance_check.py
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from model_detect.models import AuditReport, Evidence, ProbeResult, ProbeStatus
from model_detect.reporting import write_report
from model_detect.rules import match_model_rule
from model_detect.scoring import build_summary
from model_detect.storage import JobStore

TARGETS = {
    "glm-5.3": "glm-5.3",
    "glm-5.3-flash": "glm-5.3-flash",
    "kimi-k3": "kimi-k3",
    "deepseek-v4-pro": "deepseek-v4",
    "deepseek-flash": "deepseek-v4.1",
}

TARGET = {"base_url": "https://test.invalid/v1", "model": "kimi-k3"}


def probe(name: str, status: ProbeStatus, score: float | None) -> ProbeResult:
    return ProbeResult(
        probe_id=name,
        category="protocol" if name.startswith("protocol.") else "identity",
        status=status,
        score=score,
        summary="synthetic offline acceptance fixture",
        evidence_ids=["synthetic-api-reply"] if name == "protocol.chat.basic" else [],
    )


def save_case(root: Path, case: str, results: list[ProbeResult]) -> tuple[dict, str, Path]:
    report = AuditReport(
        target=TARGET,
        profile="quick",
        results=results,
        summary=build_summary(results),
        evidences=[
            Evidence(
                id="synthetic-api-reply",
                probe_id="protocol.chat.basic",
                url="https://test.invalid/v1/chat/completions",
                response_status=200,
                response_headers={"content-type": "application/json"},
                response_body={"choices": [{"message": {"content": "hello"}}]},
            )
        ],
    )
    output = write_report(report, root / case)
    data = json.loads((output / "report.json").read_text(encoding="utf-8"))
    html = (output / "report.html").read_text(encoding="utf-8")
    return data, html, output


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
            base_url=TARGET["base_url"],
            profile="quick",
        )
        checks["sqlite:create"] = row["status"] == "queued"

        # Real statuses, not an empty report: a skipped legacy score must not
        # create fake identity coverage, and no synthetic run certifies identity.
        good = [
            probe("protocol.chat.basic", ProbeStatus.PASS, 1.0),
            probe("protocol.chat.stream", ProbeStatus.PASS, 1.0),
            probe("identity.unrun", ProbeStatus.SKIPPED, 1.0),
        ]
        good_data, good_html, good_output = save_case(root, "pass", good)
        checks["report:files"] = all(
            (good_output / name).is_file() for name in ("report.json", "report.html")
        )
        checks["report:evidence"] = (
            (good_output / "evidence/synthetic-api-reply.json").is_file()
            and "evidence/synthetic-api-reply.json" in good_html
        )
        checks["report:pass_semantics"] = (
            good_data["summary"]["final_verdict"] == "pass"
            and good_data["summary"]["overall_score"] is None
            and good_data["summary"]["category_scores"].get("identity") is None
            and good_data["summary"]["coverage"].get("identity") is False
            and "已完成 2 项" in good_html
            and "未运行/不适用 1 项" in good_html
        )

        errored = [
            probe("protocol.chat.basic", ProbeStatus.PASS, 1.0),
            probe("protocol.chat.stream", ProbeStatus.ERROR, 1.0),
        ]
        error_data, error_html, _ = save_case(root, "error", errored)
        checks["report:error_not_pass"] = (
            error_data["summary"]["final_verdict"] == "insufficient"
            and error_data["summary"]["category_scores"].get("protocol") == 100.0
            and "错误/证据不足 1 项" in error_html
        )

        failed = [
            probe("protocol.chat.basic", ProbeStatus.PASS, 1.0),
            probe("protocol.chat.stream", ProbeStatus.FAIL, 0.0),
        ]
        failure_data, failure_html, _ = save_case(root, "fail", failed)
        checks["report:fail_not_pass"] = (
            failure_data["summary"]["final_verdict"] == "fail"
            and failure_data["summary"]["category_scores"].get("protocol") == 50.0
            and "异常/警告 1 项" in failure_html
        )

        store.finish("smoke-audit", report_path=str(good_output / "report.html"))
        checks["sqlite:read"] = store.get("smoke-audit")["status"] == "done"
        checks["sqlite:delete"] = store.delete("smoke-audit") is True

    print(json.dumps(
        {
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "paid_api_calls": 0,
            "note": "Offline software checks only; no provider accuracy or key-redaction claim",
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

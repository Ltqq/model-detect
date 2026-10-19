"""Offline multi-task benchmark comparison report.

All source snapshots are untrusted local records; they are never treated as
officially attested solely because a provider_role string says 'official'.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .evaluation_snapshots import EvaluationSnapshot, compare_snapshots


def _load_directory(root: Path, *, expected_model: str | None = None) -> dict[str, EvaluationSnapshot]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("snapshot directory not found")
    records: dict[str, EvaluationSnapshot] = {}
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError("invalid snapshot file")
        record = EvaluationSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        if expected_model is not None and record.model != expected_model:
            raise ValueError("artifact model differs from requested model")
        if record.task_id in records:
            raise ValueError("duplicate task in snapshot directory")
        records[record.task_id] = record
    if not records:
        raise ValueError("no evaluation snapshots found")
    return records


def compare_directories(
    official_dir: Path, vendor_dir: Path, *, expected_model: str | None = None,
) -> dict[str, Any]:
    official = _load_directory(official_dir, expected_model=expected_model)
    vendor = _load_directory(vendor_dir, expected_model=expected_model)
    rows: list[dict[str, Any]] = []
    for task in sorted(set(official) | set(vendor)):
        if task not in official or task not in vendor:
            rows.append({
                "task": task, "status": "missing_pair",
                "missing": "official" if task not in official else "vendor",
                "score_delta_vendor_minus_official": None,
            })
            continue
        # Folder names do not establish official identity: require the
        # stored roles to agree with the direction the user selected.
        if official[task].provider_role != "official" or vendor[task].provider_role != "vendor":
            rows.append({
                "task": task, "status": "not_comparable",
                "mismatch_fields": ["provider_role"],
                "score_delta_vendor_minus_official": None,
                "reason": "source_role_mismatch",
            })
            continue
        comparison = compare_snapshots(official[task], vendor[task])
        rows.append({
            "task": task,
            "status": "comparable" if comparison["comparable"] else "not_comparable",
            **comparison,
        })
    return {
        "schema": "evaluation-batch-report-v1",
        "tasks": rows,
        "total_tasks": len(rows),
        "comparable_tasks": sum(row["status"] == "comparable" for row in rows),
        "unknown_or_incompatible_tasks": sum(row["status"] != "comparable" for row in rows),
        "official_provenance_attested": False,
        "model_identity_proven": False,
        "note": "Matching scores cannot establish model identity; snapshots need independent source verification.",
    }


def compare_kimi_official_protocol_summaries(
    official_file: Path, vendor_file: Path, *, expected_model: str | None = None,
) -> dict[str, Any]:
    """Compare the SAME pinned Kimi cases; do not re-score official pytest."""
    from .kimi_report import _validated_summary

    def read(path: Path) -> dict[str, Any]:
        if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("invalid or oversized Kimi summary")
        raw = json.loads(path.read_text(encoding="utf-8"))
        body = raw.get("report") if isinstance(raw, dict) and "report" in raw else raw
        if not isinstance(body, dict) or not isinstance(body.get("model"), str):
            raise ValueError("invalid model in Kimi summary")
        summary = _validated_summary(raw, body["model"], include_case_index=True)
        if expected_model is not None and summary["model"] != expected_model:
            raise ValueError("Kimi protocol model differs from requested model")
        return summary

    official = read(official_file)
    vendor = read(vendor_file)
    same = all(
        official[key] == vendor[key]
        for key in ("model", "suite", "source_commit")
    )
    same_cases = set(official["case_index"]) == set(vendor["case_index"])
    if not same or not same_cases:
        return {
            "status": "not_comparable",
            "reason": "model_suite_source_or_testcase_mismatch",
            "official_source_attested": False,
            "model_identity_proven": False,
        }
    total = len(official["case_index"])
    newly_failed = sum(
        value == "pass" and vendor["case_index"][key] != "pass"
        for key, value in official["case_index"].items()
    )
    incomplete = bool(official["counts"]["error"] or official["counts"]["skipped"] or
                      vendor["counts"]["error"] or vendor["counts"]["skipped"])
    return {
        "status": "incomplete" if incomplete else "comparable",
        "suite": official["suite"], "model": official["model"],
        "source_commit": official["source_commit"],
        "total_cases": total,
        "official_passed": official["counts"]["pass"],
        "vendor_passed": vendor["counts"]["pass"],
        "newly_failed_cases": newly_failed,
        "official_incomplete": bool(official["counts"]["error"] or official["counts"]["skipped"]),
        "vendor_incomplete": bool(vendor["counts"]["error"] or vendor["counts"]["skipped"]),
        "official_source_attested": False,
        "model_identity_proven": False,
        "warning": "Pinned official code is claimed by input summaries, not independently authenticated.",
    }


def render_comparison_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 模型能力基准对照（离线）", "",
        "> 来源快照未经独立认证；同题同参数才允许比较。结果不能证明模型权重身份。", "",
        "| 测试任务 | 状态 | 官方端点成绩 | 供应商成绩 | 供应商减官方 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report["tasks"]:
        if row["status"] == "comparable":
            left = f'{row["official_score"]:.4f}'
            right = f'{row["vendor_score"]:.4f}'
            delta = f'{row["score_delta_vendor_minus_official"]:+.4f}'
            status = "可比（来源未认证）"
            if row.get("ceiling_warning"):
                status += "；区分度不足"
        else:
            left = right = delta = "—"
            status = "缺失配对" if row["status"] == "missing_pair" else "不可比"
        # No user-controlled task labels or raw prompt details in Markdown.
        task = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in str(row["task"]))[:128]
        lines.append(f"| {task} | {status} | {left} | {right} | {delta} |")
    lines += ["", f'可比任务：{report["comparable_tasks"]}；未知或不可比：{report["unknown_or_incompatible_tasks"]}。', ""]
    kimi = report.get("kimi_official_protocol")
    if isinstance(kimi, dict):
        lines += ["", "## Kimi 官方协议专项（与能力分数分开）", ""]
        if kimi.get("status") in {"comparable", "incomplete"}:
            if kimi["status"] == "incomplete":
                lines.append("- 存在执行错误或跳过用例，不能认定完整通过。")
            lines += [
                f'- 套件：{kimi["suite"]}；模型：{kimi["model"]}',
                f'- 同一测试用例数：{kimi["total_cases"]}',
                f'- 官方端点通过：{kimi["official_passed"]}；供应商通过：{kimi["vendor_passed"]}',
                f'- 官方端点通过但供应商未通过：{kimi["newly_failed_cases"]}',
                f'- 不完整测试：官方={kimi["official_incomplete"]}，供应商={kimi["vendor_incomplete"]}',
            ]
        else:
            lines.append("- 不可比：模型、套件、源码版本或测试用例集合不一致")
        lines.append("- 来源未经独立认证；协议通过率不能证明模型权重身份。")
    return "\n".join(lines)


def write_comparison_report(report: dict[str, Any], output_dir: Path) -> None:
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError("report directory already exists; refuse overwrite")
    target.mkdir(parents=True, exist_ok=False)
    (target / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = render_comparison_markdown(report)
    (target / "comparison.md").write_text(markdown, encoding="utf-8")
    # Reuse the already validated Chinese report and HTML-escape every character.
    # A readable offline view, NOT a separate scoring/templating engine.
    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>模型能力对照 · model-detect</title>'
        '<style>body{background:#0b0f14;color:#eaf2f8;font:15px/1.8 system-ui,sans-serif;'
        'margin:auto;max-width:1000px;padding:30px 18px}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'background:#151e28;border:1px solid #263241;padding:24px;border-radius:12px;'
        'font:inherit}p{color:#91abc2}</style></head><body>'
        '<h1>模型能力与官方协议对照</h1>'
        '<p>离线证据；来源未经独立认证；相同分数不等于模型身份相同。</p>'
        '<pre>' + escape(markdown) + '</pre></body></html>'
    )
    (target / "comparison.html").write_text(html, encoding="utf-8")

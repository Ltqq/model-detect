from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .models import AuditReport


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_.")
    return value[:80] or "model"


def write_report(report: AuditReport, output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    data = report.model_dump(mode="json")
    (root / "report.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for evidence in report.evidences:
        (evidence_dir / f"{evidence.id}.json").write_text(
            json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    (root / "report.html").write_text(_render_html(report), encoding="utf-8")
    return root


def _status_class(value: str) -> str:
    return {
        "pass": "ok",
        "warn": "warn",
        "fail": "bad",
        "error": "bad",
        "insufficient": "dim",
        "skipped": "dim",
    }.get(value, "")


def _render_html(report: AuditReport) -> str:
    rows = []
    for result in report.results:
        score = "" if result.score is None else f"{result.score * 100:.0f}"
        evidence = " ".join(
            f'<a href="evidence/{html.escape(eid)}.json">{html.escape(eid)}</a>'
            for eid in result.evidence_ids
        ) or "—"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(result.probe_id)}</code></td>"
            f"<td>{html.escape(result.category)}</td>"
            f'<td class="{_status_class(result.status.value)}">{html.escape(result.status.value)}</td>'
            f"<td>{score}</td>"
            f"<td>{html.escape(result.summary)}</td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )

    providers = "".join(
        f"<li><b>{html.escape(x.provider)}</b> — confidence {x.confidence:.0%}"
        f"<br><small>{html.escape('; '.join(x.evidence[:8]))}</small></li>"
        for x in report.provider_hypotheses
    ) or "<li>No provider fingerprint with enough evidence.</li>"

    categories = "".join(
        f"<div class='metric'><span>{html.escape(k)}</span><b>{v:.1f}</b></div>"
        for k, v in report.summary.category_scores.items()
    )

    warnings = "".join(
        f"<li>{html.escape(x)}</li>" for x in report.summary.warnings
    ) or "<li>None</li>"

    adapter_rows = []
    for name, value in report.adapters.items():
        if isinstance(value, dict):
            compact = {
                k: v for k, v in value.items()
                if k not in {"raw", "stdout_tail"}
            }
        else:
            compact = value
        adapter_rows.append(
            f"<details><summary>{html.escape(name)}</summary><pre>{html.escape(json.dumps(compact, ensure_ascii=False, indent=2, default=str))}</pre></details>"
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>model-detect audit report</title>
<style>
:root{{color-scheme:light dark}}body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1400px;margin:32px auto;padding:0 20px}}
code{{background:rgba(127,127,127,.15);padding:2px 4px;border-radius:4px}}a{{color:#2f81f7}}
table{{width:100%;border-collapse:collapse;margin-top:20px;font-size:13px}}th,td{{border-bottom:1px solid rgba(127,127,127,.28);padding:8px;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:Canvas}}
.card{{border:1px solid rgba(127,127,127,.3);border-radius:10px;padding:16px;margin:16px 0}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}}
.metric{{border:1px solid rgba(127,127,127,.25);border-radius:8px;padding:12px;display:flex;justify-content:space-between}}.ok{{color:#238636;font-weight:700}}.warn{{color:#bf8700;font-weight:700}}.bad{{color:#cf222e;font-weight:700}}.dim{{opacity:.65}}
pre{{white-space:pre-wrap;overflow:auto;background:rgba(127,127,127,.1);padding:12px;border-radius:8px}}small{{opacity:.72}}
</style></head>
<body>
<h1>model-detect Audit Report</h1>
<div class="card">
<b>Model:</b> {html.escape(str(report.target.get("model", "")))}<br>
<b>Base URL:</b> {html.escape(str(report.target.get("base_url", "")))}<br>
<b>Profile:</b> {html.escape(report.profile)}<br>
<b>Verdict:</b> {html.escape(report.summary.final_verdict)}<br>
<b>Overall score:</b> {report.summary.overall_score if report.summary.overall_score is not None else "N/A"}<br>
<b>Hard cap:</b> {report.summary.hard_cap if report.summary.hard_cap is not None else "None"}
</div>
<div class="card"><h2>Category scores</h2><div class="metrics">{categories}</div></div>
<div class="card"><h2>Provider hypotheses</h2><ul>{providers}</ul></div>
<div class="card"><h2>Warnings</h2><ul>{warnings}</ul></div>
<h2>Probe results</h2>
<table><thead><tr><th>Probe</th><th>Category</th><th>Status</th><th>Score</th><th>Summary</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<div class="card"><h2>Adapters / Reference</h2>{''.join(adapter_rows)}</div>
<p><small>Provider identification and black-box model identity checks are evidence-based estimates, not cryptographic proof. Open the linked evidence JSON files to inspect raw, redacted request/response records.</small></p>
</body></html>"""

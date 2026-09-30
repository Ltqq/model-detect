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


def _render_html(report: AuditReport) -> str:
    rows = []
    for result in report.results:
        score = "" if result.score is None else f"{result.score * 100:.0f}"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(result.probe_id)}</code></td>"
            f"<td>{html.escape(result.category)}</td>"
            f"<td>{html.escape(result.status.value)}</td>"
            f"<td>{score}</td>"
            f"<td>{html.escape(result.summary)}</td>"
            "</tr>"
        )

    providers = "".join(
        f"<li><b>{html.escape(x.provider)}</b> — confidence {x.confidence:.0%}"
        f"<br><small>{html.escape('; '.join(x.evidence[:5]))}</small></li>"
        for x in report.provider_hypotheses
    ) or "<li>No provider fingerprint with enough evidence.</li>"

    categories = "".join(
        f"<li>{html.escape(k)}: <b>{v:.1f}</b></li>"
        for k, v in report.summary.category_scores.items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>model-detect audit report</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;color:#1f2328}}
code{{background:#f6f8fa;padding:2px 4px;border-radius:4px}}
table{{width:100%;border-collapse:collapse;margin-top:20px}}
th,td{{border:1px solid #d0d7de;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f6f8fa}}
.card{{border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:16px 0}}
small{{color:#57606a}}
</style>
</head>
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
<div class="card"><h2>Category scores</h2><ul>{categories}</ul></div>
<div class="card"><h2>Provider hypotheses</h2><ul>{providers}</ul></div>
<h2>Probe results</h2>
<table>
<thead><tr><th>Probe</th><th>Category</th><th>Status</th><th>Score</th><th>Summary</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p><small>Provider identification is heuristic evidence, not a cryptographic proof. Raw evidence is stored next to this report.</small></p>
</body>
</html>"""

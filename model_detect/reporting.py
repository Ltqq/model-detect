from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from .models import AuditReport


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_.")
    return value[:80] or "model"


def _portable_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _rewrite_regression_path(
    value: object,
    *,
    source_root: Path,
) -> object:
    if not isinstance(value, str) or not value:
        return value
    try:
        relative = Path(value).resolve().relative_to(source_root.resolve())
    except (OSError, ValueError):
        return value
    return _portable_path(Path("regression") / relative)


def _persist_regression_artifacts(
    report: AuditReport,
    root: Path,
) -> None:
    adapter = report.adapters.get("promptfoo_regression")
    if not isinstance(adapter, dict):
        return

    source_value = adapter.get("artifact_root")
    if not isinstance(source_value, str) or not source_value:
        return
    if source_value == "regression":
        return

    source_root = Path(source_value)
    if not source_root.exists() or not source_root.is_dir():
        return

    destination = root / "regression"
    shutil.copytree(source_root, destination, dirs_exist_ok=True)

    for result in report.results:
        if result.metadata.get("engine") != "promptfoo":
            continue
        artifact_path = result.metadata.get("artifact_path")
        if artifact_path:
            result.metadata["artifact_path"] = _rewrite_regression_path(
                artifact_path,
                source_root=source_root,
            )

    suites = adapter.get("suites")
    if isinstance(suites, list):
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            for key in ("config_path", "output_path"):
                if suite.get(key):
                    suite[key] = _rewrite_regression_path(
                        suite[key],
                        source_root=source_root,
                    )

    adapter["artifact_root"] = "regression"
    adapter["persisted"] = True


def write_report(report: AuditReport, output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    _persist_regression_artifacts(report, root)
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



def _fingerprint_section(report: AuditReport) -> str:
    primary = next(
        (
            r for r in report.results
            if r.probe_id == "identity.fingerprint.reference_compare"
        ),
        None,
    )
    if primary is None or not isinstance(primary.observed, dict):
        return ""

    observed = primary.observed
    cells = observed.get("cells") if isinstance(observed.get("cells"), list) else []
    cell_rows = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        cell_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(cell.get('cellId') or cell.get('cell_id') or ''))}</code></td>"
            f"<td>{html.escape(str(cell.get('jsd', '')))}</td>"
            f"<td>{html.escape(str(cell.get('validA', '')))}</td>"
            f"<td>{html.escape(str(cell.get('validB', '')))}</td>"
            "</tr>"
        )

    target_meta = observed.get("target_fingerprint") if isinstance(observed.get("target_fingerprint"), dict) else {}
    ref_meta = observed.get("reference_fingerprint") if isinstance(observed.get("reference_fingerprint"), dict) else {}
    adapter = observed.get("target_adapter")
    split_half = observed.get("target_split_half_jsd")
    warnings = observed.get("warnings") if isinstance(observed.get("warnings"), list) else []
    warning_html = "".join(f"<li>{html.escape(str(x))}</li>" for x in warnings) or "<li>None</li>"

    reference_info = report.adapters.get("reference")
    reference_source = ""
    if isinstance(reference_info, dict):
        source = reference_info.get("fingerprint_source")
        ref_value = reference_info.get("fingerprint_reference")
        if source or ref_value:
            reference_source = (
                f"<p><b>Reference source:</b> {html.escape(str(source or 'unknown'))}"
                + (f" · {html.escape(str(ref_value))}" if ref_value else "")
                + "</p>"
            )

    table = ""
    if cell_rows:
        table = (
            "<h3>Per-cell JSD</h3>"
            "<table><thead><tr><th>Cell</th><th>JSD</th><th>Target valid</th><th>Reference valid</th></tr></thead>"
            f"<tbody>{''.join(cell_rows)}</tbody></table>"
        )

    return f"""
<div class="card">
<h2>Statistical Fingerprint</h2>
<p><b>Verdict:</b> {html.escape(str(observed.get('verdict', '')))}
 · <b>Mean JSD:</b> {html.escape(str(observed.get('mean_jsd', 'N/A')))}
 · <b>Comparable cells:</b> {html.escape(str(observed.get('comparable_cell_count', 'N/A')))}</p>
<p><b>Split-half JSD:</b> {html.escape(str(split_half if split_half is not None else 'N/A'))}
 · <b>Reasoning adapter:</b> {html.escape(json.dumps(adapter, ensure_ascii=False, default=str))}</p>
{reference_source}
<p><b>Target:</b> {html.escape(str(target_meta.get('model', '')))}
 · protocol {html.escape(str(target_meta.get('protocol', '')))}
 · collected {html.escape(str(target_meta.get('collected_at', '')))}
 · cells {html.escape(str(target_meta.get('cell_count', '')))}</p>
<p><b>Reference:</b> {html.escape(str(ref_meta.get('model', '')))}
 · protocol {html.escape(str(ref_meta.get('protocol', '')))}
 · collected {html.escape(str(ref_meta.get('collected_at', '')))}
 · cells {html.escape(str(ref_meta.get('cell_count', '')))}</p>
<h3>Warnings</h3><ul>{warning_html}</ul>
{table}
</div>"""


def _regression_section(report: AuditReport) -> str:
    results = [
        result
        for result in report.results
        if result.probe_id.startswith("regression.")
    ]
    if not results:
        return ""

    rows: list[str] = []
    for result in results:
        observed = result.observed if isinstance(result.observed, dict) else {}
        runs = observed.get("runs") if isinstance(observed.get("runs"), list) else []
        reason = ""
        output = ""
        if runs:
            first = runs[0] if isinstance(runs[0], dict) else {}
            reason = str(first.get("reason") or "")
            output = str(first.get("output") or "")
        if len(reason) > 500:
            reason = reason[:500] + "…"
        if len(output) > 800:
            output = output[:800] + "…"

        artifact = result.metadata.get("artifact_path")
        artifact_html = "—"
        if isinstance(artifact, str) and artifact.startswith("regression/"):
            escaped = html.escape(artifact)
            artifact_html = f'<a href="{escaped}">{escaped}</a>'

        score = (
            "—"
            if result.score is None
            else f"{result.score * 100:.0f}"
        )
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(result.probe_id)}</code></td>"
            f'<td class="{_status_class(result.status.value)}">'
            f"{html.escape(result.status.value)}</td>"
            f"<td>{score}</td>"
            f"<td>{html.escape(reason) or '—'}</td>"
            f"<td><pre>{html.escape(output) or '—'}</pre></td>"
            f"<td>{artifact_html}</td>"
            "</tr>"
        )

    adapter = report.adapters.get("promptfoo_regression")
    status = (
        adapter.get("status")
        if isinstance(adapter, dict)
        else "unknown"
    )
    return (
        '<div class="card">'
        "<h2>Regression Suites</h2>"
        f"<p><b>Status:</b> {html.escape(str(status))} · "
        f"<b>Cases:</b> {len(results)}</p>"
        "<table><thead><tr>"
        "<th>Case</th><th>Status</th><th>Score</th>"
        "<th>Reason</th><th>Output</th><th>Artifact</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )

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

    fingerprint_section = _fingerprint_section(report)
    regression_section = _regression_section(report)

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
{fingerprint_section}
{regression_section}
<h2>Probe results</h2>
<table><thead><tr><th>Probe</th><th>Category</th><th>Status</th><th>Score</th><th>Summary</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<div class="card"><h2>Adapters / Reference</h2>{''.join(adapter_rows)}</div>
<p><small>Provider identification and black-box model identity checks are evidence-based estimates, not cryptographic proof. Open the linked evidence JSON files to inspect raw, redacted request/response records.</small></p>
</body></html>"""

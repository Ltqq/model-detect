from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from .models import AuditReport
from .interpretation import (
    build_report_interpretation,
    category_label,
    probe_title,
    result_explanation,
    status_label,
)


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
    data["human_interpretation"] = build_report_interpretation(report)
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


def _evidence_links(result) -> str:
    return " ".join(
        f'<a href="evidence/{html.escape(eid)}.json">{html.escape(eid)}</a>'
        for eid in result.evidence_ids
    ) or "—"


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
    rows = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(cell.get('cellId') or cell.get('cell_id') or ''))}</code></td>"
            f"<td>{html.escape(str(cell.get('jsd', '')))}</td>"
            f"<td>{html.escape(str(cell.get('validA', '')))}</td>"
            f"<td>{html.escape(str(cell.get('validB', '')))}</td>"
            "</tr>"
        )

    mean_jsd = observed.get("mean_jsd")
    split_half = observed.get("target_split_half_jsd")
    verdict = observed.get("verdict")
    reference_info = report.adapters.get("reference")
    reference_info = reference_info if isinstance(reference_info, dict) else {}
    reference_source = reference_info.get("fingerprint_source") or "未标记"
    target_meta = observed.get("target_fingerprint") if isinstance(observed.get("target_fingerprint"), dict) else {}
    reference_meta = observed.get("reference_fingerprint") if isinstance(observed.get("reference_fingerprint"), dict) else {}
    explanation = (
        "JSD 越低，目标接口与可信参考的统计行为越接近。"
        "该结果是黑盒统计证据，不是密码学证明。"
    )
    cell_table = ""
    if rows:
        cell_table = (
            "<details><summary>查看每个统计单元的 JSD 明细</summary>"
            "<table><thead><tr><th>测试单元</th><th>JSD</th>"
            "<th>目标有效样本</th><th>参考有效样本</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></details>"
        )

    return f"""
<section class="card" id="fingerprint">
  <div class="section-head">
    <div><div class="eyebrow">强身份依据</div><h2>统计指纹对比</h2></div>
    <span class="pill {_status_class(primary.status.value)}">{html.escape(status_label(primary.status))}</span>
  </div>
  <p class="lead">{html.escape(explanation)}</p>
  <div class="metrics">
    <div class="metric"><span>指纹结论</span><b>{html.escape(str(verdict or '未知'))}</b></div>
    <div class="metric"><span>Mean JSD</span><b>{html.escape(str(mean_jsd if mean_jsd is not None else 'N/A'))}</b></div>
    <div class="metric"><span>自一致性 JSD</span><b>{html.escape(str(split_half if split_half is not None else 'N/A'))}</b></div>
    <div class="metric"><span>可比较单元</span><b>{html.escape(str(observed.get('comparable_cell_count', 'N/A')))}</b></div>
    <div class="metric"><span>Reference 来源</span><b>{html.escape(str(reference_source))}</b></div>
  </div>
  <p class="lead">目标：{html.escape(str(target_meta.get('model') or report.target.get('model','')))} · Reference：{html.escape(str(reference_meta.get('model') or '未标记'))}</p>
  {cell_table}
</section>
"""


def _regression_section(report: AuditReport) -> str:
    results = [r for r in report.results if r.probe_id.startswith("regression.")]
    if not results:
        return ""

    rows = []
    for result in results:
        observed = result.observed if isinstance(result.observed, dict) else {}
        runs = observed.get("runs") if isinstance(observed.get("runs"), list) else []
        reason = ""
        output = ""
        if runs:
            first = runs[0] if isinstance(runs[0], dict) else {}
            reason = str(first.get("reason") or "")
            output = str(first.get("output") or "")
        artifact = result.metadata.get("artifact_path")
        artifact_html = "—"
        if isinstance(artifact, str) and artifact.startswith("regression/"):
            escaped = html.escape(artifact)
            artifact_html = f'<a href="{escaped}">查看原始结果</a>'
        rows.append(
            "<tr>"
            f"<td>{html.escape(probe_title(result.probe_id))}</td>"
            f'<td><span class="pill {_status_class(result.status.value)}">{html.escape(status_label(result.status))}</span></td>'
            f"<td>{html.escape(reason[:400]) or '—'}</td>"
            f"<td><code>{html.escape(output[:500]) or '—'}</code></td>"
            f"<td>{artifact_html}</td>"
            "</tr>"
        )

    return (
        '<section class="card"><div class="section-head"><div>'
        '<div class="eyebrow">可选增强</div><h2>回归规则结果</h2></div></div>'
        '<p class="lead">这些用例用于检查已知协议/参数问题，不作为模型身份的独立证明。</p>'
        '<div class="table-wrap"><table><thead><tr>'
        '<th>规则</th><th>状态</th><th>原因</th><th>输出摘要</th><th>原始结果</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div></section>"
    )


def _render_html(report: AuditReport) -> str:
    human = build_report_interpretation(report)
    tone_class = {
        "good": "hero-good",
        "warn": "hero-warn",
        "bad": "hero-bad",
        "muted": "hero-muted",
    }.get(human["tone"], "hero-muted")

    category_cards = []
    for item in human["categories"]:
        value = item["score"]
        score_text = "未覆盖" if value is None else f"{value:.1f}"
        category_cards.append(
            f"""
            <div class="category-card">
              <div class="category-top"><b>{html.escape(item['label'])}</b><span>{html.escape(score_text)}</span></div>
              <div class="bar"><i style="width:{0 if value is None else max(0,min(100,value))}%"></i></div>
              <p>{html.escape(item['help'])}</p>
            </div>
            """
        )

    identity = human["identity"]
    provider = human["provider"]
    identity_state_label = {
        "match": "已有强身份匹配",
        "mismatch": "强身份不一致",
        "uncertain": "强身份结果不确定",
        "missing": "缺少强身份依据",
    }.get(identity["state"], identity["state"])

    policy_state_label = {
        "violation": "命中禁止上游",
        "clear": "未观察到禁止上游",
        "not_configured": "未配置禁止上游",
    }.get(provider["state"], provider["state"])

    provider_items = []
    for item in provider["hypotheses"]:
        evidence = "；".join(item["evidence"][:4])
        provider_items.append(
            "<div class='provider-row'>"
            f"<div><b>{html.escape(item.get('label') or item['provider'])}</b><small><code>{html.escape(item['provider'])}</code> · {html.escape(evidence)}</small></div>"
            f"<strong>{item['confidence']:.0%}</strong>"
            "</div>"
        )
    providers_html = "".join(provider_items) or "<div class='empty'>未观察到足够明确的 Provider / Gateway 指纹。</div>"

    issues_html = []
    for item in human["issues"]:
        action = (
            f"<div class='action-line'>建议：{html.escape(item['action'])}</div>"
            if item.get("action") else ""
        )
        evidence = " ".join(
            f'<a href="evidence/{html.escape(eid)}.json">{html.escape(eid)}</a>'
            for eid in item["evidence_ids"]
        ) or "—"
        issues_html.append(
            f"""
            <div class="issue {html.escape(item['status'])}">
              <div class="issue-main">
                <div><span class="pill {_status_class(item['status'])}">{html.escape(item['status_label'])}</span>
                <b>{html.escape(item['title'])}</b>
                <span class="muted">{html.escape(item['category'])}</span></div>
                <p>{html.escape(item['explanation'])}</p>
                <details><summary>技术原因</summary><div class="tech">{html.escape(item['technical_summary'])}</div><div class="evidence-line">Evidence：{evidence}</div></details>
                {action}
              </div>
            </div>
            """
        )
    if not issues_html:
        issues_html.append("<div class='empty good-text'>没有需要优先处理的异常项。</div>")

    actions_html = "".join(
        f"<li>{html.escape(action)}</li>" for action in human["actions"]
    )

    result_rows = []
    for result in report.results:
        score = "—" if result.score is None else f"{result.score * 100:.0f}"
        result_rows.append(
            f"""
            <tr data-status="{html.escape(result.status.value)}">
              <td><b>{html.escape(probe_title(result.probe_id))}</b><small><code>{html.escape(result.probe_id)}</code></small></td>
              <td>{html.escape(category_label(result.category))}</td>
              <td><span class="pill {_status_class(result.status.value)}">{html.escape(status_label(result.status))}</span></td>
              <td>{score}</td>
              <td>{html.escape(result_explanation(result))}<small>{html.escape(result.summary)}</small></td>
              <td>{_evidence_links(result)}</td>
            </tr>
            """
        )

    adapter_rows = []
    for name, value in report.adapters.items():
        compact = value
        if isinstance(value, dict):
            compact = {k: v for k, v in value.items() if k not in {"raw", "stdout_tail"}}
        adapter_rows.append(
            f"<details><summary>{html.escape(name)}</summary><pre>{html.escape(json.dumps(compact, ensure_ascii=False, indent=2, default=str))}</pre></details>"
        )

    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in human["limitations"]
    )
    score_text = "N/A" if human["score"] is None else str(human["score"])
    hard_cap = "无" if human["hard_cap"] is None else str(human["hard_cap"])
    model = html.escape(str(report.target.get("model", "")))
    base_url = html.escape(str(report.target.get("base_url", "")))
    fingerprint_section = _fingerprint_section(report)
    regression_section = _regression_section(report)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{model} · 模型渠道审计报告</title>
<style>
:root{{--bg:#0b0f14;--panel:#111820;--panel2:#151e28;--border:#263241;--text:#eaf2f8;--muted:#8fa2b5;--blue:#58a6ff;--green:#3fb950;--yellow:#d29922;--red:#f85149;--purple:#bc8cff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.55}}
a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
.wrap{{max-width:1240px;margin:auto;padding:28px 20px 80px}}.topbar{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}}.topbar h1{{margin:2px 0 4px;font-size:26px}}.subtitle{{color:var(--muted);font-size:13px}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:20px;margin:16px 0;box-shadow:0 8px 24px rgba(0,0,0,.12)}}.hero{{padding:24px;border-width:1px}}.hero-good{{border-color:rgba(63,185,80,.5)}}.hero-warn{{border-color:rgba(210,153,34,.55)}}.hero-bad{{border-color:rgba(248,81,73,.55)}}.hero-muted{{border-color:var(--border)}}
.hero-grid{{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:22px;align-items:center}}.decision{{font-size:14px;color:var(--muted)}}.decision strong{{display:block;font-size:30px;color:var(--text);margin:4px 0 8px}}.headline{{font-size:16px;margin:0;max-width:760px}}.scorebox{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.scorebox .metric{{background:var(--panel2)}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:14px}}.metric{{border:1px solid var(--border);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:3px}}.metric span{{font-size:12px;color:var(--muted)}}.metric b{{font-size:18px}}
.section-head{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:8px}}h2{{font-size:19px;margin:0}}.eyebrow{{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--blue);margin-bottom:3px}}.lead{{color:var(--muted);margin:7px 0 14px}}
.quick-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.quick-card{{background:var(--panel2);border:1px solid var(--border);border-radius:11px;padding:14px}}.quick-card small{{display:block;color:var(--muted);margin-bottom:5px}}.quick-card b{{font-size:16px}}.quick-card p{{font-size:13px;color:var(--muted);margin:7px 0 0}}
.category-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.category-card{{background:var(--panel2);border:1px solid var(--border);border-radius:11px;padding:14px}}.category-top{{display:flex;justify-content:space-between;gap:8px}}.category-top span{{font-weight:700}}.category-card p{{color:var(--muted);font-size:12px;margin:9px 0 0}}.bar{{height:5px;background:#202b36;border-radius:99px;overflow:hidden;margin-top:9px}}.bar i{{height:100%;display:block;background:var(--blue)}}
.pill{{display:inline-flex;align-items:center;border-radius:99px;padding:3px 8px;font-size:12px;font-weight:700;background:#202b36;margin-right:6px}}.ok{{color:var(--green)}}.warn{{color:var(--yellow)}}.bad{{color:var(--red)}}.dim{{color:var(--muted)}}
.issue{{border-top:1px solid var(--border);padding:14px 0}}.issue:first-of-type{{border-top:0}}.issue p{{margin:7px 0;color:#d5e0ea}}.action-line{{margin-top:8px;padding:8px 10px;border-left:3px solid var(--blue);background:rgba(88,166,255,.07);font-size:13px}}.tech{{color:var(--muted);font-size:13px;margin-top:8px}}.evidence-line{{font-size:12px;margin-top:5px}}
.provider-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:10px 0;border-top:1px solid var(--border)}}.provider-row:first-child{{border-top:0}}.provider-row small{{display:block;color:var(--muted);margin-top:3px;max-width:760px}}.provider-row strong{{font-size:16px}}
.actions li,.limits li{{margin:7px 0}}.empty{{padding:14px;border:1px dashed var(--border);border-radius:10px;color:var(--muted)}}.good-text{{color:var(--green)}}.muted{{color:var(--muted);font-size:12px}}
.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}}th{{color:var(--muted);font-weight:600;white-space:nowrap}}td small{{display:block;color:var(--muted);margin-top:4px;max-width:520px}}pre{{white-space:pre-wrap;overflow:auto;background:#0a0f14;border:1px solid var(--border);padding:12px;border-radius:9px;font-size:12px}}
details{{margin:7px 0}}summary{{cursor:pointer;color:var(--blue)}}.filter-row{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}button{{border:1px solid var(--border);background:var(--panel2);color:var(--text);border-radius:8px;padding:7px 11px;cursor:pointer}}button:hover{{border-color:var(--blue)}}
.notice{{padding:12px 14px;background:rgba(210,153,34,.08);border:1px solid rgba(210,153,34,.25);border-radius:10px;color:#e5c07b;font-size:13px}}
@media(max-width:900px){{.hero-grid{{grid-template-columns:1fr}}.quick-grid,.category-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:620px){{.quick-grid,.category-grid{{grid-template-columns:1fr}}.wrap{{padding:18px 12px 60px}}}}
</style>
</head>
<body><div class="wrap">
<div class="topbar">
  <div><div class="eyebrow">model-detect</div><h1>模型渠道审计报告</h1><div class="subtitle">{model} · {base_url} · {html.escape(report.profile.upper())}</div></div>
  <div><a href="/">← 返回检测首页</a></div>
</div>

<section class="card hero {tone_class}">
  <div class="hero-grid">
    <div>
      <div class="decision">准入建议<strong>{html.escape(human['decision'])}</strong></div>
      <p class="headline" id="human-headline">{html.escape(human['headline'])}</p>
      <div style="margin-top:12px"><button onclick="copyConclusion()">复制结论</button></div>
      <div class="notice" style="margin-top:14px">综合分数是审计评分，不是“模型为真”的概率。模型真假优先看“模型身份”与 Trusted Reference / Statistical Fingerprint。</div>
    </div>
    <div class="scorebox">
      <div class="metric"><span>综合分</span><b>{html.escape(score_text)}</b></div>
      <div class="metric"><span>证据可信度</span><b>{html.escape(human['confidence_label'])}</b></div>
      <div class="metric"><span>系统 Verdict</span><b>{html.escape(human['verdict_label'])}</b></div>
      <div class="metric"><span>分数硬上限</span><b>{html.escape(hard_cap)}</b></div>
    </div>
  </div>
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">先看这里</div><h2>这次结果怎么理解</h2></div></div>
  <div class="quick-grid">
    <div class="quick-card"><small>模型身份</small><b>{html.escape(identity_state_label)}</b><p>{html.escape(identity['text'])}</p></div>
    <div class="quick-card"><small>禁止上游策略</small><b>{html.escape(policy_state_label)}</b><p>{html.escape(provider['text'])}</p></div>
    <div class="quick-card"><small>429 限流</small><b>{provider['http_429_count']} 次</b><p>429 只表示限流，本工具不会用 429 单独判断 Fireworks 或其他上游。</p></div>
  </div>
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">六大维度</div><h2>检测覆盖与得分</h2></div></div>
  <div class="category-grid">{''.join(category_cards)}</div>
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">优先处理</div><h2>风险与异常解读</h2></div><span class="muted">最多展示 12 项</span></div>
  {''.join(issues_html)}
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">上游可观测证据</div><h2>Provider / Gateway 指纹</h2></div></div>
  <p class="lead">{html.escape(provider['text'])}</p>
  <div class="metrics">
    <div class="metric"><span>禁止列表</span><b>{html.escape(', '.join(provider['disallowed']) or '未配置')}</b></div>
    <div class="metric"><span>策略状态</span><b>{html.escape(policy_state_label)}</b></div>
    <div class="metric"><span>本轮 429</span><b>{provider['http_429_count']}</b></div>
  </div>
  <div style="margin-top:10px">{providers_html}</div>
</section>

{fingerprint_section}

<section class="card">
  <div class="section-head"><div><div class="eyebrow">下一步</div><h2>建议怎么处理</h2></div></div>
  <ol class="actions">{actions_html}</ol>
</section>

{regression_section}

<section class="card" id="all-results">
  <div class="section-head"><div><div class="eyebrow">技术明细</div><h2>全部检测项</h2></div><span class="muted">普通使用只需看上面的中文结论</span></div>
  <div class="filter-row">
    <button onclick="filterRows('important')">只看异常</button>
    <button onclick="filterRows('fail')">只看失败</button>
    <button onclick="filterRows('all')">全部</button>
  </div>
  <div class="table-wrap"><table id="probe-table"><thead><tr><th>检测项</th><th>维度</th><th>状态</th><th>分数</th><th>解读 / 技术摘要</th><th>证据</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table></div>
</section>

<section class="card">
  <details><summary>高级：Adapters / Reference / 原始配置</summary>{''.join(adapter_rows)}</details>
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">边界说明</div><h2>这份报告不能证明什么</h2></div></div>
  <ul class="limits">{limitations}</ul>
</section>

<script>
function copyConclusion(){{
  const text='准入建议：{html.escape(human["decision"])}\n结论：{html.escape(human["headline"])}\n综合分：{html.escape(score_text)}\n证据可信度：{html.escape(human["confidence_label"])}';
  navigator.clipboard?.writeText(text).then(()=>alert('结论已复制')).catch(()=>{{}});
}}
function filterRows(mode){{
  document.querySelectorAll('#probe-table tbody tr').forEach(row=>{{
    const s=row.dataset.status;
    const show=mode==='all'||(mode==='important'&&['fail','warn','error','insufficient'].includes(s))||(mode==='fail'&&['fail','error'].includes(s));
    row.style.display=show?'':'none';
  }});
}}
</script>
</div></body></html>"""

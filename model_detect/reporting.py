from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from importlib.resources import files

import yaml

from .models import AuditReport, ProbeStatus
from .rules import match_model_rule
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


def _kimi_official_section(report: AuditReport) -> str:
    item = report.adapters.get("kimi_official_verifier")
    if not isinstance(item, dict):
        return ""
    counts = item.get("counts") or {}
    if not isinstance(counts, dict):
        return ""
    rows = "".join(
        "<tr><td>" + html.escape(label) + "</td><td>" +
        html.escape(str(counts.get(name, "未知"))) + "</td></tr>"
        for name, label in (
            ("pass", "通过"), ("fail", "失败"),
            ("error", "异常"), ("skipped", "跳过"),
        )
    )
    return (
        '<section class="card"><h2>Kimi 官方验证器专项（独立证据）</h2>'
        '<p>本节是外部 JUnit 文件的脱敏导入，尚未核实实际执行来源。'
        '测试通过不等于证明模型身份，不参与综合评分。</p>'
        '<p>套件：' + html.escape(str(item.get("suite") or "")) +
        '　来源版本：' + html.escape(str(item.get("source_commit") or "")) +
        '　结论：' + html.escape(str(item.get("result") or "inconclusive")) +
        '</p><table><tbody>' + rows + '</tbody></table></section>'
    )


def _usage_cost_section(report: AuditReport) -> str:
    meter = report.adapters.get("token_usage") or {}
    usage = meter.get("summary") if isinstance(meter, dict) else None
    if not isinstance(usage, dict):
        return ""
    external = report.adapters.get("external_token_usage") or {}
    external_count = (external.get("unknown_usage_adapters")
                      if isinstance(external, dict) else None)
    price = report.adapters.get("token_cost") or {}
    price = price if isinstance(price, dict) else {}
    labels = [
        ("记录请求数", usage.get("requests")),
        ("观察到 Usage 的请求", usage.get("observed_requests")),
        ("缺失 Usage 的请求", usage.get("unknown_requests")),
        ("已观察输入 Token", usage.get("prompt_tokens_observed")),
        ("已观察输出 Token", usage.get("completion_tokens_observed")),
        ("缓存读（输入子项）", usage.get("cached_read_tokens_subset")),
        ("推理 Token（输出子项）", usage.get("reasoning_tokens_subset")),
        ("计费状态", price.get("status", "unconfigured")),
        ("部分计费金额", price.get("partial_amount")),
        ("费用未知请求数", price.get("unknown_cost_requests")),
        ("外部工具无法计量的适配器数", external_count),
    ]
    rows = "".join(
        "<tr><td>" + html.escape(label) + "</td><td>" +
        html.escape(str(value if value is not None else "未知")) +
        "</td></tr>" for label, value in labels
    )
    return (
        '<section class="card"><h2>Token 与费用</h2>'
        '<p>仅统计已观察到的 Usage。缓存和推理 Token 是子项，'
        '不应重复计入总量。缺失 Usage 或第三方工具用量不等于零。</p>'
        '<table><tbody>' + rows + '</tbody></table></section>'
    )


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
    <div><div class="eyebrow">行为参考信号</div><h2>统计指纹对比</h2></div>
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


def _quality_section(quality: dict) -> str:
    if quality.get("state") == "not_configured":
        return ""

    rows = []
    verdict_labels = {
        "match": ("基准范围内", "ok"),
        "regression": ("明显退化", "bad"),
        "informational": ("仅供参考", "dim"),
        "incomparable": ("条件不一致·不可比", "warn"),
    }
    for item in quality.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "informational")
        verdict_label, verdict_class = verdict_labels.get(
            verdict, (verdict, "dim")
        )
        baseline = item.get("baseline_mean")
        target = item.get("target_score")
        retention = item.get("retention_ratio")
        lower = item.get("lower_bound")
        stddev = item.get("baseline_stddev")
        rows.append(
            "<tr>"
            f"<td><b>{html.escape(str(item.get('label') or item.get('id') or ''))}</b></td>"
            f"<td>{'—' if baseline is None else f'{float(baseline)*100:.1f}%'}"
            f"<small>{int(item.get('baseline_runs') or 0)} 次基准"
            + (
                f" · σ={float(stddev)*100:.1f}%"
                if stddev is not None else ""
            )
            + "</small></td>"
            f"<td>{'—' if target is None else f'{float(target)*100:.1f}%'}</td>"
            f"<td>{'—' if retention is None else f'{float(retention)*100:.1f}%'}</td>"
            f"<td>{'—' if lower is None else f'{float(lower)*100:.1f}%'}</td>"
            f'<td><span class="pill {verdict_class}">{html.escape(verdict_label)}</span></td>'
            f"<td><small>{html.escape(str(item.get('explanation') or ''))}</small></td>"
            "</tr>"
        )

    incomparable = list(quality.get("incomparable_dimensions") or [])
    incompatible_notice = (
        '<div class="notice">不可比维度：'
        + html.escape("、".join(incomparable))
        + "。这些维度没有用于判定质量正常或退化。</div>"
        if incomparable else ""
    )
    rows_html = "".join(rows)
    if not rows_html:
        rows_html = (
            '<tr><td colspan="7" class="muted">没有可比较的同套件质量维度。</td></tr>'
        )

    state = quality.get("state")
    state_class = {
        "match": "ok",
        "regression": "bad",
        "insufficient": "warn",
    }.get(state, "dim")
    return f"""
<section class="card" id="quality-baseline">
  <div class="section-head">
    <div><div class="eyebrow">Official Baseline</div><h2>官方 / 可信基准质量对比</h2></div>
    <span class="pill {state_class}">{html.escape(str(quality.get('label') or ''))}</span>
  </div>
  <p class="lead">{html.escape(str(quality.get('text') or ''))}</p>
  {incompatible_notice}
  <div class="notice">
    这里比较的是 model-detect 用同一套 Suite 对官方 / 可信端点和当前渠道的实际测量。
    “质量退化”不能单独证明具体量化格式、蒸馏方式、GPU 或 Serving Engine。
  </div>
  <div class="metrics">
    <div class="metric"><span>基准重复次数</span><b>{int(quality.get('baseline_runs') or 0)}</b></div>
    <div class="metric"><span>可比较维度</span><b>{int(quality.get('comparable_dimensions') or 0)}</b></div>
    <div class="metric"><span>可估计波动维度</span><b>{int(quality.get('statistically_evaluable_dimensions') or 0)}</b></div>
    <div class="metric"><span>Suite</span><b>{html.escape(str(quality.get('suite_version') or '—'))}</b></div>
  </div>
  <div class="table-wrap" style="margin-top:14px"><table>
    <thead><tr><th>能力维度</th><th>可信基准</th><th>当前渠道</th><th>保持率</th><th>基准下界</th><th>判断</th><th>说明</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table></div>
</section>
"""



def _public_published_benchmarks_section(model_id: str) -> str:
    """Render sourced published aggregates as background, never comparisons."""
    path = files("model_detect").joinpath("data/public_benchmarks.yaml")
    try:
        catalog = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return ""
    rule_id = match_model_rule(model_id).id
    entries = [
        item for item in (catalog.get("entries") or [])
        if isinstance(item, dict)
        and item.get("model") == rule_id
        and item.get("evidence_type") == "official_published_aggregate"
        and item.get("comparison_status") == "background_only"
    ]
    if not entries:
        return ""
    rows = []
    for item in entries:
        source = item.get("source") or {}
        raw_url = str(source.get("url") or "")
        if not raw_url.startswith("https://"):
            continue
        conditions = item.get("conditions") or {}
        label = html.escape(str(item.get("benchmark") or "未知任务"))
        variant = html.escape(str(item.get("model_variant") or ""))
        points = html.escape(str(item.get("value") if item.get("value") is not None else "—"))
        effort = html.escape(str(conditions.get("effort") or "未知"))
        publisher = html.escape(str(source.get("publisher") or "未知"))
        when = html.escape(str(source.get("retrieved_at") or "未知"))
        href = html.escape(raw_url, quote=True)
        rows.append(
            f"<tr><td>{label}</td><td>{variant}</td><td>{points}</td>"
            f"<td>{effort}</td><td><a href='{href}'>{publisher}</a>"
            f"<small>采集：{when}</small></td></tr>"
        )
    if not rows:
        return ""
    return (
        "<section class='card'><div class='section-head'><h2>官方已发布成绩 · 仅背景参考</h2></div>"
        "<p class='notice'>下表来自官方公开材料，不是本次 API 实测；"
        "数据集、样本、提示词和评分器可能不同，不能直接与本次分数相减，"
        "不能据此认定模型身份或渠道质量达标。</p>"
        "<div class='table-wrap'><table><thead><tr>"
        "<th>任务</th><th>官方模型配置</th><th>公布分数</th>"
        "<th>思考档位</th><th>出处</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div></section>"
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
        category_results = [r for r in report.results if r.category == item["id"]]
        observed = sum(r.status not in {ProbeStatus.SKIPPED} for r in category_results)
        abnormal = sum(
            r.status in {ProbeStatus.FAIL, ProbeStatus.WARN, ProbeStatus.ERROR,
                         ProbeStatus.INSUFFICIENT}
            for r in category_results
        )
        coverage_text = f"已测 {observed} 项 · 异常/不确定 {abnormal} 项" if observed else "本次未覆盖"
        category_cards.append(
            f"""
            <div class="category-card">
              <div class="category-top"><b>{html.escape(item['label'])}</b><span>{html.escape(coverage_text)}</span></div>
              <p>{html.escape(item['help'])}</p>
            </div>
            """
        )

    identity = human["identity"]
    provider = human["provider"]
    quality = human["quality"]
    identity_state_label = {
        "behavioral_match": "行为指纹与参考接近",
        "behavioral_mismatch": "行为指纹与参考有差异",
        "behavioral_uncertain": "行为指纹结果不确定",
        "insufficient": "指纹证据不足",
        "missing": "未运行可用的参考对比",
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
            "<strong>响应头线索</strong>"
            "</div>"
        )
    providers_html = "".join(provider_items) or "<div class='empty'>未观察到足够明确的 Provider / Gateway 指纹。</div>"

    blocked_items = []
    for item in provider["detected"]:
        signals = []
        for ev in item.get("evidence") or []:
            for signal in ev.get("signals") or []:
                signals.append(
                    f"{signal.get('kind')}:{signal.get('value')}"
                )
        blocked_items.append(
            "<div class='issue fail'>"
            f"<b>{html.escape(str(item.get('provider') or 'unknown'))}</b>"
            "<p>配置的响应头规则匹配；该线索不是模型权重身份认证，也不是统计概率。</p>"
            f"<div class='tech'>命中信号：{html.escape('；'.join(signals[:12]) or '未列出')}</div>"
            "</div>"
        )
    blocked_html = "".join(blocked_items)

    issues_html = []
    deferred = []
    for item in human["issues"]:
        # Lack of a reference / unrun Quick-only checks is not an API defect.
        if item["status"] == "insufficient":
            deferred.append(item)
            continue
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
        issues_html.append("<div class='empty good-text'>没有需要优先处理的明确失败或警告项。</div>")
    if deferred:
        deferred_lines = "".join(
            f"<li>{html.escape(item['title'])}：{html.escape(item['technical_summary'])}</li>"
            for item in deferred
        )
        issues_html.append(
            f"<details class='uncertain-list'><summary>另有 {len(deferred)} 项证据不足（非模型失败）</summary>"
            f"<ul>{deferred_lines}</ul></details>"
        )

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
    usage_cost_section = _usage_cost_section(report)
    kimi_official_section = _kimi_official_section(report)
    quality_section = _quality_section(quality)
    public_benchmarks_section = _public_published_benchmarks_section(str(report.target.get('model', '')))
    regression_section = _regression_section(report)
    copy_text_json = json.dumps(
        "准入建议：" + str(human["decision"]) + "\n"
        + "结论：" + str(human["headline"]) + "\n"
        + "模型身份：未经独立认证，需结合逐项证据复核\n"
        + "质量基准：" + str(quality.get("label") or "未配置"),
        ensure_ascii=False,
    )

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
.quick-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.quick-card{{background:var(--panel2);border:1px solid var(--border);border-radius:11px;padding:14px}}.quick-card small{{display:block;color:var(--muted);margin-bottom:5px}}.quick-card b{{font-size:16px}}.quick-card p{{font-size:13px;color:var(--muted);margin:7px 0 0}}
.category-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.category-card{{background:var(--panel2);border:1px solid var(--border);border-radius:11px;padding:14px}}.category-top{{display:flex;justify-content:space-between;gap:8px}}.category-top span{{font-weight:700}}.category-card p{{color:var(--muted);font-size:12px;margin:9px 0 0}}.bar{{height:5px;background:#202b36;border-radius:99px;overflow:hidden;margin-top:9px}}.bar i{{height:100%;display:block;background:var(--blue)}}
.pill{{display:inline-flex;align-items:center;border-radius:99px;padding:3px 8px;font-size:12px;font-weight:700;background:#202b36;margin-right:6px}}.ok{{color:var(--green)}}.warn{{color:var(--yellow)}}.bad{{color:var(--red)}}.dim{{color:var(--muted)}}
.issue{{border-top:1px solid var(--border);padding:14px 0}}.issue:first-of-type{{border-top:0}}.issue p{{margin:7px 0;color:#d5e0ea}}.action-line{{margin-top:8px;padding:8px 10px;border-left:3px solid var(--blue);background:rgba(88,166,255,.07);font-size:13px}}.tech{{color:var(--muted);font-size:13px;margin-top:8px}}.evidence-line{{font-size:12px;margin-top:5px}}
.provider-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:10px 0;border-top:1px solid var(--border)}}.provider-row:first-child{{border-top:0}}.provider-row small{{display:block;color:var(--muted);margin-top:3px;max-width:760px}}.provider-row strong{{font-size:16px}}
.actions li,.limits li{{margin:7px 0}}.empty{{padding:14px;border:1px dashed var(--border);border-radius:10px;color:var(--muted)}}.good-text{{color:var(--green)}}.muted{{color:var(--muted);font-size:12px}}
.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}}th{{color:var(--muted);font-weight:600;white-space:nowrap}}td small{{display:block;color:var(--muted);margin-top:4px;max-width:520px}}pre{{white-space:pre-wrap;overflow:auto;background:#0a0f14;border:1px solid var(--border);padding:12px;border-radius:9px;font-size:12px}}
details{{margin:7px 0}}summary{{cursor:pointer;color:var(--blue)}}.filter-row{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}button{{border:1px solid var(--border);background:var(--panel2);color:var(--text);border-radius:8px;padding:7px 11px;cursor:pointer}}button:hover{{border-color:var(--blue)}}
.notice{{padding:12px 14px;background:rgba(210,153,34,.08);border:1px solid rgba(210,153,34,.25);border-radius:10px;color:#e5c07b;font-size:13px}}
@media(max-width:900px){{.hero-grid{{grid-template-columns:1fr}}.quick-grid,.category-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:620px){{.quick-grid,.category-grid{{grid-template-columns:1fr}}.wrap{{padding:18px 12px 60px}}}}

/* V2 report: evidence-first hierarchy and restrained editorial layout. */
:root{{--bg:#f5f7fb;--panel:#fff;--panel2:#f8fafc;--border:#e3e8f0;--text:#182234;--muted:#69778b;--blue:#385fe7;--green:#12845b;--yellow:#a96b10;--red:#c73f48;--purple:#7258cc}}
body{{background:radial-gradient(ellipse at 12% 0%,#eaf0ff,transparent 42%),var(--bg);font-size:14px;line-height:1.62}}
.wrap{{max-width:1100px;padding:39px 24px 82px}}
.topbar{{margin-bottom:22px;align-items:center}}.topbar h1{{font-size:30px;letter-spacing:-.6px}}
.report-links{{display:flex;gap:19px;flex-shrink:0;font-size:13px}}
.card{{border-radius:17px;padding:24px 27px;box-shadow:0 12px 45px rgba(29,51,96,.035);margin:16px 0}}
.hero{{border-color:#d9e2fd!important;padding:29px;box-shadow:0 16px 65px rgba(56,95,231,.07)}}
.hero-grid{{grid-template-columns:minmax(0,1fr) 260px;gap:25px}}
.decision strong{{font-size:32px;letter-spacing:-.5px}}
.headline{{color:#40506a;line-height:1.65}}
.scorebox{{gap:9px}}.scorebox .metric{{padding:12px;background:#f8faff}}
.metric{{border-radius:11px}}.metric b{{font-size:19px}}
.notice{{background:#f0f4ff!important;color:#4b6392!important;border:1px solid #dae4ff!important;border-radius:9px;padding:11px 13px}}
h2{{font-size:20px;letter-spacing:-.4px}}.section-head{{margin-bottom:13px}}
.eyebrow{{color:var(--blue)}}.issue{{padding:16px 0}}.issue p{{color:#465670}}
.pill{{background:#f0f3f8;color:#45566e}}.pill.ok{{background:#eaf8f1;color:#11724b}}.pill.warn{{background:#fff6e5;color:#9b6511}}.pill.bad{{background:#ffeded;color:#b93b41}}.pill.dim{{color:#65768b}}
.action-line{{background:#f0f4ff;border-left-color:#6687ed;color:#405777}}
.issue details>summary{{color:#4264a5;font-size:12px;cursor:pointer}}
.report-optional{{padding:17px 23px;box-shadow:none}}
.report-optional>summary{{cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:12px;align-items:center;color:#34445d;font-size:14px;font-weight:730}}
.report-optional>summary:after{{content:"⌄";font-size:17px;color:#8492a5}}
.report-optional[open]>summary:after{{content:"⌃"}}
.report-optional>summary .muted{{font-weight:400;font-size:12px}}
.report-optional>.quick-grid,.report-optional>.section-head,.report-optional>.lead,.report-optional>.metrics,.report-optional>.filter-row,.report-optional>.table-wrap,.report-optional>.optional-body{{margin-top:18px}}
.report-optional .card{{border:0;box-shadow:none;border-radius:11px;background:#f7f9fc;padding:18px;margin:12px 0}}
.uncertain-list{{border-top:1px solid var(--border);margin-top:14px;padding-top:14px;color:var(--muted);font-size:13px}}
.uncertain-list>summary{{cursor:pointer;font-weight:650;color:#53647b}}
.uncertain-list li{{padding:4px 0}}.empty{{background:#f9fbfe}}
.table-wrap{{overflow:auto;border:1px solid var(--border);border-radius:10px}}th{{background:#f8fafc}}
th,td{{padding:12px}}.quick-card,.category-card{{background:#f7f9fc}}
button{{background:#385fe7!important;color:#fff!important;border-radius:9px;font-size:13px}}
@media(max-width:820px){{.wrap{{padding:21px 12px 45px}}.card{{padding:17px}}.hero-grid{{grid-template-columns:1fr}}.quick-grid{{grid-template-columns:1fr 1fr}}.category-grid{{grid-template-columns:1fr}}.report-links{{flex-direction:column;gap:5px}}}}
</style>
</head>
<body><div class="wrap">
<div class="topbar">
  <div><div class="eyebrow">MODEL DETECT / AUDIT</div><h1>模型接口检测报告</h1><div class="subtitle">{model} · {base_url} · {html.escape(report.profile.upper())}</div></div>
  <div class="report-links"><a href="/">← 返回检测</a><a href="#all-results">查看明细</a></div>
</div>

<section class="card hero {tone_class}">
  <div class="hero-grid">
    <div>
      <div class="decision">本次检测结论<strong>{html.escape(human['decision'])}</strong></div>
      <p class="headline" id="human-headline">{html.escape(human['headline'])}</p>
      <div style="margin-top:12px"><button onclick="copyConclusion()">复制结论</button></div>
      <div class="notice" style="margin-top:14px">此次报告根据实际执行项形成结论。未运行的能力测试、缺少 Reference、输出预算截断均不等于模型失败；协议通过也不证明模型权重身份。</div>
    </div>
    <div class="scorebox">
      <div class="metric"><span>通过检查项</span><b>{sum(r.status == ProbeStatus.PASS for r in report.results)}</b></div>
      <div class="metric"><span>失败检查项</span><b>{sum(r.status == ProbeStatus.FAIL for r in report.results)}</b></div>
      <div class="metric"><span>执行错误</span><b>{sum(r.status == ProbeStatus.ERROR for r in report.results)}</b></div>
      <div class="metric"><span>模型身份</span><b>未独立认证</b></div>
    </div>
  </div>
</section>

<details class="card report-optional">
  <summary>检测范围及身份限制 <span class="muted">仅在需要时展开查看</span></summary>
  <div class="section-head"><div><h2>这次结果怎么理解</h2></div></div>
  <div class="quick-grid">
    <div class="quick-card"><small>模型身份</small><b>{html.escape(identity_state_label)}</b><p>{html.escape(identity['text'])}</p></div>
    <div class="quick-card"><small>质量保持</small><b>{html.escape(str(quality.get('label') or '未配置'))}</b><p>{html.escape(str(quality.get('text') or ''))}</p></div>
    <div class="quick-card"><small>禁止上游策略</small><b>{html.escape(policy_state_label)}</b><p>{html.escape(provider['text'])}</p></div>
    <div class="quick-card"><small>429 限流</small><b>{provider['http_429_count']} 次</b><p>429 只表示限流，本工具不会用 429 单独判断 Fireworks 或其他上游。</p></div>
  </div>
</details>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">优先处理</div><h2>风险与异常解读</h2></div><span class="muted">最多展示 12 项</span></div>
  {''.join(issues_html)}
</section>

<details class="card report-optional">
  <summary>上游 / Gateway 观察信息 <span class="muted">未配置禁止上游时不影响准入</span></summary>
  <div class="section-head"><div><h2>Provider / Gateway 指纹</h2></div></div>
  <p class="lead">{html.escape(provider['text'])}</p>
  <div class="metrics">
    <div class="metric"><span>禁止列表</span><b>{html.escape(', '.join(provider['disallowed']) or '未配置')}</b></div>
    <div class="metric"><span>策略状态</span><b>{html.escape(policy_state_label)}</b></div>
    <div class="metric"><span>本轮 429</span><b>{provider['http_429_count']}</b></div>
  </div>
  <div style="margin-top:10px">{providers_html}</div>
  {('<div style="margin-top:14px"><div class="eyebrow">禁止上游命中证据</div>' + blocked_html + '</div>') if blocked_html else ''}
</details>

{fingerprint_section}
{usage_cost_section}
{kimi_official_section}

<section class="card">
  <div class="section-head"><div><div class="eyebrow">下一步</div><h2>建议怎么处理</h2></div></div>
  <ol class="actions">{actions_html}</ol>
</section>

{regression_section}

<details class="card report-optional">
  <summary>模型官方公开成绩、质量基准与六维度覆盖 <span class="muted">背景参考，不作直接判定</span></summary>
  <div class="optional-body">
{quality_section}
{public_benchmarks_section}

<section class="card">
  <div class="section-head"><div><div class="eyebrow">六大维度</div><h2>检测覆盖与异常数量</h2></div></div>
  <div class="category-grid">{''.join(category_cards)}</div>
</section>

  </div>
</details>

<details class="card report-optional" id="all-results">
  <summary>完整检测明细与原始证据 <span class="muted">{len(report.results)} 个检测项，可筛选异常</span></summary>
  <div class="section-head"><div><h2>全部检测项</h2></div></div>
  <div class="filter-row">
    <button onclick="filterRows('important')">只看异常</button>
    <button onclick="filterRows('fail')">只看失败</button>
    <button onclick="filterRows('all')">全部</button>
  </div>
  <div class="table-wrap"><table id="probe-table"><thead><tr><th>检测项</th><th>维度</th><th>状态</th><th>分数</th><th>解读 / 技术摘要</th><th>证据</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table></div>
</details>

<section class="card">
  <details><summary>高级：Adapters / Reference / 原始配置</summary>{''.join(adapter_rows)}</details>
</section>

<section class="card">
  <div class="section-head"><div><div class="eyebrow">边界说明</div><h2>这份报告不能证明什么</h2></div></div>
  <ul class="limits">{limitations}</ul>
</section>

<script>
function copyConclusion(){{
  const text={copy_text_json};
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

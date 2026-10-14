"""Offline, read-only recalculation of historical GLM-5.3 evidence.

Never posts to model endpoints, extracts archive members, mutates the source,
or exports raw responses/URLs/API keys. Only hashes and aggregate diagnostics
are written; original source reports remain unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import lm_eval
from .capability_scoring import SCORER_VERSION, grade_answer
from .glm53_benchmark import _check_task, benchmark_plan, compare_benchmark_runs
from .glm53_qualification import (
    build_comparison, plan_comparison, render_qualification_html,
    selected_cases,
)

REPLAY_VERSION = "glm53-evidence-replay-v1"
_MAX_MEMBER = 4_000_000
_MAX_TOTAL = 32_000_000
_STAGES = (
    "glm53-01-protocol",
    "glm53-02-smoke",
    "glm53-03-standard",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(z: zipfile.ZipFile, member: str) -> tuple[dict[str, Any], str]:
    info = z.getinfo(member)
    if info.file_size > _MAX_MEMBER:
        raise ValueError("oversized replay JSON file")
    data = z.read(info)
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError("replay input must be a JSON object")
    return obj, _sha(data)


def _task_answers(
    records: list[dict[str, Any]],
    case_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    new = copy.deepcopy(records)
    changes = []
    for row in new:
        old = row["status"]
        if row.get("kind") != "capability":
            # Historical protocol records omit the raw 400 response body.
            # Notes alone cannot turn an insufficient result into a pass.
            continue
        case = case_by_id.get(row.get("id"))
        if case is None or "pattern" not in case:
            row["status"] = "insufficient"
        elif row.get("http_status") != 200:
            # Preserve real old errors: replay must not recast transport failure
            # into a model answer or silently turn it into a correct response.
            if old not in {"error", "insufficient"}:
                row["status"] = "insufficient"
        elif row.get("finish_reason") == "length":
            row["status"] = "insufficient"
        else:
            answer = row.get("observed_answer_excerpt")
            if not isinstance(answer, str) or len(answer) >= 160:
                row["status"] = "insufficient"
            else:
                grade = grade_answer(
                    category=case["category"],
                    task_id=case["id"].split(".", 1)[1],
                    pattern=case["pattern"],
                    answer=answer,
                )
                row["status"] = "pass" if grade.matched else "fail"
                row["scorer_version"] = SCORER_VERSION
                row["answer_normalization"] = grade.normalization
                # Do not retain the answer in the exported offline summary.
        if row["status"] != old:
            changes.append({
                "endpoint": row["endpoint"], "run": row["run"],
                "case": row["id"], "before": old, "after": row["status"],
                "reason": "offline deterministic rescoring" if row["status"] != "insufficient"
                          else "historical response not fully available",
            })
    return new, changes


def _sanitized_stage(source: dict[str, Any], *, source_sha256: str) -> dict[str, Any]:
    plan = source.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("historical report has no plan")
    cases = selected_cases(plan["mode"], plan["profile"])
    by_id = {case["id"]: case for case in cases}
    runs = source.get("runs")
    if not isinstance(runs, dict):
        raise ValueError("historical report missing runs")
    official, changed_o = _task_answers(runs["official"], by_id)
    customer, changed_c = _task_answers(runs["customer"], by_id)
    # The original suite hash describes the original requests, and MUST NOT
    # be replaced by a regraded suite hash as though fresh calls were made.
    aggregate = build_comparison(official, customer, plan=plan)
    return {
        "original_report_sha256": source_sha256,
        "original_suite_sha256": source.get("suite_sha256"),
        "scorer_version": SCORER_VERSION,
        "original_generated_at": source.get("generated_at"),
        "assessment": aggregate.get("assessment"),
        "protocol": aggregate["protocol"],
        "capability": aggregate["capability"],
        "usage": aggregate["usage"],
        "changes": changed_o + changed_c,
        "historical_protocol_note": (
            "Old report does not contain raw thinking.disabled 400 error body; "
            "its status is kept unmodified, despite separate manual notes."
        ),
    }


def replay_archive(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("evidence ZIP file does not exist")
    if path.stat().st_size > 100_000_000:
        raise ValueError("evidence ZIP exceeds compressed size limit")
    archive_sha = _sha(path.read_bytes())  # original entire file, never changed
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        if (
            len(members) > 300
            or sum(x.file_size for x in members) > _MAX_TOTAL
            or any(x.file_size > _MAX_MEMBER for x in members if not x.is_dir())
        ):
            raise ValueError("evidence archive exceeds offline safety limits")
        names = {x.filename for x in members}
        if len(names) != len(members):
            raise ValueError("evidence archive has duplicate filenames")
        stages = {}
        for stage in _STAGES:
            name = f"{stage}/glm53-comparison.json"
            if name not in names:
                raise ValueError(f"missing expected report: {name}")
            original, sha = _read_json(z, name)
            stages[stage] = _sanitized_stage(original, source_sha256=sha)

        historical_smoke = {}
        for stage in ("glm53-04-attempt1-FAILED-ifeval-dep",
                      "glm53-04-benchmark-smoke"):
            name = f"{stage}/glm53-comparison.json"
            if name in names:
                old, sha = _read_json(z, name)
                info = old.get("standard_benchmark") or {}
                historical_smoke[stage] = {
                    "original_report_sha256": sha,
                    "original_state": info.get("result", "unknown"),
                    "historical_scores_only": [
                        {
                            "task": x.get("task"),
                            "official_scores": x.get("official_scores"),
                            "customer_scores": x.get("customer_scores"),
                            "sample_count": x.get("sample_count"),
                        }
                        for x in info.get("tasks", [])
                    ],
                    "verdict": "not_regraded_no_raw_lm_eval_config",
                }
        benchmark_sources = {}
        benchmark_rows = {}
        for label in ("official", "customer"):
            candidates = [
                x for x in names
                if x.startswith(f"glm53-05-benchmark-standard-raw/{label}/")
                and "/results_" in x and x.endswith(".json")
            ]
            if len(candidates) != 1:
                raise ValueError(f"expected exactly one {label} raw lm-eval result")
            data, sha = _read_json(z, candidates[0])
            benchmark_sources[label] = sha
            benchmark_rows[label] = [_check_task(r) for r in lm_eval.parse_result_payload(data)]
        profile = benchmark_plan("standard", official_runs=1, customer_runs=1)
        benchmark = compare_benchmark_runs(
            [benchmark_rows["official"]],
            [benchmark_rows["customer"]],
            plan=profile,
            harness_version="from-source",  # check source versions separately below
        )
        # Report authoritative version from each JSON, not a synthetic label.
        versions = {}
        for label in ("official", "customer"):
            candidates = [
                x for x in names
                if x.startswith(f"glm53-05-benchmark-standard-raw/{label}/")
                and "/results_" in x and x.endswith(".json")
            ]
            data, _ = _read_json(z, candidates[0])
            versions[label] = str(data.get("lm_eval_version") or "unknown")
        benchmark["harness_version"] = versions["official"] if len(set(versions.values())) == 1 else "incomparable"
        if len(set(versions.values())) != 1:
            benchmark["result"] = "partial_or_incomparable"
            for task in benchmark["tasks"]:
                task.update(status="incomparable", reason="lm-eval versions differ",
                            official_mean=None, customer_mean=None, delta=None)
                task["metrics"] = []
        benchmark["original_result_sha256"] = benchmark_sources
    return {
        "replay_version": REPLAY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": archive_sha,
        "input_origin": "local user-provided historical archive; authenticity not independently verified",
        "stages": stages,
        "historical_smoke": historical_smoke,
        "standard_benchmark": benchmark,
        "assessment": {
            "protocol": "observed_but_some_historical_cases_remain_inconclusive",
            "capability": "limited_samples_observation_only",
            "model_identity": "not_verified",
            "supplier_accreditation": "not_determined",
        },
        "limitations": [
            "Offline regrading is not a new official API measurement.",
            "04 historical Smoke scores remain unverified without its original lm-eval configs; 05 full raw reports were reprocessed.",
            "Only the saved 160-character excerpts can be rescored; truncated/missing evidence is insufficient.",
            "Historical thinking.disabled 400 bodies were not saved in report JSON; manual notes do not silently overwrite status.",
            "Standard benchmark task parity is not proof that the real reasoning settings were applied by either endpoint.",
            "N=25 per task cannot establish statistical equivalence, full model quality, or model identity.",
            "Raw external benchmark Token usage is unavailable.",
        ],
    }


def write_replay(result: dict[str, Any], destination: Path) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    output = {
        "json": destination / "glm53-replay.json",
        "markdown": destination / "glm53-replay.md",
        "html": destination / "glm53-replay.html",
    }
    if any(p.exists() for p in output.values()):
        raise FileExistsError("offline replay outputs already exist; choose a new directory")
    lines = [
        "# GLM-5.3 历史证据离线重算报告", "",
        f"Archive SHA256：{result['archive_sha256']}",
        f"Replay 版本：{result['replay_version']}",
        "**仅根据本地旧证据重算；没有发起官方或客户 API 请求。**",
        "", "## 阶段汇总", "",
        "| 阶段 | 协议观察一致 | 官方证据不足 | 客户证据不足 | 客户偏离 | 答案判分变更 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, stage in result["stages"].items():
        statuses = [x["verdict"] for x in stage["protocol"]]
        lines.append(
            f"| {name} | {statuses.count('consistent')} "
            f"| {statuses.count('official_inconclusive')} "
            f"| {statuses.count('customer_inconclusive')} "
            f"| {statuses.count('deviation')} | {len(stage['changes'])} |"
        )
    lines.extend([
        "", "## 04 历史 Smoke / 首次安装失败", "",
        "04 仅保存旧汇总，缺原始评测配置，不能重算为可比或通过；"
        "其旧分数仅作为诊断记录。",
        "",
    ])
    for name, evidence in result.get("historical_smoke", {}).items():
        lines.append(
            f"- {name}：{evidence['original_state']}；"
            "原始评测配置缺失，仍未验证。"
        )
    lines.extend([
        "", "## 标准 Benchmark 全部评分指标（05 原始 lm-eval）", "",
        "| 任务 | 指标 | 官方 | 客户 | 差值 | 证据 |",
        "|---|---|---:|---:|---:|---|",
    ])
    for task in result["standard_benchmark"]["tasks"]:
        for metric in task.get("metrics") or []:
            lines.append(
                f"| {task['task']} | {metric['metric']} "
                f"| {metric['official_mean']:.2%} "
                f"| {metric['customer_mean']:.2%} "
                f"| {metric['delta']:+.2%} | {task['status']} |"
            )
        if not task.get("metrics"):
            lines.append(
                f"| {task['task']} | 不可比 | — | — | — | {task['reason']} |"
            )
    lines.extend(["", "## 本次重新判分的轻量题", "",
                  "| 阶段 | 端点/轮次 | 用例 | 原判定 | 新判定 |",
                  "|---|---|---|---|---|"])
    for name, stage in result["stages"].items():
        for change in stage["changes"]:
            lines.append(
                f"| {name} | {change['endpoint']} #{change['run']} "
                f"| {change['case']} | {change['before']} | {change['after']} |"
            )
    lines.extend([
        "", "## 证据边界与下一步", "",
        "标准评测只显示同配置题集的观测差值；未评定模型权重身份、等价性或正式客户准入。",
        "旧协议记录缺原始中文 400 的 HTTP body，thinking.disabled 必须保留证据不足或人工待复核。",
        "原 01～05 文件未覆盖。建议在 G1 前复核评测任务实际 reasoning 配置和失败后的证据留存。",
    ])
    lines.extend("- " + item for item in result["limitations"])
    markdown = "\n".join(lines) + "\n"
    output["json"].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    output["markdown"].write_text(markdown, encoding="utf-8")
    output["html"].write_text(render_qualification_html(markdown), encoding="utf-8")
    return output

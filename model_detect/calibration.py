from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .validation import _confusion

SIGNALS = ("identity", "routing", "quality")
QUALITY_STDDEV_MULTIPLIERS = (1.0, 2.0, 3.0)


def wilson95(successes: int, trials: int) -> dict[str, float] | None:
    """Descriptive Wilson score interval for a binomial outcome.

    Only use independent *cases*, never repeat runs from the same case.
    """
    if trials < 1 or not 0 <= successes <= trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    middle = (p + z2 / (2 * trials)) / denom
    radius = z * math.sqrt(
        (p * (1.0 - p) + z2 / (4.0 * trials)) / trials
    ) / denom
    return {"lower": round(max(0.0, middle - radius), 6),
            "upper": round(min(1.0, middle + radius), 6)}


def _case_predictions(
    validation: dict[str, Any],
    *,
    override: dict[tuple[str, int], bool | None] | None = None,
    only_signal: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in validation.get("runs") or []:
        grouped[str(row["case_id"])].append(row)

    cases: list[dict[str, Any]] = []
    for case in validation.get("cases") or []:
        case_id = str(case["id"])
        rows = sorted(grouped.get(case_id, []), key=lambda x: x["run"])
        expected = case.get("expected")
        if not isinstance(expected, dict):
            expected = rows[0].get("expected", {}) if rows else {}
        complete = (
            len(rows) == int(case.get("runs_expected") or 0)
            and all(row["run"] == i for i, row in enumerate(rows, 1))
        )
        predictions: dict[str, bool | None] = {}
        for signal in SIGNALS:
            if only_signal is not None and signal != only_signal:
                predictions[signal] = None
                continue
            observed = [
                override.get((case_id, row["run"]))
                if override is not None and signal == only_signal
                else row["predicted"].get(signal)
                for row in rows
            ]
            # A case counts only when all declared runs have usable, identical
            # predictions. Do not cherry-pick successful repetitions.
            if (
                complete and observed and all(type(x) is bool for x in observed)
                and len(set(observed)) == 1
            ):
                predictions[signal] = observed[0]
            else:
                predictions[signal] = None
        cases.append({
            "case_id": case_id,
            "scenario": case.get("scenario"),
            "routing_fraction": case.get("routing_fraction"),
            "truth_source": case.get("truth_source"),
            "runs_found": len(rows),
            "runs_expected": case.get("runs_expected"),
            "expected": {signal: expected.get(signal) for signal in SIGNALS},
            "predicted": predictions,
        })
    return cases


def _intervals(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "sensitivity": wilson95(
            metrics["tp"], metrics["tp"] + metrics["fn"]
        ),
        "false_positive_rate": wilson95(
            metrics["fp"], metrics["fp"] + metrics["tn"]
        ),
        "coverage": wilson95(metrics["evaluated"], metrics["labelled"]),
    }


def _group_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        signal: {
            **_confusion(rows, signal),
            "wilson95": _intervals(_confusion(rows, signal)),
        }
        for signal in SIGNALS
    }


def _quality_candidate_prediction(
    report_path: str,
    multiplier: float,
) -> bool | None:
    """Offline threshold replay; never changes production detector thresholds."""
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    adapters = report.get("adapters") or {}
    comparison = adapters.get("official_baseline_comparison")
    if not isinstance(comparison, dict):
        return None
    if comparison.get("incomparable_dimensions"):
        return None
    if int(comparison.get("statistically_evaluable_dimensions") or 0) < 1:
        return None
    dimensions = comparison.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        return None

    has_evaluable = False
    regression = False
    for item in dimensions.values():
        if not isinstance(item, dict):
            return None
        if item.get("verdict") == "incomparable" or item.get("contract_valid") is not True:
            return None
        if item.get("statistically_evaluable") is not True:
            return None
        if int(item.get("baseline_runs") or 0) < 3:
            return None
        try:
            mean = float(item["baseline_mean"])
            stddev = float(item["baseline_stddev"])
            current = float(item["target_score"])
            granularity = float(item.get("task_granularity") or 0.0)
        except (KeyError, TypeError, ValueError):
            return None
        if not all(math.isfinite(x) for x in (mean, stddev, current, granularity)):
            return None
        if not (0 <= mean <= 1 and 0 <= current <= 1 and 0 <= stddev <= 1
                and 0 <= granularity <= 1):
            return None
        has_evaluable = True
        lower_bound = max(0.0, mean - max(multiplier * stddev, granularity))
        regression = regression or current < lower_bound
    return regression if has_evaluable else None


def _quality_sweep(
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    runs = validation.get("runs") or []
    results = []
    for multiplier in QUALITY_STDDEV_MULTIPLIERS:
        overrides: dict[tuple[str, int], bool | None] = {}
        candidates: list[dict[str, Any]] = []
        for row in runs:
            prediction = _quality_candidate_prediction(
                row["report_path"], multiplier
            )
            key = (row["case_id"], row["run"])
            overrides[key] = prediction
            candidates.append({
                "expected": {"quality": row["expected"].get("quality")},
                "predicted": {"quality": prediction},
            })
        cases = _case_predictions(
            validation, override=overrides, only_signal="quality"
        )
        case_metrics = _confusion(cases, "quality")
        results.append({
            "stddev_multiplier": multiplier,
            "run_metrics": _confusion(candidates, "quality"),
            "case_metrics": {
                **case_metrics,
                "wilson95": _intervals(case_metrics),
            },
            "case_predictions": [{
                "case_id": item["case_id"],
                "expected": item["expected"]["quality"],
                "predicted": item["predicted"]["quality"],
            } for item in cases],
        })
    return results


def calibrate_validation(validation: dict[str, Any]) -> dict[str, Any]:
    """Analyze reports already evaluated with Phase 3; never invent observations."""
    if validation.get("schema_version") != 1:
        raise ValueError("unsupported validation schema version")
    cases = _case_predictions(validation)
    run_metrics = _group_metrics(validation.get("runs") or [])
    case_metrics = _group_metrics(cases)
    by_scenario: dict[str, dict[str, Any]] = {}
    for scenario in sorted({str(row["scenario"]) for row in cases}):
        group = [row for row in cases if row["scenario"] == scenario]
        by_scenario[scenario] = {
            "cases": len(group),
            "case_metrics": _group_metrics(group),
        }

    routing_groups: dict[str, dict[str, Any]] = {}
    for ratio in (0.0, 0.1, 0.3, 0.5):
        group = [
            row for row in cases
            if row["scenario"] == "mixed_routing"
            and row["routing_fraction"] is not None
            and math.isclose(row["routing_fraction"], ratio, abs_tol=1e-8)
        ]
        routing_groups[str(int(ratio * 100))] = {
            "configured_fraction": ratio,
            "case_count": len(group),
            "metrics": _confusion(group, "routing"),
            "meaning": "controlled gateway target fraction, not actual observed route share",
        }

    readiness = {}
    for signal in SIGNALS:
        metrics = case_metrics[signal]
        positive = metrics["tp"] + metrics["fn"]
        negative = metrics["tn"] + metrics["fp"]
        sufficient = (
            positive >= 5 and negative >= 5
            and metrics["coverage"] is not None
            and metrics["coverage"] >= 0.8
        )
        readiness[signal] = {
            "status": (
                "no_data" if not metrics["labelled"]
                else "descriptive_only" if sufficient
                else "insufficient_independent_cases"
            ),
            "independent_positive_cases": positive,
            "independent_negative_cases": negative,
            "min_per_class_for_pilot": 5,
            "min_coverage_for_pilot": 0.8,
            "certified": False,
            "notes": (
                "These are user-labelled controlled cases, not independent "
                "external certification. Hold-out providers and actual route "
                "logs are needed before operational threshold changes."
            ),
        }

    return {
        "schema_version": 1,
        "suite_id": validation.get("suite_id"),
        "observed_reports": validation.get("observed_reports", 0),
        "expected_reports": validation.get("expected_reports", 0),
        "case_count": len(cases),
        "run_metrics": run_metrics,
        "case_metrics": case_metrics,
        "by_scenario": by_scenario,
        "mixed_routing_target_groups": routing_groups,
        "quality_threshold_replay": _quality_sweep(validation),
        "readiness": readiness,
        "cases": cases,
        "warnings": [
            "Ground truth is asserted by the manifest author; not independently verified.",
            "Case-level aggregation requires all expected runs, with identical predictions.",
            "Wilson 95% intervals are descriptive for independent cases; not proof of population-level accuracy.",
            "Threshold replay uses only comparable existing Quality dimensions; it does not modify production settings.",
            "Reported routing percentages are configured targets; actual upstream shares require gateway logs.",
        ],
    }


def _rate(value: float | None) -> str:
    return "样本不足" if value is None else f"{value:.1%}"


def _ci(value: dict[str, float] | None) -> str:
    return "样本不足" if value is None else (
        f"{value['lower']:.1%}～{value['upper']:.1%}"
    )


def write_calibration(
    calibration: dict[str, Any], output_dir: str | Path
) -> tuple[Path, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "calibration.json"
    md_path = root / "calibration.md"
    json_path.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    names = {"identity": "模型身份", "routing": "混合路由", "quality": "质量退化"}
    lines = [
        f"# Phase 4：受控实验校准诊断 · {calibration['suite_id']}",
        "",
        f"报告数量：{calibration['observed_reports']}/{calibration['expected_reports']}；"
        f"独立 Case：{calibration['case_count']} 个",
        "",
        "**注意：此文件是实验诊断，不是官方模型认证或已校准的准确率声明。**",
        "",
        "## 独立 Case 级别汇总",
        "",
        "| 指标 | 有标签 Case | 有效判断 | 弃权 | TP | TN | FP | FN | 灵敏度（95% Wilson） | 误报率（95% Wilson） |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for key, name in names.items():
        m = calibration["case_metrics"][key]
        lines.append(
            f"| {name} | {m['labelled']} | {m['evaluated']} | {m['abstained']} "
            f"| {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} "
            f"| {_rate(m['sensitivity'])} ({_ci(m['wilson95']['sensitivity'])}) "
            f"| {_rate(m['false_positive_rate'])} ({_ci(m['wilson95']['false_positive_rate'])}) |"
        )

    lines.extend([
        "",
        "多次运行同一个 Case **不视作多个独立供应商**。不同运行预测不一致、缺失任何一轮或出现弃权时，整个 Case 记为弃权。",
        "",
        "## 混合路由：外部配置目标分流比例",
        "",
        "| 比例 | Case 数量 | TP | TN | FP | FN | 弃权 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for key, obj in calibration["mixed_routing_target_groups"].items():
        m = obj["metrics"]
        lines.append(
            f"| {key}%（目标） | {obj['case_count']} | {m['tp']} | {m['tn']} "
            f"| {m['fp']} | {m['fn']} | {m['abstained']} |"
        )

    lines.extend([
        "",
        "## 质量退化阈值敏感性（仅离线候选回放）",
        "",
        "| 基准标准差系数 | 有效 Case | 弃权 | TP | TN | FP | FN | 灵敏度 | 误报率 |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for row in calibration["quality_threshold_replay"]:
        m = row["case_metrics"]
        lines.append(
            f"| {row['stddev_multiplier']:.1f}× | {m['evaluated']} | {m['abstained']} "
            f"| {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} "
            f"| {_rate(m['sensitivity'])} | {_rate(m['false_positive_rate'])} |"
        )
    lines.extend([
        "",
        "以上 k=1/2/3 只是当前样本的对照结果。**不能自动调整生产阈值**；请在独立保留的渠道 / 时间窗上继续检验。",
        "",
        "## 验证准备情况",
        "",
    ])
    for key, name in names.items():
        item = calibration["readiness"][key]
        lines.append(
            f"- {name}：{item['status']}；独立正例 {item['independent_positive_cases']}，"
            f"独立负例 {item['independent_negative_cases']}。未认证。"
        )
    lines.extend(["", "## 实验边界", ""])
    lines.extend("- " + str(w) for w in calibration["warnings"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path

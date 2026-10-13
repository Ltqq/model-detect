from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import AuditReport

Scenario = Literal[
    "same_model", "different_model", "different_effort",
    "mixed_routing", "different_provider", "different_version",
]
Signal = Literal["identity", "routing", "quality"]


class TruthLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: Literal["same", "different"] | None = None
    routing_mixed: bool | None = None
    quality_regressed: bool | None = None

    @model_validator(mode="after")
    def require_label(self) -> "TruthLabels":
        if all(value is None for value in (
            self.identity, self.routing_mixed, self.quality_regressed
        )):
            raise ValueError("at least one known truth label is required")
        return self


class ValidationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    scenario: Scenario
    truth_source: str = Field(min_length=8)
    truth: TruthLabels
    runs: int = Field(default=1, ge=1, le=5)
    reports: list[str] = Field(default_factory=list)
    # External controlled routing proportion is *declared*, not measured here.
    routing_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    reference_id: str | None = None
    profile: Literal["standard", "deep"] = "standard"
    benchmark_profile: Literal["smoke", "standard", "deep"] | None = None

    @model_validator(mode="after")
    def validate_scenario(self) -> "ValidationCase":
        if self.scenario == "mixed_routing":
            if self.routing_fraction is None:
                raise ValueError("mixed_routing requires routing_fraction")
            if self.truth.routing_mixed is None:
                raise ValueError("mixed_routing requires routing_mixed truth")
            if self.truth.routing_mixed != (self.routing_fraction > 0):
                raise ValueError("routing truth contradicts declared routing_fraction")
        elif self.routing_fraction is not None:
            raise ValueError("routing_fraction is only valid for mixed_routing")
        if len(self.reports) > self.runs:
            raise ValueError("reports cannot exceed declared runs")
        if len(set(self.reports)) != len(self.reports):
            raise ValueError("duplicate report paths")
        return self


class ValidationSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    reference_dir: str = "references"
    cases: list[ValidationCase] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def unique_cases(self) -> "ValidationSuite":
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        return self


def load_suite(path: str | Path) -> ValidationSuite:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("validation manifest must be a YAML/JSON object")
    return ValidationSuite.model_validate(payload)


def _find_report_paths(
    case: ValidationCase,
    *,
    manifest: Path,
    output_dir: Path,
) -> list[Path]:
    if case.reports:
        supplied = [
            (manifest.parent / relative).resolve()
            for relative in case.reports
        ]
        return supplied + [
            output_dir / case.id / f"{run:02d}" / "report.json"
            for run in range(len(supplied) + 1, case.runs + 1)
        ]
    return [
        output_dir / case.id / f"{run:02d}" / "report.json"
        for run in range(1, case.runs + 1)
    ]


def _result(report: AuditReport, probe_id: str):
    return next((r for r in report.results if r.probe_id == probe_id), None)


def _identity_signal(report: AuditReport) -> str | None:
    item = _result(report, "identity.fingerprint.reference_compare")
    if not item or item.metadata.get("identity_strength") != "strong":
        return None
    verdict = item.metadata.get("verdict")
    if verdict == "match" and item.status.value == "pass":
        return "same"
    if verdict == "mismatch" and item.status.value == "fail":
        return "different"
    return None


def _routing_signal(report: AuditReport) -> bool | None:
    item = _result(report, "routing.summary")
    repeat = _result(report, "routing.repeat.same_probe")
    if not item or not repeat:
        return None
    samples = repeat.observed.get("samples") if isinstance(repeat.observed, dict) else None
    if not isinstance(samples, int) or samples < 1:
        return None
    if item.metadata.get("verdict") == "mixed-routing-likely":
        return True
    cluster = _result(report, "routing.cluster")
    if (
        item.metadata.get("verdict") == "stable"
        and repeat.status.value == "pass"
        and cluster is not None
        and cluster.status.value == "pass"
        and not (
            isinstance(item.observed, dict)
            and item.observed.get("suspicious_signals")
        )
    ):
        return False
    return None


def _quality_signal(report: AuditReport) -> bool | None:
    raw = report.adapters.get("official_baseline_comparison")
    if not isinstance(raw, dict):
        return None
    if (
        raw.get("incomparable_dimensions")
        or int(raw.get("statistically_evaluable_dimensions") or 0) < 1
    ):
        return None
    if raw.get("verdict") == "quality_regression" and raw.get("regression_dimensions"):
        return True
    if raw.get("verdict") == "baseline_match":
        return False
    return None


def classify_report(report: AuditReport) -> dict[str, Any]:
    return {
        "identity": _identity_signal(report),
        "routing": _routing_signal(report),
        "quality": _quality_signal(report),
    }


def _fraction(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _confusion(records: list[dict[str, Any]], signal: Signal) -> dict[str, Any]:
    abstained = 0
    labelled = 0
    for row in records:
        expected = row["expected"][signal]
        if expected is None:
            continue
        labelled += 1
        predicted = row["predicted"][signal]
        if predicted is None:
            abstained += 1
            continue
        # Keep FP/FN separate; don't count uncertain calls as correct.
    tp = sum(
        1 for row in records
        if row["expected"][signal] is True
        and row["predicted"][signal] is True
    )
    tn = sum(
        1 for row in records
        if row["expected"][signal] is False
        and row["predicted"][signal] is False
    )
    fp = sum(
        1 for row in records
        if row["expected"][signal] is False
        and row["predicted"][signal] is True
    )
    fn = sum(
        1 for row in records
        if row["expected"][signal] is True
        and row["predicted"][signal] is False
    )
    evaluated = tp + tn + fp + fn
    return {
        "labelled": labelled,
        "evaluated": evaluated,
        "abstained": abstained,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "coverage": _fraction(evaluated, labelled),
        "accuracy": _fraction(tp + tn, evaluated),
        "sensitivity": _fraction(tp, tp + fn),
        "false_positive_rate": _fraction(fp, fp + tn),
        "precision": _fraction(tp, tp + fp),
        "specificity": _fraction(tn, tn + fp),
    }


def evaluate_suite(
    suite: ValidationSuite,
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    manifest = Path(manifest_path).resolve()
    root = Path(output_dir).resolve()
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    cases: list[dict[str, Any]] = []
    for case in suite.cases:
        paths = _find_report_paths(case, manifest=manifest, output_dir=root)
        found = 0
        for index, path in enumerate(paths, 1):
            if not path.is_file():
                missing.append(f"{case.id} #{index}: report missing")
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                report = AuditReport.model_validate(raw)
                # Invalid/failed target and unexecuted probes cannot count as
                # detector negative predictions.
                if report.summary.final_verdict == "invalid_target":
                    raise ValueError("invalid API target")
                if case.model and str(report.target.get("model")) != case.model:
                    raise ValueError("model does not match declared case")
                if report.profile != case.profile:
                    raise ValueError("profile does not match declared case")
            except (OSError, ValueError) as exc:
                missing.append(f"{case.id} #{index}: invalid report ({type(exc).__name__})")
                continue
            found += 1
            predicted = classify_report(report)
            expected = {
                "identity": (
                    None if case.truth.identity is None
                    else case.truth.identity == "different"
                ),
                "routing": case.truth.routing_mixed,
                "quality": case.truth.quality_regressed,
            }
            rows.append({
                "case_id": case.id,
                "scenario": case.scenario,
                "run": index,
                "truth_source": case.truth_source,
                "routing_fraction": case.routing_fraction,
                "report_path": str(path),
                "expected": expected,
                "predicted": {
                    "identity": (
                        None if predicted["identity"] is None
                        else predicted["identity"] == "different"
                    ),
                    "routing": predicted["routing"],
                    "quality": predicted["quality"],
                },
                "raw_verdicts": predicted,
            })
        cases.append({
            "id": case.id,
            "scenario": case.scenario,
            "truth_source": case.truth_source,
            "routing_fraction": case.routing_fraction,
            "runs_expected": case.runs,
            "runs_found": found,
        })

    metrics = {
        signal: _confusion(rows, signal)
        for signal in ("identity", "routing", "quality")
    }
    return {
        "schema_version": 1,
        "suite_id": suite.id,
        "manifest": str(manifest),
        "observed_reports": len(rows),
        "expected_reports": sum(case.runs for case in suite.cases),
        "cases": cases,
        "runs": rows,
        "missing": missing,
        "metrics": metrics,
        "warnings": [
            "True labels come from the experiment manifest, not cryptographic proof.",
            "Repeated runs of one case are correlated; these rates are descriptive, not confidence intervals.",
            "Insufficient/uncertain signals abstain rather than count as negative.",
        ],
    }


def _metric(value: float | None) -> str:
    return "样本不足" if value is None else f"{value:.1%}"


def write_validation(result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "validation.json"
    md_path = root / "validation.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    labels = {"identity": "模型身份", "routing": "混合路由", "quality": "质量退化"}
    lines = [
        f"# 受控鉴别实验：{result['suite_id']}",
        "",
        f"实际读取报告：{result['observed_reports']} / {result['expected_reports']}",
        "",
        "> 仅统计真实存在且可解析的报告。实验标签由执行者声明；结果不构成模型权重认证。",
        "",
        "| 检测维度 | 有标签 | 有效判断 | 弃权 | TP | TN | FP | FN | 有效覆盖率 | 灵敏度 | 误报率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in labels.items():
        m = result["metrics"][key]
        lines.append(
            f"| {label} | {m['labelled']} | {m['evaluated']} | {m['abstained']} "
            f"| {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} "
            f"| {_metric(m['coverage'])} | {_metric(m['sensitivity'])} "
            f"| {_metric(m['false_positive_rate'])} |"
        )
    lines.extend([
        "",
        "说明：TP=正确检出异常，TN=正确识别正常，FP=正常被误报，FN=异常漏检。",
        "灵敏度 TP/(TP+FN)，误报率 FP/(FP+TN)；没有相应分母则显示“样本不足”。",
        "UNCERTAIN / INSUFFICIENT / 不可比均记弃权，不充当正常判断。",
        "",
        "## 按场景的真实报告",
        "",
        "| Case | 场景 | 实测次数/计划次数 | 配置分流比例 | 真实标签来源 |",
        "|---|---|---:|---|---|",
    ])
    for case in result["cases"]:
        fraction = (
            "—" if case["routing_fraction"] is None
            else f"{case['routing_fraction']:.0%}（仅配置目标）"
        )
        lines.append(
            f"| {case['id']} | {case['scenario']} "
            f"| {case['runs_found']}/{case['runs_expected']} "
            f"| {fraction} | {str(case['truth_source']).replace('|', '/')} |"
        )
    lines.extend(["", "## 证据边界", ""])
    for warning in result["warnings"]:
        lines.append("- " + warning)
    if result["missing"]:
        lines.extend(["", "## 缺失 / 无效报告", ""])
        lines.extend("- " + entry for entry in result["missing"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path

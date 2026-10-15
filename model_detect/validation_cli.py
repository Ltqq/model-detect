from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .validation import evaluate_suite, load_suite, write_validation
from .calibration import calibrate_validation, write_calibration
from .validation_runner import execution_plan, run_suite
from .validation_doctor import validation_manifest_readiness

validation_app = typer.Typer(
    no_args_is_help=True,
    help="Run controlled labelled experiments or score existing audit reports.",
)
console = Console()


@validation_app.command("evaluate")
def evaluate(
    manifest: Path = typer.Option(
        ..., "--manifest", exists=True, readable=True,
        help="YAML/JSON manifest with known truth labels and report paths.",
    ),
    output_dir: Path = typer.Option(
        Path("model-detect-validation"), "--output-dir", "-o",
    ),
) -> None:
    """Score actual local reports against independently declared ground truth."""
    suite = load_suite(manifest)
    result = evaluate_suite(
        suite, manifest_path=manifest, output_dir=output_dir,
    )
    json_path, md_path = write_validation(result, output_dir)
    console.print(
        f"[cyan]Real reports: {result['observed_reports']}"
        f"/{result['expected_reports']}[/cyan]"
    )
    rows = Table("维度", "有效/有标签", "弃权", "TP", "TN", "FP", "FN")
    for name, label in (
        ("identity", "模型身份"),
        ("routing", "混合路由"),
        ("quality", "质量退化"),
    ):
        entry = result["metrics"][name]
        rows.add_row(
            label,
            f"{entry['evaluated']}/{entry['labelled']}",
            str(entry["abstained"]),
            str(entry["tp"]), str(entry["tn"]),
            str(entry["fp"]), str(entry["fn"]),
        )
    console.print(rows)
    console.print(f"JSON: {json_path}")
    console.print(f"中文实验报告: {md_path}")
    if not result["observed_reports"]:
        console.print(
            "[yellow]没有真实报告：未计算检出率或误报率。[/yellow]"
        )


@validation_app.command("calibrate")
def calibrate(
    manifest: Path = typer.Option(
        ..., "--manifest", exists=True, readable=True,
        help="Controlled experiment manifest with real truth labels.",
    ),
    output_dir: Path = typer.Option(
        Path("model-detect-validation"), "--output-dir", "-o",
    ),
) -> None:
    """Offline per-case calibration diagnostics and threshold sensitivity."""
    suite = load_suite(manifest)
    evaluated = evaluate_suite(
        suite, manifest_path=manifest, output_dir=output_dir,
    )
    results = calibrate_validation(evaluated)
    json_path, md_path = write_calibration(results, output_dir)
    console.print(
        f"[cyan]Real reports: {results['observed_reports']}/"
        f"{results['expected_reports']} · independent cases: "
        f"{results['case_count']}[/cyan]"
    )
    table = Table("维度", "独立正例", "独立负例", "有效", "弃权", "状态")
    labels = {
        "identity": "模型身份",
        "routing": "混合路由",
        "quality": "质量退化",
    }
    for signal, label in labels.items():
        case = results["case_metrics"][signal]
        ready = results["readiness"][signal]
        table.add_row(
            label,
            str(ready["independent_positive_cases"]),
            str(ready["independent_negative_cases"]),
            str(case["evaluated"]), str(case["abstained"]),
            ready["status"],
        )
    console.print(table)
    console.print(f"JSON: {json_path}")
    console.print(f"中文校准诊断: {md_path}")
    if not results["observed_reports"]:
        console.print(
            "[yellow]没有真实报告。已保留空白诊断，未推算任何准确率。[/yellow]"
        )


@validation_app.command("run")
def run(
    manifest: Path = typer.Option(
        ..., "--manifest", exists=True, readable=True,
    ),
    output_dir: Path = typer.Option(
        Path("model-detect-validation"), "--output-dir", "-o",
    ),
    execute: bool = typer.Option(
        False, "--execute",
        help="Explicitly allow real, potentially billable API calls.",
    ),
    max_audits: int = typer.Option(
        16, "--max-audits", min=1, max=40,
        help="Hard limit on total audits; default 16.",
    ),
) -> None:
    """Show the execution plan; use --execute to actually call endpoints."""
    suite = load_suite(manifest)
    plan = execution_plan(suite)
    table = Table("Case", "场景", "次数", "官方Reference", "Benchmark")
    for case in plan["cases"]:
        table.add_row(
            case["case_id"], case["scenario"], str(case["runs"]),
            "已配置" if case["reference_configured"] else "无",
            case["benchmark_profile"] or "关闭",
        )
    console.print(table)
    console.print(
        f"[yellow]预计执行 {plan['total_audits']} 次完整审计。"
        "每次包含多个模型请求，实际 Token 数取决于 Probe 与模型。[/yellow]"
    )
    if not execute:
        console.print(
            "预览模式：没有请求任何 API。确认后附加 --execute。"
        )
        return
    if plan["total_audits"] > max_audits:
        raise typer.BadParameter(
            f"planned {plan['total_audits']} audits exceeds "
            f"--max-audits={max_audits}"
        )

    def progress(case_id: str, index: int, total: int) -> None:
        console.print(f"[cyan][{index}/{total}][/cyan] {case_id}")

    result = asyncio.run(run_suite(
        suite,
        manifest_path=manifest,
        output_dir=output_dir,
        max_audits=max_audits,
        progress=progress,
    ))
    errors = sum(
        entry["status"] == "error" for entry in result["outcomes"]
    )
    console.print(
        f"实测报告：{result['summary']['observed_reports']}；"
        f"失败执行：{errors}"
    )
    console.print(f"JSON: {output_dir / 'validation.json'}")
    console.print(f"中文实验报告: {output_dir / 'validation.md'}")
    if errors:
        raise typer.Exit(code=1)


@validation_app.command("doctor")
def doctor(
    manifest: Path = typer.Option(..., "--manifest", exists=True, readable=True),
    output_dir: Path = typer.Option(
        Path("model-detect-validation"), "--output-dir",
    ),
    strict_reports: bool = typer.Option(
        False, "--strict-reports", help="Fail when declared real reports are absent",
    ),
) -> None:
    """Check independent class labels and evidence files without invoking APIs."""
    suite = load_suite(manifest)
    readiness = validation_manifest_readiness(
        suite, manifest_path=manifest, output_dir=output_dir,
    )
    console.print_json(data=readiness)
    if strict_reports and readiness["missing_report_files"]:
        raise typer.Exit(code=1)

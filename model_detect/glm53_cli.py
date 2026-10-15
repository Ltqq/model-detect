from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .glm53_benchmark import benchmark_plan, run_standard_benchmark
from .glm53_replay import replay_archive, write_replay
from .glm53_preflight import benchmark_preflight
from .glm53_task_cache import verify_offline_task_cache
from .glm53_wire import verify_wire_requests
from .glm53_qualification import (
    build_comparison, normalize_base_url, plan_comparison,
    run_endpoint, selected_cases, write_comparison,
)

glm53_app = typer.Typer(
    no_args_is_help=True,
    help="GLM-5.3 first-party vs customer protocol and capability comparison.",
)
console = Console()


@glm53_app.command("compare")
def compare(
    official_url: str = typer.Option(
        ..., "--official-url",
        help="First-party Z.ai OpenAI-compatible URL, e.g. https://api.z.ai/api/paas/v4",
    ),
    customer_url: str = typer.Option(..., "--customer-url"),
    official_key_env: str = typer.Option("GLM53_OFFICIAL_KEY", "--official-key-env"),
    customer_key_env: str = typer.Option("GLM53_CUSTOMER_KEY", "--customer-key-env"),
    official_runs: int = typer.Option(3, "--official-runs", min=1, max=5),
    customer_runs: int = typer.Option(1, "--customer-runs", min=1, max=5),
    mode: str = typer.Option("all", "--mode", help="all / protocol / capability"),
    capability_profile: str = typer.Option(
        "standard", "--capability-profile", help="smoke (10) / standard (25)"
    ),
    input_price: Optional[float] = typer.Option(
        None, "--input-price", min=0, help="Price per 1 million input tokens (same currency for both endpoints)",
    ),
    output_price: Optional[float] = typer.Option(
        None, "--output-price", min=0, help="Price per 1 million output tokens",
    ),
    benchmark_level: str = typer.Option(
        "none", "--benchmark",
        help="none (default) / smoke / standard / deep (lm-eval generative tasks)",
    ),
    benchmark_runs: int = typer.Option(
        1, "--benchmark-runs", min=1, max=3,
        help="Runs per endpoint for optional external benchmark",
    ),
    benchmark_max_gen_toks: int = typer.Option(
        8192, "--benchmark-max-gen-toks", min=256, max=32768,
    ),
    benchmark_reasoning_effort: str = typer.Option(
        "max", "--benchmark-reasoning-effort",
        help="Reasoning effort sent by lm-eval to BOTH official and customer: low/high/max",
    ),
    allow_unverified_reference: bool = typer.Option(
        False, "--allow-unverified-reference",
        help="Permit a non-official baseline host; report is not first-party verified.",
    ),
    max_requests: int = typer.Option(160, "--max-requests", min=1),
    max_nominal_output_tokens: Optional[int] = typer.Option(
        None, "--max-nominal-output-tokens", min=1,
        help="Fail closed when configured output max_tokens sum exceeds this limit",
    ),
    max_estimated_input_tokens: Optional[int] = typer.Option(
        None, "--max-estimated-input-tokens", min=1,
        help="Fail when heuristic input estimate exceeds this limit; not a hard bound",
    ),
    require_offline_task_cache: bool = typer.Option(
        False, "--require-offline-task-cache",
        help="Block all paid requests unless selected lm-eval tasks load from local cache",
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Allow actual potentially billable calls to both APIs"
    ),
    output_dir: Path = typer.Option(Path("glm53-output"), "--output-dir", "-o"),
) -> None:
    """Preview request/token budget, or --execute matched official/customer audits."""
    try:
        official_base = normalize_base_url(official_url)
        customer_base = normalize_base_url(customer_url)
        parsed_official = urlsplit(official_base)
        trusted_hosts = {"api.z.ai", "open.bigmodel.cn"}
        is_first_party_url = (
            parsed_official.scheme == "https"
            and parsed_official.hostname in trusted_hosts
        )
        if not is_first_party_url and not allow_unverified_reference:
            raise ValueError(
                "the official reference must use HTTPS on api.z.ai or "
                "open.bigmodel.cn; use --allow-unverified-reference "
                "only for a controlled trusted reference (not official certification)"
            )
        benchmark = (
            benchmark_plan(
                benchmark_level, official_runs=benchmark_runs,
                customer_runs=benchmark_runs,
                max_gen_toks=benchmark_max_gen_toks,
                reasoning_effort=benchmark_reasoning_effort,
            )
            if benchmark_level != "none" else None
        )
        plan = plan_comparison(
            mode=mode,
            profile=capability_profile,
            official_runs=official_runs,
            customer_runs=customer_runs,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    summary = Table("预算项目", "数值")
    summary.add_row("协议 Case（每轮）", str(plan["protocol_cases"]))
    summary.add_row("能力题（每轮）", str(plan["capability_cases"]))
    summary.add_row("官方/客户重复轮数", f"{official_runs}/{customer_runs}")
    summary.add_row("总 API 请求计划", str(plan["requests"]))
    summary.add_row("粗略输入 Token 估算", str(plan["estimated_input_tokens"]))
    summary.add_row("名义输出预算 max_tokens 合计", str(plan["nominal_output_token_cap"]))
    if benchmark:
        summary.add_row(
            "附加标准 Benchmark", 
            f"{benchmark['tasks']} × 最多 {benchmark['limit']} 题"
        )
        summary.add_row("Benchmark 样本调用（名义）", str(benchmark["nominal_samples"]))
        summary.add_row(
            "Benchmark 双端推理等级", benchmark["reasoning_effort"],
        )
        summary.add_row(
            "Benchmark 额外输出上限合计",
            str(benchmark["nominal_max_output_tokens"]),
        )
        console.print(
            "[yellow]标准 Benchmark 使用独立 lm-eval 子进程；Token usage "
            "暂时无法计量，费用预估不包含这部分输入。[/yellow]"
        )
    if plan["scenario_max_cost"] is not None:
        summary.add_row(
            "粗略费用情景（使用输入估算+输出满额）",
            str(plan["scenario_max_cost"]) + "（单价所用货币）",
        )
    console.print(summary)
    console.print("[yellow]" + plan["warning"] + "[/yellow]")
    console.print(
        "能力部分是客观小题 Smoke/Standard，非 GLM-5.3 官方高难 Coding/Agent Benchmark。"
    )
    total_planned = plan["requests"] + (
        benchmark["nominal_samples"] if benchmark else 0
    )
    nominal_output = plan["nominal_output_token_cap"] + (
        benchmark["nominal_max_output_tokens"] if benchmark else 0
    )
    if (max_nominal_output_tokens is not None
            and nominal_output > max_nominal_output_tokens):
        raise typer.BadParameter(
            f"nominal output token cap {nominal_output} exceeds "
            f"--max-nominal-output-tokens {max_nominal_output_tokens}; "
            "no paid requests started"
        )
    if (max_estimated_input_tokens is not None
            and plan["estimated_input_tokens"] > max_estimated_input_tokens):
        raise typer.BadParameter(
            "estimated native input tokens exceed --max-estimated-input-tokens; "
            "not a billable or tokenizer-verified hard bound"
        )
    if total_planned > max_requests:
        raise typer.BadParameter(
            f"planned native requests + benchmark samples {total_planned} "
            f"exceed --max-requests {max_requests}"
        )
    if not execute:
        console.print(
            "[green]预览完成，未发送付费请求。确认配置后加 --execute。[/green]"
        )
        return

    if require_offline_task_cache and not benchmark:
        raise typer.BadParameter(
            "--require-offline-task-cache needs --benchmark smoke/standard/deep"
        )
    if require_offline_task_cache:
        precheck = verify_offline_task_cache(benchmark_level)
        if not precheck["verified"]:
            raise typer.BadParameter(
                "offline benchmark task-cache check did not pass; "
                "no paid requests were started. Run glm53 doctor "
                "--verify-task-cache to diagnose local task/data cache."
            )

    # Preflight both credentials and endpoints before any potentially paid request.
    official_key = os.getenv(official_key_env)
    customer_key = os.getenv(customer_key_env)
    if not official_key or not customer_key:
        raise typer.BadParameter(
            "Both API key environment variables must be set before --execute"
        )
    if official_base == customer_base and official_key == customer_key:
        raise typer.BadParameter(
            "Official and customer endpoints/credentials are identical; "
            "a self-match is not a supplier comparison"
        )

    if benchmark:
        diagnostics = benchmark_preflight(benchmark_level)
        if not diagnostics["ready"]:
            failed = ", ".join(
                item["name"] for item in diagnostics["checks"]
                if item["status"] == "fail"
            )
            raise typer.BadParameter(
                f"local Benchmark preflight failed: {failed}. "
                "Run 'model-detect glm53 doctor --benchmark "
                f"{benchmark_level}' before any paid requests."
            )
        console.print(
            "[yellow]本地依赖已检查，但数据集缓存和真正生效的"
            "推理参数尚未验证；不要将此当作 Benchmark 正式准入。[/yellow]"
        )
    if output_dir.joinpath("glm53-comparison.json").exists():
        raise typer.BadParameter(
            "comparison output already exists; choose a new --output-dir "
            "to avoid losing costly previous measurements"
        )
    if benchmark and (output_dir / "benchmark-evidence" / "benchmark-checkpoint.json").exists():
        raise typer.BadParameter(
            "existing benchmark checkpoint detected; refusing to repeat "
            "native or benchmark paid calls. Inspect existing evidence and "
            "use a fresh --output-dir for an intentional new run."
        )
    cases = selected_cases(mode, capability_profile)

    async def collect():
        console.print("[cyan]测试官方端点...[/cyan]")
        official = await run_endpoint(
            base_url=official_base, api_key=official_key,
            cases=cases, runs=official_runs, label="official",
        )
        console.print("[cyan]测试客户端点...[/cyan]")
        customer = await run_endpoint(
            base_url=customer_base, api_key=customer_key,
            cases=cases, runs=customer_runs, label="customer",
        )
        return official, customer

    official, customer = asyncio.run(collect())
    result = build_comparison(
        official, customer, plan=plan,
        input_price_per_million=input_price,
        output_price_per_million=output_price,
    )
    result["reference_provenance"] = {
        "official_host_verified": is_first_party_url,
        "reference_type": "first_party_domain" if is_first_party_url
                          else "unverified_trusted_endpoint",
    }
    if benchmark:
        console.print(
            "[cyan]执行附加标准 Benchmark；数据集会下载/缓存，"
            "官方和客户各运行指定轮次...[/cyan]"
        )
        try:
            result["standard_benchmark"] = run_standard_benchmark(
                level=benchmark_level,
                official_url=official_base,
                customer_url=customer_base,
                official_key=official_key,
                customer_key=customer_key,
                official_runs=benchmark_runs,
                customer_runs=benchmark_runs,
                max_gen_toks=benchmark_max_gen_toks,
                reasoning_effort=benchmark_reasoning_effort,
                checkpoint_dir=output_dir / "benchmark-evidence",
            )
        except Exception as exc:
            result["standard_benchmark"] = {
                "result": "error",
                "error_type": type(exc).__name__,
                "warning": (
                    "Standard Benchmark did not finish; there is no "
                    "claim of comparable capability for the benchmark."
                ),
            }
            write_comparison(result, output_dir)
            raise typer.Exit(code=1)
    outputs = write_comparison(result, output_dir)
    console.print("[green]已生成 GLM-5.3 官方对照报告。[/green]")
    for kind, path in outputs.items():
        console.print(f"{kind}: {path}")



@glm53_app.command("replay")
def replay(
    evidence_zip: Path = typer.Option(
        ..., "--evidence-zip", exists=True, dir_okay=False,
        help="Historical GLM-5.3 ZIP containing 01-03 reports and original 05 lm-eval JSON"
    ),
    output_dir: Path = typer.Option(
        ..., "--output-dir", "-o",
        help="New, distinct output directory; originals are never overwritten"
    ),
) -> None:
    """Recalculate saved historical evidence locally; no API keys or Token."""
    outputs = [
        output_dir / "glm53-replay.json",
        output_dir / "glm53-replay.md",
        output_dir / "glm53-replay.html",
    ]
    if any(x.exists() for x in outputs):
        raise typer.BadParameter("offline replay outputs exist; use a fresh directory")
    if evidence_zip.resolve().parent == output_dir.resolve():
        raise typer.BadParameter("output directory must be separate from the evidence ZIP")
    try:
        result = replay_archive(evidence_zip)
        paths = write_replay(result, output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Errors may contain user file paths: do not echo potentially private paths.
        raise typer.BadParameter(
            f"offline replay failed ({type(exc).__name__}); check archive schema"
        ) from None
    console.print("[green]离线重算完成；没有调用模型 API，也未覆盖旧报告。[/green]")
    for kind, path in paths.items():
        console.print(f"{kind}: {path}")



@glm53_app.command("doctor")
def doctor(
    benchmark_level: str = typer.Option(
        "standard", "--benchmark",
        help="smoke / standard / deep; checks local prerequisites, no API calls",
    ),
    verify_task_cache: bool = typer.Option(
        False, "--verify-task-cache",
        help="Also instantiate selected lm-eval tasks using offline-only Hugging Face settings",
    ),
) -> None:
    """Inspect local Benchmark dependencies without sending model API calls."""
    try:
        diagnostics = benchmark_preflight(benchmark_level)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    table = Table("本地预检项目", "状态", "解释")
    for item in diagnostics["checks"]:
        table.add_row(item["name"], item["status"], item["explanation"])
    console.print(table)
    console.print("[yellow]" + diagnostics["warning"] + "[/yellow]")
    if not diagnostics["ready"]:
        console.print("[red]预检未通过：不会建议启动付费 Benchmark。[/red]")
        raise typer.Exit(code=1)
    console.print(
        "[green]本地依赖预检通过（未访问数据集、未使用 Key、未调用模型）。[/green]"
    )
    if verify_task_cache:
        evidence = verify_offline_task_cache(benchmark_level)
        console.print_json(data=evidence)
        if not evidence["verified"]:
            raise typer.Exit(code=1)


@glm53_app.command("verify-wire")
def verify_wire(
    captured_json: Path = typer.Option(
        ..., "--captured-json", exists=True, dir_okay=False,
        help="Local JSON with official/customer arrays of captured request bodies",
    ),
    output_file: Path = typer.Option(
        ..., "--output-file", help="New sanitized verification JSON file",
    ),
    reasoning_effort: str = typer.Option(
        "max", "--reasoning-effort", help="Expected low/high/max",
    ),
) -> None:
    """Compare captured HTTP JSON bodies offline; never send model requests."""
    if output_file.exists():
        raise typer.BadParameter("output already exists; refusing to overwrite evidence")
    try:
        raw = json.loads(captured_json.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("expected JSON object")
        verdict = verify_wire_requests(
            raw.get("official"), raw.get("customer"),
            expected_effort=reasoning_effort,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise typer.BadParameter("invalid local captured request JSON; no content shown") from None
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("x", encoding="utf-8") as target:
        json.dump(verdict, target, ensure_ascii=False, indent=2)
    console.print(
        f"Offline wire validation: {verdict['status']}; "
        "raw messages and credentials were not exported."
    )
    if verdict["status"] != "request_payload_matched":
        raise typer.Exit(code=1)


@glm53_app.command("inspect-checkpoint")
def inspect_checkpoint_command(
    checkpoint: Path = typer.Option(..., "--checkpoint", exists=True, dir_okay=False),
) -> None:
    """Summarize an existing checkpoint offline; never resume or call models."""
    from .glm53_checkpoint_doctor import inspect_checkpoint
    try:
        evidence = inspect_checkpoint(checkpoint)
    except (OSError, ValueError, TypeError, KeyError):
        raise typer.BadParameter("invalid checkpoint; source details withheld") from None
    console.print_json(data=evidence)


@glm53_app.command("capture-local-wire")
def capture_local_wire(
    benchmark_level: str = typer.Option("smoke", "--benchmark"),
    reasoning_effort: str = typer.Option("max", "--reasoning-effort"),
    max_gen_toks: int = typer.Option(1024, "--max-gen-toks"),
    output_file: Path = typer.Option(..., "--output-file"),
) -> None:
    """Capture actual lm-eval outgoing request JSON on a local mock HTTP server."""
    from .glm53_local_wire import capture_local_lm_eval_wire
    if output_file.exists() or output_file.is_symlink():
        raise typer.BadParameter("capture output already exists")
    try:
        outcome = capture_local_lm_eval_wire(
            benchmark_level, reasoning_effort=reasoning_effort,
            max_gen_toks=max_gen_toks,
        )
    except (OSError, ValueError, RuntimeError):
        raise typer.BadParameter(
            "local lm-eval wire capture failed; check offline tasks and installation"
        ) from None
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("x", encoding="utf-8") as handle:
        json.dump(outcome, handle, ensure_ascii=False, indent=2)
    console.print_json(data={
        "capture_count": outcome["capture_count"],
        "parameter_match": outcome["parameter_match"],
        "harness_returncode": outcome["harness_returncode"],
        "external_model_api_calls": 0,
        "result_file": str(output_file),
    })

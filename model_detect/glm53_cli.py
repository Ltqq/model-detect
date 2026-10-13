from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

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
    max_requests: int = typer.Option(160, "--max-requests", min=1),
    execute: bool = typer.Option(
        False, "--execute", help="Allow actual potentially billable calls to both APIs"
    ),
    output_dir: Path = typer.Option(Path("glm53-output"), "--output-dir", "-o"),
) -> None:
    """Preview request/token budget, or --execute matched official/customer audits."""
    try:
        official_base = normalize_base_url(official_url)
        customer_base = normalize_base_url(customer_url)
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
    if plan["requests"] > max_requests:
        raise typer.BadParameter(
            f"request plan {plan['requests']} exceeds --max-requests {max_requests}"
        )
    if not execute:
        console.print(
            "[green]预览完成，未发送付费请求。确认配置后加 --execute。[/green]"
        )
        return

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
    outputs = write_comparison(result, output_dir)
    console.print("[green]已生成 GLM-5.3 官方对照报告。[/green]")
    for kind, path in outputs.items():
        console.print(f"{kind}: {path}")

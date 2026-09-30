from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .adapters import fingerprint, proxy_sleuth
from .audit import run_audit
from .config import AuditConfig, RegressionAuditConfig, load_config
from .models import AuditTarget
from .reference_cli import reference_app
from .reporting import safe_name, write_report
from .drift import compare_reports


app = typer.Typer(
    no_args_is_help=True,
    help="LLM API model authenticity, protocol and capability audit toolkit.",
)
app.add_typer(reference_app, name="reference")
console = Console()


@app.command()
def audit(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="YAML audit config"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="OpenAI-compatible base URL, usually ending in /v1"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Claimed model id"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env", help="Environment variable containing the API key"),
    profile: str = typer.Option("quick", "--profile", help="quick / standard / deep"),
    output_dir: Path = typer.Option(Path("model-detect-output"), "--output-dir", "-o"),
    fingerprint_reference: Optional[Path] = typer.Option(None, "--fingerprint-reference", help="Trusted llm-fingerprint reference JSON"),
    reference_id: Optional[str] = typer.Option(None, "--reference-id", help="Trusted reference registry ID"),
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
    declared_context_tokens: Optional[int] = typer.Option(None, "--declared-context-tokens"),
    with_proxy_sleuth: Optional[bool] = typer.Option(
        None,
        "--with-proxy-sleuth/--without-proxy-sleuth",
        help="Enable/disable proxy-sleuth OSS augmentation; default follows config.",
    ),
    coding_sandbox: Optional[bool] = typer.Option(
        None,
        "--coding-sandbox/--no-coding-sandbox",
        help="Explicitly enable/disable Docker-isolated executable coding evaluation.",
    ),
    regression_suite: list[Path] = typer.Option(
        [],
        "--regression-suite",
        help=(
            "Regression YAML suite to run; repeat this option to add multiple suites."
        ),
    ),
) -> None:
    """Run a model audit and write report.json, report.html and raw evidence."""
    if config:
        cfg = load_config(config)
        if output_dir != Path("model-detect-output"):
            cfg.output_dir = str(output_dir)
        if fingerprint_reference:
            cfg.fingerprint_reference = str(fingerprint_reference)
        if reference_id:
            cfg.reference_id = reference_id
        if reference_dir != Path("references"):
            cfg.reference_dir = str(reference_dir)
        if declared_context_tokens:
            cfg.declared_context_tokens = declared_context_tokens
        if coding_sandbox is not None:
            cfg.coding_sandbox_enabled = coding_sandbox
        if regression_suite:
            cfg.regression.suites.extend(
                str(path.expanduser().resolve())
                for path in regression_suite
            )
            cfg.regression.suites = list(
                dict.fromkeys(cfg.regression.suites)
            )
    else:
        if not base_url or not model:
            raise typer.BadParameter("--base-url and --model are required when --config is not used")
        cfg = AuditConfig(
            target=AuditTarget(
                base_url=base_url,
                model=model,
                api_key_env=api_key_env,
                protocol="openai",
            ),
            profile=profile,
            output_dir=str(output_dir),
            fingerprint_reference=str(fingerprint_reference) if fingerprint_reference else None,
            reference_id=reference_id,
            reference_dir=str(reference_dir),
            declared_context_tokens=declared_context_tokens,
            coding_sandbox_enabled=bool(coding_sandbox),
            regression=RegressionAuditConfig(
                suites=[
                    str(path.expanduser().resolve())
                    for path in regression_suite
                ]
            ),
        )

    def progress(name: str, current: int, total: int) -> None:
        console.print(f"[cyan][{current}/{total}][/cyan] {name}")

    console.print(f"[bold]model-detect v{__version__}[/bold]")
    console.print(f"Target: {cfg.target.base_url}  Model: {cfg.target.model}")
    report = asyncio.run(
        run_audit(
            cfg,
            progress=progress,
            use_proxy_sleuth=with_proxy_sleuth,
        )
    )

    target_dir = Path(cfg.output_dir) / safe_name(cfg.target.model)
    root = write_report(report, target_dir)

    console.print()
    console.print(f"Verdict: [bold]{report.summary.final_verdict}[/bold]")
    console.print(f"Score: {report.summary.overall_score}")
    if report.provider_hypotheses:
        console.print("Provider hypotheses:")
        for item in report.provider_hypotheses[:5]:
            console.print(f"  - {item.provider}: {item.confidence:.0%}")
    console.print(f"JSON: {root / 'report.json'}")
    console.print(f"HTML: {root / 'report.html'}")



@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
    state_dir: Path = typer.Option(Path(".model-detect"), "--state-dir"),
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
    output_dir: Path = typer.Option(Path("model-detect-output"), "--output-dir"),
) -> None:
    """Start the local Web UI."""
    import uvicorn
    from .webapp import create_app

    console.print(
        f"[bold]model-detect web[/bold] http://{host}:{port} "
        f"(state={state_dir}, references={reference_dir})"
    )
    uvicorn.run(
        create_app(
            state_dir=state_dir,
            reference_dir=reference_dir,
            output_dir=output_dir,
        ),
        host=host,
        port=port,
    )


@app.command("compare")
def compare_command(
    old_report: Path = typer.Argument(..., exists=True, readable=True),
    new_report: Path = typer.Argument(..., exists=True, readable=True),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Compare two report.json files to spot provider/model drift."""
    data = compare_reports(old_report, new_report)
    if json_output:
        console.print_json(data=data)
        return

    console.print(
        f"Old: {data['old']['verdict']} / {data['old']['overall_score']}  "
        f"→ New: {data['new']['verdict']} / {data['new']['overall_score']}"
    )
    table = Table("Category", "Old", "New", "Delta")
    for name, item in data["category_deltas"].items():
        table.add_row(
            name,
            str(item["old"]),
            str(item["new"]),
            str(item["delta"]),
        )
    console.print(table)
    if data["provider_changes"]["added"] or data["provider_changes"]["removed"]:
        console.print(
            "Provider changes: "
            f"+{data['provider_changes']['added']} "
            f"-{data['provider_changes']['removed']}"
        )
    if data["probe_changes"]:
        ptable = Table("Probe", "Old", "New")
        for item in data["probe_changes"][:50]:
            ptable.add_row(
                item["probe_id"],
                str(item["old_status"]),
                str(item["new_status"]),
            )
        console.print(ptable)


@app.command("oss-status")
def oss_status() -> None:
    """Show availability of optional open-source engines."""
    table = Table("Engine", "Available", "Details")
    fp = fingerprint.availability()
    ps = proxy_sleuth.availability()
    from .sandbox import availability as sandbox_availability
    sb = sandbox_availability()
    table.add_row(
        "llm-fingerprint-detector",
        "yes" if fp["available"] else "no",
        fp.get("direct_binary") or fp.get("npx") or "install Node.js/npm or llm-fingerprint",
    )
    table.add_row(
        "proxy-sleuth",
        "yes" if ps["available"] else "no",
        ps.get("binary") or "install Babapei/proxy-sleuth",
    )
    table.add_row(
        "Docker coding sandbox",
        "yes" if sb["available"] else "no",
        sb.get("binary") or "install Docker; host execution fallback is intentionally disabled",
    )
    console.print(table)


@app.command()
def version() -> None:
    console.print(__version__)

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
from .config import AuditConfig, load_config
from .models import AuditTarget
from .reference_cli import reference_app
from .reporting import safe_name, write_report


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


@app.command("oss-status")
def oss_status() -> None:
    """Show availability of optional open-source engines."""
    table = Table("Engine", "Available", "Details")
    fp = fingerprint.availability()
    ps = proxy_sleuth.availability()
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
    console.print(table)


@app.command()
def version() -> None:
    console.print(__version__)

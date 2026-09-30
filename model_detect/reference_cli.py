from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .adapters import fingerprint
from .audit import run_audit
from .config import AuditConfig, get_api_key
from .models import AuditTarget
from .references import ReferenceManifest, ReferenceRegistry
from .reporting import safe_name, write_report


console = Console()
reference_app = typer.Typer(no_args_is_help=True, help="Manage trusted model references.")


@reference_app.command("list")
def list_references(
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
) -> None:
    registry = ReferenceRegistry(reference_dir)
    rows = registry.list()
    table = Table("ID", "Model", "Provider", "Collected", "Fingerprint")
    for item in rows:
        table.add_row(
            item.id,
            item.model,
            item.provider,
            item.collected_at,
            "yes" if item.fingerprint_artifact else "no",
        )
    console.print(table)


@reference_app.command("show")
def show_reference(
    reference_id: str,
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
) -> None:
    manifest = ReferenceRegistry(reference_dir).get(reference_id)
    console.print_json(data=manifest.model_dump(mode="json"))


@reference_app.command("collect")
def collect_reference(
    reference_id: str = typer.Option(..., "--id"),
    base_url: str = typer.Option(..., "--base-url"),
    model: str = typer.Option(..., "--model", "-m"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env"),
    provider: str = typer.Option("trusted", "--provider"),
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
    collect_fingerprint: bool = typer.Option(
        True, "--fingerprint/--no-fingerprint"
    ),
) -> None:
    target = AuditTarget(
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        protocol="openai",
    )
    cfg = AuditConfig(
        target=target,
        profile="standard",
        capability_enabled=False,
        proxy_sleuth_enabled=False,
    )
    console.print("[cyan]Collecting trusted protocol signature...[/cyan]")
    report = asyncio.run(run_audit(cfg, use_proxy_sleuth=False))
    registry = ReferenceRegistry(reference_dir)
    fp_path = None
    if collect_fingerprint:
        if fingerprint.availability().get("available"):
            fp_path = registry.path_for(reference_id) / "fingerprint.json"
            console.print("[cyan]Collecting statistical fingerprint...[/cyan]")
            fingerprint.collect(
                base_url=base_url,
                model=model,
                api_key=get_api_key(target),
                output=fp_path,
            )
        else:
            console.print(
                "[yellow]llm-fingerprint-detector unavailable; reference will contain protocol signature only.[/yellow]"
            )

    manifest = registry.create_from_report(
        reference_id=reference_id,
        model=model,
        provider=provider,
        protocol="openai",
        report=report,
        fingerprint_path=fp_path,
    )
    report_dir = registry.path_for(reference_id) / "baseline-report"
    write_report(report, report_dir)
    console.print(f"[green]Saved reference {manifest.id}[/green]")
    console.print(f"Manifest: {registry.path_for(reference_id) / 'manifest.json'}")


@reference_app.command("import-fingerprint")
def import_fingerprint(
    reference_id: str = typer.Option(..., "--id"),
    model: str = typer.Option(..., "--model", "-m"),
    fingerprint_file: Path = typer.Option(..., "--file", exists=True, readable=True),
    provider: str = typer.Option("trusted", "--provider"),
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
) -> None:
    """Import an existing llm-fingerprint-detector reference JSON."""
    registry = ReferenceRegistry(reference_dir)
    if registry.exists(reference_id):
        raise typer.BadParameter(f"reference already exists: {reference_id}")
    root = registry.path_for(reference_id)
    root.mkdir(parents=True, exist_ok=True)
    dst = root / "fingerprint.json"
    shutil.copy2(fingerprint_file, dst)
    manifest = ReferenceManifest(
        id=reference_id,
        model=model,
        provider=provider,
        protocol="openai",
        fingerprint_artifact=dst.name,
        notes=["Imported fingerprint artifact; no protocol signature was collected."],
    )
    registry.save_manifest(manifest)
    console.print(f"[green]Imported reference {reference_id}[/green]")
    console.print(f"Manifest: {root / 'manifest.json'}")


@reference_app.command("verify")
def verify_reference(
    reference_id: str = typer.Option(..., "--id"),
    base_url: str = typer.Option(..., "--base-url"),
    model: str = typer.Option(..., "--model", "-m"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env"),
    reference_dir: Path = typer.Option(Path("references"), "--reference-dir"),
    profile: str = typer.Option("standard", "--profile"),
    output_dir: Path = typer.Option(Path("model-detect-output"), "--output-dir", "-o"),
) -> None:
    cfg = AuditConfig(
        target=AuditTarget(
            base_url=base_url,
            model=model,
            api_key_env=api_key_env,
            protocol="openai",
        ),
        profile=profile,
        reference_id=reference_id,
        reference_dir=str(reference_dir),
        output_dir=str(output_dir),
    )
    report = asyncio.run(run_audit(cfg))
    root = write_report(report, output_dir / safe_name(model))
    console.print(
        f"Verdict: [bold]{report.summary.final_verdict}[/bold]  Score: {report.summary.overall_score}"
    )
    console.print(f"Report: {root / 'report.html'}")

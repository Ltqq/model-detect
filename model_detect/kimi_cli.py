"""Lightweight offline CLI for a pinned official Kimi verifier subset."""
from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console

from .kimi_official import OFFICIAL_CASES, import_official_junit, plan_official_subset
from .kimi_runner import run_official_subset

kimi_app = typer.Typer(no_args_is_help=True, help="Kimi official verifier subset: plan and offline JUnit evidence import.")
console = Console()


@kimi_app.command("plan")
def plan(
    suite: list[str] = typer.Option(
        ["params", "k3_features", "tool_call_json_schema", "prompt_tokens"],
        "--suite", help="Official suite name; repeat to select more",
    ),
) -> None:
    try:
        evidence = plan_official_subset(suite)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    console.print_json(data=evidence)


@kimi_app.command("import-junit")
def import_junit(
    xml_file: Path = typer.Option(..., "--file", exists=True, dir_okay=False),
    suite: str = typer.Option(..., "--suite"),
    model: str = typer.Option(..., "--model"),
    output_file: Path = typer.Option(..., "--output-file"),
) -> None:
    if suite not in OFFICIAL_CASES:
        raise typer.BadParameter("unknown official suite")
    if output_file.exists():
        raise typer.BadParameter("output exists; refusing to overwrite evidence")
    try:
        report = import_official_junit(xml_file, suite=suite, model=model)
    except (ValueError, OSError) as exc:
        # Never repeat XML parser errors or attacker-controlled raw content.
        raise typer.BadParameter("invalid local JUnit evidence") from None
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
    console.print(f"Imported {sum(report['counts'].values())} JUnit cases. No model calls.")


@kimi_app.command("run")
def run(
    repo_dir: Path = typer.Option(..., "--repo-dir", exists=True, file_okay=False),
    python_executable: Path = typer.Option(..., "--python-executable", exists=True, dir_okay=False),
    suite: str = typer.Option("params", "--suite"),
    model: str = typer.Option(..., "--model"),
    base_url: str = typer.Option(..., "--base-url"),
    api_key_env: str = typer.Option("KIMI_API_KEY", "--api-key-env"),
    output_dir: Path = typer.Option(Path("kimi-verifier-results"), "--output-dir"),
    max_cases: int = typer.Option(10, "--max-cases", min=1, max=20),
    execute: bool = typer.Option(False, "--execute", help="Authorize paid official pytest API calls"),
) -> None:
    """Preview by default; execute only a selected suite from the pinned official checkout."""
    if suite not in OFFICIAL_CASES:
        raise typer.BadParameter("unknown Kimi official suite")
    console.print_json(data=plan_official_subset([suite]))
    if not execute:
        console.print("Preview only. No external test or model call.")
        return
    key = os.getenv(api_key_env)
    if not key:
        raise typer.BadParameter("configured API key environment variable missing")
    if output_dir.exists():
        raise typer.BadParameter("output directory already exists; refusing overwrite")
    result = run_official_subset(
        repo_dir=repo_dir, python_executable=python_executable,
        suite=suite, model=model, base_url=base_url, api_key=key,
        output_xml=output_dir / "pytest-junit.xml", max_cases=max_cases,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "summary.json").open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    console.print(f"Result status: {result['status']}; sanitized summary saved.")
    if result["status"] != "finished":
        raise typer.Exit(code=1)

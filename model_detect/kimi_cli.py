"""Lightweight offline CLI for a pinned official Kimi verifier subset."""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from .kimi_official import OFFICIAL_CASES, import_official_junit, plan_official_subset

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

"""Command-line front door for the enricher (Typer) — the network tier's user-facing command.

    just-dna-enricher enrich spec/ --strict --offline
    just-dna-enricher enrich-and-compile spec/ out/ --strict
"""

from pathlib import Path
from typing import Optional

import typer
from just_dna_compiler.compiler import compile_module

from just_dna_enricher.enrich import EnrichmentError, enrich

app = typer.Typer(
    add_completion=False,
    help="Fill the source-independent resolution table (cache + live Ensembl) the compiler consumes.",
    no_args_is_help=True,
)


def _mode(strict: bool) -> str:
    return "strict" if strict else "best_effort"


@app.command("enrich")
def enrich_(  # `enrich` command; function name avoids shadowing the imported enrich()
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Optional[Path] = typer.Option(None, "--ensembl-cache", help="Explicit cache dir/.duckdb."),
) -> None:
    """Resolve a spec's variants into resolution.csv beside the spec. Exit 1 in strict mode if unresolved."""
    try:
        result = enrich(spec_dir, mode=_mode(strict), offline=offline, ensembl_cache=ensembl_cache)
    except EnrichmentError as exc:
        typer.secho(f"ENRICH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"enriched: {spec_dir / 'resolution.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"rows: {len(result.rows)}  fully_resolved: {result.fully_resolved}  sources: {result.sources}")
    if result.unresolved:
        typer.secho(f"  unresolved: {result.unresolved}", fg=typer.colors.YELLOW, err=True)


@app.command("enrich-and-compile")
def enrich_and_compile(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for parquet + manifest.json"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Optional[Path] = typer.Option(None, "--ensembl-cache", help="Explicit cache dir/.duckdb."),
) -> None:
    """Enrich, then compile from the produced resolution.csv (offline, deterministic). Exit 1 on failure."""
    try:
        enrich(spec_dir, mode=_mode(strict), offline=offline, ensembl_cache=ensembl_cache)
    except EnrichmentError as exc:
        typer.secho(f"ENRICH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # Compile consumes the just-written resolution.csv (path 1); no reference, no network.
    result = compile_module(spec_dir, output_dir, ensembl_cache=None, strict=strict)
    for w in result.warnings:
        typer.secho(f"  warning: {w}", fg=typer.colors.YELLOW, err=True)
    if not result.success:
        for e in result.errors:
            typer.secho(f"  error: {e}", fg=typer.colors.RED, err=True)
        typer.secho(f"COMPILE FAILED: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"compiled: {output_dir}", fg=typer.colors.GREEN)
    typer.echo(f"digest: {result.manifest.artifact.digest if result.manifest else '?'}")


if __name__ == "__main__":
    app()

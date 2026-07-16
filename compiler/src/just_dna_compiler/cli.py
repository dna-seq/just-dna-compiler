"""
Command-line front door for the reference compiler — a thin Typer shell over the Python API
(`validate_spec` / `compile_module` / `reverse_module`). Lives in `just-dna-compiler` (never
`just-dna-format`): the CLI dep (Typer/click) rides with the already-heavy compiler, keeping the
schema package's dependency tier untouched (CONSTITUTION Goal 2).

Exit codes are CI/registry-gateable: `0` success, `1` failure (invalid spec / failed compile).

    just-dna-compiler validate spec/
    just-dna-compiler compile spec/ out/ --strict --ensembl-cache ref.duckdb
    just-dna-compiler reverse parquet_dir/ spec_out/ --version 1.2.3
"""

from pathlib import Path
from typing import Optional

import typer
from just_dna_format.normalize import IDENTITY_AUTHORITY_KEYS

from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec

app = typer.Typer(
    add_completion=False,
    help="Validate, compile, and reverse just-dna annotation modules.",
    no_args_is_help=True,
)


def _authority_keys(strip_identity: bool, authority_key: list[str]) -> Optional[set[str]]:
    """Assemble the inject-only authority-key set from the two flags, or None if neither is given."""
    keys: set[str] = set(authority_key)
    if strip_identity:
        keys |= set(IDENTITY_AUTHORITY_KEYS)
    return keys or None


def _echo_messages(result) -> None:
    """Print a validate/compile result's errors, warnings, and info to the right streams."""
    for e in result.errors:
        typer.secho(f"  error: {e}", fg=typer.colors.RED, err=True)
    for w in result.warnings:
        typer.secho(f"  warning: {w}", fg=typer.colors.YELLOW, err=True)
    for i in getattr(result, "info", []):
        typer.secho(f"  info: {i}", fg=typer.colors.BLUE)


@app.command()
def validate(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strip_identity: bool = typer.Option(
        False, "--strip-identity", help="Inject the identity authority keys (namespace/owner/canonical_id) to strip."
    ),
    authority_key: list[str] = typer.Option(
        [], "--authority-key", help="Extra authority-owned module key to strip (repeatable)."
    ),
) -> None:
    """Validate a spec directory without producing output. Exit 1 if invalid."""
    result = validate_spec(spec_dir, authority_keys=_authority_keys(strip_identity, authority_key))
    _echo_messages(result)
    if result.valid:
        typer.secho(f"valid: {spec_dir}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"INVALID: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def compile(  # noqa: A001 — the verb is the command name; shadowing builtins.compile is fine in a CLI module
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for parquet + manifest.json"),
    strict: bool = typer.Option(
        False, "--strict/--no-strict", help="All-or-nothing: fail rather than emit a partial artifact with unresolved positions."
    ),
    ensembl_cache: Optional[Path] = typer.Option(
        None, "--ensembl-cache", help="Injected Ensembl reference (.duckdb file or parquet dir)."
    ),
    resolve: bool = typer.Option(
        True, "--resolve/--no-resolve", help="Resolve missing rsid/position via the injected Ensembl reference."
    ),
    compression: str = typer.Option("zstd", "--compression", help="Parquet compression codec."),
    compiled_by: Optional[str] = typer.Option(
        None, "--compiled-by", help="Provenance tag for the manifest (e.g. marketplace-server)."
    ),
    strip_identity: bool = typer.Option(
        False, "--strip-identity", help="Inject the identity authority keys (namespace/owner/canonical_id) to strip."
    ),
    authority_key: list[str] = typer.Option(
        [], "--authority-key", help="Extra authority-owned module key to strip (repeatable)."
    ),
) -> None:
    """Compile a spec directory into a parquet artifact + manifest.json. Exit 1 on failure."""
    result = compile_module(
        spec_dir,
        output_dir,
        compression=compression,
        resolve_with_ensembl=resolve,
        ensembl_cache=ensembl_cache,
        compiled_by=compiled_by,
        authority_keys=_authority_keys(strip_identity, authority_key),
        strict=strict,
    )
    _echo_messages(result)
    if result.success:
        digest = result.manifest.artifact.digest if result.manifest else "?"
        typer.secho(f"compiled: {output_dir}", fg=typer.colors.GREEN)
        typer.echo(f"digest: {digest}")
    else:
        typer.secho(f"COMPILE FAILED: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def reverse(
    parquet_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Compiled parquet directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for the reconstructed spec"),
    module_name: Optional[str] = typer.Option(None, "--module-name", help="Override the recovered module name."),
    title: Optional[str] = typer.Option(None, "--title"),
    description: Optional[str] = typer.Option(None, "--description"),
    report_title: Optional[str] = typer.Option(None, "--report-title"),
    icon: str = typer.Option("database", "--icon"),
    color: str = typer.Option("#6435c9", "--color"),
    version: Optional[str] = typer.Option(None, "--version", help="Advisory module.version to re-emit into the spec."),
) -> None:
    """Reverse a compiled parquet artifact back into the authored spec DSL (yaml + csv)."""
    out = reverse_module(
        parquet_dir,
        output_dir,
        module_name=module_name,
        title=title,
        description=description,
        report_title=report_title,
        icon=icon,
        color=color,
        version=version,
    )
    typer.secho(f"reversed: {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

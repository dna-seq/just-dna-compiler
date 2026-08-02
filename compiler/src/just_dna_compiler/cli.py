"""
Command-line front door for the reference compiler — a thin Typer shell over the Python API
(`validate_spec` / `compile_module` / `reverse_module`). Lives in `just-dna-compiler` (never
`just-dna-format`): the CLI dep (Typer/click) rides with the already-heavy compiler, keeping the
schema package's dependency tier untouched (CONSTITUTION Goal 2).

Exit codes are CI/registry-gateable: `0` success, `1` failure (invalid spec / failed compile).

    just-dna-compiler validate spec/
    just-dna-compiler compile spec/ out/ --strict --ensembl-cache ref.duckdb
    just-dna-compiler reverse parquet_dir/ spec_out/ --version 1.2.3
    just-dna-compiler verify out/ --no-require-marketplace --public-key <base64>
    just-dna-compiler sign out/ --private-key key.pem
"""

from pathlib import Path
from typing import Optional

import typer
from just_dna_format.integrity import IntegrityError, verify_manifest
from just_dna_format.manifest import read_manifest, write_manifest
from just_dna_format.normalize import IDENTITY_AUTHORITY_KEYS
from just_dna_format.signing import sign_digest

from just_dna_compiler.compiler import (
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)

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
        None, "--ensembl-cache",
        help="DEPRECATED (removed at 1.0): Ensembl reference (.duckdb/parquet dir); routes to "
             "just-dna-enricher. Prefer producing resolution.csv with `just-dna-enricher enrich`.",
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
        manifest = result.manifest
        typer.secho(f"compiled: {output_dir}", fg=typer.colors.GREEN)
        typer.echo(f"digest: {manifest.artifact.digest if manifest else '?'}")
        typer.echo(f"content_signature: {manifest.content_signature if manifest else '?'}")
        if manifest is not None:
            comp = manifest.compilation
            typer.echo(f"resolution_mode: {comp.resolution_mode}  fully_resolved: {comp.fully_resolved}")
            if comp.resolution_signature is not None:
                typer.echo(f"resolution_signature: {comp.resolution_signature}")
    else:
        typer.secho(f"COMPILE FAILED: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def signature(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
) -> None:
    """Print the content signature of a spec's raw authored data — no compile, no Ensembl.

    Name- and reference-independent, so a client can compute it and dedup against a registry without
    recompiling (surviving metadata-strip and a recompile against a different reference)."""
    typer.echo(content_signature(spec_dir))


@app.command()
def verify(
    module_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Compiled module directory (holding manifest.json)"
    ),
    require_marketplace: bool = typer.Option(
        True,
        "--require-marketplace/--no-require-marketplace",
        help="Demand compile_success and compiled_by=marketplace-server. Off for a local artifact.",
    ),
    public_key: Optional[str] = typer.Option(
        None, "--public-key", help="Base64 raw Ed25519 key the manifest signature MUST verify against."
    ),
    check_inputs: bool = typer.Option(False, "--check-inputs", help="Also hash the declared inputs[]."),
    check_logs: bool = typer.Option(False, "--check-logs", help="Also hash any logs[] present on disk."),
    check_provenance: bool = typer.Option(
        False, "--check-provenance", help="Also hash the provenance document, if declared and present."
    ),
    check_logo: bool = typer.Option(False, "--check-logo", help="Also hash the logo, if declared."),
) -> None:
    """Verify a compiled module against its manifest (SPEC §5 verify-then-install). Exit 1 on failure.

    The verify-only path the format has always specified and never exposed: `verify_manifest` and the
    signature check live in `just-dna-format`, which ships no CLI of its own (Typer would breach its
    pydantic-plus-cryptography dependency floor), so until now a consumer had to write Python to check
    a download. It re-hashes every artifact file, recomputes `artifact.digest` over the set, and — when
    a key is pinned — verifies the Ed25519 signature over that digest.
    """
    manifest_path = module_dir / "manifest.json"
    if not manifest_path.is_file():
        typer.secho(f"no manifest.json in {module_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    manifest = read_manifest(manifest_path)
    try:
        verify_manifest(
            module_dir,
            manifest,
            require_marketplace=require_marketplace,
            check_inputs=check_inputs,
            check_logs=check_logs,
            check_provenance=check_provenance,
            check_logo=check_logo,
            public_key=public_key,
        )
    except IntegrityError as exc:
        typer.secho(f"VERIFY FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"verified: {module_dir}", fg=typer.colors.GREEN)
    typer.echo(f"digest: {manifest.artifact.digest}  files: {len(manifest.artifact.files)}")
    # Say which of the three trust questions were actually answered — an unsigned artifact that
    # verifies is a weaker statement than a signed one, and reporting them alike would blur that.
    typer.echo(
        f"signature: {'verified against the pinned key' if public_key else
                      ('present, self-consistent only' if manifest.signature else 'absent')}"
    )


@app.command()
def sign(
    module_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Compiled module directory (holding manifest.json)"
    ),
    private_key: Path = typer.Option(
        ..., "--private-key", exists=True, dir_okay=False, help="Ed25519 private key PEM."
    ),
) -> None:
    """Sign a compiled module's `artifact.digest` and write the signature into its manifest.json.

    Signs the digest, never the files directly: the digest is already a Merkle root over the whole
    file set, so one signature covers every artifact byte, and re-signing after any edit is impossible
    to forget — the digest moves and the old signature stops verifying.
    """
    manifest_path = module_dir / "manifest.json"
    if not manifest_path.is_file():
        typer.secho(f"no manifest.json in {module_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    manifest = read_manifest(manifest_path)
    manifest.signature = sign_digest(manifest.artifact.digest, private_key.read_bytes())
    write_manifest(manifest, manifest_path)
    typer.secho(f"signed: {manifest_path}", fg=typer.colors.GREEN)
    typer.echo(f"digest: {manifest.artifact.digest}")
    typer.echo(f"public key: {manifest.signature.public_key}")


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
    resolution: bool = typer.Option(
        True, "--resolution/--no-resolution",
        help="Also emit resolution.csv (the resolved facts), so reverse→compile is fully offline.",
    ),
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
        write_resolution=resolution,
    )
    typer.secho(f"reversed: {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()

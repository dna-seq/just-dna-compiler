"""Whole-module commands: `enrich-and-compile` and `upload` (RM260 split this out of the former
single-file `cli.py`).
"""

from pathlib import Path

import typer
from just_dna_compiler.compiler import compile_module

from just_dna_enricher.cli._shared import _mode, app
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.frequencies import FrequencyEnrichmentError, enrich_frequencies
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, enrich_gene_metrics


@app.command("enrich-and-compile")
def enrich_and_compile(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for parquet + manifest.json"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Path | None = typer.Option(
        None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."
    ),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
    use_clinvar: bool = typer.Option(
        True, "--clinvar/--no-clinvar", help="Use the ClinVar link (after the Ensembl cache)."
    ),
    use_gnomad: bool = typer.Option(
        True, "--gnomad/--no-gnomad", help="Use the gnomAD link (last, after live Ensembl)."
    ),
    frequencies: bool = typer.Option(
        False, "--frequencies", help="Also run the frequency pass (writes frequencies.csv)."
    ),
    gene_metrics: bool = typer.Option(
        False, "--gene-metrics", help="Also run the gene-constraint pass (writes gene_metrics.csv)."
    ),
) -> None:
    """Enrich, then compile from the produced resolution.csv (offline, deterministic). Exit 1 on failure."""
    try:
        enrich(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            ensembl_cache=ensembl_cache,
            clinvar_cache=clinvar_cache,
            use_clinvar=use_clinvar,
            use_gnomad=use_gnomad,
        )
        # The sidecar passes run between enrich and compile so one command produces every input the
        # compile then consumes. Each is opt-in: a frequency pass costs real requests against a
        # 10-per-minute budget, so it must never be something a plain compile does by surprise.
        if frequencies:
            enrich_frequencies(spec_dir, mode=_mode(strict), offline=offline)
        if gene_metrics:
            enrich_gene_metrics(spec_dir, mode=_mode(strict), offline=offline)
    except (EnrichmentError, FrequencyEnrichmentError, GeneMetricsEnrichmentError) as exc:
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


@app.command("upload")
def upload_(
    module_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Compiled module directory (at least one annotation parquet + manifest.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/annotators.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help=(
            "Module name under data/<name>/ (and data/<name>/v<version>/) in the repo. "
            "Default: the directory basename."
        ),
    ),
    commit_message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Commit message. Default: 'Add <name> module'.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be uploaded without contacting HuggingFace.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Overwrite data/<name>/v<version>/ even when it already holds a different artifact. "
            "Without this the publish refuses; the flat path is always overwritten."
        ),
    ),
) -> None:
    """Upload a compiled module to a HuggingFace dataset collection (publisher/dev surface).

    Writes data/<name>/, which keeps meaning "latest", and — when the
    manifest states a version — data/<name>/v<version>/ under it, in
    that order, as two commits. With no version, the flat path alone,
    and the reason why.

    Refuses when the versioned path already holds a different artifact
    (compare by artifact.digest), unless --force. The flat path means
    latest and is overwritten either way.
    """
    from just_dna_enricher.upload import PublishCollisionError, plan_upload, upload_module

    module_name = name or module_dir.name
    if dry_run:
        plan = plan_upload(module_dir, module_name, repo_id)
        typer.echo(f"Would upload to {plan.repo_id} at {plan.path_in_repo}/:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        if plan.versioned_path_in_repo is not None:
            typer.echo(f"…and the same files to {plan.versioned_path_in_repo}/")
        else:
            typer.secho(
                f"no versioned copy: {plan.version_unknown_reason}",
                fg=typer.colors.YELLOW,
                err=True,
            )
        return

    try:
        plan = upload_module(
            module_dir,
            module_name,
            repo_id=repo_id,
            commit_message=commit_message,
            force=force,
        )
    except PublishCollisionError as exc:
        # Its own branch, and its own word: this module is publishable and the remote already has
        # this version. "UPLOAD FAILED" beside the three `plan_upload` refusals would read as
        # "your module is broken", which is the opposite of what happened.
        typer.secho(f"ALREADY PUBLISHED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"UPLOAD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"uploaded: {module_name} → {plan.repo_id}/{plan.path_in_repo} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )
    if plan.versioned_path_in_repo is not None:
        typer.secho(
            f"uploaded: {module_name} → {plan.repo_id}/{plan.versioned_path_in_repo} "
            f"({len(plan.files)} files)",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"no versioned copy: {plan.version_unknown_reason}",
            fg=typer.colors.YELLOW,
            err=True,
        )

"""The `opentargets` group: build the Open Targets Platform snapshot lane, and fill a module from it (RM333)."""

import shutil
from pathlib import Path

import typer

from just_dna_enricher.cli._shared import _use
from just_dna_enricher.licensing import sidecar_path
from just_dna_enricher.locations import repro_out
from just_dna_enricher.opentargets import OWNED_TABLES, OpenTargetsError, enrich_opentargets, summarise
from just_dna_enricher.opentargets_build import (
    DEFAULT_OPENTARGETS_BASE_URL,
    OPENTARGETS_RELEASE,
    OpenTargetsBuildError,
    build_snapshot,
    download_release,
)

opentargets_app = typer.Typer(
    add_completion=False,
    help=(
        "The Open Targets Platform lane (RM333): locus-to-gene scores, colocalisations, per-transcript "
        "consequences and fine-mapping posteriors, from one pinned, CC0-marked release."
    ),
    no_args_is_help=True,
)


@opentargets_app.command("build")
def opentargets_build_(
    source: Path | None = typer.Option(
        None,
        "--source",
        exists=True,
        file_okay=False,
        help=(
            "A directory already holding the release's parts as `<dataset>/part-*.parquet` (and "
            "`croissant.json`). Omit to download them into `<out>/source/`."
        ),
    ),
    parts: int | None = typer.Option(
        None,
        "--parts",
        min=1,
        help=(
            "Download only the first N parts of each dataset, for a test-sized build. The snapshot "
            "records what it read against the total, and the pass warns that it is partial."
        ),
    ),
    release: str = typer.Option(
        OPENTARGETS_RELEASE, "--release", help="The Platform release directory to pin."
    ),
    out: Path = typer.Option(
        repro_out("opentargets"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/*.parquet + release.json).",
    ),
) -> None:
    """Download (or read) one Open Targets Platform release and flatten it into the lane's snapshot.

    The full release this lane reads is about 22 GB of parquet over EBI's FTP (coloc alone is 16.5 GB),
    and it trims to a few GB: GWAS credible sets and their members, the L2G scores, the GWAS × molecular-QTL
    colocalisations and every variant's per-transcript consequences. No row is dropped for its value.
    """
    try:
        mirror = source
        if mirror is None:
            # One directory per release, so a rebuild under a new pin never reads the old one's parts.
            mirror = out / "source" / release
            download_release(mirror, release=release, base_url=DEFAULT_OPENTARGETS_BASE_URL, parts=parts)
        elif parts is not None:
            raise typer.BadParameter(
                "--parts limits a download; with --source the parts already on disk are what is read."
            )
        result = build_snapshot(mirror, out, release=release)
        if source is None:
            # The mirror is ~22 GB and the snapshot a few: what was downloaded is dropped once the
            # snapshot (and its source digest) is written. `--source` parts are the operator's, kept.
            shutil.rmtree(out / "source")
    except (OpenTargetsBuildError, FileNotFoundError, ImportError, OSError) as exc:
        typer.secho(f"OPEN TARGETS BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"snapshot: {result.out_dir}", fg=typer.colors.GREEN)
    typer.echo(", ".join(f"{name} {count}" for name, count in result.row_counts.items()))
    partial = {
        name: (got, result.parts_total[name])
        for name, got in result.parts_read.items()
        if name in result.parts_total and got < result.parts_total[name]
    }
    if partial:
        typer.secho(
            "  partial: " + ", ".join(f"{n} {got} of {total} parts" for n, (got, total) in partial.items()),
            fg=typer.colors.YELLOW,
        )


@opentargets_app.command("enrich")
def opentargets_enrich_(
    spec: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        exists=True,
        file_okay=False,
        help="The built snapshot. Omit to use $JUST_DNA_OPENTARGETS_CACHE, then the cache base.",
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Refuse a partial snapshot (one built from some of a dataset's parts)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be written without writing it."),
    use: str = typer.Option(
        "unstated",
        "--use",
        help="Declared use recorded on the licence rows: unstated|non-commercial|commercial.",
    ),
) -> None:
    """Fill locus_to_gene.csv, colocalisations.csv, consequences.csv and RM239's posterior on gwas_effects.csv.

    Reads only the provisioned snapshot, so it never fetches and needs no --offline: with no snapshot
    it says so and writes nothing. Coordinates come from resolution.csv, so run `enrich` first.
    """
    try:
        result = enrich_opentargets(
            spec,
            mode="strict" if strict else "best_effort",
            write=not dry_run,
            snapshot=snapshot,
            declared_use=_use(use),
        )
    except OpenTargetsError as exc:
        typer.secho(f"OPEN TARGETS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped:
        typer.secho(f"skipped: {result.skipped}", fg=typer.colors.YELLOW)
        return
    summary = summarise(result)
    for csv_name, _model, _layer in OWNED_TABLES:
        typer.echo(
            f"{sidecar_path(spec, csv_name, error=OpenTargetsError)}: {summary[csv_name.removesuffix('.csv')]} row(s)"
        )
    typer.echo(
        f"dataset: {summary['dataset']}  asked: {summary['asked']}  not in release: "
        f"{summary['not_in_release']}  not read (snapshot not whole): {summary['not_read']}  off build: "
        f"{summary['off_build']}  allele-ambiguous: "
        f"{summary['allele_ambiguous']}"
    )
    typer.echo(
        f"rows stating no ALT: allele supplied by the release {summary['allele_supplied']}  withheld "
        f"(several candidate alleles) {summary['allele_unstated_withheld']}  no rsID "
        f"{summary['allele_unstated_no_rsid']}  not asked (snapshot without rsIDs) "
        f"{summary['allele_unstated_unasked']}"
    )
    typer.echo(
        "posterior on gwas_effects.csv: "
        + ", ".join(f"{name.replace('_', ' ')} {n}" for name, n in summary["posterior"].items())
    )

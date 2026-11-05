"""ClinVar-GKM: the `clinvar-gkm` group — build the indel witness, ask whether it is current, look one up
(RM305). Its own group rather than a `clinvar` subcommand, because it is ClinGen's transformation under
its own `SourceRow`, not a second surface of ClinVar.
"""

from pathlib import Path

import typer

from just_dna_enricher.clinvar_gkm import (
    ClinVarGkmClient,
    ClinVarGkmError,
    ClinVarGkmWitness,
    lane_currency,
    parse_manifest,
)
from just_dna_enricher.clinvar_gkm_build import build_snapshot, download_and_build
from just_dna_enricher.locations import repro_out, resolve_clinvar_gkm_reference

clinvar_gkm_app = typer.Typer(
    add_completion=False,
    help=(
        "ClinGen's ClinVar-GKM, cut to its indels: an offline witness for where an indel sits. CC0, "
        "so a deployment may publish it (`cache rebuild --only clinvar_gkm --publish`)."
    ),
    no_args_is_help=True,
)


@clinvar_gkm_app.command("build")
def clinvar_gkm_build_(
    out: Path = typer.Option(
        repro_out("clinvar_gkm"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/*.parquet, LICENSE.txt and release.json).",
    ),
    allele: Path | None = typer.Option(
        None, "--allele", exists=True, dir_okay=False, help="An allele.parquet you already hold."
    ),
    variation: Path | None = typer.Option(
        None, "--variation", exists=True, dir_okay=False, help="A variation.parquet you already hold."
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        exists=True,
        dir_okay=False,
        help="The parquet/manifest.json the two files are verified against. Required with --allele/--variation.",
    ),
    keep_downloads: bool = typer.Option(
        False, "--keep-downloads", help="Keep the ~5 GB of downloaded Parquet under <out>/_downloads."
    ),
) -> None:
    """Download ClinVar-GKM's allele and variation Parquet whole, verify both against the set's
    manifest, and keep the net insertions and deletions on GRCh38 with their VRS id, VCF spelling,
    ClinVar variation and rsID.

    The source overwrites its one Parquet set every week, so the snapshot pins `(source_release,
    sha256)` and a file that does not match the manifest is refused. With local files, all three of
    --allele, --variation and --manifest are needed: a file with nothing to verify it against cannot
    be labelled with a release.
    """
    local = (allele, variation, manifest)
    try:
        if any(path is not None for path in local):
            if allele is None or variation is None or manifest is None:
                typer.secho(
                    "--allele, --variation and --manifest go together: two Parquet files and the "
                    "manifest that verifies them",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)
            result = build_snapshot(
                allele,
                variation,
                out,
                manifest=parse_manifest(manifest.read_text(encoding="utf-8")),
                source_url={"allele.parquet": None, "variation.parquet": None},
            )
        else:
            result = download_and_build(out, keep_downloads=keep_downloads)
    except (ClinVarGkmError, ImportError, OSError) as exc:
        typer.secho(f"CLINVAR-GKM BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.witness_file}", fg=typer.colors.GREEN)
    typer.echo(
        f"  {result.row_count} indel rows from {result.counts.alleles} alleles, "
        f"{result.with_rsid} with an rsID ({result.distinct_rsids} distinct), dataset {result.dataset}"
    )
    if result.source_lags:
        typer.secho(
            f"  the source's newest weekly release is {result.latest_release}; its Parquet set still "
            f"holds {result.source_release}",
            fg=typer.colors.YELLOW,
            err=True,
        )


def _snapshot_or_exit(snapshot: Path | None) -> Path:
    found = snapshot or resolve_clinvar_gkm_reference()
    if found is None:
        typer.secho(
            "no ClinVar-GKM snapshot found: build one with `clinvar-gkm build`, or `cache pull clinvar_gkm`",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    return found


@clinvar_gkm_app.command("currency")
def clinvar_gkm_currency_(
    snapshot: Path | None = typer.Argument(
        None, exists=True, file_okay=False, help="Snapshot directory (default: the resolved cache)."
    ),
) -> None:
    """Ask the source whether the snapshot is current. Three answers, kept apart: a newer Parquet set
    exists (rebuild), the set was overwritten under the same release (rebuild), or the set itself
    lags the newest weekly release (nothing to do but wait). Exits 1 only when a rebuild would help."""
    found = _snapshot_or_exit(snapshot)
    currency = lane_currency(found, client=ClinVarGkmClient())
    typer.echo(f"snapshot {found}: {currency.pinned_release or 'release unstated'}")
    lines = currency.sentences()
    for line in lines:
        typer.echo(f"  {line}")
    if not lines:
        typer.echo(f"  current: the source's Parquet set is {currency.published_release}")
    if currency.behind or currency.drifted:
        raise typer.Exit(code=1)


@clinvar_gkm_app.command("lookup")
def clinvar_gkm_lookup_(
    key: str = typer.Argument(..., help="A VRS id, an rsID, or a one-ALT chrom:start:ref:alt key."),
    snapshot: Path | None = typer.Option(None, "--snapshot", exists=True, file_okay=False),
) -> None:
    """Where the witness places one allele. Nothing found means not witnessed, never placed wrong."""
    try:
        witness = ClinVarGkmWitness.load(_snapshot_or_exit(snapshot))
    except ClinVarGkmError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    try:
        rows = witness.lookup(key)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    if not rows:
        typer.echo(f"{key}: not witnessed by {witness.dataset or 'this snapshot'} (indels only)")
        return
    for row in rows:
        typer.echo(
            f"{row.vrs_id}  {row.vcf_key}  spdi {row.spdi}  {row.clinvar_variation_id or '-'}  "
            f"{row.rsid or '-'}  ({row.state_type})"
        )
    typer.echo(f"ids minted under VRS {witness.vrs_version} (declared, not measured)")

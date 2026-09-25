"""ClinVar and its ClinVar-shaped sibling PubMind: the `clinvar` and `pubmind` groups (RM260 split this
out of the former single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.clinvar_build import DEFAULT_CITATIONS_URL, build_citations, download_var_citations
from just_dna_enricher.locations import CITATIONS_DIRNAME, RELEASE_FILENAME, repro_out
from just_dna_enricher.pubmind_build import PubMindBuildError, download_pubmind_table
from just_dna_enricher.pubmind_build import build_snapshot as build_pubmind_snapshot

clinvar_app = typer.Typer(
    add_completion=False,
    help="Build and publish the ClinVar reference snapshot (publisher/dev surface).",
    no_args_is_help=True,
)


@clinvar_app.command("build")
def clinvar_build_(
    vcf: Path | None = typer.Option(
        None,
        "--vcf",
        exists=True,
        dir_okay=False,
        help="Local ClinVar VCF (.vcf.gz). Omit and pass --download to fetch from NCBI.",
    ),
    download: bool = typer.Option(
        False,
        "--download",
        help="Download the NCBI ClinVar GRCh38 VCF into --out first.",
    ),
    out: Path = typer.Option(
        repro_out("clinvar"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/*.parquet + release.json).",
    ),
) -> None:
    """Convert a ClinVar VCF into the per-chromosome parquet snapshot the resolver reads."""
    from just_dna_enricher.clinvar_build import build_snapshot, download_clinvar_vcf

    if vcf is None and not download:
        typer.secho("Provide --vcf PATH or --download.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    try:
        source_vcf = vcf if vcf is not None else download_clinvar_vcf(out / "clinvar.vcf.gz")
        result = build_snapshot(source_vcf, out)
    except (FileNotFoundError, ImportError) as exc:
        typer.secho(f"BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.out_dir}", fg=typer.colors.GREEN)
    typer.echo(
        f"records: {result.record_count}  chromosomes: {len(result.chromosomes)}  "
        f"clinvar_file_date: {result.clinvar_file_date}"
    )
    typer.secho(
        f"  skipped: non-ACGT {result.skipped_non_acgt}, too-long {result.skipped_too_long}, "
        f"off-target chrom {result.skipped_bad_chrom}",
        fg=typer.colors.YELLOW,
    )


@clinvar_app.command("publish")
def clinvar_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/clinvar.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be uploaded. Reads the repo's file list; uploads nothing.",
    ),
) -> None:
    """Create-or-update the dataset repo and upload the built ClinVar snapshot (publisher/dev)."""
    from just_dna_enricher.upload import (
        OrphanedSidecarError,
        check_publish_orphans_no_sidecar,
        plan_reference_snapshot,
        publish_reference_snapshot,
    )

    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, repo_id)
        # A rehearsal that skips the check the real thing refuses on is a different operation. This
        # is the one command that can reach the published ClinVar repo from a snapshot built without
        # its citations half, so the dry run reads the repo rather than promising a refused publish.
        try:
            check_publish_orphans_no_sidecar(plan)
        except OrphanedSidecarError as exc:
            typer.secho(f"WOULD BE REFUSED: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Would upload to {plan.repo_id}:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        return
    try:
        plan = publish_reference_snapshot(snapshot_dir, repo_id, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError, OrphanedSidecarError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


pubmind_app = typer.Typer(
    add_completion=False,
    help=("Build the PubMind literature-derived snapshot. Operator-built and inject-only; never published."),
    no_args_is_help=True,
)


#: The refusal `pubmind publish` prints. Pinned by a test because a refusal's *reason* is the whole
#: value of a command that exists in order to say no (`@warning-text-is-api`).
PUBMIND_PUBLISH_REFUSAL = (
    "pubmind publish is refused by design. The ANNOVAR-distributed PubMind table states no data "
    "terms of its own: CHOP's LICENSE.md covers the software (academic, non-commercial), the paper "
    "is CC BY-NC-ND 4.0, and nobody publishes a licence for those bytes. An unestablished permission "
    "is not a permission, so a bulk file arriving under terms we cannot establish is not a file we "
    "may pass on — the same rule that leaves PharmVar's snapshot unpublishable. Build your own with "
    "`pubmind build` and point at it with $JUST_DNA_PUBMIND_CACHE. Lifting this needs an answer from "
    "WGLab and CHOP's Office of Technology Transfer, in writing, not a flag."
)


@pubmind_app.command("build")
def pubmind_build_(
    table: Path | None = typer.Option(
        None,
        "--table",
        exists=True,
        dir_okay=False,
        help="Local hg38_pubmind_db.txt.gz. Omit and pass --download to fetch it from ANNOVAR.",
    ),
    download: bool = typer.Option(
        False,
        "--download",
        help="Download the ANNOVAR-distributed PubMind table into --out first.",
    ),
    out: Path = typer.Option(
        repro_out("pubmind"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/pubmind.parquet + release.json).",
    ),
) -> None:
    """Reduce the ANNOVAR-distributed PubMind table to the parquet snapshot the checks read.

    **There is no `--use` flag, and its absence is the design.** PubMind's data terms could not be
    established, and unknown terms warn rather than gate (`commercial_use=None` never taints a
    module). A declared-use gate here would refuse every build unconditionally, and a flag feeding a
    gate that never gates is a flag that does nothing. What the unknown terms do gate is *publishing*
    a snapshot or a module carrying these bytes — see `pubmind publish`, which refuses.
    """
    if table is None and not download:
        typer.secho("Provide --table PATH or --download.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    fetched = None
    # `PubMindBuildError` covers the download too: it translates `httpx` into `PubMindUnavailable`, a
    # subclass, so this one arm catches a moved bulk URL as well as a malformed table. Without that,
    # ANNOVAR rotating the file — the rot the source's own lack of a cadence invites — printed a
    # traceback instead of this line.
    try:
        if table is None:
            fetched = download_pubmind_table(out / "hg38_pubmind_db.txt.gz")
        result = build_pubmind_snapshot(
            fetched.path if fetched is not None else table,
            out,
            source_url=fetched.url if fetched is not None else None,
            source_sha256=fetched.sha256 if fetched is not None else None,
            source_etag=fetched.etag if fetched is not None else None,
            source_last_modified=fetched.last_modified if fetched is not None else None,
        )
    except (FileNotFoundError, ImportError, PubMindBuildError) as exc:
        typer.secho(f"PUBMIND BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"pubmind snapshot: {result.parquet_file}", fg=typer.colors.GREEN)
    typer.echo(
        f"kept: {result.record_count} of {result.input_rows} row(s)  "
        f"dataset: {result.dataset}  "
        + "  ".join(f"{name}: {count}" for name, count in sorted(result.derivations.items()))
    )
    typer.secho(
        "  dropped: " + ", ".join(f"{name} {count}" for name, count in result.dropped.items()),
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        f"  {result.multi_pvid_keys} of {result.allele_keys} coordinate(s) carry several PVIDs "
        f"(worst {result.max_pvids_per_key}), and {result.contested_keys} of those disagree. Every "
        f"PVID is kept as its own row: choosing a winner would be an ordering nobody defined.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        "  data terms unestablished: operator-built and inject-only, never published.",
        fg=typer.colors.YELLOW,
    )


@pubmind_app.command("publish")
def pubmind_publish_() -> None:
    """Refuse to publish the PubMind snapshot, and say why.

    The command exists in order to refuse. A missing one reads as an oversight somebody will helpfully
    add, and the reason belongs where a reader looks for it rather than only in a design document.
    """
    typer.secho(f"REFUSED: {PUBMIND_PUBLISH_REFUSAL}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@clinvar_app.command("citations")
def clinvar_citations_(
    out: Path = typer.Option(..., "--out", file_okay=False, help="Existing ClinVar snapshot dir."),
    citations_txt: Path | None = typer.Option(
        None, "--citations", exists=True, dir_okay=False, help="Local var_citations.txt."
    ),
    download: bool = typer.Option(False, "--download", help="Fetch var_citations.txt first."),
    url: str = typer.Option(DEFAULT_CITATIONS_URL, "--url", help="Source for --download."),
) -> None:
    """Add ClinVar's literature links to a snapshot: `data/citations.parquet` (\\[dev], needs polars).

    Separate from `clinvar build` because ClinVar publishes citations separately from the VCF — which
    is precisely why a drafted gene panel could not compile without this: `studies.csv` is mandatory
    and the VCF carries no PMIDs. Written beside the snapshot, so an existing cache keeps its bytes.
    """
    if citations_txt is None and not download:
        typer.secho("give --citations, or --download", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    source_sha: str | None = None
    if citations_txt is None:
        path, source_sha = download_var_citations(out / "var_citations.txt", url=url)
    else:
        path = citations_txt
    try:
        result = build_citations(path, out, source_url=url, source_sha256=source_sha)
    except (ImportError, RuntimeError) as exc:
        typer.secho(f"CITATIONS BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"wrote {result.row_count} PubMed citation link(s) under {out / CITATIONS_DIRNAME}",
        fg=typer.colors.GREEN,
    )
    if result.release_updated:
        # ClinVar publishes citations on its own cadence, so a snapshot can carry two releases — the
        # block says which, and `clinvar publish` now ships the table with the data.
        typer.echo(f"  recorded the citations provenance in {out / RELEASE_FILENAME}")
    else:
        typer.secho(
            f"  could not record the citations provenance in {out / RELEASE_FILENAME} — the snapshot "
            f"will not say which citations release it carries",
            fg=typer.colors.YELLOW,
            err=True,
        )

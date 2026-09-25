"""The `mitomap` group: build, miss and publish (RM260 split this out of the former single-file
`cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.locations import read_release, repro_out
from just_dna_enricher.mitomap import MitomapError
from just_dna_enricher.mitomap_build import DEFAULT_MITOMAP_URL
from just_dna_enricher.upload import DEFAULT_MITOMAP_REPO_ID

mitomap_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the MITOMAP snapshot and the derived miss lane. CC BY 3.0 with commercial use stated "
        "free, so a deployment may publish the snapshot."
    ),
    no_args_is_help=True,
)


@mitomap_app.command("build")
def mitomap_build_(
    out: Path = typer.Option(
        repro_out("mitomap"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/mitomap-*.parquet + release.json).",
    ),
    dump: Path | None = typer.Option(
        None,
        "--dump",
        exists=True,
        dir_okay=False,
        help=(
            "A mitomap.dump.sql.gz you already have. Without it the dump is downloaded — the data "
            "surface answers plain curl, unlike the web surface. A local dump carries no "
            "Last-Modified, so that snapshot is honestly unlabelled."
        ),
    ),
    url: str = typer.Option(
        DEFAULT_MITOMAP_URL,
        "--url",
        help="Source URL for the dump (used only when --dump is absent).",
    ),
) -> None:
    """Cut the two curated mtDNA variant tables, their citations and the references out of the dump.

    602 `mmutation` rows and 494 `rtmutation` rows out of 6.76 million lines. The snapshot records
    every count this build computes — rows per table, the dump's own per-table edit dates, how much of
    `reference.nlmid` is a PMID, the alleles that cannot be spelled as VCF and the brackets that are
    not a documented VCEP class — because a number computed and dropped is one every reader has to
    recompute.
    """
    from just_dna_enricher.mitomap_build import (
        build_snapshot,
        download_mitomap_dump,
    )

    try:
        if dump is not None:
            result = build_snapshot(dump, out, source_url=f"file://{dump.resolve()}")
        else:
            fetched = download_mitomap_dump(out / "mitomap.dump.sql.gz", url)
            result = build_snapshot(
                fetched.path,
                out,
                source_url=fetched.url,
                source_sha256=fetched.sha256,
                source_last_modified=fetched.last_modified,
            )
    except (MitomapError, ImportError, OSError) as exc:
        typer.secho(f"MITOMAP BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.out_dir}", fg=typer.colors.GREEN)
    for name, count in result.rows.items():
        typer.echo(
            f"  {name} {count} rows, curated through {result.edit_dates.get(name) or 'an undated pass'}"
        )
    typer.echo(
        f"  {result.citation_links} citation links from {result.reference_rows} references "
        f"({result.references_without_nlmid} state no nlmid, "
        f"{result.references_not_a_pmid} state something that is not a PMID)"
    )
    if result.unmintable:
        typer.echo(
            "  alleles that cannot be spelled as VCF: "
            + ", ".join(f"{reason} {count}" for reason, count in result.unmintable.items())
        )
    if result.withheld_brackets:
        typer.secho(
            "  brackets withheld as undocumented (never mapped onto clin_sig): "
            + ", ".join(f"{token} {count}" for token, count in result.withheld_brackets.items()),
            fg=typer.colors.YELLOW,
        )
    if result.dataset:
        typer.echo(f"  release {result.dataset}")
    else:
        typer.secho(
            "  the dump states no edit_date for one of its variant tables, so this snapshot has no "
            "release label and the miss lane built from it cannot name the MITOMAP release it "
            "compared",
            fg=typer.colors.YELLOW,
            err=True,
        )


@mitomap_app.command("miss")
def mitomap_miss_(
    out: Path = typer.Option(
        repro_out("mitomap_miss"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/mitomap_miss.parquet + release.json).",
    ),
    mitomap_cache: Path | None = typer.Option(
        None,
        "--mitomap-cache",
        exists=True,
        file_okay=False,
        help="Built MITOMAP snapshot (see `mitomap build`). Omit it and $JUST_DNA_MITOMAP_CACHE is used.",
    ),
    clinvar_cache: Path | None = typer.Option(
        None,
        "--clinvar-cache",
        exists=True,
        file_okay=False,
        help="Built ClinVar snapshot (see `clinvar build`). Omit it and $JUST_DNA_CLINVAR_CACHE is used.",
    ),
) -> None:
    """Join MITOMAP against the ClinVar chrMT parquet and write the increment (RM171).

    **A derived lane, not a download.** Its acquire stage is both parents being on disk, and a parent
    that is absent is reported as could-not-run rather than as an empty increment — a miss set
    computed without ClinVar would say MITOMAP publishes a thousand alleles nobody else has, from a
    comparison that never ran.

    Exact `(start, ref, alt)` on chrMT, upper-cased both sides, no position-level fallback. Four
    buckets, and `draft-panel --source mitomap-miss` writes only one of them.
    """
    from just_dna_enricher.mitomap_miss_build import build_miss_snapshot

    parents = {}
    missing = []
    for name, explicit in (("mitomap", mitomap_cache), ("clinvar", clinvar_cache)):
        found = explicit or LANES_BY_NAME[name].resolve()
        if found is None:
            missing.append(name)
        else:
            parents[name] = found
    if missing:
        typer.secho(
            f"MITOMAP MISS NOT RUN: derived from mitomap and clinvar, and "
            f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not on disk. Provision "
            f"with `cache prepare --only {' --only '.join(missing)}`, or name one with "
            f"--mitomap-cache/--clinvar-cache. An increment computed without a parent is not an "
            f"empty increment.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        result = build_miss_snapshot(parents["mitomap"], parents["clinvar"], out)
    except (MitomapError, ImportError, OSError) as exc:
        typer.secho(f"MITOMAP MISS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.parquet_file}", fg=typer.colors.GREEN)
    for table, counts in result.buckets_by_table.items():
        typer.echo(f"  {table}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    typer.echo(
        f"  against {result.clinvar_keys} distinct ClinVar chrMT alleles "
        f"({result.parents['clinvar'].get('clinvar_file_date') or 'an undated snapshot'})"
    )
    if result.rated_miss_by_class:
        typer.echo(
            "  rated misses by class: " + ", ".join(f"{k} {v}" for k, v in result.rated_miss_by_class.items())
        )
    if result.rated_miss_indels:
        typer.secho(
            f"  {result.rated_miss_indels} of {result.rated_misses} rated miss(es) key on an indel. "
            f"The join is exact and neither side is left-aligned here, so one of those is an "
            f"absence or a difference of anchor and this lane cannot tell you which.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    if result.withheld_in_miss:
        typer.secho(
            "  missing rows whose only rating is an undocumented bracket, counted and never mapped: "
            + ", ".join(f"{k} {v}" for k, v in result.withheld_in_miss.items()),
            fg=typer.colors.YELLOW,
        )
    if result.unmintable:
        typer.echo(
            "  rows the join has no key for (Principle 2 forbids fetching the rCRS anchor): "
            + ", ".join(f"{k} {v}" for k, v in result.unmintable.items())
        )


@mitomap_app.command("publish")
def mitomap_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/ + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_MITOMAP_REPO_ID,
        "--repo",
        help="Target HuggingFace dataset repo (owner/name).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be uploaded; send nothing."),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Create-or-update the dataset repo and upload the built MITOMAP snapshot (publisher/dev).

    Publishable on the source's own terms: CC BY 3.0, with commercial and clinical use stated free and
    attribution the one condition — which the snapshot's `SourceRow` carries. **Only the parent lane
    publishes.** The derived miss snapshot pins two parent digests, so a pulled copy would be an
    increment whose own currency check cannot be run by whoever pulled it; it is rebuilt locally from
    the parents instead, which is cheaper than the download and cannot be stale.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    if not (read_release(snapshot_dir) or {}).get("dataset"):
        typer.secho(
            "  this snapshot carries no release label (it was built from a local dump), so everyone "
            "who pulls it inherits a comparison that cannot name its own MITOMAP release.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    try:
        if dry_run:
            plan = plan_reference_snapshot(snapshot_dir, repo)
            typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
            return
        plan = publish_reference_snapshot(snapshot_dir, repo, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )

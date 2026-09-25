"""Gene-level reference snapshots: `gnomad constraint` and `mane` (RM260 split this out of the former
single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.locations import repro_out

# ── gnomAD constraint snapshot (build + publish, publisher/dev surface) ─────────────────────────

gnomad_app = typer.Typer(
    add_completion=False,
    help="Build and publish the gnomAD gene-constraint snapshot (publisher/dev surface).",
    no_args_is_help=True,
)


constraint_app = typer.Typer(
    add_completion=False,
    help="The gene-level constraint snapshot the gene-metrics pass reads offline.",
    no_args_is_help=True,
)


gnomad_app.add_typer(constraint_app, name="constraint")


@constraint_app.command("build")
def constraint_build_(
    tsv: Path | None = typer.Option(
        None,
        "--tsv",
        exists=True,
        dir_okay=False,
        help="Local gnomAD constraint metrics TSV. Omit and pass --download to fetch it.",
    ),
    download: bool = typer.Option(
        False,
        "--download",
        help="Download the gnomAD v4.1 constraint TSV (95.5 MB) into --out first.",
    ),
    out: Path = typer.Option(
        repro_out("gnomad_constraint"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/gnomad_constraint.parquet + release.json).",
    ),
) -> None:
    """Reduce the per-transcript constraint TSV to the gene-level parquet the resolver reads."""
    from just_dna_enricher.constraint_build import build_snapshot, download_constraint_tsv

    if tsv is None and not download:
        typer.secho("Provide --tsv PATH or --download.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    try:
        source = (
            tsv if tsv is not None else download_constraint_tsv(out / "gnomad.v4.1.constraint_metrics.tsv")
        )
        result = build_snapshot(source, out)
    except (FileNotFoundError, ImportError) as exc:
        typer.secho(f"BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.out_dir}", fg=typer.colors.GREEN)
    typer.echo(f"genes: {result.gene_count}  from transcript rows: {result.source_rows}")
    if result.unresolved_genes:
        typer.secho(
            f"  dropped (no MANE/canonical Ensembl row): {len(result.unresolved_genes)}",
            fg=typer.colors.YELLOW,
        )


@constraint_app.command("publish")
def constraint_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/gnomad_constraint.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be uploaded without contacting HuggingFace.",
    ),
) -> None:
    """Create-or-update the dataset repo and upload the built constraint snapshot (publisher/dev)."""
    from just_dna_enricher.upload import (
        DEFAULT_CONSTRAINT_REPO_ID,
        plan_reference_snapshot,
        publish_reference_snapshot,
    )

    target = repo_id or DEFAULT_CONSTRAINT_REPO_ID
    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, target)
        typer.echo(f"Would upload to {plan.repo_id}:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        return
    try:
        plan = publish_reference_snapshot(snapshot_dir, target, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


# ── MANE snapshot (build, publisher/dev surface) — RM168 ───────────────────────────────────────

mane_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the MANE transcript snapshot — the numbering frame, cached and pinned instead of "
        "downloaded by hand and cited in prose."
    ),
    no_args_is_help=True,
)


@mane_app.command("build")
def mane_build_(
    download: bool = typer.Option(
        False,
        "--download",
        help=(
            "Fetch the release from NCBI. Without --release the newest version is discovered from "
            "current/README_versions.txt and then pinned to its versioned directory."
        ),
    ),
    release: str | None = typer.Option(
        None,
        "--release",
        help="MANE version to pin, e.g. 1.5. Resolves to release_<version>/, never current/.",
    ),
    summary: Path | None = typer.Option(
        None,
        "--summary",
        exists=True,
        dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.summary.txt.gz. Use instead of --download to build offline.",
    ),
    changed: Path | None = typer.Option(
        None,
        "--changed",
        exists=True,
        dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.changed_select_accessions.txt.gz.",
    ),
    not_in_mane: Path | None = typer.Option(
        None,
        "--not-in-mane",
        exists=True,
        dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.protein_coding_genes_not_in_mane.txt.gz.",
    ),
    versions: Path | None = typer.Option(
        None,
        "--versions",
        exists=True,
        dir_okay=False,
        help=(
            "Local README_versions.txt. Optional, and the only way an offline build can name its "
            "release: a filename is never parsed for one."
        ),
    ),
    out: Path = typer.Option(
        repro_out("mane"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes data/*.parquet + release.json).",
    ),
) -> None:
    """Reduce one pinned MANE release to the three parquet tables the numbering frame needs.

    **All three files, in one pass.** The summary is the frame; `changed_select_accessions` is the
    currency check and `Update_Affects_CDS` is the numbering-frame axis stated by the source; the
    negative roster is what makes "MANE has no answer for this gene" distinguishable from "nobody
    asked", with the reason attached. Shipping the cache without the thing that notices it going
    stale is the defect this command exists to close.

    **There is no `--offline` flag**: the off-switch is passing the local files instead of
    `--download`. And there is no `--use` flag, because NCBI states a policy rather than a licence —
    every gating axis is unknown, and `check_declared_use` returns a *skip* for an unknown whatever
    the declaration says, so the gate would silently skip every build. A flag feeding a gate that
    never gates is a flag that does nothing (`@acquisition-gate-is-not-a-read-gate`).

    **MANE is the default, not the answer.** A gene with two rows carries two CDS numbering frames
    and `MANE_status` says which; a gene with one row says nothing about the isoforms MANE does not
    carry, so a pass treating this table as an oracle would be wrong in a way the table cannot report.
    """
    from just_dna_enricher.mane_build import (
        MANE_TABLES,
        MANE_VERSIONS_FILENAME,
        ManeBuildError,
        build_snapshot,
        discover_current_release,
        download_mane_file,
        mane_release_url,
        mane_versions_url,
    )

    local = {
        "summary": summary,
        "changed_select_accessions": changed,
        "protein_coding_genes_not_in_mane": not_in_mane,
    }
    given = {name: path for name, path in local.items() if path is not None}
    if download and given:
        raise typer.BadParameter(
            "pass --download to fetch a release or the local file flags to build from files you "
            "already hold, not both. Two sources for one input is a build whose provenance nothing "
            "can state."
        )
    if not download and len(given) != len(local):
        raise typer.BadParameter(
            "pass --download, or all three of --summary, --changed and --not-in-mane. Two of the "
            "three is not a snapshot: the summary is the frame, the changed-accession list is what "
            "notices the frame moving, and the negative roster is what tells a gene MANE excluded "
            "from a gene nobody asked about."
        )
    if release is not None and not download:
        raise typer.BadParameter(
            "--release pins which directory to fetch from, so it only means something with "
            "--download. To name the release of files you already hold, pass their "
            "README_versions.txt as --versions — that is the source's own statement, where a bare "
            "--release would be ours about somebody else's bytes."
        )
    if versions is not None and download:
        raise typer.BadParameter(
            "--versions names the release of files you already hold; a --download build fetches the "
            "release's own README_versions.txt and would ignore yours. Drop one — a flag that is "
            "silently overwritten is worse than a flag that is refused."
        )

    downloads: dict = {}
    versions_file = versions
    try:
        if download:
            pinned = release or discover_current_release()
            out.mkdir(parents=True, exist_ok=True)
            fetched_versions = download_mane_file(out / MANE_VERSIONS_FILENAME, mane_versions_url(pinned))
            versions_file = fetched_versions.path
            for table in MANE_TABLES:
                filename = f"MANE.GRCh38.v{pinned}.{table.source_suffix}"
                downloads[table.name] = download_mane_file(
                    out / filename, mane_release_url(pinned, table.source_suffix)
                )
            inputs = {name: got.path for name, got in downloads.items()}
        else:
            pinned = None
            inputs = given
        result = build_snapshot(
            inputs, out, versions_file=versions_file, release=pinned, downloads=downloads or None
        )
    except (FileNotFoundError, ImportError, ManeBuildError) as exc:
        typer.secho(f"MANE BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"mane snapshot: {result.out_dir / 'data'}", fg=typer.colors.GREEN)
    typer.echo(
        f"dataset: {result.dataset or 'unknown release'}  "
        + "  ".join(f"{name}: {count}" for name, count in result.rows.items())
    )
    typer.echo(
        "  MANE_status: "
        + ", ".join(f"{status} {count}" for status, count in sorted(result.mane_status_counts.items()))
    )
    typer.secho(
        "  changed MANE Select accessions: "
        + ", ".join(
            f"Update_Affects_CDS {token} {count}"
            for token, count in sorted(result.update_affects_cds_counts.items())
        )
        + " — a gene absent from that table has had a stable numbering frame.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        "  excluded genes: "
        + ", ".join(f"{reason} {count}" for reason, count in sorted(result.excluded_reasons.items())),
        fg=typer.colors.YELLOW,
    )
    # The withheld cells reach the terminal too, not only `release.json`: a residue an operator
    # cannot see is one nobody looks for. Printed only when there is one — the measured zeros are in
    # `release.json`, where a reader who wants to know that nothing was withheld can find them.
    withheld = {
        **{f"gene id ({table})": n for table, n in result.unparsable_gene_id.items() if n},
        **({"coordinate": result.unparsable_coordinate} if result.unparsable_coordinate else {}),
        **(
            {"Update_Affects_CDS": result.unparsable_update_affects_cds}
            if result.unparsable_update_affects_cds
            else {}
        ),
    }
    if withheld:
        typer.secho(
            "  withheld cells (the row was kept): "
            + ", ".join(f"{label} {count}" for label, count in sorted(withheld.items())),
            fg=typer.colors.YELLOW,
        )
    typer.secho(
        "  MANE is the default, not the answer: it shows a gene's second clinical transcript where "
        "there is one, and says nothing about isoforms it does not carry.",
        fg=typer.colors.YELLOW,
    )

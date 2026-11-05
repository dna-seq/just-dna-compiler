"""The ACMG secondary-findings list: `check-acmg` and the `acmg` builder group (RM260 split this out of
the former single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.acmg import (
    DEFAULT_ACMG_URL,
    AcmgListUnavailable,
    AcmgReport,
    AcmgSfError,
    verify_acmg_sf,
)
from just_dna_enricher.acmg import verification_record as acmg_record
from just_dna_enricher.cli._shared import _attest_on_the_way_out, _mode, app
from just_dna_enricher.enrich import EnrichmentError
from just_dna_enricher.locations import repro_out
from just_dna_enricher.verification import record_verification, skipped


@app.command("check-acmg")
def check_acmg_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Exit 1 if any acmg_sf disagrees."),
    offline: bool = typer.Option(
        False, "--offline", help="No network. Needs --sf-list, else nothing is checked."
    ),
    url: str = typer.Option(DEFAULT_ACMG_URL, "--url", help="ACMG secondary-findings page URL (fallback)."),
    sf_list: Path | None = typer.Option(
        None,
        "--sf-list",
        exists=True,
        file_okay=False,
        help=(
            "Built ACMG SF snapshot (see `acmg build`). Preferred: NCBI's page still serves "
            "v3.2. Omit it and a snapshot in $JUST_DNA_ACMG_CACHE (or the shared cache base) "
            "is used; the page is scraped only when neither is there."
        ),
    ),
) -> None:
    """Check each row's `acmg_sf` against the ACMG secondary-findings list (reports only).

    **Writes no authored cell, and records that the question was put** — the same two halves as
    `check-identifiers`. `acmg_sf` is an authored cell this asks a registry about, not a fact this
    pass contributes, and filling it here would break the check (see `hints.REDUNDANCY_BEARING`). The
    `verification.json` record is an attestation, never a value: it says the list was consulted and
    over how many rows, which is the one thing a downstream reader cannot reconstruct from the
    artifact (RM45/RM72).
    """
    if not (spec_dir / "variants.csv").exists():
        # Nothing attested — see `check-identifiers`: `acmg_sf` is a `variants.csv` column, so with no
        # such file the check does not apply and there is no claim to have an opinion about.
        typer.secho("no variants.csv — nothing to check", fg=typer.colors.YELLOW)
        return
    try:
        report = verify_acmg_sf(
            spec_dir=spec_dir, mode=_mode(strict), offline=offline, url=url, snapshot_dir=sf_list
        )
    except AcmgListUnavailable as exc:
        # No list was obtained, so the check applies and did not run — the one failure here that is a
        # skip. The reason travels on the exception (`unreachable` for a request that never answered,
        # `no_reference` for a source that was there and carried no readable list), decided where the
        # failure happened rather than sniffed out of the message.
        _attest_on_the_way_out(
            [skipped("acmg_secondary_findings", exc.skip, detail=str(exc), source="acmg")],
            spec_dir,
        )
        typer.secho(f"ACMG CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except AcmgSfError as exc:
        # Everything else: a `strict` refusal, or a `variants.csv` that will not load. Nothing is
        # attested — the strict path read the list and got an answer, so recording a skip would say the
        # question was never put on the one run where it was put and answered badly; and a module whose
        # rows will not load has no bytes for an attestation to bind to.
        typer.secho(f"ACMG CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    version = f"ACMG SF v{report.version}" if report.version else "not consulted"
    typer.echo(f"{version}: {report.checked}/{len(report.verdicts)} row(s) checked")
    for warning in report.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    # Unverifiable disagreements are printed like mismatches and excluded from the exit code: the
    # module may be right and the list old. They are the loud half of the stale-list fix.
    for gene, rows, message in AcmgReport.by_gene(report.unverifiable):
        typer.secho(
            f"  unverifiable: {gene} ({len(rows)} row(s), first at {rows[0]}): {message}",
            fg=typer.colors.YELLOW,
            err=True,
        )
    # Grouped by gene: every verdict is a statement about a gene, so a per-row list prints one
    # sentence once per variant in it.
    for gene, rows, message in AcmgReport.by_gene(report.notes):
        typer.secho(f"  note: {gene} ({len(rows)} row(s)): {message}", fg=typer.colors.CYAN)
    for gene, rows, message in AcmgReport.by_gene(report.mismatches):
        typer.secho(
            f"  {gene} ({len(rows)} row(s), first at {rows[0]}): {message}", fg=typer.colors.YELLOW, err=True
        )
    # After the report, for `check-identifiers`' reason: the check ran and its answer is above, so an
    # attestation that cannot be written must not take the answer down with it. `vrs mint`'s shape —
    # the message says which of the two failed, because saying "the check failed" would be false.
    try:
        record_verification([acmg_record(report)], spec_dir, error=EnrichmentError)
    except EnrichmentError as exc:
        typer.secho(f"CHECKED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # No `and report.version` guard any more: the property carries the reason a run cannot certify
    # instead of the caller remembering to test for one (RM234, retrofitted to a `Verdict`).
    if report.clean:
        # **A pass over nothing is not a pass, and this is the arm where that can happen.** `offline`
        # is an error and lands in the verdict; `nothing_to_check` — the list was read and the module
        # states no `acmg_sf` cell — is not, so it arrives here truthy. Saying *every stated acmg_sf
        # agrees* over zero stated cells is the S86 shape the sibling command already guards.
        if not report.checked:
            typer.secho(
                f"no acmg_sf cell to check — list {report.version} read, 0 row(s) state one",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho(
                f"every stated acmg_sf agrees with the list ({report.checked} row(s) checked)",
                fg=typer.colors.GREEN,
            )
    else:
        typer.secho(f"acmg check: {report.clean}", fg=typer.colors.RED)


# ── clinvar reference snapshot (build + publish, publisher/dev surface) ─────────────────────────

acmg_app = typer.Typer(
    add_completion=False,
    help="Build the ACMG secondary-findings snapshot from ACMG's published workbook (dev surface).",
    no_args_is_help=True,
)


@acmg_app.command("build")
def acmg_build_(
    workbook: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        help="ACMG SF supplementary workbook (.xlsx), downloaded by you.",
    ),
    out: Path = typer.Option(
        repro_out("acmg_sf"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes acmg_sf.csv + release.json).",
    ),
    source_url: str | None = typer.Option(
        None,
        "--source-url",
        help="Where the workbook came from, recorded in release.json.",
    ),
    doi: str | None = typer.Option(
        None,
        "--doi",
        help="DOI of the statement the workbook accompanies, recorded in release.json.",
    ),
) -> None:
    """Convert ACMG's SF workbook into the snapshot `check-acmg --sf-list` reads.

    Why this exists: NCBI's page serves **v3.2** and ACMG published **v3.3** in June 2025, so the live
    scrape reports correctly authored rows as wrong. Nothing is downloaded here — the workbook is
    ACMG/Elsevier supplementary material and the author supplies their own copy, which is the same
    inject-only shape every other reference in this repo uses.
    """
    from just_dna_enricher.acmg_build import build_acmg_snapshot

    try:
        sf_list = build_acmg_snapshot(workbook, out, source_url=source_url, doi=doi)
    except (AcmgSfError, ImportError) as exc:
        typer.secho(f"BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {out}", fg=typer.colors.GREEN)
    typer.echo(
        f"ACMG SF v{sf_list.version}: {len(sf_list.genes)} genes over {len(sf_list.findings)} "
        f"gene-condition rows"
    )
    added = sorted({f.gene for f in sf_list.findings if f.since_version == sf_list.version})
    if added:
        typer.echo(f"  first listed in v{sf_list.version}: {', '.join(added)}")

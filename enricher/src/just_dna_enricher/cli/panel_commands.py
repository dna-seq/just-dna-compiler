"""`draft-panel` and the closed set of authorities it drafts from (RM260 split this out of the former
single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.civic_draft import draft_panel_from_civic
from just_dna_enricher.cli._shared import _DRAFT_PRECONDITION_ERRORS, _use, app
from just_dna_enricher.clinvar_draft import ClinVarDraftError, draft_gene_panel
from just_dna_enricher.mitomap_draft import SOURCE_LABEL as MITOMAP_MISS_SOURCE
from just_dna_enricher.mitomap_draft import MitomapDraftError, draft_panel_from_mitomap_miss
from just_dna_enricher.pubmind_draft import (
    DEFAULT_MIN_CONFIDENCE,
    PubMindDraftError,
    draft_gene_panel_from_pubmind,
)

#: Which authority `draft-panel` may draft from. A closed set, and the members reach an author's
#: `sources.csv` through `SourceRow.source`, so they are named after the source and nothing else.
PANEL_SOURCES: frozenset[str] = frozenset({"clinvar", "pubmind", "civic", MITOMAP_MISS_SOURCE})


#: The panel sources that draft **by gene** and cannot run without one. MITOMAP's increment is the
#: exception and it is a real difference rather than a convenience: the whole point of that lane is
#: "everything MITOMAP publishes that ClinVar does not", which is a set the caller asks for as a
#: whole. A `--gene` there filters; here it is the query.
_GENE_SCOPED_PANEL_SOURCES: frozenset[str] = PANEL_SOURCES - {MITOMAP_MISS_SOURCE}


def _panel_source(spelling: str) -> str | None:
    """A `--source` value as the vocabulary declares it, or `None` for a name nothing answers to.

    Accepts `-` for `_` and returns the declared member, the rule every closed vocabulary here
    follows — `mitomap-miss` is the declared spelling and `mitomap_miss` is the cache lane's, and a
    caller who has just typed `cache rebuild --only mitomap_miss` should not be told this command has
    never heard of it (`@vocab-separator-slip`).
    """
    folded = spelling.strip().lower().replace("_", "-")
    return folded if folded in PANEL_SOURCES else None


@app.command("draft-panel")
def draft_panel_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: list[str] = typer.Option(
        [],
        "--gene",
        help=(
            "Gene to draft rows for (repeatable). Required for every source but mitomap-miss, whose "
            "increment is asked for as a whole and where --gene only filters."
        ),
    ),
    source: str = typer.Option(
        "clinvar",
        "--source",
        help=(
            "Which authority to draft the calls from: clinvar (the default); pubmind — an LLM's "
            "reading of the literature, which needs an operator-built snapshot and still reads the "
            "ClinVar one for its gene attribution; civic — curated cancer interpretations, which "
            "writes the DIRECTION axis rather than clin_sig and needs a `civic build` snapshot; or "
            "mitomap-miss — the curated mtDNA calls MITOMAP publishes and the ClinVar cache does "
            "not, which needs a `mitomap miss` snapshot."
        ),
    ),
    mitomap_miss_cache: Path | None = typer.Option(
        None,
        "--mitomap-miss-cache",
        exists=True,
        file_okay=False,
        help=(
            "Built MITOMAP-miss snapshot (see `mitomap miss`). Only read under "
            "--source mitomap-miss; omit it and $JUST_DNA_MITOMAP_MISS_CACHE is used."
        ),
    ),
    civic_cache: Path | None = typer.Option(
        None,
        "--civic-cache",
        exists=True,
        file_okay=False,
        help=(
            "Built CIViC snapshot (see `civic build`). Only read under --source civic; omit it and "
            "$JUST_DNA_CIVIC_CACHE is used."
        ),
    ),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        exists=True,
        file_okay=False,
        help=(
            "Built ClinVar snapshot (see `clinvar build`). Omit it and the cache is used, or the "
            "published snapshot downloaded — the citations table comes with it, which is what a panel "
            "needs to compile. Read for its gene attribution under --source pubmind, which publishes "
            "no gene column of its own."
        ),
    ),
    pubmind_cache: Path | None = typer.Option(
        None,
        "--pubmind-cache",
        exists=True,
        file_okay=False,
        help=(
            "Built PubMind snapshot (see `pubmind build`), for --source pubmind. Omit it and "
            "$JUST_DNA_PUBMIND_CACHE is read; there is no published one to download."
        ),
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Use a local snapshot only: never download one.",
    ),
    download: bool = typer.Option(
        True,
        "--download/--no-download",
        help="Provision the published snapshot when no local one is found. Fetching it is this "
        "command's only network use, so --no-download coincides with --offline today; it is a "
        "separate switch because it says 'do not go and get one', not 'make no request'.",
    ),
    clin_sig: str | None = typer.Option(
        None,
        "--clin-sig",
        help="Comma-separated calls to include. Default: pathogenic,likely_pathogenic.",
    ),
    min_review_stars: int = typer.Option(
        2,
        "--min-review-stars",
        min=0,
        max=4,
        help="Review-status floor, --source clinvar only. 2 = multiple submitters, no conflicts.",
    ),
    max_citations: int = typer.Option(
        3,
        "--max-citations",
        min=0,
        help="Study rows to draft per variant from ClinVar's literature links. 0 disables. "
        "--source clinvar only: PubMind's channel carries no PMID.",
    ),
    min_confidence: int = typer.Option(
        DEFAULT_MIN_CONFIDENCE,
        "--min-confidence",
        min=0,
        max=3,
        help="Evidence-depth floor, --source pubmind only. PubMind's confidence counts how much of "
        "the literature spoke, 0-3; 1 means more than a single mention.",
    ),
    use: str = typer.Option("unstated", "--use", help="Declared use (ClinVar is public domain)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft a gene panel's variants.csv rows from an authority — appends, never overwrites a row.

    The drafted rows carry a **genotype placeholder**, so the module will not compile until you decide
    what each finding is about. That is deliberate: ClinVar publishes alleles, and whether carrying one
    is a carrier state or an affected one follows from the condition's inheritance mode, which the
    source does not say. Rows land in their gene's block, and a re-run leaves anything already there —
    stub or filled — exactly as it is.
    """
    resolved = _panel_source(source)
    if resolved is None:
        typer.secho(
            f"--source {source!r} is not an authority this command drafts from. "
            f"Known: {', '.join(sorted(PANEL_SOURCES))}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    source = resolved
    if not gene and source in _GENE_SCOPED_PANEL_SOURCES:
        # Refused rather than defaulted to "every gene": ClinVar's snapshot is 4.4M records and CIViC's
        # is a cancer corpus, so an unfiltered draft from either is not a panel, it is the source.
        typer.secho(
            f"--source {source} drafts a gene panel and needs at least one --gene. Only "
            f"--source {MITOMAP_MISS_SOURCE} is asked for as a whole, because its snapshot IS the "
            f"increment.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    calls = frozenset(c.strip() for c in clin_sig.split(",") if c.strip()) if clin_sig else None
    # A dial belonging to the other authority, set to something other than its default, is named
    # rather than silently ignored: a run that honoured neither the flag nor the author's expectation
    # is the failure this reports before it happens.
    for dial, value, default, belongs in (
        ("--min-review-stars", min_review_stars, 2, "clinvar"),
        ("--max-citations", max_citations, 3, "clinvar"),
        ("--min-confidence", min_confidence, DEFAULT_MIN_CONFIDENCE, "pubmind"),
    ):
        if value != default and source != belongs:
            typer.secho(
                f"  warning: {dial} is a --source {belongs} dial and does nothing under --source {source}",
                fg=typer.colors.YELLOW,
                err=True,
            )
    # `--clin-sig` is the third dial belonging elsewhere, and it is named outside the loop above
    # because it is not merely inert under --source civic: CIViC's germline clinical-significance
    # calls are five in all with none benign-class, which is exactly why that provider writes
    # `direction` instead. Once, not once per dial — a warning emitted from inside the loop printed
    # three times for one condition.
    if calls and source == "civic":
        typer.secho(
            "  warning: --clin-sig does nothing under --source civic, which drafts the "
            "direction axis (risk/protective) rather than clinical significance",
            fg=typer.colors.YELLOW,
            err=True,
        )
    # And the fourth, for its own reason again: MITOMAP's increment is already filtered to the five
    # documented VCEP classes, and everything outside them is *withheld* rather than assigned. A
    # `--clin-sig` there would narrow a set this command has no way to widen.
    if calls and source == MITOMAP_MISS_SOURCE:
        typer.secho(
            f"  warning: --clin-sig does nothing under --source {MITOMAP_MISS_SOURCE}, which drafts "
            f"exactly the five documented ClinGen mtDNA VCEP classes and withholds everything else",
            fg=typer.colors.YELLOW,
            err=True,
        )
    try:
        if source == MITOMAP_MISS_SOURCE:
            result = draft_panel_from_mitomap_miss(
                spec_dir,
                gene,
                snapshot=mitomap_miss_cache,
                declared_use=_use(use),
                dry_run=dry_run,
            )
        elif source == "civic":
            result = draft_panel_from_civic(
                spec_dir,
                gene,
                snapshot=civic_cache,
                declared_use=_use(use),
                offline=offline,
                dry_run=dry_run,
            )
        elif source == "pubmind":
            result = draft_gene_panel_from_pubmind(
                spec_dir,
                gene,
                snapshot=snapshot,
                pubmind_snapshot=pubmind_cache,
                offline=offline,
                download=download,
                **({"clin_sig": calls} if calls else {}),
                min_confidence=min_confidence,
                declared_use=_use(use),
                dry_run=dry_run,
            )
        else:
            result = draft_gene_panel(
                spec_dir,
                gene,
                snapshot=snapshot,
                offline=offline,
                download=download,
                **({"clin_sig": calls} if calls else {}),
                min_review_stars=min_review_stars,
                max_citations=max_citations,
                declared_use=_use(use),
                dry_run=dry_run,
            )
    except (
        ClinVarDraftError,
        PubMindDraftError,
        MitomapDraftError,
        *_DRAFT_PRECONDITION_ERRORS,
    ) as exc:
        typer.secho(f"DRAFT FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # Only the ClinVar result carries `skipped`; `PubMindDraftResult` has no such field. A
    # `getattr(..., False)` default reads "this type cannot skip" and "this run did not skip" as the
    # same answer, so a skip path added to the PubMind provider would go dark with nothing failing.
    # Ask whether the field exists, then read it.
    if hasattr(result, "skipped") and result.skipped:
        for warning in result.warnings:
            typer.secho(f"  skipped: {warning}", fg=typer.colors.YELLOW, err=True)
        return
    for report in result.reports:
        typer.echo(f"  {report}")
    for warning in result.warnings:
        typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW, err=True)
    verb = "would add" if dry_run else "added"
    # Per table, never a rolled-up total. The draft writes `variants.csv` AND `studies.csv`, so a single
    # number matches neither file — `ClinVarDraftResult.added` says as much in its own docstring.
    breakdown = ", ".join(f"{r.csv_name} {len(r.added)}" for r in result.reports) or "nothing"
    typer.secho(f"{verb}: {breakdown} — in {spec_dir}", fg=typer.colors.GREEN)

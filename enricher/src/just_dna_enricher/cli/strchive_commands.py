"""STRchive: the `strchive` builder group, `draft-repeats` and `check-repeat-bands` (RM260 split this
out of the former single-file `cli.py`).
"""

from pathlib import Path

import typer
from just_dna_compiler.draft import DraftError
from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher.cli._shared import _mode, _use, app
from just_dna_enricher.locations import STRCHIVE_CATALOGUE_FILENAME, read_release, repro_out
from just_dna_enricher.strchive import StrchiveError, check_repeat_bands
from just_dna_enricher.strchive_draft import StrchiveDraftError, draft_repeat_loci
from just_dna_enricher.upload import DEFAULT_STRCHIVE_REPO_ID

strchive_app = typer.Typer(
    add_completion=False,
    help="Build the STRchive repeat-locus snapshot. MIT-licensed, so a deployment may publish it.",
    no_args_is_help=True,
)


@strchive_app.command("build")
def strchive_build_(
    out: Path = typer.Option(
        repro_out("strchive"),
        "--out",
        file_okay=False,
        help="Output snapshot directory (writes STRchive-loci.json + release.json).",
    ),
    catalogue: Path | None = typer.Option(
        None,
        "--catalogue",
        exists=True,
        dir_okay=False,
        help="A STRchive-loci.json you already have. Without it the file is downloaded.",
    ),
    release: str | None = typer.Option(
        None,
        "--release",
        help="Upstream release tag to pin, e.g. v2.26.0. Without it, the default branch, unlabelled.",
    ),
) -> None:
    """Fetch (or copy in) the STRchive catalogue and record its provenance beside it.

    Pin a release: the default branch moves, so a comparison whose reference is "whatever was there
    that afternoon" cannot be re-run, and only a pinned build gets a `dataset` label the verification
    record can name.
    """
    from just_dna_enricher.strchive_build import build_strchive_snapshot

    try:
        result = build_strchive_snapshot(out, catalogue=catalogue, release=release)
    except (StrchiveError, OSError) as exc:
        typer.secho(f"STRCHIVE BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"built: {result.catalogue_file}", fg=typer.colors.GREEN)
    typer.echo(f"  {result.locus_count} locus/loci, sha256 {result.source_sha256}")
    if result.dataset:
        typer.echo(f"  release {result.dataset}")
    else:
        typer.secho(
            "  no --release was pinned, so this snapshot carries no release label and the check "
            "will not be able to say which version it compared against",
            fg=typer.colors.YELLOW,
            err=True,
        )


@strchive_app.command("publish")
def strchive_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (STRchive-loci.json + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_STRCHIVE_REPO_ID,
        "--repo",
        help="Target HuggingFace dataset repo (owner/name).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be uploaded; send nothing."),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Create-or-update the dataset repo and upload the built STRchive catalogue (publisher/dev).

    Publishable on the source's own terms: STRchive is MIT, which grants redistribution outright.
    This lane had no publish command because it grew from a check rather than from a cache, not
    because anything withheld the permission — the same distinction the roster draws between CIViC's
    absent `ensure_*` (a gap) and PharmVar's (a refusal).

    **Publish a pinned build.** An unlabelled snapshot carries no `dataset`, so whoever pulls it can
    run the comparison and cannot say which release they compared against — build with `--release`
    first, and this refuses nothing but says so.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    if not (read_release(snapshot_dir) or {}).get("dataset"):
        typer.secho(
            "  this snapshot carries no release label, so everyone who pulls it inherits a "
            "comparison that cannot name its own reference. Rebuild with `strchive build --release`.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    try:
        if dry_run:
            plan = plan_reference_snapshot(snapshot_dir, repo, payload=STRCHIVE_CATALOGUE_FILENAME)
            typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
            return
        plan = publish_reference_snapshot(
            snapshot_dir,
            repo,
            commit_message=commit_message,
            payload=STRCHIVE_CATALOGUE_FILENAME,
        )
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


@app.command("draft-repeats")
def draft_repeats_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    genes: list[str] = typer.Option(
        [],
        "--gene",
        "-g",
        help="Restrict to these genes. Repeatable; omit for every catalogue locus.",
    ),
    catalogue: Path | None = typer.Option(
        None,
        "--catalogue",
        exists=True,
        help=(
            "Built STRchive snapshot directory (see `strchive build`), or a STRchive-loci.json. "
            "Omit it and $JUST_DNA_STRCHIVE_CACHE (or the shared cache base) is used."
        ),
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=f"Declared use: one of {sorted(VALID_DECLARED_USE)}.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft repeat_alleles.csv identity rows from STRchive — appends, never overwrites a row.

    **The bands are not drafted, and that is the design rather than a limitation.** A drafted row
    carries the gene, the motif as the catalogue spells it, the trait CURIE where the locus names
    exactly one disease, and a `conclusion` placeholder — so the table cannot compile until a human
    has filled in what each band means. `measure_min`/`measure_max` stay empty: run
    `check-repeat-bands` once you have written them and it will report where the catalogue disagrees.

    The catalogue's coordinates, `ref_copies` and `locus_structure` have no authored column to land
    in; the run counts them and says so rather than dropping them silently.
    """
    try:
        result = draft_repeat_loci(
            spec_dir,
            genes,
            catalogue=catalogue,
            declared_use=_use(use),
            dry_run=dry_run,
        )
    except (StrchiveError, StrchiveDraftError, DraftError) as exc:
        typer.secho(f"DRAFT FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    if result.skipped:
        raise typer.Exit(code=1)
    label = f" ({result.dataset})" if result.dataset else ""
    verb = "would add" if dry_run else "added"
    typer.secho(
        f"{verb} {result.drafted} row(s) from {result.candidates} strchive locus/loci{label}",
        fg=typer.colors.GREEN,
    )
    if result.drafted:
        typer.echo(
            "  every drafted row needs its bands and its conclusion written; the placeholder is "
            "what stops the module compiling until they are"
        )


@app.command("check-repeat-bands")
def check_repeat_bands_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    catalogue: Path | None = typer.Option(
        None,
        "--catalogue",
        exists=True,
        help="Built STRchive snapshot directory (see `strchive build`), or a STRchive-loci.json.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict/--best-effort",
        help="Carried into the report. A band difference NEVER fails, in either mode.",
    ),
) -> None:
    """Compare a module's `repeat_alleles.csv` bands against STRchive's, and report the differences.

    **Writes no authored cell and never fails on a difference.** Where a catalogue and an expert
    author draw a repeat threshold in different places, both are claims by an authority, and a compile
    that refused would make this format pick the winner — the rule the ClinVar `clin_sig` and PGx
    allele-function checks already follow. `--strict` is accepted so the flag means one thing across
    the tier, and it changes nothing here but the mode recorded in the report.

    The catalogue's `pathogenic_max` is reported as its own finding and is never written: it is the
    longest allele the literature records, not a clinical ceiling, and a module that imported it would
    silently answer nothing at all for a longer one.
    """
    try:
        result = check_repeat_bands(spec_dir, catalogue=catalogue, mode=_mode(strict))
    except StrchiveError as exc:
        typer.secho(f"REPEAT-BAND CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    if not result.compared and not result.withheld:
        # Three different ways to get here and only one of them is "no table": the warnings above
        # already name the other two (no catalogue was provisioned; the table is only `unresolved`
        # sentinels), so saying "no repeat_alleles.csv" unconditionally would print a false diagnosis
        # over a true one.
        if not result.warnings:
            typer.secho("no repeat_alleles.csv — nothing to check", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    label = f" ({result.dataset})" if result.dataset else ""
    typer.echo(f"compared {len(result.compared)} bin group(s) against strchive{label}")
    for _key, reason in result.withheld:
        typer.secho(f"  withheld: {reason}", fg=typer.colors.CYAN)
    for finding in result.findings:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW, err=True)
    if result.compared and not result.findings:
        typer.secho("every compared band matches the catalogue", fg=typer.colors.GREEN)

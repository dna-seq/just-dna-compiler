"""The pharmacogenomic sources: the `clinpgx`, `cpic` and `pharmvar` groups and `draft-clinpgx` (RM260
split this out of the former single-file `cli.py`).
"""

from pathlib import Path
from urllib.parse import urlparse

import typer
from just_dna_compiler.draft import DraftError
from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher.cli._shared import _mode, _use, app
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.clinpgx_build import (
    CURRENT_ARCHIVE,
    DEFAULT_CLINPGX_URL,
    ClinPgxArchiveError,
    download_clinpgx_zip,
)
from just_dna_enricher.clinpgx_build import build_snapshot as build_clinpgx_snapshot
from just_dna_enricher.clinpgx_draft import draft_pharm_variants
from just_dna_enricher.cpic import DEFAULT_CPIC_ENDPOINT, CpicError
from just_dna_enricher.cpic_build import CpicBuildError
from just_dna_enricher.cpic_build import build_snapshot as build_cpic_snapshot
from just_dna_enricher.drug_labels import (
    DEFAULT_DRUG_LABELS_URL,
    DrugLabelError,
    arm_summary,
    check_drug_labels,
)
from just_dna_enricher.licensing import (
    CLINPGX_TERMS,
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    check_declared_use,
)
from just_dna_enricher.locations import SNAPSHOT_LICENSE_FILENAME, repro_out
from just_dna_enricher.pharmvar import PharmVarError
from just_dna_enricher.pharmvar_build import build_snapshot as build_pharmvar_snapshot
from just_dna_enricher.upload import (
    DEFAULT_CLINPGX_REPO_ID,
    DEFAULT_CPIC_REPO_ID,
    DEFAULT_DRUG_LABELS_REPO_ID,
)

clinpgx_app = typer.Typer(
    add_completion=False,
    help="Build the ClinPGx clinical-annotation and drug-label snapshots, and cross-check against them.",
    no_args_is_help=True,
)


@clinpgx_app.command("build")
def clinpgx_build_(
    out_dir: Path = typer.Option(
        repro_out("clinpgx"), "--out", file_okay=False, help="Snapshot output directory."
    ),
    zip_path: Path | None = typer.Option(
        None,
        "--zip",
        help=f"An existing {CURRENT_ARCHIVE.archive} (else downloaded).",
    ),
    url: str = typer.Option(DEFAULT_CLINPGX_URL, "--url", help="ClinPGx bulk download URL."),
    use: str = typer.Option(
        "unstated", "--use", help="Declared use: unstated | non-commercial | commercial."
    ),
) -> None:
    """Download + build the ClinPGx snapshot (dev surface; needs polars)."""
    declared = _use(use)
    try:
        # The terms are accepted when the data is TAKEN, so the gate runs before the download.
        reason = check_declared_use(CLINPGX_TERMS, declared)
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if reason is not None:
        typer.secho(f"SKIPPED: {reason}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    source_sha: str | None = None
    try:
        if zip_path is None:
            # Named for what `--url` actually points at, so a mirror or a retired name is visible on
            # disk rather than filed under whatever this lane used to download.
            filename = Path(urlparse(url).path).name or CURRENT_ARCHIVE.archive
            zip_path, source_sha = download_clinpgx_zip(Path(out_dir) / filename, url)
        result = build_clinpgx_snapshot(zip_path, out_dir, source_url=url, source_sha256=source_sha)
    except (ClinPgxArchiveError, OSError) as exc:
        typer.secho(f"CLINPGX BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"clinpgx snapshot: {result.parquet_path}", fg=typer.colors.GREEN)
    typer.echo(
        f"rows: {result.row_count}  annotations: {result.annotation_count}  "
        f"genes: {len(result.genes)}  release: {result.created_date}"
    )
    typer.echo(f"licence pinned: {result.license_sha256}")


@clinpgx_app.command("check")
def clinpgx_check_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        help="Explicit ClinPGx snapshot dir. Omit it and the cache is used, or one is downloaded.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Use a local snapshot only: never download one.",
    ),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail on a stale evidence level."),
    use: str = typer.Option(
        "unstated", "--use", help="Declared use: unstated | non-commercial | commercial."
    ),
) -> None:
    """Cross-check pharm_variants.csv against the ClinPGx snapshot.

    The snapshot no longer has to be handed over by hand (RM38): explicit path → `$JUST_DNA_CLINPGX_CACHE`
    / the default cache → downloaded from HuggingFace. `--offline` stops at the second step.
    """
    try:
        result = enrich_clinpgx(
            spec_dir,
            mode=_mode(strict),
            declared_use=_use(use),
            snapshot=snapshot,
            offline=offline,
        )
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except ClinPgxEnrichmentError as exc:
        typer.secho(f"CLINPGX FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"dataset: {result.dataset}  sources recorded: {len(result.rows)}")
    for warning in result.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    for conflict in result.conflicts:
        typer.secho(f"  evidence-level difference: {conflict}", fg=typer.colors.YELLOW, err=True)


# ── the licence-gated snapshots (build + publish, publisher/dev surface) — RM38 ─────────────────
#
# Three sources, three shapes, and the differences are the licensing argument rather than plumbing:
#
#   clinpgx   build → publish → ensure_*   (snapshot existed; the plumbing did not)
#   cpic      build → publish → ensure_*   (new; open source, but a host must not spend one shared
#                                           per-IP budget on every caller's request)
#   pharmvar  build only                   (personal, non-transferable key: no publish, no ensure_*)

cpic_app = typer.Typer(
    add_completion=False,
    help="Build and publish the CPIC snapshot, so a hosted enricher never reaches CPIC per request.",
    no_args_is_help=True,
)


@cpic_app.command("build")
def cpic_build_(
    out_dir: Path = typer.Option(
        repro_out("cpic"), "--out", file_okay=False, help="Snapshot output directory."
    ),
    endpoint: str = typer.Option(DEFAULT_CPIC_ENDPOINT, "--endpoint", help="CPIC PostgREST base URL."),
    use: str = typer.Option(
        "unstated", "--use", help="Declared use: unstated | non-commercial | commercial."
    ),
) -> None:
    """Fetch CPIC whole into `data/*.parquet` + release.json (dev surface; needs polars).

    No gene filter, deliberately: the whole database is ~120k narrow rows, and a snapshot covering only
    the genes the operator thought of answers "CPIC has nothing" for the next one.
    """
    declared = _use(use)
    try:
        # The terms are accepted when the data is TAKEN, so the gate runs before the fetch.
        reason = check_declared_use(CPIC_TERMS, declared)
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if reason is not None:
        typer.secho(f"SKIPPED: {reason}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    try:
        result = build_cpic_snapshot(out_dir, endpoint=endpoint)
    except (CpicError, CpicBuildError) as exc:
        typer.secho(f"CPIC BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"cpic snapshot: {result.out_dir / 'data'}", fg=typer.colors.GREEN)
    typer.echo(f"genes: {result.gene_count}  rows: {result.total_rows}  dataset: {result.dataset}")
    for name, count in sorted(result.row_counts.items()):
        typer.echo(f"  {name}: {count}")


@cpic_app.command("publish")
def cpic_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_CPIC_REPO_ID,
        "--repo",
        help="Target HuggingFace dataset repo (owner/name).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be uploaded; send nothing."),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Create-or-update the dataset repo and upload the built CPIC snapshot (publisher/dev).

    Publishable because CPIC's recorded terms permit redistribution — CC BY-SA grants sharing under
    share-alike plus attribution, which `sources.csv` carries. PharmVar has no equivalent command, and
    that is the design rather than an omission.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, repo)
        typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
        return
    plan = publish_reference_snapshot(snapshot_dir, repo, commit_message=commit_message)
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


@clinpgx_app.command("publish")
def clinpgx_publish_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_CLINPGX_REPO_ID,
        "--repo",
        help="Target HuggingFace dataset repo (owner/name).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be uploaded; send nothing."),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Publish a built ClinPGx snapshot so `clinpgx check` can provision it (publisher/dev).

    `LICENSE.txt` travels with the parquet — the terms ClinPGx ships inside its own archive are what
    `license_sha256` pins, and a published snapshot without them pins nothing for whoever downloads it.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, repo)
        typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
        return
    plan = publish_reference_snapshot(snapshot_dir, repo, commit_message=commit_message)
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


pharmvar_app = typer.Typer(
    add_completion=False,
    help="Build the PharmVar snapshot with your own key. Operator-built and inject-only; never published.",
    no_args_is_help=True,
)


@pharmvar_app.command("build")
def pharmvar_build_(
    out_dir: Path = typer.Option(
        repro_out("pharmvar"), "--out", file_okay=False, help="Snapshot output directory."
    ),
    use: str = typer.Option(
        "unstated", "--use", help="Declared use: unstated | non-commercial | commercial."
    ),
) -> None:
    """Fetch PharmVar whole into `data/*.parquet` + release.json (dev surface; needs polars + a key).

    **There is no `pharmvar publish`, and there will not be.** The data is pulled under a key
    PharmVar's terms §2 make personal and non-transferable, and no axis `SourceTerms` records covers
    passing that on — an unestablished permission is not a permission. Build your own; point at it with
    `$JUST_DNA_PHARMVAR_CACHE` or `--pharmvar-cache`.
    """
    declared = _use(use)
    try:
        reason = check_declared_use(PHARMVAR_TERMS, declared)
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if reason is not None:
        typer.secho(f"SKIPPED: {reason}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    try:
        result = build_pharmvar_snapshot(out_dir)
    except PharmVarError as exc:
        typer.secho(f"PHARMVAR BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"pharmvar snapshot: {result.out_dir / 'data'}", fg=typer.colors.GREEN)
    typer.echo(
        f"genes: {result.gene_count}  alleles: {result.allele_count}  "
        f"variants: {result.variant_count} on {result.genome_build}  dataset: {result.dataset}"
    )
    typer.secho(
        "  operator-built and inject-only: do not publish or pass this snapshot on (terms §2).",
        fg=typer.colors.YELLOW,
    )


@app.command("draft-clinpgx")
def draft_clinpgx_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    snapshot: Path = typer.Option(
        ...,
        "--snapshot",
        exists=True,
        file_okay=False,
        help="Built ClinPGx snapshot (see `clinpgx build`). Inject-only; nothing is downloaded.",
    ),
    drug: list[str] = typer.Option([], "--drug", help="Only annotations naming this drug (repeatable)."),
    gene: list[str] = typer.Option([], "--gene", help="Only annotations naming this gene (repeatable)."),
    min_evidence_level: str | None = typer.Option(
        None, "--min-evidence-level", help="Keep annotations at least this strong: 1A|1B|2A|2B|3|4."
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help="Declared use: unstated | non-commercial | commercial. ClinPGx forbids sale.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft pharm_variants.csv rows from the ClinPGx snapshot — appends, never overwrites a row.

    Narrow with --drug and re-run as the module grows. A row already in the file is reported, never
    replaced: drift against ClinPGx is `clinpgx check`'s finding, not this command's edit to make.
    """
    try:
        result = draft_pharm_variants(
            spec_dir,
            snapshot=snapshot,
            genes=gene,
            drugs=drug,
            min_evidence_level=min_evidence_level,
            declared_use=_use(use),
            dry_run=dry_run,
        )
    except (ClinPgxEnrichmentError, DraftError) as exc:
        typer.secho(f"DRAFT FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped:
        for warning in result.warnings:
            typer.secho(f"  skipped: {warning}", fg=typer.colors.YELLOW, err=True)
        return
    for report in result.reports:
        typer.echo(f"  {report}")
        for outcome in report.differs:
            typer.secho(f"    {outcome}", fg=typer.colors.YELLOW)
    for warning in result.warnings:
        typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW, err=True)
    verb = "would add" if dry_run else "added"
    typer.secho(f"{verb} {result.added} row(s) in {spec_dir}", fg=typer.colors.GREEN)


@clinpgx_app.command("build-labels")
def clinpgx_build_labels_(
    out_dir: Path = typer.Option(
        repro_out("drug_labels"), "--out", file_okay=False, help="Snapshot output directory."
    ),
    zip_path: Path | None = typer.Option(
        None,
        "--zip",
        exists=True,
        dir_okay=False,
        help="A drugLabels.zip you already have. Without it the archive is downloaded.",
    ),
    url: str = typer.Option(DEFAULT_DRUG_LABELS_URL, "--url", help="ClinPGx bulk download URL."),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=f"Declared use: one of {sorted(VALID_DECLARED_USE)}.",
    ),
) -> None:
    """Download + build the regulator drug-label snapshot (dev surface; needs polars).

    A **second** archive from a source this tier already adopted, with its own `release.json`: ClinPGx
    publishes at least twelve downloads on this endpoint and they do not refresh in lockstep, so the
    label snapshot is dated from its own `CREATED_*.txt` rather than from the annotation lane's.

    There is no `--offline`: a builder's off-switch is passing `--zip` instead of downloading.
    """
    from just_dna_enricher.drug_labels_build import (
        build_drug_label_snapshot,
        download_drug_labels_zip,
    )

    declared = _use(use)
    try:
        # The terms are accepted when the data is TAKEN, so the gate runs before the download.
        reason = check_declared_use(CLINPGX_TERMS, declared)
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if reason is not None:
        typer.secho(f"SKIPPED: {reason}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)

    source_sha: str | None = None
    try:
        if zip_path is None:
            zip_path, source_sha = download_drug_labels_zip(Path(out_dir) / "drugLabels.zip", url)
        result = build_drug_label_snapshot(zip_path, out_dir, source_url=url, source_sha256=source_sha)
    except (DrugLabelError, OSError) as exc:
        typer.secho(f"DRUG-LABEL BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"drug-label snapshot: {result.parquet_path}", fg=typer.colors.GREEN)
    typer.echo(
        f"labels: {result.label_count}  regulators: {', '.join(result.regulators)}  "
        f"release: {result.created_date or 'undated'}"
    )
    typer.echo(f"testing levels stated: {', '.join(result.testing_levels)}")
    typer.echo(f"licence pinned: {result.license_sha256}")
    if result.dataset is None:
        typer.secho(
            "  the archive carried no CREATED_<date>.txt, so this snapshot has no release label and "
            "the check will not be able to say which version it compared against",
            fg=typer.colors.YELLOW,
            err=True,
        )


@clinpgx_app.command("check-labels")
def clinpgx_check_labels_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        exists=True,
        file_okay=False,
        help=(
            "Built drug-label snapshot directory (see `clinpgx build-labels`). Omit it and "
            "$JUST_DNA_DRUG_LABELS_CACHE (or the shared cache base) is used."
        ),
    ),
    strict: bool = typer.Option(
        False,
        "--strict/--best-effort",
        help="Carried into the report. A label difference NEVER fails, in either mode.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=f"Declared use: one of {sorted(VALID_DECLARED_USE)}.",
    ),
) -> None:
    """Compare a module's gene/allele/drug claims against the drug labels five regulators publish.

    **Two join tiers, reported apart, and the tier belongs to the question.** *What do the agencies
    say about this gene and this medicine* is the gene-tier subject; *…and this star allele or rsID*
    is the allele-tier one. A label naming both answers both, because they are two questions rather
    than one asked twice, and a gene-level agreement is not an allele-level agreement.

    **Writes no authored cell and never fails on a difference.** Five agencies genuinely disagree with
    each other — clopidogrel and CYP2C19 is `Actionable PGx` at four of them and `Informative PGx` at
    the EMA — and a compile that refused would make this format pick the winner. A blank `Testing
    Level` is a third of the file and is reported as unknown, never as `No Clinical PGx`.
    """
    try:
        result = check_drug_labels(
            spec_dir,
            snapshot=snapshot,
            mode=_mode(strict),
            declared_use=_use(use),
        )
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except DrugLabelError as exc:
        typer.secho(f"DRUG-LABEL CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    if not result.compared and not result.withheld:
        raise typer.Exit(code=0)
    label = f" ({result.dataset})" if result.dataset else ""
    tiers = ", ".join(f"{count} at the {tier} tier" for tier, count in result.tier_subjects.items())
    typer.echo(
        f"compared {len(result.compared)} claim(s) against {len(result.regulators)} regulator(s)"
        f"{label} — {tiers}"
    )
    if result.unstated_labels:
        typer.secho(
            f"  {len(result.unstated_labels)} label(s) state no testing level: counted as unknown, never "
            f"as a negative",
            fg=typer.colors.CYAN,
        )
    if result.verdicts:
        typer.secho(f"  {arm_summary(result)}", fg=typer.colors.CYAN)
    for _subject, note in result.withheld:
        typer.secho(f"  withheld: {note}", fg=typer.colors.CYAN)
    for finding in result.findings:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW, err=True)
    if result.compared and not result.findings:
        typer.secho("every compared claim agrees with the labels that reached it", fg=typer.colors.GREEN)


@clinpgx_app.command("publish-labels")
def clinpgx_publish_labels_(
    snapshot_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Built snapshot directory (data/drug_labels.parquet + LICENSE.txt + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_DRUG_LABELS_REPO_ID,
        "--repo",
        help="Target HuggingFace dataset repo (owner/name).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be uploaded; send nothing."),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
) -> None:
    """Publish a built drug-label snapshot so `clinpgx check-labels` can provision it (publisher/dev).

    A **second** repo rather than a second table in `just-dna-seq/clinpgx`, for the reason the builder
    already gives its own `release.json`: the two ClinPGx archives do not refresh in lockstep, and one
    repo holding both would date the pair from whichever was published last.

    Same grounds as `clinpgx publish` — CC BY-SA permits redistribution, forbids sale, and requires
    attribution, which `sources.csv` carries. `LICENSE.txt` travels with the parquet: a share-alike
    snapshot whose terms did not travel pins nothing for whoever downloads it.
    """
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    try:
        if dry_run:
            plan = plan_reference_snapshot(snapshot_dir, repo)
            typer.echo(f"would upload {len(plan.files)} file(s) to {plan.repo_id}: {plan.files}")
            return
        plan = publish_reference_snapshot(snapshot_dir, repo, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if SNAPSHOT_LICENSE_FILENAME not in plan.files:
        typer.secho(
            f"  no {SNAPSHOT_LICENSE_FILENAME} in this snapshot, so `license_sha256` pins nothing "
            f"for whoever pulls it. Rebuild with `clinpgx build-labels`.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )

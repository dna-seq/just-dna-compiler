"""Command-line front door for the enricher (Typer) — the network tier's user-facing command.

    just-dna-enricher enrich spec/ --strict --offline
    just-dna-enricher frequencies spec/                 # pass 2: allele frequency (online only)
    just-dna-enricher gene-metrics spec/                # pass 3: gene constraint (offline capable)
    just-dna-enricher literature spec/                  # pass 4: citations (online only)
    just-dna-enricher enrich-and-compile spec/ out/ --frequencies --gene-metrics
    just-dna-enricher gnomad constraint build --download --out gnomad_constraint/   # [dev]
    just-dna-enricher upload out/coronary --repo just-dna-seq/annotators            # [dev]
"""

import json
from pathlib import Path

import typer
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.draft import DraftError, authoring_requirements, blank_template
from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher.acmg import DEFAULT_ACMG_URL, AcmgReport, AcmgSfError, verify_acmg_sf
from just_dna_enricher.clingen import (
    DEFAULT_CLINGEN_URL,
    ClinGenError,
    enrich_dosage_sensitivity,
)
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.clinpgx_build import (
    DEFAULT_CLINPGX_URL,
    download_clinpgx_zip,
)
from just_dna_enricher.clinpgx_build import (
    build_snapshot as build_clinpgx_snapshot,
)
from just_dna_enricher.clinpgx_draft import draft_pharm_variants
from just_dna_enricher.clinvar_build import (
    DEFAULT_CITATIONS_URL,
    build_citations,
    download_var_citations,
)
from just_dna_enricher.clinvar_draft import ClinVarDraftError, draft_gene_panel
from just_dna_enricher.cpic import DEFAULT_CPIC_ENDPOINT, CpicError
from just_dna_enricher.cpic_build import CpicBuildError
from just_dna_enricher.cpic_build import build_snapshot as build_cpic_snapshot
from just_dna_enricher.download import (
    ensure_clinpgx_snapshot,
    ensure_clinvar_snapshot,
    ensure_constraint_snapshot,
    ensure_cpic_snapshot,
    ensure_snapshot,
)
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.frequencies import FrequencyEnrichmentError, enrich_frequencies
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, enrich_gene_metrics
from just_dna_enricher.identifiers import check_identifiers
from just_dna_enricher.licensing import (
    CLINPGX_TERMS,
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    check_declared_use,
)
from just_dna_enricher.literature import LiteratureEnrichmentError, enrich_literature
from just_dna_enricher.locations import (
    CITATIONS_DIRNAME,
    RELEASE_FILENAME,
    resolve_clinpgx_reference,
    resolve_clinvar_reference,
    resolve_constraint_reference,
    resolve_cpic_reference,
    resolve_ensembl_reference,
    resolve_pharmvar_reference,
)
from just_dna_enricher.lookup import (
    as_report_rows,
    lookup_citation,
    lookup_gene,
    lookup_trait,
    lookup_variant,
)
from just_dna_enricher.pgx import PgxEnrichmentError, enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene
from just_dna_enricher.pharmvar import PharmVarError
from just_dna_enricher.pharmvar_build import build_snapshot as build_pharmvar_snapshot
from just_dna_enricher.sequences import summarize_ref_mismatches
from just_dna_enricher.upload import DEFAULT_CLINPGX_REPO_ID, DEFAULT_CPIC_REPO_ID

app = typer.Typer(
    add_completion=False,
    help="Fill the source-independent resolution table (cache + live Ensembl) the compiler consumes.",
    no_args_is_help=True,
)


def _mode(strict: bool) -> str:
    return "strict" if strict else "best_effort"


def _use(value: str) -> str:
    """Normalize the `--use` spelling to the `VALID_DECLARED_USE` member.

    A three-state string rather than a `--commercial/--non-commercial` bool pair: a bool cannot
    express the default, and defaulting either way would have the tool assert a purpose on the
    user's behalf. `unstated` is the honest default.
    """
    normalized = value.strip().replace("-", "_").lower()
    if normalized not in VALID_DECLARED_USE:
        raise typer.BadParameter(
            f"--use must be one of {sorted(VALID_DECLARED_USE)}, got: {value!r}"
        )
    return normalized


@app.command("enrich")
def enrich_(  # `enrich` command; function name avoids shadowing the imported enrich()
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Path | None = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
    use_clinvar: bool = typer.Option(True, "--clinvar/--no-clinvar", help="Use the ClinVar link (after the Ensembl cache)."),
    use_gnomad: bool = typer.Option(True, "--gnomad/--no-gnomad", help="Use the gnomAD link (last, after live Ensembl)."),
    mint_vrs: bool = typer.Option(True, "--vrs/--no-vrs", help="Mint GA4GH VRS allele ids onto resolved rows."),
    verify_ref: bool = typer.Option(
        True, "--verify-ref/--no-verify-ref",
        help="Check each authored ref against the reference sequence and report disagreements.",
    ),
    verify_clinsig: bool = typer.Option(
        True, "--verify-clinsig/--no-verify-clinsig",
        help="Check each authored clin_sig against the ClinVar snapshot's own (warns, never fails).",
    ),
    verify_rsids: bool = typer.Option(
        True, "--verify-rsids/--no-verify-rsids",
        help="Check each authored rsID against dbSNP for merges/withdrawals (online only).",
    ),
    keep_par_twin: bool = typer.Option(
        False, "--keep-par-twin",
        help="Record both contigs of a pseudoautosomal locus. Default keeps only the X spelling, "
             "which is the one every annotation source uses and the only one a hard-masked GRCh38 "
             "analysis set can match.",
    ),
) -> None:
    """Resolve a spec's variants into resolution.csv beside the spec. Exit 1 in strict mode if unresolved."""
    try:
        result = enrich(
            spec_dir, mode=_mode(strict), offline=offline,
            ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache, use_clinvar=use_clinvar,
            use_gnomad=use_gnomad, mint_vrs=mint_vrs, verify_ref=verify_ref,
            verify_clinsig=verify_clinsig, verify_rsids=verify_rsids, keep_par_twin=keep_par_twin,
        )
    except EnrichmentError as exc:
        typer.secho(f"ENRICH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"enriched: {spec_dir / 'resolution.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"rows: {len(result.rows)}  fully_resolved: {result.fully_resolved}  sources: {result.sources}")
    if result.unresolved:
        typer.secho(f"  unresolved: {result.unresolved}", fg=typer.colors.YELLOW, err=True)
    if result.par_twins_dropped:
        # Cyan, not yellow: this is not a finding about the module. It is the table being half the size
        # an author might expect, said out loud so the selection is never silent.
        typer.secho(
            f"  pseudoautosomal: kept the X spelling of {len(result.par_twins_dropped)} locus/loci; "
            f"left out "
            + ", ".join(f"{r} {c}:{p}" for r, c, p in result.par_twins_dropped)
            + " (--keep-par-twin records both)",
            fg=typer.colors.CYAN,
        )
    # Grouped by cause, not one line per row: a systematic mistake (every coordinate shifted one base)
    # produces a finding per variant, and thousands of them hide both the shared cause and every other
    # thing the run reported. Red rather than yellow even in best_effort — this is authored data
    # contradicting the genome, a different and worse thing than a variant the chain could not find.
    for line in summarize_ref_mismatches(result.ref_mismatches):
        typer.secho(f"  ref mismatch: {line}", fg=typer.colors.RED, err=True)
    for stale in result.stale_rsids:
        typer.secho(f"  stale rsid: {stale}", fg=typer.colors.YELLOW, err=True)
    for conflict in result.clin_sig_conflicts:
        # Yellow, not red, and in every mode: this is a disagreement between two opinions, not a row
        # contradicting a fact. An opposed call still deserves the author's attention.
        label = "clin_sig conflict" if conflict.opposed else "clin_sig differs"
        typer.secho(f"  {label}: {conflict}", fg=typer.colors.YELLOW, err=True)


@app.command("frequencies")
def frequencies_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every resolved allele has a frequency."),
    offline: bool = typer.Option(False, "--offline", help="No-op with a warning: gnomAD frequency has no offline snapshot."),
    populations: str | None = typer.Option(
        None, "--populations",
        help="Comma-separated ancestry groups to keep (e.g. 'global' for one row per allele). Default: all.",
    ),
    dataset: str | None = typer.Option(None, "--dataset", help="Override the dataset label recorded on each row."),
) -> None:
    """Fill frequencies.csv from the coordinates already in resolution.csv (pass 2, online only)."""
    from just_dna_enricher.gnomad import FREQUENCY_DATASET_LABEL

    groups = [p.strip() for p in populations.split(",") if p.strip()] if populations else None
    try:
        result = enrich_frequencies(
            spec_dir, mode=_mode(strict), offline=offline, populations=groups,
            dataset=dataset or FREQUENCY_DATASET_LABEL,
        )
    except FrequencyEnrichmentError as exc:
        typer.secho(f"FREQUENCIES FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho("skipped: --offline (gnomAD frequency has no offline snapshot)", fg=typer.colors.YELLOW)
        return
    typer.secho(f"frequencies: {spec_dir / 'frequencies.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"rows: {len(result.rows)}  alleles covered: {len(result.covered)}  sources: {result.sources}")
    if result.missing:
        typer.secho(f"  no gnomAD frequency: {result.missing}", fg=typer.colors.YELLOW, err=True)


@app.command("gene-metrics")
def gene_metrics_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every gene has constraint metrics."),
    offline: bool = typer.Option(False, "--offline", help="Snapshot only: never touch the network."),
    constraint_cache: Path | None = typer.Option(None, "--constraint-cache", help="Explicit gnomAD constraint snapshot dir."),
) -> None:
    """Fill gene_metrics.csv for the genes variants.csv mentions (pass 3, snapshot then live API).

    With no local snapshot the v4.1 one is downloaded from HuggingFace first, exactly as `enrich`
    provisions the Ensembl and ClinVar snapshots — `--offline` is what turns that off, and then the pass
    is snapshot-only. Reaching the live API instead means **v2.1.1** numbers, which the row's `dataset`
    records; provisioning is what keeps a plain install on v4.1.
    """
    try:
        result = enrich_gene_metrics(
            spec_dir, mode=_mode(strict), offline=offline, constraint_cache=constraint_cache,
        )
    except GeneMetricsEnrichmentError as exc:
        typer.secho(f"GENE METRICS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"gene metrics: {spec_dir / 'gene_metrics.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"rows: {len(result.rows)}  genes covered: {len(result.covered)}  sources: {result.sources}")
    if result.missing:
        typer.secho(f"  no gnomAD constraint: {result.missing}", fg=typer.colors.YELLOW, err=True)


@app.command("dosage")
def dosage_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every gene is ClinGen-curated."),
    offline: bool = typer.Option(
        False, "--offline",
        help="No-op with a warning: ClinGen's curation list is a live download with no snapshot.",
    ),
    url: str = typer.Option(DEFAULT_CLINGEN_URL, "--url", help="ClinGen gene-curation list URL."),
    use: str = typer.Option(
        "unstated", "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. ClinGen is CC0, so no declaration "
            "is refused here — it is recorded into sources.csv beside the rows it justifies."
        ),
    ),
) -> None:
    """Add ClinGen dosage-sensitivity rows to gene_metrics.csv (haploinsufficiency/triplosensitivity)."""
    try:
        result = enrich_dosage_sensitivity(
            spec_dir, mode=_mode(strict), declared_use=_use(use), offline=offline, url=url
        )
    except ClinGenError as exc:
        typer.secho(f"DOSAGE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho(
            "skipped: --offline (ClinGen's curation list has no offline snapshot)",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(f"dosage sensitivity: {spec_dir / 'gene_metrics.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"dataset: {result.dataset}  genes curated: {len(result.covered)}")
    if result.missing:
        # ClinGen curates a subset by design, so this is information rather than a problem.
        typer.secho(f"  not in the ClinGen curation list: {result.missing}", fg=typer.colors.YELLOW)


@app.command("literature")
def literature_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail if a cited PMID does not resolve."),
    offline: bool = typer.Option(False, "--offline", help="No-op with a warning: there is no offline PubMed snapshot."),
    check_fulltext: bool = typer.Option(
        True, "--fulltext/--no-fulltext",
        help="Also match provenance quotes against fulltext, falling back to the abstract.",
    ),
    check_doi: bool = typer.Option(
        True, "--doi/--no-doi",
        help="Also confirm the authored DOI resolves in Crossref (covers preprints/books).",
    ),
) -> None:
    """Fill literature.csv from the citations in studies.csv (pass 4, online only)."""
    try:
        result = enrich_literature(
            spec_dir, mode=_mode(strict), offline=offline, check_fulltext=check_fulltext,
            check_doi=check_doi,
        )
    except LiteratureEnrichmentError as exc:
        typer.secho(f"LITERATURE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho("skipped: --offline (PubMed/Europe PMC have no offline snapshot)", fg=typer.colors.YELLOW)
        return
    typer.secho(f"literature: {spec_dir / 'literature.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"citations: {len(result.rows)}  {result.coverage}")
    typer.echo(f"quotes: {result.quotes_found}/{result.quotes_authored} found, "
               f"{result.quotes_unchecked} not checkable")
    if result.missing:
        # Red: a citation that does not resolve is a defect in the module, not a coverage gap.
        typer.secho(f"  PubMed has no record of: {result.missing}", fg=typer.colors.RED, err=True)
    if result.doi_missing:
        typer.secho(f"  Crossref has no record of: {result.doi_missing}", fg=typer.colors.RED, err=True)
    for conflict in result.doi_conflicts:
        typer.secho(f"  doi conflict: {conflict}", fg=typer.colors.RED, err=True)


@app.command("pgx")
def pgx_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail on an allele-function discrepancy."),
    offline: bool = typer.Option(
        False, "--offline", help="Snapshots only: never reach PharmVar or CPIC live.",
    ),
    use: str = typer.Option(
        "unstated", "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. Sources that forbid sale are "
            "SKIPPED when unstated and REFUSED when commercial."
        ),
    ),
    use_pharmvar: bool = typer.Option(True, "--pharmvar/--no-pharmvar", help="Consult PharmVar (needs PHARMVAR_API_KEY)."),
    use_cpic: bool = typer.Option(True, "--cpic/--no-cpic", help="Consult CPIC (open, no key)."),
    cpic_cache: Path | None = typer.Option(None, "--cpic-cache", help="Explicit CPIC snapshot dir."),
    pharmvar_cache: Path | None = typer.Option(None, "--pharmvar-cache", help="Explicit PharmVar snapshot dir."),
) -> None:
    """Cross-check star-allele tables against PharmVar/CPIC and record terms into sources.csv.

    Snapshot first, live second (RM38). A built snapshot serves the check without egress and without
    spending a shared per-IP budget; `--offline` says snapshot-only, and a leg with neither is skipped
    with a reason rather than silently passing.
    """
    try:
        result = enrich_pgx(
            spec_dir, mode=_mode(strict), offline=offline, declared_use=_use(use),
            use_pharmvar=use_pharmvar, use_cpic=use_cpic,
            cpic_cache=cpic_cache, pharmvar_cache=pharmvar_cache,
        )
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except PgxEnrichmentError as exc:
        typer.secho(f"PGX FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.rows:
        typer.secho(f"sources: {spec_dir / 'sources.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"sources recorded: {len(result.rows)}  declared use: {result.declared_use}")
    if result.routes:
        typer.echo("  routes: " + ", ".join(f"{s}={r}" for s, r in sorted(result.routes.items())))
    for reason in result.skipped_offline:
        typer.secho(f"  {reason}", fg=typer.colors.YELLOW, err=True)
    for reason in result.skipped:
        typer.secho(f"  skipped: {reason}", fg=typer.colors.YELLOW, err=True)
    for warning in result.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    # Warns in BOTH modes on purpose: PharmVar and CPIC are different expert panels and genuinely
    # disagree, so failing would make the format arbitrate between its own authorities.
    for conflict in result.conflicts:
        typer.secho(f"  allele-function difference: {conflict}", fg=typer.colors.YELLOW, err=True)


clinpgx_app = typer.Typer(
    add_completion=False,
    help="Build the ClinPGx clinical-annotation snapshot, and cross-check against it.",
    no_args_is_help=True,
)
app.add_typer(clinpgx_app, name="clinpgx")


@clinpgx_app.command("build")
def clinpgx_build_(
    out_dir: Path = typer.Option(..., "--out", help="Snapshot output directory."),
    zip_path: Path | None = typer.Option(None, "--zip", help="Existing clinicalAnnotations.zip (else downloaded)."),
    url: str = typer.Option(DEFAULT_CLINPGX_URL, "--url", help="ClinPGx bulk download URL."),
    use: str = typer.Option("unstated", "--use", help="Declared use: unstated | non-commercial | commercial."),
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
    if zip_path is None:
        zip_path, source_sha = download_clinpgx_zip(Path(out_dir) / "clinicalAnnotations.zip", url)
    result = build_clinpgx_snapshot(zip_path, out_dir, source_url=url, source_sha256=source_sha)
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
        None, "--snapshot",
        help="Explicit ClinPGx snapshot dir. Omit it and the cache is used, or one is downloaded.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use a local snapshot only: never download one.",
    ),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail on a stale evidence level."),
    use: str = typer.Option("unstated", "--use", help="Declared use: unstated | non-commercial | commercial."),
) -> None:
    """Cross-check pharm_variants.csv against the ClinPGx snapshot.

    The snapshot no longer has to be handed over by hand (RM38): explicit path → `$JUST_DNA_CLINPGX_CACHE`
    / the default cache → downloaded from HuggingFace. `--offline` stops at the second step.
    """
    try:
        result = enrich_clinpgx(
            spec_dir, mode=_mode(strict), declared_use=_use(use), snapshot=snapshot,
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


@app.command("draft")
def draft_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: list[str] = typer.Option(..., "--gene", help="Gene to draft from CPIC (repeatable)."),
    drug: list[str] = typer.Option(
        [], "--drug",
        help="Also draft CPIC's prescribing recommendations for this drug (repeatable).",
    ),
    allele: list[str] = typer.Option(
        [], "--allele",
        help=(
            "Draft only these star alleles, in all three tables (repeatable; `*1` is always kept). "
            "A caller emits a bounded allele set, and n alleles is n(n+1)/2 pairs — CYP2D6 is 16,290 "
            "diplotypes unfiltered. Requires a single --gene, since a star name is gene-scoped."
        ),
    ),
    population: str | None = typer.Option(
        None, "--population",
        help="Draft only this CPIC clinical context (e.g. 'NVI'). Default: every context, as rows.",
    ),
    use: str = typer.Option(
        "unstated", "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. CPIC forbids sale, so a draft is "
            "SKIPPED when unstated and REFUSED when commercial."
        ),
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Draft from a built CPIC snapshot only; never reach CPIC live.",
    ),
    cpic_cache: Path | None = typer.Option(None, "--cpic-cache", help="Explicit CPIC snapshot dir."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft PGx tables for one or more genes from CPIC — appends rows, never overwrites one.

    Re-runnable and additive, so a multi-gene module is built up a gene at a time. A row whose key is
    already in the file is reported, never replaced: what CPIC now says about a row you already wrote
    is a finding for `pgx`, not an edit for this command to make.
    """
    declared = _use(use)
    if allele and len(gene) != 1:
        # `*2` in CYP2C9 and `*2` in CYP2C19 are different alleles of different genes, so one set
        # applied across several genes would filter each by a name that means something else there.
        # Drafting is per-gene and re-runnable by design — run the command once per gene.
        typer.secho(
            f"--allele needs exactly one --gene (got {len(gene)}): a star-allele name means a "
            f"different allele in each gene. Draft one gene at a time; the command is additive.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)
    total_added = 0
    for name in gene:
        try:
            result = draft_gene(
                spec_dir, name, drugs=drug, alleles=allele, population=population,
                declared_use=declared, dry_run=dry_run, offline=offline, cpic_cache=cpic_cache,
            )
        except (CpicError, DraftError) as exc:
            typer.secho(f"DRAFT FAILED ({name}): {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        if result.skipped:
            for warning in result.warnings:
                typer.secho(f"  skipped: {warning}", fg=typer.colors.YELLOW, err=True)
            continue
        typer.secho(f"{name}:", fg=typer.colors.GREEN)
        for report in result.reports:
            typer.echo(f"  {report}")
            for outcome in report.differs:
                typer.secho(f"    {outcome}", fg=typer.colors.YELLOW)
        for warning in result.warnings:
            typer.secho(f"  warning: {warning}", fg=typer.colors.YELLOW, err=True)
        total_added += result.added
    verb = "would add" if dry_run else "added"
    typer.echo(f"{verb} {total_added} row(s) across {len(gene)} gene(s) in {spec_dir}")


@app.command("template")
def template_(
    kind: str = typer.Argument(..., help="Authored CSV to emit a header for, e.g. repeat_alleles.csv"),
) -> None:
    """Print a header-only CSV for one authored table kind, generated from the live models.

    Kept working here, but `just-dna-compiler template` is canonical: this needs no network, and an
    author who installed only the tier that owns the CSV shape should not have to add the network
    tier to get a header. See `just-dna-compiler stub` for a template with rows to replace.
    """
    try:
        typer.echo(blank_template(kind), nl=False)
        reqs = authoring_requirements(kind)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"required: {', '.join(reqs['always'])}", fg=typer.colors.BLUE, err=True)
    for group in reqs["any_of"]:
        typer.secho(f"and one of: {' + '.join(group)}", fg=typer.colors.BLUE, err=True)
    if reqs["defaulted"]:
        # Without this line the command gave actively wrong advice: these columns are not "required",
        # so they were never listed, yet an empty cell arrives as None and fails on type.
        shown = ", ".join(f"{k}={v}" for k, v in reqs["defaulted"].items())
        typer.secho(f"must not be left empty (defaults): {shown}", fg=typer.colors.YELLOW, err=True)


@app.command("check-identifiers")
def check_identifiers_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Exit 1 if any identifier is stale."),
    traits: bool = typer.Option(True, "--traits/--no-traits", help="Check trait_efo_id against OLS4."),
    genes: bool = typer.Option(True, "--genes/--no-genes", help="Check gene symbols against HGNC."),
) -> None:
    """Report obsolete trait ontology terms and retired gene symbols (online, reports only).

    Writes nothing: unlike the rsID check (whose verdict lands on resolution.csv), these are module-
    level identifiers with no sidecar column to record, so the report is the whole output.
    """
    if not (spec_dir / "variants.csv").exists():
        typer.secho("no variants.csv — nothing to check", fg=typer.colors.YELLOW)
        return
    try:
        # `spec_dir=` rather than loading the rows here (RM41). This command was the workspace's own
        # evidence that the row-taking form leaves every caller reaching for a private loader.
        report = check_identifiers(spec_dir=spec_dir, check_traits=traits, check_genes=genes)
    except ValueError as exc:
        typer.secho(f"{exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"traits checked: {len(report.traits)}  genes checked: {len(report.genes)}")
    for finding in [*report.stale_traits, *report.stale_genes]:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW, err=True)
    if report.clean:
        typer.secho("all identifiers current", fg=typer.colors.GREEN)
    elif strict:
        raise typer.Exit(code=1)


@app.command("check-acmg")
def check_acmg_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Exit 1 if any acmg_sf disagrees."),
    offline: bool = typer.Option(False, "--offline", help="No network. Needs --sf-list, else nothing is checked."),
    url: str = typer.Option(DEFAULT_ACMG_URL, "--url", help="ACMG secondary-findings page URL (fallback)."),
    sf_list: Path | None = typer.Option(
        None, "--sf-list", exists=True, file_okay=False,
        help="Built ACMG SF snapshot (see `acmg build`). Preferred: NCBI's page still serves v3.2.",
    ),
) -> None:
    """Check each row's `acmg_sf` against the ACMG secondary-findings list (reports only).

    Writes nothing, for the same reason `check-identifiers` writes nothing: `acmg_sf` is an authored
    cell this asks a registry about, not a fact this pass contributes. Filling it here would break the
    check — see `hints.REDUNDANCY_BEARING`.
    """
    if not (spec_dir / "variants.csv").exists():
        typer.secho("no variants.csv — nothing to check", fg=typer.colors.YELLOW)
        return
    try:
        report = verify_acmg_sf(
            spec_dir=spec_dir, mode=_mode(strict), offline=offline, url=url, snapshot_dir=sf_list
        )
    except AcmgSfError as exc:
        typer.secho(f"ACMG CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    version = f"ACMG SF v{report.version}" if report.version else "not consulted"
    typer.echo(f"{version}: {report.checked}/{len(report.verdicts)} row(s) checked")
    for warning in report.warnings:
        typer.secho(f"  {warning}", fg=typer.colors.YELLOW, err=True)
    # Unverifiable disagreements are printed like mismatches and excluded from the exit code: the
    # module may be right and the list old. They are the loud half of the stale-list fix.
    for gene, rows, message in AcmgReport.by_gene(report.unverifiable):
        typer.secho(f"  unverifiable: {gene} ({len(rows)} row(s), first at {rows[0]}): {message}",
                    fg=typer.colors.YELLOW, err=True)
    # Grouped by gene: every verdict is a statement about a gene, so a per-row list prints one
    # sentence once per variant in it.
    for gene, rows, message in AcmgReport.by_gene(report.notes):
        typer.secho(f"  note: {gene} ({len(rows)} row(s)): {message}", fg=typer.colors.CYAN)
    for gene, rows, message in AcmgReport.by_gene(report.mismatches):
        typer.secho(f"  {gene} ({len(rows)} row(s), first at {rows[0]}): {message}",
                    fg=typer.colors.YELLOW, err=True)
    if report.clean and report.version:
        typer.secho("every stated acmg_sf agrees with the list", fg=typer.colors.GREEN)


@app.command("enrich-and-compile")
def enrich_and_compile(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for parquet + manifest.json"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Path | None = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
    use_clinvar: bool = typer.Option(True, "--clinvar/--no-clinvar", help="Use the ClinVar link (after the Ensembl cache)."),
    use_gnomad: bool = typer.Option(True, "--gnomad/--no-gnomad", help="Use the gnomAD link (last, after live Ensembl)."),
    frequencies: bool = typer.Option(False, "--frequencies", help="Also run the frequency pass (writes frequencies.csv)."),
    gene_metrics: bool = typer.Option(False, "--gene-metrics", help="Also run the gene-constraint pass (writes gene_metrics.csv)."),
) -> None:
    """Enrich, then compile from the produced resolution.csv (offline, deterministic). Exit 1 on failure."""
    try:
        enrich(
            spec_dir, mode=_mode(strict), offline=offline,
            ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache, use_clinvar=use_clinvar,
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
        help="Compiled module directory (weights/annotations/studies.parquet + manifest.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/annotators.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Module name under data/<name>/ in the repo. Default: the directory basename.",
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
) -> None:
    """Upload a compiled module to a HuggingFace dataset collection (publisher/dev surface)."""
    from just_dna_enricher.upload import plan_upload, upload_module

    module_name = name or module_dir.name
    if dry_run:
        plan = plan_upload(module_dir, module_name, repo_id)
        typer.echo(f"Would upload to {plan.repo_id} at {plan.path_in_repo}/:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        return

    try:
        plan = upload_module(
            module_dir,
            module_name,
            repo_id=repo_id,
            commit_message=commit_message,
        )
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"UPLOAD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"uploaded: {module_name} → {plan.repo_id}/{plan.path_in_repo} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )


# ── clinvar reference snapshot (build + publish, publisher/dev surface) ─────────────────────────

acmg_app = typer.Typer(
    add_completion=False,
    help="Build the ACMG secondary-findings snapshot from ACMG's published workbook (dev surface).",
    no_args_is_help=True,
)
app.add_typer(acmg_app, name="acmg")


@acmg_app.command("build")
def acmg_build_(
    workbook: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="ACMG SF supplementary workbook (.xlsx), downloaded by you.",
    ),
    out: Path = typer.Option(
        Path("acmg_sf"), "--out", file_okay=False,
        help="Output snapshot directory (writes acmg_sf.csv + release.json).",
    ),
    source_url: str | None = typer.Option(
        None, "--source-url", help="Where the workbook came from, recorded in release.json.",
    ),
    doi: str | None = typer.Option(
        None, "--doi", help="DOI of the statement the workbook accompanies, recorded in release.json.",
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


clinvar_app = typer.Typer(
    add_completion=False,
    help="Build and publish the ClinVar reference snapshot (publisher/dev surface).",
    no_args_is_help=True,
)
app.add_typer(clinvar_app, name="clinvar")


@clinvar_app.command("build")
def clinvar_build_(
    vcf: Path | None = typer.Option(
        None, "--vcf", exists=True, dir_okay=False,
        help="Local ClinVar VCF (.vcf.gz). Omit and pass --download to fetch from NCBI.",
    ),
    download: bool = typer.Option(
        False, "--download", help="Download the NCBI ClinVar GRCh38 VCF into --out first.",
    ),
    out: Path = typer.Option(
        Path("clinvar"), "--out", file_okay=False,
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
        ..., exists=True, file_okay=False, help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None, "--repo", help="Target HF dataset (owner/name). Default: just-dna-seq/clinvar.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be uploaded without contacting HuggingFace.",
    ),
) -> None:
    """Create-or-update the dataset repo and upload the built ClinVar snapshot (publisher/dev)."""
    from just_dna_enricher.upload import plan_reference_snapshot, publish_reference_snapshot

    if dry_run:
        plan = plan_reference_snapshot(snapshot_dir, repo_id)
        typer.echo(f"Would upload to {plan.repo_id}:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        return
    try:
        plan = publish_reference_snapshot(snapshot_dir, repo_id, commit_message=commit_message)
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"PUBLISH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN,
    )


# ── the caches (pre-provision, and say what is where) ───────────────────────────────────────────

cache_app = typer.Typer(
    add_completion=False,
    help="Pre-provision the parquet snapshots, and report which are present.",
    no_args_is_help=True,
)
app.add_typer(cache_app, name="cache")

#: `name -> (resolve, ensure or None, what it serves)`. One table, because the whole point of a cache
#: chapter is that a deployment can see all of them at once — and because the *shape* of the row is the
#: licensing story: PharmVar has no `ensure_*` and never will (personal, non-transferable key).
_CACHES: list[tuple[str, object, object, str]] = [
    ("ensembl", resolve_ensembl_reference, ensure_snapshot, "rsID → coordinate (enrich)"),
    ("clinvar", resolve_clinvar_reference, ensure_clinvar_snapshot, "clinical records (enrich, draft-panel)"),
    ("constraint", resolve_constraint_reference, ensure_constraint_snapshot, "gnomAD v4.1 gene constraint (gene-metrics)"),
    ("clinpgx", resolve_clinpgx_reference, ensure_clinpgx_snapshot, "clinical annotations (clinpgx check)"),
    ("cpic", resolve_cpic_reference, ensure_cpic_snapshot, "alleles/diplotypes/recommendations (pgx, draft)"),
    ("pharmvar", resolve_pharmvar_reference, None, "star alleles (pgx) — build your own, never published"),
]


@cache_app.command("status")
def cache_status_() -> None:
    """Say which snapshots are present, where, and which release each holds.

    Reads only: nothing is downloaded, so this is safe on a machine with no network and it is the first
    thing to run when a pass reports that a source was skipped.
    """
    for name, resolve, ensure, serves in _CACHES:
        path = resolve()
        if path is None:
            how = "`cache pull`" if ensure is not None else f"`{name} build`"
            typer.secho(f"  {name:11} absent   — {serves}; provision with {how}", fg=typer.colors.YELLOW)
            continue
        release = path / RELEASE_FILENAME
        label = ""
        if release.is_file():
            try:
                label = json.loads(release.read_text()).get("dataset") or ""
            except (OSError, json.JSONDecodeError):
                # A provenance failure is not a data failure — the snapshot is still usable.
                label = "(unreadable release.json)"
        typer.secho(f"  {name:11} present  {path}  {label}", fg=typer.colors.GREEN)


@cache_app.command("pull")
def cache_pull_(
    only: list[str] = typer.Option(
        [], "--only", help="Pull just these caches (repeatable). Default: every publishable one.",
    ),
    use: str = typer.Option(
        "unstated", "--use",
        help=(
            "Declared use for the licence-gated snapshots (clinpgx, cpic). They forbid sale, so they "
            "are SKIPPED when unstated and REFUSED when commercial — downloading is taking the data."
        ),
    ),
) -> None:
    """Download the published parquet snapshots from HuggingFace into the local caches.

    The provisioning step a hosted deployment runs **once**, so no pass ever reaches a source live per
    request. Already-complete caches are trusted without touching the network, so this is re-runnable
    and cheap; a truncated file is removed and refetched.

    PharmVar is deliberately not here: its bulk data is pulled under a personal, non-transferable key,
    so there is nothing published to pull. Build it with `pharmvar build --out <dir>`.
    """
    declared = _use(use)
    wanted = {n.strip().lower() for n in only if n.strip()}
    known = {name for name, _, ensure, _ in _CACHES if ensure is not None}
    unknown = sorted(wanted - {name for name, *_ in _CACHES})
    if unknown:
        raise typer.BadParameter(f"unknown cache(s) {unknown}. Known: {sorted(n for n, *_ in _CACHES)}")

    gated = {"clinpgx": CLINPGX_TERMS, "cpic": CPIC_TERMS}
    failures = 0
    for name, _resolve, ensure, _serves in _CACHES:
        if wanted and name not in wanted:
            continue
        if ensure is None:
            if name in wanted:   # asked for by name, so say why it is not coming
                typer.secho(
                    f"  {name}: nothing published to pull — build it with `{name} build --out <dir>`.",
                    fg=typer.colors.YELLOW, err=True,
                )
            continue
        if name in gated:
            # The terms are accepted when the data is TAKEN, and a download is taking it.
            try:
                reason = check_declared_use(gated[name], declared)
            except LicenseRefusal as exc:
                typer.secho(f"  {name}: REFUSED — {exc}", fg=typer.colors.RED, err=True)
                failures += 1
                continue
            if reason is not None:
                typer.secho(f"  {name}: skipped — {reason}", fg=typer.colors.YELLOW, err=True)
                continue
        try:
            path = ensure()
        except Exception as exc:  # noqa: BLE001 - one snapshot failing must not sink the rest
            typer.secho(f"  {name}: FAILED — {exc}", fg=typer.colors.RED, err=True)
            failures += 1
            continue
        typer.secho(f"  {name}: {path}", fg=typer.colors.GREEN)
    if failures:
        raise typer.Exit(code=1)
    typer.echo(f"caches available: {', '.join(sorted(known))}. Run `cache status` to confirm.")


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
app.add_typer(cpic_app, name="cpic")


@cpic_app.command("build")
def cpic_build_(
    out_dir: Path = typer.Option(..., "--out", file_okay=False, help="Snapshot output directory."),
    endpoint: str = typer.Option(DEFAULT_CPIC_ENDPOINT, "--endpoint", help="CPIC PostgREST base URL."),
    use: str = typer.Option("unstated", "--use", help="Declared use: unstated | non-commercial | commercial."),
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
        ..., exists=True, file_okay=False, help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_CPIC_REPO_ID, "--repo", help="Target HuggingFace dataset repo (owner/name).",
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
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN,
    )


@clinpgx_app.command("publish")
def clinpgx_publish_(
    snapshot_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo: str = typer.Option(
        DEFAULT_CLINPGX_REPO_ID, "--repo", help="Target HuggingFace dataset repo (owner/name).",
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
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN,
    )


pharmvar_app = typer.Typer(
    add_completion=False,
    help="Build the PharmVar snapshot with your own key. Operator-built and inject-only; never published.",
    no_args_is_help=True,
)
app.add_typer(pharmvar_app, name="pharmvar")


@pharmvar_app.command("build")
def pharmvar_build_(
    out_dir: Path = typer.Option(..., "--out", file_okay=False, help="Snapshot output directory."),
    use: str = typer.Option("unstated", "--use", help="Declared use: unstated | non-commercial | commercial."),
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
app.add_typer(gnomad_app, name="gnomad")
gnomad_app.add_typer(constraint_app, name="constraint")


@constraint_app.command("build")
def constraint_build_(
    tsv: Path | None = typer.Option(
        None, "--tsv", exists=True, dir_okay=False,
        help="Local gnomAD constraint metrics TSV. Omit and pass --download to fetch it.",
    ),
    download: bool = typer.Option(
        False, "--download", help="Download the gnomAD v4.1 constraint TSV (95.5 MB) into --out first.",
    ),
    out: Path = typer.Option(
        Path("gnomad_constraint"), "--out", file_okay=False,
        help="Output snapshot directory (writes data/gnomad_constraint.parquet + release.json).",
    ),
) -> None:
    """Reduce the per-transcript constraint TSV to the gene-level parquet the resolver reads."""
    from just_dna_enricher.constraint_build import build_snapshot, download_constraint_tsv

    if tsv is None and not download:
        typer.secho("Provide --tsv PATH or --download.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    try:
        source = tsv if tsv is not None else download_constraint_tsv(
            out / "gnomad.v4.1.constraint_metrics.tsv"
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
        ..., exists=True, file_okay=False, help="Built snapshot directory (data/*.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None, "--repo", help="Target HF dataset (owner/name). Default: just-dna-seq/gnomad_constraint.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be uploaded without contacting HuggingFace.",
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
        f"published: {snapshot_dir} → {plan.repo_id} ({len(plan.files)} files)", fg=typer.colors.GREEN,
    )


# ── VRS allele ids ──────────────────────────────────────────────────────────────────────────────

vrs_app = typer.Typer(
    add_completion=False,
    help="GA4GH VRS allele identity for an already-resolved module.",
    no_args_is_help=True,
)
app.add_typer(vrs_app, name="vrs")


@vrs_app.command("mint")
def vrs_mint_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    offline: bool = typer.Option(
        False, "--offline",
        help="Substitutions only: indels need the reference sequence, which means a network call.",
    ),
) -> None:
    """Stamp ga4gh:VA.… allele ids onto resolution.csv (substitutions offline, indels online)."""
    from just_dna_compiler.compiler import load_csv_rows
    from just_dna_format.resolution import ResolutionRow

    from just_dna_enricher.enrich import _write_resolution_csv
    from just_dna_enricher.vrs import mint_resolution_rows

    path = spec_dir / "resolution.csv"
    if not path.exists():
        typer.secho(f"no resolution.csv in {spec_dir} — run `enrich` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    rows, errors, _ = load_csv_rows(path, ResolutionRow, "resolution.csv")
    if errors:
        typer.secho(f"resolution.csv is invalid: {errors[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    result = mint_resolution_rows(rows, offline=offline)
    _write_resolution_csv(rows, path)
    typer.secho(f"minted: {path}", fg=typer.colors.GREEN)
    typer.echo(
        f"stdlib: {result.minted_stdlib}  normalized: {result.minted_normalized}  "
        f"unmintable: {result.skipped_unmintable}  already present: {result.already_present}"
    )
    typer.echo(f"coverage: {result.identified}/{result.alleles} allele(s) carry a ga4gh:VA. id")
    for line in result.coverage_warnings():
        typer.secho(f"  warning: {line}", fg=typer.colors.YELLOW, err=True)
    for mismatch in result.mismatches:
        typer.secho(f"  mismatch: {mismatch}", fg=typer.colors.YELLOW, err=True)


if __name__ == "__main__":
    app()


# ── Authoring lookups (0.5): questions about a value, never an edit to one ───────────────────────
hint_app = typer.Typer(help="Look up what is known about a variant or citation. Writes nothing.")
app.add_typer(hint_app, name="hint")


def _echo_hint(hint: object) -> None:
    """Findings to stderr, advisory answers to stdout — so a pipe carries the answers alone."""
    colours = {"error": typer.colors.RED, "warning": typer.colors.YELLOW, "info": typer.colors.BLUE}
    for row in as_report_rows(hint):
        typer.echo(f"{row['column']}\t{row['value']}\t[{row['refusal']}, from {row['source']}]")
    for finding in getattr(hint, "findings", []):
        typer.secho(f"  {finding.level}: {finding.message}", fg=colours[finding.level], err=True)


@hint_app.command("variant")
def hint_variant_(
    rsid: str | None = typer.Option(None, "--rsid", help="dbSNP id to look up."),
    chrom: str | None = typer.Option(None, "--chrom", help="Chromosome (with --start)."),
    start: int | None = typer.Option(None, "--start", help="1-based position (with --chrom)."),
    ref: str | None = typer.Option(None, "--ref", help="Reference allele, for an allele-exact lookup."),
    alts: str | None = typer.Option(None, "--alts", help="Alt allele(s), comma-separated."),
    ambiguity: bool = typer.Option(False, "--ambiguity", help="Warn when the answer is not unique."),
    frequencies: bool = typer.Option(False, "--frequencies", help="Add gnomAD populations (paced: ~6s)."),
    offline: bool = typer.Option(False, "--offline", help="Snapshots only; never touch the network."),
    ensembl_cache: Path | None = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache."),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Validity, coordinates, alleles, populations and clinical calls for one variant.

    Nothing is decided for you: a one-to-many rsID returns every locus and a position matching
    several rsIDs returns every candidate. The coordinate is reported, never written into
    `variants.csv` — resolution puts it in `resolution.csv`, which is where it belongs.
    """
    if rsid is None and (chrom is None or start is None):
        typer.secho("give --rsid, or --chrom and --start", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    hint = lookup_variant(
        rsid=rsid, chrom=chrom, start=start, ref=ref, alts=alts,
        ambiguity=ambiguity, frequencies=frequencies, offline=offline,
        ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache,
    )
    if as_json:
        typer.echo(json.dumps({
            "rsid": hint.rsid,
            "rsid_status": str(hint.rsid_status) if hint.rsid_status else None,
            "loci": hint.loci,
            "rsid_candidates": hint.rsid_candidates,
            "populations": hint.populations,
            "clin_sig": hint.clin_sig,
            "vrs_id": hint.vrs_id,
            "ambiguous": hint.ambiguous,
            "advisory": as_report_rows(hint),
            "findings": [f"{f.level}: {f.message}" for f in hint.findings],
        }, indent=2, default=str))
        return
    for locus in hint.loci:
        typer.echo(f"locus\t{locus['chrom']}:{locus['start']}\t{locus.get('ref')}>{locus.get('alts')}")
    for candidate in hint.rsid_candidates:
        typer.echo(f"rsid_candidate\t{candidate}")
    for population in hint.populations:
        af = population.get("allele_frequency")
        typer.echo(
            f"population\t{population.get('population')}\tAC={population.get('allele_count')}"
            f"\tAN={population.get('allele_number')}\tAF={'' if af is None else f'{af:.6g}'}"
        )
    _echo_hint(hint)


@hint_app.command("citation")
def hint_citation_(
    pmid: str | None = typer.Option(None, "--pmid", help="PubMed id to check."),
    doi: str | None = typer.Option(None, "--doi", help="DOI to check (the one you authored)."),
    offline: bool = typer.Option(False, "--offline", help="Skip the check and say so."),
) -> None:
    """Does this citation exist, and what is its other identifier?

    A paywall hides the fulltext, never the PubMed record, so existence is answerable for paywalled
    work; Crossref covers what PubMed does not index at all. Every answer is tri-state — `unknown`
    means the registry could not be asked, which is not the same as "no such paper".
    """
    if pmid is None and doi is None:
        typer.secho("give --pmid or --doi", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    hint = lookup_citation(pmid=pmid, doi=doi, offline=offline)
    for label, value in (("pmid_exists", hint.pmid_exists), ("doi_exists", hint.doi_exists)):
        typer.echo(f"{label}\t{'unknown' if value is None else value}")
    if hint.pmcid:
        typer.echo(f"pmcid\t{hint.pmcid}")
    _echo_hint(hint)


@hint_app.command("trait")
def hint_trait_(curie: str = typer.Argument(..., help="Trait CURIE, e.g. EFO_0004340")) -> None:
    """Is this trait id current, obsolete, or unknown?"""
    typer.echo(str(lookup_trait(curie)))


@hint_app.command("gene")
def hint_gene_(symbol: str = typer.Argument(..., help="Gene symbol, e.g. MTHFR")) -> None:
    """Is this gene symbol approved or retired?"""
    typer.echo(str(lookup_gene(symbol)))


@app.command("draft-clinpgx")
def draft_clinpgx_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    snapshot: Path = typer.Option(
        ..., "--snapshot", exists=True, file_okay=False,
        help="Built ClinPGx snapshot (see `clinpgx build`). Inject-only; nothing is downloaded.",
    ),
    drug: list[str] = typer.Option([], "--drug", help="Only annotations naming this drug (repeatable)."),
    gene: list[str] = typer.Option([], "--gene", help="Reserved; the annotation snapshot has no gene column."),
    min_evidence_level: str | None = typer.Option(
        None, "--min-evidence-level", help="Keep annotations at least this strong: 1A|1B|2A|2B|3|4."
    ),
    use: str = typer.Option(
        "unstated", "--use",
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
            spec_dir, snapshot=snapshot, genes=gene, drugs=drug,
            min_evidence_level=min_evidence_level, declared_use=_use(use), dry_run=dry_run,
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


@app.command("draft-panel")
def draft_panel_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: list[str] = typer.Option(..., "--gene", help="Gene to draft from ClinVar (repeatable)."),
    snapshot: Path | None = typer.Option(
        None, "--snapshot", exists=True, file_okay=False,
        help=(
            "Built ClinVar snapshot (see `clinvar build`). Omit it and the cache is used, or the "
            "published snapshot downloaded — the citations table comes with it, which is what a panel "
            "needs to compile."
        ),
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use a local snapshot only: never download one.",
    ),
    clin_sig: str | None = typer.Option(
        None, "--clin-sig",
        help="Comma-separated calls to include. Default: pathogenic,likely_pathogenic.",
    ),
    min_review_stars: int = typer.Option(
        2, "--min-review-stars", min=0, max=4,
        help="Review-status floor. 2 = multiple submitters, no conflicts.",
    ),
    max_citations: int = typer.Option(
        3, "--max-citations", min=0,
        help="Study rows to draft per variant from ClinVar's literature links. 0 disables.",
    ),
    use: str = typer.Option("unstated", "--use", help="Declared use (ClinVar is public domain)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be added; write nothing."),
) -> None:
    """Draft a gene panel's variants.csv rows from ClinVar — appends, never overwrites a row.

    The drafted rows carry a **genotype placeholder**, so the module will not compile until you decide
    what each finding is about. That is deliberate: ClinVar publishes alleles, and whether carrying one
    is a carrier state or an affected one follows from the condition's inheritance mode, which the
    source does not say. Rows land in their gene's block, and a re-run leaves anything already there —
    stub or filled — exactly as it is.
    """
    calls = (
        frozenset(c.strip() for c in clin_sig.split(",") if c.strip()) if clin_sig else None
    )
    try:
        result = draft_gene_panel(
            spec_dir, gene, snapshot=snapshot, offline=offline,
            **({"clin_sig": calls} if calls else {}),
            min_review_stars=min_review_stars, max_citations=max_citations,
            declared_use=_use(use), dry_run=dry_run,
        )
    except (ClinVarDraftError, DraftError) as exc:
        typer.secho(f"DRAFT FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped:
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
    breakdown = ", ".join(
        f"{r.csv_name} {len(r.added)}" for r in result.reports
    ) or "nothing"
    typer.secho(f"{verb}: {breakdown} — in {spec_dir}", fg=typer.colors.GREEN)


@clinvar_app.command("citations")
def clinvar_citations_(
    out: Path = typer.Option(..., "--out", file_okay=False, help="Existing ClinVar snapshot dir."),
    citations_txt: Path | None = typer.Option(
        None, "--citations", exists=True, dir_okay=False, help="Local var_citations.txt."
    ),
    download: bool = typer.Option(False, "--download", help="Fetch var_citations.txt first."),
    url: str = typer.Option(DEFAULT_CITATIONS_URL, "--url", help="Source for --download."),
) -> None:
    """Add ClinVar's literature links to a snapshot: `data/citations.parquet` ([dev], needs polars).

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
            fg=typer.colors.YELLOW, err=True,
        )

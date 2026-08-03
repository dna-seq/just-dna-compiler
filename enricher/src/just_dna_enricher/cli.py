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
from typing import Optional

import typer
from just_dna_compiler.compiler import compile_module

from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_compiler.draft import DraftError, authoring_requirements, blank_template
from just_dna_enricher.acmg import DEFAULT_ACMG_URL, AcmgReport, AcmgSfError, verify_acmg_sf
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.lookup import (
    as_report_rows,
    lookup_citation,
    lookup_gene,
    lookup_trait,
    lookup_variant,
)
from just_dna_enricher.clinpgx_build import (
    DEFAULT_CLINPGX_URL,
    build_snapshot as build_clinpgx_snapshot,
    download_clinpgx_zip,
)
from just_dna_enricher.licensing import CLINPGX_TERMS, LicenseRefusal, check_declared_use
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.cpic import CpicError
from just_dna_enricher.pgx import PgxEnrichmentError, enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene
from just_dna_enricher.clinpgx_draft import draft_pharm_variants
from just_dna_enricher.clinvar_draft import ClinVarDraftError, draft_gene_panel
from just_dna_enricher.clinvar_build import (
    DEFAULT_CITATIONS_URL,
    build_citations,
    download_var_citations,
)
from just_dna_enricher.locations import CITATIONS_DIRNAME, RELEASE_FILENAME
from just_dna_enricher.frequencies import FrequencyEnrichmentError, enrich_frequencies
from just_dna_enricher.clingen import (
    DEFAULT_CLINGEN_URL,
    ClinGenError,
    enrich_dosage_sensitivity,
)
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, enrich_gene_metrics
from just_dna_enricher.literature import LiteratureEnrichmentError, enrich_literature

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
    ensembl_cache: Optional[Path] = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."),
    clinvar_cache: Optional[Path] = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
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
) -> None:
    """Resolve a spec's variants into resolution.csv beside the spec. Exit 1 in strict mode if unresolved."""
    try:
        result = enrich(
            spec_dir, mode=_mode(strict), offline=offline,
            ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache, use_clinvar=use_clinvar,
            use_gnomad=use_gnomad, mint_vrs=mint_vrs, verify_ref=verify_ref,
            verify_clinsig=verify_clinsig, verify_rsids=verify_rsids,
        )
    except EnrichmentError as exc:
        typer.secho(f"ENRICH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"enriched: {spec_dir / 'resolution.csv'}", fg=typer.colors.GREEN)
    typer.echo(f"rows: {len(result.rows)}  fully_resolved: {result.fully_resolved}  sources: {result.sources}")
    if result.unresolved:
        typer.secho(f"  unresolved: {result.unresolved}", fg=typer.colors.YELLOW, err=True)
    for mismatch in result.ref_mismatches:
        # Red rather than yellow even in best_effort: this is authored data contradicting the genome,
        # which is a different (and worse) thing than a variant the chain could not find.
        typer.secho(f"  ref mismatch: {mismatch}", fg=typer.colors.RED, err=True)
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
    populations: Optional[str] = typer.Option(
        None, "--populations",
        help="Comma-separated ancestry groups to keep (e.g. 'global' for one row per allele). Default: all.",
    ),
    dataset: Optional[str] = typer.Option(None, "--dataset", help="Override the dataset label recorded on each row."),
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
    constraint_cache: Optional[Path] = typer.Option(None, "--constraint-cache", help="Explicit gnomAD constraint snapshot dir."),
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
            spec_dir, mode=_mode(strict), declared_use=_use(use), url=url
        )
    except ClinGenError as exc:
        typer.secho(f"DOSAGE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
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
    offline: bool = typer.Option(False, "--offline", help="No-op: PharmVar/CPIC are live-only."),
    use: str = typer.Option(
        "unstated", "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. Sources that forbid sale are "
            "SKIPPED when unstated and REFUSED when commercial."
        ),
    ),
    use_pharmvar: bool = typer.Option(True, "--pharmvar/--no-pharmvar", help="Consult PharmVar (needs PHARMVAR_API_KEY)."),
    use_cpic: bool = typer.Option(True, "--cpic/--no-cpic", help="Consult CPIC (open, no key)."),
) -> None:
    """Cross-check star-allele tables against PharmVar/CPIC and record terms into sources.csv."""
    try:
        result = enrich_pgx(
            spec_dir, mode=_mode(strict), offline=offline, declared_use=_use(use),
            use_pharmvar=use_pharmvar, use_cpic=use_cpic,
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
    zip_path: Optional[Path] = typer.Option(None, "--zip", help="Existing clinicalAnnotations.zip (else downloaded)."),
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
    source_sha: Optional[str] = None
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
    snapshot: Optional[Path] = typer.Option(None, "--snapshot", help="ClinPGx snapshot directory."),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail on a stale evidence level."),
    use: str = typer.Option("unstated", "--use", help="Declared use: unstated | non-commercial | commercial."),
) -> None:
    """Cross-check pharm_variants.csv against the ClinPGx snapshot (offline-capable)."""
    try:
        result = enrich_clinpgx(
            spec_dir, mode=_mode(strict), declared_use=_use(use), snapshot=snapshot,
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
    population: Optional[str] = typer.Option(
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
                declared_use=declared, dry_run=dry_run,
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
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_format.spec import VariantRow

    from just_dna_enricher.identifiers import check_identifiers

    variants_path = spec_dir / "variants.csv"
    if not variants_path.exists():
        typer.secho("no variants.csv — nothing to check", fg=typer.colors.YELLOW)
        return
    variants, errors, _ = _load_csv_rows(variants_path, VariantRow, "variants.csv")
    if errors:
        typer.secho(f"variants.csv is invalid: {errors[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    report = check_identifiers(variants, check_traits=traits, check_genes=genes)
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
    sf_list: Optional[Path] = typer.Option(
        None, "--sf-list", exists=True, file_okay=False,
        help="Built ACMG SF snapshot (see `acmg build`). Preferred: NCBI's page still serves v3.2.",
    ),
) -> None:
    """Check each row's `acmg_sf` against the ACMG secondary-findings list (reports only).

    Writes nothing, for the same reason `check-identifiers` writes nothing: `acmg_sf` is an authored
    cell this asks a registry about, not a fact this pass contributes. Filling it here would break the
    check — see `hints.REDUNDANCY_BEARING`.
    """
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_format.spec import VariantRow

    variants_path = spec_dir / "variants.csv"
    if not variants_path.exists():
        typer.secho("no variants.csv — nothing to check", fg=typer.colors.YELLOW)
        return
    variants, errors, _ = _load_csv_rows(variants_path, VariantRow, "variants.csv")
    if errors:
        typer.secho(f"variants.csv is invalid: {errors[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        report = verify_acmg_sf(
            variants, mode=_mode(strict), offline=offline, url=url, snapshot_dir=sf_list
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
    ensembl_cache: Optional[Path] = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."),
    clinvar_cache: Optional[Path] = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
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
    repo_id: Optional[str] = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/annotators.",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Module name under data/<name>/ in the repo. Default: the directory basename.",
    ),
    commit_message: Optional[str] = typer.Option(
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
    source_url: Optional[str] = typer.Option(
        None, "--source-url", help="Where the workbook came from, recorded in release.json.",
    ),
    doi: Optional[str] = typer.Option(
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
    vcf: Optional[Path] = typer.Option(
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
    repo_id: Optional[str] = typer.Option(
        None, "--repo", help="Target HF dataset (owner/name). Default: just-dna-seq/clinvar.",
    ),
    commit_message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message."),
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
    tsv: Optional[Path] = typer.Option(
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
    repo_id: Optional[str] = typer.Option(
        None, "--repo", help="Target HF dataset (owner/name). Default: just-dna-seq/gnomad_constraint.",
    ),
    commit_message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message."),
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
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_format.resolution import ResolutionRow

    from just_dna_enricher.enrich import _write_resolution_csv
    from just_dna_enricher.vrs import mint_resolution_rows

    path = spec_dir / "resolution.csv"
    if not path.exists():
        typer.secho(f"no resolution.csv in {spec_dir} — run `enrich` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    rows, errors, _ = _load_csv_rows(path, ResolutionRow, "resolution.csv")
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
    rsid: Optional[str] = typer.Option(None, "--rsid", help="dbSNP id to look up."),
    chrom: Optional[str] = typer.Option(None, "--chrom", help="Chromosome (with --start)."),
    start: Optional[int] = typer.Option(None, "--start", help="1-based position (with --chrom)."),
    ref: Optional[str] = typer.Option(None, "--ref", help="Reference allele, for an allele-exact lookup."),
    alts: Optional[str] = typer.Option(None, "--alts", help="Alt allele(s), comma-separated."),
    ambiguity: bool = typer.Option(False, "--ambiguity", help="Warn when the answer is not unique."),
    frequencies: bool = typer.Option(False, "--frequencies", help="Add gnomAD populations (paced: ~6s)."),
    offline: bool = typer.Option(False, "--offline", help="Snapshots only; never touch the network."),
    ensembl_cache: Optional[Path] = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache."),
    clinvar_cache: Optional[Path] = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot."),
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
    pmid: Optional[str] = typer.Option(None, "--pmid", help="PubMed id to check."),
    doi: Optional[str] = typer.Option(None, "--doi", help="DOI to check (the one you authored)."),
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
    min_evidence_level: Optional[str] = typer.Option(
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
    snapshot: Path = typer.Option(
        ..., "--snapshot", exists=True, file_okay=False,
        help="Built ClinVar snapshot (see `clinvar build`). Inject-only; nothing is downloaded.",
    ),
    clin_sig: Optional[str] = typer.Option(
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
            spec_dir, gene, snapshot=snapshot,
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
    typer.secho(
        f"{verb} {result.added} row(s), {result.already_present} already present, in {spec_dir}",
        fg=typer.colors.GREEN,
    )


@clinvar_app.command("citations")
def clinvar_citations_(
    out: Path = typer.Option(..., "--out", file_okay=False, help="Existing ClinVar snapshot dir."),
    citations_txt: Optional[Path] = typer.Option(
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
    source_sha: Optional[str] = None
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

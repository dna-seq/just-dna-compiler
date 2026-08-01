"""Command-line front door for the enricher (Typer) — the network tier's user-facing command.

    just-dna-enricher enrich spec/ --strict --offline
    just-dna-enricher frequencies spec/                 # pass 2: allele frequency (online only)
    just-dna-enricher gene-metrics spec/                # pass 3: gene constraint (offline capable)
    just-dna-enricher literature spec/                  # pass 4: citations (online only)
    just-dna-enricher enrich-and-compile spec/ out/ --frequencies --gene-metrics
    just-dna-enricher gnomad constraint build --download --out gnomad_constraint/   # [dev]
    just-dna-enricher upload out/coronary --repo just-dna-seq/annotators            # [dev]
"""

from pathlib import Path
from typing import Optional

import typer
from just_dna_compiler.compiler import compile_module

from just_dna_format.vocab import VALID_DECLARED_USE

from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_enricher.pgx import PgxEnrichmentError, enrich_pgx
from just_dna_enricher.frequencies import FrequencyEnrichmentError, enrich_frequencies
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
    """Fill gene_metrics.csv for the genes variants.csv mentions (pass 3, snapshot then live API)."""
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

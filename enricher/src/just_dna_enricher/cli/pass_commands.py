"""The enrichment passes: `enrich`, `frequencies`, `gene-metrics`, `dosage`, `gene-validity`, `gwas`,
`assertions`, `literature` and `pgx` (RM260 split this out of the former single-file `cli.py`).
"""

from pathlib import Path

import typer

from just_dna_enricher.assertions import (
    ASSERTION_GENOME_BUILD,
    ClinicalAssertionError,
    enrich_clinical_assertions,
)
from just_dna_enricher.cli._shared import _mode, _use, app
from just_dna_enricher.clingen import DEFAULT_CLINGEN_URL, ClinGenError, enrich_dosage_sensitivity
from just_dna_enricher.currency import unchecked_sentences
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.frequencies import FrequencyEnrichmentError, enrich_frequencies
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError, enrich_gene_metrics
from just_dna_enricher.gene_validity import CLINGEN_SOURCE as CLINGEN_VALIDITY_SOURCE
from just_dna_enricher.gene_validity import GeneValidityError, enrich_gene_validity
from just_dna_enricher.grch37 import summarize_build_diagnoses
from just_dna_enricher.gwas import GwasError, enrich_gwas
from just_dna_enricher.licensing import LicenseRefusal, sidecar_path, sources_path
from just_dna_enricher.literature import LiteratureEnrichmentError, enrich_literature
from just_dna_enricher.pgx import PgxEnrichmentError, enrich_pgx
from just_dna_enricher.sequences import summarize_ref_mismatches


@app.command("enrich")
def enrich_(  # `enrich` command; function name avoids shadowing the imported enrich()
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Path | None = typer.Option(
        None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."
    ),
    clinvar_cache: Path | None = typer.Option(None, "--clinvar-cache", help="Explicit ClinVar snapshot dir."),
    pubmind_cache: Path | None = typer.Option(
        None,
        "--pubmind-cache",
        help=(
            "Built PubMind snapshot dir (from `pubmind build`) — the second authority in the "
            "clinical-significance concordance check. Omit it and $JUST_DNA_PUBMIND_CACHE is read; "
            "with neither, PubMind's leg reads unchecked rather than agreement."
        ),
    ),
    use_clinvar: bool = typer.Option(
        True, "--clinvar/--no-clinvar", help="Use the ClinVar link (after the Ensembl cache)."
    ),
    use_gnomad: bool = typer.Option(
        True, "--gnomad/--no-gnomad", help="Use the gnomAD link (last, after live Ensembl)."
    ),
    mint_vrs: bool = typer.Option(
        True, "--vrs/--no-vrs", help="Mint GA4GH VRS allele ids onto resolved rows."
    ),
    verify_ref: bool = typer.Option(
        True,
        "--verify-ref/--no-verify-ref",
        help="Check each authored ref against the reference sequence and report disagreements.",
    ),
    verify_clinsig: bool = typer.Option(
        True,
        "--verify-clinsig/--no-verify-clinsig",
        help="Check each authored clin_sig against the ClinVar snapshot's own (warns, never fails).",
    ),
    verify_rsids: bool = typer.Option(
        True,
        "--verify-rsids/--no-verify-rsids",
        help="Check each authored rsID against dbSNP for merges/withdrawals (online only).",
    ),
    verify_datasets: bool = typer.Option(
        True,
        "--verify-datasets/--no-verify-datasets",
        help="Check each release recorded in sources.csv against the one that source publishes now, "
        "and report the gap. One request per source, and the cheap question to put before "
        "--rederive: it tells you whether re-asking every subject is worth the run.",
    ),
    keep_par_twin: bool = typer.Option(
        False,
        "--keep-par-twin",
        help="Record both contigs of a pseudoautosomal locus. Default keeps only the X spelling, "
        "which is the one every annotation source uses and the only one a hard-masked GRCh38 "
        "analysis set can match.",
    ),
    rederive: bool = typer.Option(
        False,
        "--rederive",
        help="Re-ask every source about every subject, including the ones already recorded, and "
        "report which of them changed value. An ordinary run gap-fills and never re-asks, so a "
        "source that quietly revised an answer moves nothing you could notice.",
    ),
    keep_staging: bool = typer.Option(
        False,
        "--keep-staging",
        help="Leave the staged answers beside resolution.csv after a successful run. They are "
        "removed by default; a killed run leaves them either way, and the next run resumes "
        "from them.",
    ),
) -> None:
    """Resolve a spec's variants into resolution.csv beside the spec. Exit 1 in strict mode if unresolved."""
    try:
        result = enrich(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            ensembl_cache=ensembl_cache,
            clinvar_cache=clinvar_cache,
            pubmind_cache=pubmind_cache,
            use_clinvar=use_clinvar,
            use_gnomad=use_gnomad,
            mint_vrs=mint_vrs,
            verify_ref=verify_ref,
            verify_clinsig=verify_clinsig,
            verify_rsids=verify_rsids,
            verify_datasets=verify_datasets,
            keep_par_twin=keep_par_twin,
            rederive=rederive,
            keep_staging=keep_staging,
        )
    except EnrichmentError as exc:
        typer.secho(f"ENRICH FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # The path the pass actually wrote, not `spec_dir / <name>` (RM99) — a module keeping its
    # sidecars under `derived/` is written there, and a guess sends the author to a file that
    # did not change.
    typer.secho(
        f"enriched: {sidecar_path(spec_dir, 'resolution.csv', error=EnrichmentError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"rows: {len(result.rows)}  fully_resolved: {result.fully_resolved}  sources: {result.sources}"
    )
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
    # Why the ref disagrees, when GRCh37 explains it (RM48). Printed right under the mismatch it
    # diagnoses, because a wrong build is a different remedy from a wrong cell: one row is edited, a
    # whole module is re-authored from rs-numbers.
    for line in summarize_build_diagnoses(result.build_diagnoses):
        typer.secho(f"  old-assembly coordinate: {line}", fg=typer.colors.RED, err=True)
    # Unconditional on `ref_mismatches`, because gating it on them made it unreachable: offline
    # skips the reference check too, so the list is always empty in exactly the runs this notice is
    # about. Which is the point worth saying — an offline run checked neither, and silence here would
    # read as "checked, all clear" (S4).
    if result.build_not_diagnosed == "skipped_offline":
        typer.secho(
            "  reference-allele check and wrong-build diagnosis not run: --offline (both need a "
            "live sequence service, and neither has a local equivalent)",
            fg=typer.colors.CYAN,
        )
    for stale in result.stale_rsids:
        typer.secho(f"  stale rsid: {stale}", fg=typer.colors.YELLOW, err=True)
    for conflict in result.clin_sig_conflicts:
        # Yellow, not red, and in every mode: this is a disagreement between two opinions, not a row
        # contradicting a fact. An opposed call still deserves the author's attention.
        label = "clin_sig conflict" if conflict.opposed else "clin_sig differs"
        typer.secho(f"  {label}: {conflict}", fg=typer.colors.YELLOW, err=True)
    # Say when the check did not run. Silence here reads as "checked, all clear" — which is the one
    # thing it must never mean (S4). `not_requested` is the author's own `--no-verify-clinsig` and
    # needs no echo back.
    if result.clin_sig_not_checked and result.clin_sig_not_checked != "not_requested":
        reason = {
            "no_snapshot": "no ClinVar snapshot this run",
            "unusable_snapshot": "the ClinVar snapshot is present but not queryable",
        }.get(result.clin_sig_not_checked, result.clin_sig_not_checked)
        typer.secho(f"  clin_sig cross-check not run: {reason}", fg=typer.colors.CYAN)
    # One aggregated line, never one per row: on a drafted panel this is thousands of comparisons and
    # what the author has to know is the split. The conflicts themselves printed above, individually,
    # because those are the rows that need answering.
    if result.clin_sig_comparison is not None:
        typer.secho(f"  clin_sig: {result.clin_sig_comparison}", fg=typer.colors.CYAN)
    # `None` means nobody re-derived and there is nothing to say; an empty list means every recorded
    # subject was re-asked and none moved, which prints nothing either — a comparison whose empty
    # result is the normal case would be announcing a zero as evidence. Only a real difference prints.
    for drift in result.rederived or ():
        typer.secho(f"  re-derived: {drift}", fg=typer.colors.YELLOW, err=True)
    # RM85. One line per superseded release rather than an aggregate: `sources.csv` carries one row
    # per (source, layer), so this is a handful of lines on the largest module — the collapse rule is
    # for the per-variant passes, where a systematic mistake produces thousands. Yellow, because an
    # author has something to do about it; the legs nobody could ask are cyan, since that is not a
    # finding about the module, and they are aggregated by reason because a reason repeats.
    if result.dataset_currency is not None:
        for superseded in result.dataset_currency.behind:
            typer.secho(f"  dataset moved on: {superseded}", fg=typer.colors.YELLOW, err=True)
        for line in unchecked_sentences(result.dataset_currency):
            typer.secho(f"  dataset currency: {line}", fg=typer.colors.CYAN)
        # Silence would read as "checked, all clear" (S4). `not_requested` is the author's own
        # `--no-verify-datasets` and needs no echo back.
        if (
            result.dataset_currency.not_checked is not None
            and result.dataset_currency.not_checked != "nothing_to_check"
        ):
            typer.secho(
                f"  dataset currency not checked: {result.dataset_currency.not_checked} — no source "
                f"was asked which release it publishes, so every recorded dataset is unchecked "
                f"rather than current",
                fg=typer.colors.CYAN,
            )


@app.command("frequencies")
def frequencies_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every resolved allele has a frequency."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="No-op with a warning: gnomAD frequency has no offline snapshot."
    ),
    populations: str | None = typer.Option(
        None,
        "--populations",
        help="Comma-separated ancestry groups to keep (e.g. 'global' for one row per allele). Default: all.",
    ),
    dataset: str | None = typer.Option(
        None, "--dataset", help="Override the dataset label recorded on each row."
    ),
) -> None:
    """Fill frequencies.csv from the coordinates already in resolution.csv (pass 2, online only)."""
    from just_dna_enricher.gnomad import FREQUENCY_DATASET_LABEL

    groups = [p.strip() for p in populations.split(",") if p.strip()] if populations else None
    try:
        result = enrich_frequencies(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            populations=groups,
            dataset=dataset or FREQUENCY_DATASET_LABEL,
        )
    except FrequencyEnrichmentError as exc:
        typer.secho(f"FREQUENCIES FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho("skipped: --offline (gnomAD frequency has no offline snapshot)", fg=typer.colors.YELLOW)
        return
    # The path the pass actually wrote, not `spec_dir / <name>` (RM99) — a module keeping its
    # sidecars under `derived/` is written there, and a guess sends the author to a file that
    # did not change.
    typer.secho(
        f"frequencies: {sidecar_path(spec_dir, 'frequencies.csv', error=FrequencyEnrichmentError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"rows: {len(result.rows)}  alleles covered: {len(result.covered)}  sources: {result.sources}")
    if result.missing:
        typer.secho(f"  no gnomAD frequency: {result.missing}", fg=typer.colors.YELLOW, err=True)


@app.command("gene-metrics")
def gene_metrics_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every gene has constraint metrics."
    ),
    offline: bool = typer.Option(False, "--offline", help="Snapshot only: never touch the network."),
    constraint_cache: Path | None = typer.Option(
        None, "--constraint-cache", help="Explicit gnomAD constraint snapshot dir."
    ),
) -> None:
    """Fill gene_metrics.csv for the genes variants.csv mentions (pass 3, snapshot then live API).

    With no local snapshot the v4.1 one is downloaded from HuggingFace first, exactly as `enrich`
    provisions the Ensembl and ClinVar snapshots — `--offline` is what turns that off, and then the pass
    is snapshot-only. Reaching the live API instead means **v2.1.1** numbers, which the row's `dataset`
    records; provisioning is what keeps a plain install on v4.1.
    """
    try:
        result = enrich_gene_metrics(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            constraint_cache=constraint_cache,
        )
    except GeneMetricsEnrichmentError as exc:
        typer.secho(f"GENE METRICS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # The path the pass actually wrote, not `spec_dir / <name>` (RM99) — a module keeping its
    # sidecars under `derived/` is written there, and a guess sends the author to a file that
    # did not change.
    typer.secho(
        f"gene metrics: {sidecar_path(spec_dir, 'gene_metrics.csv', error=GeneMetricsEnrichmentError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"rows: {len(result.rows)}  genes covered: {len(result.covered)}  sources: {result.sources}")
    if result.missing:
        typer.secho(f"  no gnomAD constraint: {result.missing}", fg=typer.colors.YELLOW, err=True)


@app.command("dosage")
def dosage_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every gene is ClinGen-curated."
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="No-op with a warning: ClinGen's curation list is a live download with no snapshot.",
    ),
    url: str = typer.Option(DEFAULT_CLINGEN_URL, "--url", help="ClinGen gene-curation list URL."),
    use: str = typer.Option(
        "unstated",
        "--use",
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
    # The path the pass actually wrote, not `spec_dir / <name>` (RM99) — a module keeping its
    # sidecars under `derived/` is written there, and a guess sends the author to a file that
    # did not change.
    typer.secho(
        f"dosage sensitivity: {sidecar_path(spec_dir, 'gene_metrics.csv', error=ClinGenError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"dataset: {result.dataset}  genes curated: {len(result.covered)}")
    if result.missing:
        # ClinGen curates a subset by design, so this is information rather than a problem.
        typer.secho(f"  not in the ClinGen curation list: {result.missing}", fg=typer.colors.YELLOW)


@app.command("gene-validity")
def gene_validity_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    source: str = typer.Option(
        CLINGEN_VALIDITY_SOURCE,
        "--source",
        help="Which submitter to read: clingen (expert panels) or gencc (an aggregate of nineteen).",
    ),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every gene carries a curated assertion."
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="No-op with a warning: neither ClinGen nor GenCC publishes an offline snapshot.",
    ),
    url: str | None = typer.Option(None, "--url", help="Override the submitter's export URL."),
) -> None:
    """Fill gene_validity.csv with curated gene-disease assertions for the genes variants.csv names.

    One row per (gene, disease, mode of inheritance, submitter) — the source's own grain. Mode of
    inheritance is in the key because 59 ClinGen (gene, disease) pairs carry two curations that differ
    only there, and `submitter` is in it because GenCC publishes the disagreement between submitters,
    which is the thing it exists to publish.
    """
    try:
        result = enrich_gene_validity(spec_dir, source=source, mode=_mode(strict), offline=offline, url=url)
    except GeneValidityError as exc:
        typer.secho(f"GENE VALIDITY FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho(
            "skipped: --offline (no gene-validity submitter publishes an offline snapshot)",
            fg=typer.colors.YELLOW,
        )
        return
    # The path the pass actually wrote, not `spec_dir / <name>` — a module keeping its sidecars under
    # `derived/` (RM49) is written there, and printing a guess sends the author to a file that is not
    # the one that changed.
    typer.secho(
        f"gene validity: {sidecar_path(spec_dir, 'gene_validity.csv', error=GeneValidityError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"dataset: {result.dataset}  rows: {len(result.rows)}  genes curated: {len(result.covered)}")
    if result.missing:
        # Both submitters curate a subset by design, so this is information rather than a problem.
        typer.secho(f"  no {source} assertion: {result.missing}", fg=typer.colors.YELLOW)
    if result.unmapped:
        typer.secho(
            f"  wordings this release does not model (kept verbatim in classification_raw): "
            f"{result.unmapped}",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command("gwas")
def gwas_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Severity ladder for findings; see the pass docstring."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="No-op with a warning: this pass reads the REST API, not a snapshot."
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help="Declared use recorded on the licence row: unstated|non-commercial|commercial.",
    ),
    study_facts: bool = typer.Option(
        True,
        "--study-facts/--no-study-facts",
        help="Follow each association's study and trait links. Costs 2 requests per association; "
        "measured at 382 requests for one real module. Off keeps effects, drops pmid/trait/ancestry "
        "PERMANENTLY for the rows it writes: the merge is keyed on association_id, so a later run "
        "with study facts on skips those rows rather than back-filling. Delete gwas_effects.csv to "
        "re-derive them.",
    ),
) -> None:
    """Fill gwas_effects.csv with the GWAS Catalog's published effect sizes for this module's rsIDs.

    One row per published association, not per variant — a well-studied variant carries dozens across
    different traits and papers. It does NOT fill `weight`: an authored weight is the author's model
    of the finding, and no tool writes one. The two sit side by side and a consumer picks.

    Reads `effect_unit` verbatim, including the Catalog's uninformative "unit", because a beta whose
    scale is unknown must not look like one whose scale is shared. An association the Catalog
    published without establishing which allele carries the effect keeps a null `effect_allele` and is
    counted in the manifest, never dropped.
    """
    try:
        result = enrich_gwas(
            spec_dir, mode=_mode(strict), offline=offline, declared_use=_use(use), study_facts=study_facts
        )
    except GwasError as exc:
        typer.secho(f"GWAS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho(
            "skipped: --offline (the GWAS Catalog pass has no offline snapshot)", fg=typer.colors.YELLOW
        )
        return
    # Both halves of the request budget, because the pass computed them and an operator spending
    # somebody else's rate limit is the person who needs the number.
    typer.secho(
        f"gwas: {len(result.rows)} row(s) for {len(result.covered)} variant(s), "
        f"{len(result.missing)} with no published association; "
        f"{result.requests_made} request(s), {result.requests_saved} saved by caching, "
        f"{result.p_value_underflows} p-value(s) below float64 range",
        fg=typer.colors.GREEN,
    )
    # The path the pass actually wrote, never `spec_dir / <name>` — a module keeping its sidecars
    # under `derived/` is written there, and a guess sends the author to the wrong file.
    typer.secho(
        f"gwas effects: {sidecar_path(spec_dir, 'gwas_effects.csv', error=GwasError)}",
        fg=typer.colors.GREEN,
    )


@app.command("assertions")
def assertions_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every resolved allele has a ClinVar record."
    ),
    offline: bool = typer.Option(False, "--offline", help="Snapshot only: never touch the network."),
    clinvar_cache: Path | None = typer.Option(
        None, "--clinvar-cache", help="Explicit ClinVar snapshot directory."
    ),
) -> None:
    """Fill clinical_assertions.csv from the coordinates already in resolution.csv.

    Records what ClinVar says about each allele **and how much review sits behind it** — the star
    rating a compiled module previously discarded, so a one-star single submission and a practice
    guideline stopped being the same claim. Offline-capable: with a snapshot provisioned this pass
    never touches the network, and with none reachable it is a no-op rather than a failure.

    It records; it does not adjudicate. Whether the module's own clin_sig agrees with ClinVar's is the
    `enrich` cross-check's question, and that one warns in both modes on purpose.
    """
    try:
        result = enrich_clinical_assertions(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            clinvar_cache=clinvar_cache,
        )
    except ClinicalAssertionError as exc:
        typer.secho(f"ASSERTIONS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_no_snapshot:
        typer.secho(
            "skipped: no ClinVar snapshot reachable (provision one with `clinvar pull`)",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(
        "clinical assertions: "
        f"{sidecar_path(spec_dir, 'clinical_assertions.csv', error=ClinicalAssertionError)}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"dataset: {result.dataset}  rows: {len(result.rows)}  alleles covered: {len(result.covered)}")
    if result.missing:
        typer.secho(f"  no ClinVar record: {result.missing}", fg=typer.colors.YELLOW)
    if result.off_build:
        typer.secho(
            f"  not on {ASSERTION_GENOME_BUILD}, so never queried: {result.off_build}",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command("literature")
def literature_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail if a cited PMID does not resolve."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="No-op with a warning: there is no offline PubMed snapshot."
    ),
    check_fulltext: bool = typer.Option(
        True,
        "--fulltext/--no-fulltext",
        help="Also match provenance quotes against fulltext, falling back to the abstract.",
    ),
    check_doi: bool = typer.Option(
        True,
        "--doi/--no-doi",
        help="Also confirm the authored DOI resolves in Crossref (covers preprints/books).",
    ),
) -> None:
    """Fill literature.csv from a module's citations (pass 4, online only).

    `studies.csv` is one citation site of several: a `pmid` on a binning row grounds the threshold it
    sits on, and one on a `pharm_variants.csv` row grounds that row's own drug and genotype claim. The
    pass reads every site, so a module citing only from those tables is enriched rather than refused.
    """
    try:
        result = enrich_literature(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            check_fulltext=check_fulltext,
            check_doi=check_doi,
        )
    except LiteratureEnrichmentError as exc:
        typer.secho(f"LITERATURE FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho("skipped: --offline (PubMed/Europe PMC have no offline snapshot)", fg=typer.colors.YELLOW)
        return
    # The path the pass actually wrote, not `spec_dir / <name>` (RM99) — a module keeping its
    # sidecars under `derived/` is written there, and a guess sends the author to a file that
    # did not change.
    typer.secho(
        f"literature: {sidecar_path(spec_dir, 'literature.csv', error=LiteratureEnrichmentError)}",
        fg=typer.colors.GREEN,
    )
    # The citations the module makes, not the rows the sidecar holds: merge-not-clobber keeps a row
    # for a citation the author has since deleted, and counting it here would put a number in front
    # of the author that nothing else in the run agrees with.
    typer.echo(f"citations: {len(result.cited)}  {result.coverage}")
    typer.echo(
        f"quotes: {result.quotes_found}/{result.quotes_authored} found, {result.quotes_unchecked} not checked"
    )
    if result.quotes_unexamined:
        # Split out rather than left inside "not checked": an article whose text could not be read
        # and a quote nobody went looking for have different remedies, and only this one is the
        # author's to clear. Calling it "not checkable" was false for an open-access article whose
        # fulltext the previous run read.
        typer.secho(
            f"  {result.quotes_unexamined} authored quote(s) were never looked up: literature.csv "
            f"already pins their citation and a merge never refetches one — delete it to re-derive",
            fg=typer.colors.YELLOW,
        )
    if result.missing:
        # Red: a citation that does not resolve is a defect in the module, not a coverage gap.
        typer.secho(f"  PubMed has no record of: {result.missing}", fg=typer.colors.RED, err=True)
    if result.doi_missing:
        typer.secho(f"  Crossref has no record of: {result.doi_missing}", fg=typer.colors.RED, err=True)
    for conflict in result.doi_conflicts:
        typer.secho(f"  doi conflict: {conflict}", fg=typer.colors.RED, err=True)
    # Printed for the same reason and in the same place: a cross-check that only ever speaks under
    # `--strict` is invisible in the mode almost every author runs, and the two identifiers naming
    # different articles is exactly the case the schema's PMC guard cannot see (RM50).
    for conflict in result.pmcid_conflicts:
        typer.secho(f"  pmcid conflict: {conflict}", fg=typer.colors.RED, err=True)
    # Off the tally, which knows which citations the module quotes *now*: the sidecar keeps a row for
    # a citation the author has since dropped, and its pinned `quotes_authored` would have gone on
    # naming publisher text this module no longer carries.
    noncommercial = result.noncommercial_quoted
    if noncommercial:
        # Yellow, not red, and never a non-zero exit: quoting for comment or research is often fine,
        # and the format is not the tier that adjudicates copyright (the `clin_sig` precedent).
        typer.secho(
            f"  quoted under a non-commercial licence: {noncommercial} — the passage is publisher "
            f"text in this module's annotation layer",
            fg=typer.colors.YELLOW,
        )
    # Yellow and never an exit code, for the same reason: what the author wrote is a quote, and
    # whether a title is an acceptable locator for their claim is theirs to decide. What the tool can
    # say is that `quotes_found` establishes nothing here — a title always appears in its own
    # fulltext, so this is the one shape the quote check cannot fail on (S54).
    if result.titles_as_quotes:
        typer.secho(
            f"  provenance_quote is the article's own title: {result.titles_as_quotes} — a title "
            f"appears in its own fulltext, so quotes_found cannot fail on it and establishes nothing "
            f"about whether the claim is in the paper. Replace it with the passage the claim rests on",
            fg=typer.colors.YELLOW,
        )


@app.command("pgx")
def pgx_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail on an allele-function discrepancy."
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Snapshots only: never reach PharmVar or CPIC live.",
    ),
    use: str = typer.Option(
        "unstated",
        "--use",
        help=(
            "Declared use: unstated | non-commercial | commercial. Sources that forbid sale are "
            "SKIPPED when unstated and REFUSED when commercial."
        ),
    ),
    use_pharmvar: bool = typer.Option(
        True, "--pharmvar/--no-pharmvar", help="Consult PharmVar (needs PHARMVAR_API_KEY)."
    ),
    use_cpic: bool = typer.Option(True, "--cpic/--no-cpic", help="Consult CPIC (open, no key)."),
    cpic_cache: Path | None = typer.Option(None, "--cpic-cache", help="Explicit CPIC snapshot dir."),
    pharmvar_cache: Path | None = typer.Option(
        None, "--pharmvar-cache", help="Explicit PharmVar snapshot dir."
    ),
) -> None:
    """Cross-check star-allele tables against PharmVar/CPIC and record terms into sources.csv.

    Snapshot first, live second (RM38). A built snapshot serves the check without egress and without
    spending a shared per-IP budget; `--offline` says snapshot-only, and a leg with neither is skipped
    with a reason rather than silently passing.
    """
    try:
        result = enrich_pgx(
            spec_dir,
            mode=_mode(strict),
            offline=offline,
            declared_use=_use(use),
            use_pharmvar=use_pharmvar,
            use_cpic=use_cpic,
            cpic_cache=cpic_cache,
            pharmvar_cache=pharmvar_cache,
        )
    except LicenseRefusal as exc:
        typer.secho(f"REFUSED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except PgxEnrichmentError as exc:
        typer.secho(f"PGX FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.rows:
        # The file the pass actually wrote, not a guessed name — the module may carry either spelling.
        typer.secho(f"sources: {sources_path(spec_dir, error=PgxEnrichmentError)}", fg=typer.colors.GREEN)
    typer.echo(f"sources recorded: {len(result.rows)}  declared use: {result.declared_use}")
    if result.recorded_use:
        typer.echo(
            "  declared in the licence table by an earlier run: "
            + ", ".join(f"{s}={u}" for s, u in sorted(result.recorded_use.items()))
        )
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

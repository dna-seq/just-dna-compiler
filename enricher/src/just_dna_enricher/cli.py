"""Command-line front door for the enricher (Typer) — the network tier's user-facing command.

    just-dna-enricher enrich spec/ --strict --offline
    just-dna-enricher frequencies spec/                 # pass 2: allele frequency (online only)
    just-dna-enricher gene-metrics spec/                # pass 3: gene constraint (offline capable)
    just-dna-enricher literature spec/                  # pass 4: citations (online only)
    just-dna-enricher gene-validity spec/ --source gencc  # curated gene-disease assertions (online)
    just-dna-enricher assertions spec/                  # ClinVar call + review tier (offline capable)
    just-dna-enricher enrich-and-compile spec/ out/ --frequencies --gene-metrics
    just-dna-enricher gnomad constraint build --download --out gnomad_constraint/   # [dev]
    just-dna-enricher upload out/coronary --repo just-dna-seq/annotators            # [dev]
"""

import json
from pathlib import Path

import typer
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.draft import DraftError, authoring_requirements, blank_template
from just_dna_format.manifest import VerificationRecord
from just_dna_format.vocab import VALID_DECLARED_USE, match_vocab

from just_dna_enricher.acmg import (
    DEFAULT_ACMG_URL,
    AcmgListUnavailable,
    AcmgReport,
    AcmgSfError,
    verify_acmg_sf,
)
from just_dna_enricher.acmg import verification_record as acmg_record
from just_dna_enricher.assertions import (
    ASSERTION_GENOME_BUILD,
    ClinicalAssertionError,
    enrich_clinical_assertions,
)
from just_dna_enricher.civic_draft import draft_panel_from_civic
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
from just_dna_enricher.currency import unchecked_sentences
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
from just_dna_enricher.gene_validity import (
    CLINGEN_SOURCE as CLINGEN_VALIDITY_SOURCE,
)
from just_dna_enricher.gene_validity import (
    GeneValidityError,
    enrich_gene_validity,
)
from just_dna_enricher.grch37 import GRCH37_BUILD, summarize_build_diagnoses
from just_dna_enricher.gwas import GwasError, enrich_gwas
from just_dna_enricher.identifiers import IdentifierUnavailable, check_identifiers
from just_dna_enricher.identifiers import unreachable_records as identifier_unreachable
from just_dna_enricher.identifiers import verification_records as identifier_records
from just_dna_enricher.licensing import (
    CLINPGX_TERMS,
    CPIC_TERMS,
    PHARMVAR_TERMS,
    LicenseRefusal,
    check_declared_use,
    sidecar_path,
    sources_path,
)
from just_dna_enricher.literature import LiteratureEnrichmentError, enrich_literature
from just_dna_enricher.locations import (
    CITATIONS_DIRNAME,
    RELEASE_FILENAME,
    resolve_civic_reference,
    resolve_clinpgx_reference,
    resolve_clinvar_reference,
    resolve_constraint_reference,
    resolve_cpic_reference,
    resolve_ensembl_reference,
    resolve_mane_reference,
    resolve_pharmvar_reference,
    resolve_pubmind_reference,
)
from just_dna_enricher.lookup import (
    as_report_rows,
    lookup_citation,
    lookup_gene,
    lookup_old_assembly,
    lookup_trait,
    lookup_variant,
)
from just_dna_enricher.pgx import PgxEnrichmentError, enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene
from just_dna_enricher.pharmvar import PharmVarError
from just_dna_enricher.pharmvar_build import build_snapshot as build_pharmvar_snapshot
from just_dna_enricher.pubmind_build import (
    PubMindBuildError,
    download_pubmind_table,
)
from just_dna_enricher.pubmind_build import build_snapshot as build_pubmind_snapshot
from just_dna_enricher.pubmind_draft import (
    DEFAULT_MIN_CONFIDENCE,
    PubMindDraftError,
    draft_gene_panel_from_pubmind,
)
from just_dna_enricher.sequences import summarize_ref_mismatches
from just_dna_enricher.upload import DEFAULT_CLINPGX_REPO_ID, DEFAULT_CPIC_REPO_ID
from just_dna_enricher.verification import record_verification, skipped
from just_dna_enricher.vrs import MintResult

app = typer.Typer(
    add_completion=False,
    help="Fill the source-independent resolution table (cache + live Ensembl) the compiler consumes.",
    no_args_is_help=True,
)


#: What a drafting command must catch beyond its own source's error, and **why it is a named tuple
#: rather than two more entries in two `except` clauses** (R2-2).
#:
#: Every provider that writes a coordinate asks `enrich.source_build_mismatch` before it writes (F1),
#: and that function raises `EnrichmentError` on a present-but-unreadable `module_spec.yaml` —
#: deliberately, because picking a build for a module whose declaration cannot be read is the
#: invention it exists to remove. Neither CLI caught it: `draft` caught `(CpicError, DraftError)` and
#: `draft-panel` caught `(ClinVarDraftError, DraftError)`, so a spec carrying only `name:` — an
#: ordinary mid-authoring state — turned `draft-panel --gene PALB2 --offline` into a rich traceback
#: where every other enricher command exits cleanly. The presentation regressed *because* the build
#: defect was fixed, which is the shape worth naming: a shared precondition added to three providers
#: owes the same addition to each of their handlers, and a tuple makes the fourth provider inherit it
#: instead of rediscovering it.
_DRAFT_PRECONDITION_ERRORS: tuple[type[Exception], ...] = (DraftError, EnrichmentError)


def _mode(strict: bool) -> str:
    return "strict" if strict else "best_effort"


def _use(value: str) -> str:
    """Normalize the `--use` spelling to the `VALID_DECLARED_USE` member.

    A three-state string rather than a `--commercial/--non-commercial` bool pair: a bool cannot
    express the default, and defaulting either way would have the tool assert a purpose on the
    user's behalf. `unstated` is the honest default.

    The separator normalization moved onto `vocab.match_vocab`, which every closed vocabulary now
    shares. This private copy was the whole reason `--use non-commercial` worked while the identical
    string in an authored cell was refused: the flag taught a spelling the file rejected. What stays
    here is the case-folding and the `--use`-specific message — the flag is the CLI's, the vocabulary
    is the schema's.
    """
    matched = match_vocab(value.strip().lower(), VALID_DECLARED_USE)
    if matched is None:
        raise typer.BadParameter(
            f"--use must be one of {sorted(VALID_DECLARED_USE)}, got: {value!r}"
        )
    return matched


@app.command("enrich")
def enrich_(  # `enrich` command; function name avoids shadowing the imported enrich()
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strict: bool = typer.Option(False, "--strict/--best-effort", help="Fail unless every variant resolves."),
    offline: bool = typer.Option(False, "--offline", help="Cache-only: never touch the network."),
    ensembl_cache: Path | None = typer.Option(None, "--ensembl-cache", help="Explicit Ensembl cache dir/.duckdb."),
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
    verify_datasets: bool = typer.Option(
        True, "--verify-datasets/--no-verify-datasets",
        help="Check each release recorded in sources.csv against the one that source publishes now, "
             "and report the gap. One request per source, and the cheap question to put before "
             "--rederive: it tells you whether re-asking every subject is worth the run.",
    ),
    keep_par_twin: bool = typer.Option(
        False, "--keep-par-twin",
        help="Record both contigs of a pseudoautosomal locus. Default keeps only the X spelling, "
             "which is the one every annotation source uses and the only one a hard-masked GRCh38 "
             "analysis set can match.",
    ),
    rederive: bool = typer.Option(
        False, "--rederive",
        help="Re-ask every source about every subject, including the ones already recorded, and "
             "report which of them changed value. An ordinary run gap-fills and never re-asks, so a "
             "source that quietly revised an answer moves nothing you could notice.",
    ),
    keep_staging: bool = typer.Option(
        False, "--keep-staging",
        help="Leave the staged answers beside resolution.csv after a successful run. They are "
             "removed by default; a killed run leaves them either way, and the next run resumes "
             "from them.",
    ),
) -> None:
    """Resolve a spec's variants into resolution.csv beside the spec. Exit 1 in strict mode if unresolved."""
    try:
        result = enrich(
            spec_dir, mode=_mode(strict), offline=offline,
            ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache,
            pubmind_cache=pubmind_cache, use_clinvar=use_clinvar,
            use_gnomad=use_gnomad, mint_vrs=mint_vrs, verify_ref=verify_ref,
            verify_clinsig=verify_clinsig, verify_rsids=verify_rsids,
            verify_datasets=verify_datasets, keep_par_twin=keep_par_twin,
            rederive=rederive, keep_staging=keep_staging,
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
        CLINGEN_VALIDITY_SOURCE, "--source",
        help="Which submitter to read: clingen (expert panels) or gencc (an aggregate of nineteen).",
    ),
    strict: bool = typer.Option(
        False, "--strict/--best-effort", help="Fail unless every gene carries a curated assertion."
    ),
    offline: bool = typer.Option(
        False, "--offline",
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
        result = enrich_gene_validity(spec_dir, source=source, mode=_mode(strict), offline=offline,
                                      url=url)
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
    typer.echo(
        f"dataset: {result.dataset}  rows: {len(result.rows)}  genes curated: {len(result.covered)}"
    )
    if result.missing:
        # Both submitters curate a subset by design, so this is information rather than a problem.
        typer.secho(f"  no {source} assertion: {result.missing}", fg=typer.colors.YELLOW)
    if result.unmapped:
        typer.secho(
            f"  wordings this release does not model (kept verbatim in classification_raw): "
            f"{result.unmapped}",
            fg=typer.colors.YELLOW, err=True,
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
        "unstated", "--use",
        help="Declared use recorded on the licence row: unstated|non-commercial|commercial.",
    ),
    study_facts: bool = typer.Option(
        True, "--study-facts/--no-study-facts",
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
        result = enrich_gwas(spec_dir, mode=_mode(strict), offline=offline, declared_use=_use(use),
                             study_facts=study_facts)
    except GwasError as exc:
        typer.secho(f"GWAS FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if result.skipped_offline:
        typer.secho("skipped: --offline (the GWAS Catalog pass has no offline snapshot)",
                    fg=typer.colors.YELLOW)
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
            spec_dir, mode=_mode(strict), offline=offline, clinvar_cache=clinvar_cache,
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
    typer.echo(
        f"dataset: {result.dataset}  rows: {len(result.rows)}  alleles covered: {len(result.covered)}"
    )
    if result.missing:
        typer.secho(f"  no ClinVar record: {result.missing}", fg=typer.colors.YELLOW)
    if result.off_build:
        typer.secho(
            f"  not on {ASSERTION_GENOME_BUILD}, so never queried: {result.off_build}",
            fg=typer.colors.YELLOW, err=True,
        )


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
    """Fill literature.csv from a module's citations (pass 4, online only).

    `studies.csv` is one citation site of several: a `pmid` on a binning row grounds the threshold it
    sits on, and one on a `pharm_variants.csv` row grounds that row's own drug and genotype claim. The
    pass reads every site, so a module citing only from those tables is enriched rather than refused.
    """
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
    typer.echo(f"quotes: {result.quotes_found}/{result.quotes_authored} found, "
               f"{result.quotes_unchecked} not checked")
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
        # The file the pass actually wrote, not a guessed name — the module may carry either spelling.
        typer.secho(
            f"sources: {sources_path(spec_dir, error=PgxEnrichmentError)}", fg=typer.colors.GREEN
        )
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
        except (CpicError, *_DRAFT_PRECONDITION_ERRORS) as exc:
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

    **Writes no authored cell, and records that the question was put.** Unlike the rsID check (whose
    verdict lands on resolution.csv), these are module-level identifiers with no sidecar column to
    record, and filling one from the registry being asked about it would make the comparison vacuous
    — see `hints.REDUNDANCY_BEARING`. What this does write is `verification.json`: an attestation that
    the three checks ran and over how many rows, never a value. A consumer holding the artifact has no
    other way to tell "asked and clean" from "never asked" (RM45/RM72).
    """
    try:
        # `spec_dir=` rather than loading the rows here (RM41). This command was the workspace's own
        # evidence that the row-taking form leaves every caller reaching for a private loader.
        report = check_identifiers(spec_dir=spec_dir, check_traits=traits, check_genes=genes)
    except ValueError as exc:
        # A module whose rows will not load: nothing is attested, because there are no bytes for an
        # attestation to bind to and no question was reached.
        typer.secho(f"{exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except IdentifierUnavailable as exc:
        # The registry never answered, which is `unreachable` rather than an absence (S20) — and it is
        # the run on which a reader most needs the record, since the report is empty. `check-acmg`
        # records the same thing through `AcmgListUnavailable`; without this the promise two lines up
        # would be false exactly when it matters.
        #
        # This read `except httpx.HTTPError` until RM101, and it only ever fired because
        # `OntologyClient` leaked its transport library's exception — the very defect RM97 set out to
        # end. So the leak was not merely unnoticed here, it was **load-bearing**: repairing the
        # client without this line would have turned the attestation off silently, on exactly the run
        # the comment above says needs it most. The comment already named the right shape one clause
        # over; the type now matches it.
        _attest_on_the_way_out(
            identifier_unreachable(check_traits=traits, check_genes=genes, detail=str(exc)),
            spec_dir,
        )
        typer.secho(f"IDENTIFIER CHECK FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    # **The guard is the roster, not a filename.** This command opened with `if not (spec_dir /
    # "variants.csv").exists(): return "nothing to check"`, on the reasoning that such a module "has no
    # gene, trait_efo_id or row for these checks to have an opinion about". Nine tables carry each
    # column and four of them are the PGx kinds a module with no `variants.csv` is built out of, so
    # that sentence was false and the command exited 0 having asked nothing — S86's unreadable zero
    # surviving one level above the function that repaired it, on this repo's own
    # `cyp2c19_star_alleles`, which names CYP2C19 on every row it has.
    #
    # No attestation here, which is the one half of the old guard that was right: with no id-bearing
    # table present there is no question to record having put, and minting a nonce would create a
    # `verification.json` on a module that never asked for one. Both checks switched off is a
    # different state and keeps its existing path below, where it is recorded as `not_requested`.
    if (traits or genes) and not (report.trait_tables_read or report.gene_tables_read):
        typer.secho(
            "no table carrying trait ids or gene symbols — nothing to check", fg=typer.colors.YELLOW
        )
        return
    # **The count names the tables it is out of (S86).** `traits checked: 0` used to say two things —
    # the module declares no trait, and its traits are in a table the roster never read — and a reader
    # took the second for the first, which is how a retired CURIE ships with every gate green.
    typer.echo(
        f"traits checked: {len(report.traits)}"
        f" (from {len(report.trait_tables_read)} table(s): {', '.join(report.trait_tables_read) or 'none'})"
        f"  genes checked: {len(report.genes)}"
        f" (from {len(report.gene_tables_read)} table(s): {', '.join(report.gene_tables_read) or 'none'})"
    )
    for name, why in sorted(report.unreadable_tables.items()):
        # Only the tables that exist and would not parse. An absent optional table is every module's
        # normal shape and would bury this line in noise.
        typer.secho(
            f"  {name} carries identifiers and could not be read ({why}) — its ids were NOT checked",
            fg=typer.colors.YELLOW,
            err=True,
        )
    for finding in [*report.stale_traits, *report.stale_genes, *report.gene_loci]:
        typer.secho(f"  {finding}", fg=typer.colors.YELLOW, err=True)
    if report.gene_loci_not_checked:
        # Never silently: an empty conflict list means "nothing disagreed" and "never compared", and
        # a reader who cannot tell them apart is being told a check passed that was never put (S24).
        typer.secho(
            f"  gene/chromosome agreement not checked: {report.gene_loci_not_checked}",
            fg=typer.colors.YELLOW,
        )
    # One call for all three records: the proof-of-work binds the whole document, so a per-check write
    # would pay it three times for one guarantee. Before the strict exit below, because the check DID
    # run — the exit code is presentation, and an attestation withheld on it would make the record
    # depend on which flag the author passed.
    try:
        record_verification(
            identifier_records(report, check_traits=traits, check_genes=genes),
            spec_dir,
            error=EnrichmentError,
        )
    except EnrichmentError as exc:
        # The check did not fail — the report is above and it is complete. What failed is the
        # attestation, so the message says which, in the `vrs mint` shape.
        typer.secho(f"CHECKED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if report.clean:
        # **"Current" out of nothing is the same unreadable zero one level up (S86).** With both
        # checks off, or with every id-bearing table absent, `report.clean` is vacuously true and the
        # green line asserted a pass over a question nobody put. It says what it read instead.
        looked_at = len(report.trait_tables_read) + len(report.gene_tables_read)
        if not report.traits and not report.genes:
            typer.secho(
                "no identifiers were checked"
                + (
                    f" — {looked_at} table(s) read and none carries a trait id or gene symbol"
                    if looked_at
                    else " — no table carrying identifiers was read"
                ),
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho("all identifiers current", fg=typer.colors.GREEN)
    elif strict:
        raise typer.Exit(code=1)


def _attest_on_the_way_out(records: list[VerificationRecord], spec_dir: Path) -> None:
    """Attest on the way out of a failed run, and report rather than raise if that fails too.

    Used by the two check commands' failure paths only. The command is already exiting 1 with the
    reason the source could not be read, and replacing that sentence with a layout or filesystem
    complaint would tell the author about the wrong problem. `vrs mint`'s "BUT NOT ATTESTED" message
    exists because *there* the run succeeded and only the record failed; here both went wrong and the
    first one is the one to say. `OSError` is caught beside the caller's own error because
    `record_verification` translates only a sidecar collision — a read-only spec directory reaches
    here as an `OSError` and would otherwise replace the message this exists to protect.
    """
    try:
        record_verification(records, spec_dir, error=EnrichmentError)
    except (EnrichmentError, OSError) as exc:
        typer.secho(f"  (not attested either: {exc})", fg=typer.colors.YELLOW, err=True)


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
        typer.secho(f"  unverifiable: {gene} ({len(rows)} row(s), first at {rows[0]}): {message}",
                    fg=typer.colors.YELLOW, err=True)
    # Grouped by gene: every verdict is a statement about a gene, so a per-row list prints one
    # sentence once per variant in it.
    for gene, rows, message in AcmgReport.by_gene(report.notes):
        typer.secho(f"  note: {gene} ({len(rows)} row(s)): {message}", fg=typer.colors.CYAN)
    for gene, rows, message in AcmgReport.by_gene(report.mismatches):
        typer.secho(f"  {gene} ({len(rows)} row(s), first at {rows[0]}): {message}",
                    fg=typer.colors.YELLOW, err=True)
    # After the report, for `check-identifiers`' reason: the check ran and its answer is above, so an
    # attestation that cannot be written must not take the answer down with it. `vrs mint`'s shape —
    # the message says which of the two failed, because saying "the check failed" would be false.
    try:
        record_verification([acmg_record(report)], spec_dir, error=EnrichmentError)
    except EnrichmentError as exc:
        typer.secho(f"CHECKED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
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
        help="Compiled module directory (at least one annotation parquet + manifest.json).",
    ),
    repo_id: str | None = typer.Option(
        None,
        "--repo",
        help="Target HF dataset (owner/name). Default: just-dna-seq/annotators.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help=(
            "Module name under data/<name>/ (and data/<name>/v<version>/) in the repo. "
            "Default: the directory basename."
        ),
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
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Overwrite data/<name>/v<version>/ even when it already holds a different artifact. "
            "Without this the publish refuses; the flat path is always overwritten."
        ),
    ),
) -> None:
    """Upload a compiled module to a HuggingFace dataset collection (publisher/dev surface).

    Writes data/<name>/, which keeps meaning "latest", and — when the
    manifest states a version — data/<name>/v<version>/ under it, in
    that order, as two commits. With no version, the flat path alone,
    and the reason why.

    Refuses when the versioned path already holds a different artifact
    (compare by artifact.digest), unless --force. The flat path means
    latest and is overwritten either way.
    """
    from just_dna_enricher.upload import PublishCollisionError, plan_upload, upload_module

    module_name = name or module_dir.name
    if dry_run:
        plan = plan_upload(module_dir, module_name, repo_id)
        typer.echo(f"Would upload to {plan.repo_id} at {plan.path_in_repo}/:")
        for f in plan.files:
            typer.echo(f"  • {f}")
        if plan.versioned_path_in_repo is not None:
            typer.echo(f"…and the same files to {plan.versioned_path_in_repo}/")
        else:
            typer.secho(
                f"no versioned copy: {plan.version_unknown_reason}",
                fg=typer.colors.YELLOW,
                err=True,
            )
        return

    try:
        plan = upload_module(
            module_dir,
            module_name,
            repo_id=repo_id,
            commit_message=commit_message,
            force=force,
        )
    except PublishCollisionError as exc:
        # Its own branch, and its own word: this module is publishable and the remote already has
        # this version. "UPLOAD FAILED" beside the three `plan_upload` refusals would read as
        # "your module is broken", which is the opposite of what happened.
        typer.secho(f"ALREADY PUBLISHED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, PermissionError, ImportError) as exc:
        typer.secho(f"UPLOAD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"uploaded: {module_name} → {plan.repo_id}/{plan.path_in_repo} ({len(plan.files)} files)",
        fg=typer.colors.GREEN,
    )
    if plan.versioned_path_in_repo is not None:
        typer.secho(
            f"uploaded: {module_name} → {plan.repo_id}/{plan.versioned_path_in_repo} "
            f"({len(plan.files)} files)",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"no versioned copy: {plan.version_unknown_reason}",
            fg=typer.colors.YELLOW,
            err=True,
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
    ("pubmind", resolve_pubmind_reference, None, "literature-derived verdicts — build your own, never published"),
    # No `ensure_*` for the opposite reason to the two above it: nothing forbids publishing a CIViC
    # snapshot — CC0 grants it outright — and none exists only because nobody has run `civic publish`.
    # The absent third column here records a gap, where PharmVar's and PubMind's record a refusal.
    ("civic", resolve_civic_reference, None, "curated cancer interpretations, direction axis (draft-panel --source civic)"),
    # A fourth reason for an absent `ensure_*`, distinct from the three above: NCBI states a policy
    # rather than a licence, so whether a snapshot of these bytes may be published is unestablished
    # — not granted like CIViC's, and not refused like PharmVar's and PubMind's.
    ("mane", resolve_mane_reference, None, "MANE transcripts, the numbering frame (mane build)"),
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


# ── the PubMind snapshot (build only; publish exists in order to refuse) — RM134 § A ────────────

civic_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the CIViC snapshot from a dated bulk release. CC0, so unlike the PubMind snapshot "
        "this one may be published."
    ),
    no_args_is_help=True,
)
app.add_typer(civic_app, name="civic")


@civic_app.command("build")
def civic_build_(
    release: str | None = typer.Option(
        None, "--release",
        help=(
            "Dated CIViC release to download, e.g. 01-Aug-2026. A DATED release, never the nightly: "
            "a snapshot that cannot name its input is one nothing can reproduce."
        ),
    ),
    evidence: Path | None = typer.Option(
        None, "--evidence", exists=True, dir_okay=False,
        help="Local ClinicalEvidenceSummaries.tsv. Use instead of --release to build offline.",
    ),
    variants: Path | None = typer.Option(
        None, "--variants", exists=True, dir_okay=False,
        help="Local VariantSummaries.tsv.",
    ),
    profiles: Path | None = typer.Option(
        None, "--profiles", exists=True, dir_okay=False,
        help="Local MolecularProfileSummaries.tsv.",
    ),
    out: Path = typer.Option(
        Path("civic"), "--out", file_okay=False,
        help="Output snapshot directory (writes data/civic.parquet + release.json).",
    ),
    submitted: bool = typer.Option(
        False, "--submitted",
        help=(
            "Also read the release's civic_accepted_and_submitted.vcf, so evidence a curator entered "
            "but no editor signed off joins the snapshot. Over 01-Aug-2026 that widens the direction "
            "corpus from 507 rows on 270 variants to 1149 on 397, adding 642 submitted rows and 127 "
            "variants, and every row carries the status CIViC gave it. Dated and pinnable like the "
            "TSVs, so the build stays reproducible."
        ),
    ),
    vcf: Path | None = typer.Option(
        None, "--vcf", exists=True, dir_okay=False,
        help="Local civic_accepted_and_submitted.vcf. Use with the local TSV flags to build offline.",
    ),
) -> None:
    """Reduce a dated CIViC release to the parquet snapshot the direction-axis drafter reads.

    **The bulk release, not the GraphQL API, and the two are not interchangeable.** Every row of
    `ClinicalEvidenceSummaries.tsv` is status `accepted`; the API defaults to `NON_REJECTED` and
    serves roughly 2.35x as many evidence items. A snapshot has to be reproducible from a pinned
    input, so this reads the dated files and records the basis in `release.json`.

    **`--submitted` widens that basis without leaving the dated release (RM169).** CIViC publishes
    `<date>-civic_accepted_and_submitted.vcf` beside the TSVs, so unreviewed evidence is pinnable too
    and no API read is needed. The TSVs stay primary — the VCF cannot carry a variant with no GRCh37
    coordinate, which is exactly the class whose identity had to be read out of its name — and the VCF
    supplies the curation status, the submitted evidence, and the identity for the 112 variants
    `VariantSummaries.tsv` (itself accepted-only) does not describe. Those rows are stamped
    `identity_derivation="vcf_csq"`, and nothing is placed from the VCF's own GRCh37 position.

    **There is no `--use` flag.** CIViC is CC0 on every axis, so a declared-use gate would permit
    every build unconditionally, and a flag feeding a gate that never gates is a flag that does
    nothing (`@acquisition-gate-is-not-a-read-gate`).
    """
    from just_dna_enricher.civic_build import (
        CIVIC_EVIDENCE_FILE,
        CIVIC_PROFILE_FILE,
        CIVIC_VARIANT_FILE,
        build_snapshot,
        civic_release_url,
        download_civic_file,
    )
    from just_dna_enricher.civic_vcf import CIVIC_VCF_FILE

    if vcf is not None and submitted:
        raise typer.BadParameter(
            "pass --vcf to read a local VCF or --submitted to download the release's one, not both. "
            "Two sources for one input is a build whose provenance nothing can state."
        )
    local = (evidence, variants, profiles)
    if release is None and not all(local):
        raise typer.BadParameter(
            "pass --release to download a dated release, or all three of --evidence, --variants "
            "and --profiles to build from local files. Two of the three is not a build: the "
            "evidence file carries the claims, the variant file the identities, and the profile "
            "file is what tells a combination genotype from a dangling reference."
        )
    shas: dict[str, str | None] = {}
    vcf_path = vcf
    if all(local):
        evidence_path, variant_path, profile_path = local
    else:
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for filename in (CIVIC_EVIDENCE_FILE, CIVIC_VARIANT_FILE, CIVIC_PROFILE_FILE):
            got = download_civic_file(out / filename, civic_release_url(release, filename))
            shas[filename] = got.sha256
            paths.append(got.path)
        evidence_path, variant_path, profile_path = paths
        if submitted:
            got = download_civic_file(out / CIVIC_VCF_FILE, civic_release_url(release, CIVIC_VCF_FILE))
            shas[CIVIC_VCF_FILE] = got.sha256
            vcf_path = got.path

    result = build_snapshot(
        evidence_path, variant_path, profile_path, out,
        release=release,
        evidence_sha256=shas.get(CIVIC_EVIDENCE_FILE),
        variant_sha256=shas.get(CIVIC_VARIANT_FILE),
        profile_sha256=shas.get(CIVIC_PROFILE_FILE),
        vcf=vcf_path,
        vcf_sha256=shas.get(CIVIC_VCF_FILE),
    )
    typer.echo(f"Wrote {result.parquet_file} ({result.record_count} rows, {result.variants} variants)")
    typer.echo(f"  status basis: {result.status_basis}")
    if result.status_counts:
        typer.echo("  " + " · ".join(f"{k} {v}" for k, v in sorted(result.status_counts.items())))
    typer.echo(f"  dataset: {result.dataset or 'unknown (no --release named)'}")
    typer.echo(f"  read {result.input_rows} evidence rows; dropped:")
    for reason, count in result.dropped.items():
        typer.echo(f"    {reason:24s} {count}")
    typer.echo(f"  identity: {result.identity_derivations}")
    if result.withheld_direction:
        typer.echo(
            f"  {result.withheld_direction} row(s) kept with no direction: the source refuted a "
            f"claim rather than making one, and a refutation is not the opposite claim."
        )
    if result.dropped["unresolvable_identity"]:
        typer.echo(
            f"  {result.dropped['unresolvable_identity']} row(s) dropped for carrying neither an "
            f"rsID nor a GRCh38 accession; {result.unresolvable_with_caid} of those variants do "
            f"carry a ClinGen CAID, so they stay addressable by a later identity pass."
        )


@civic_app.command("publish")
def civic_publish_(
    snapshot_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Built snapshot directory (data/civic.parquet + release.json).",
    ),
    repo_id: str | None = typer.Option(
        None, "--repo", help="Target HF dataset (owner/name). Default: just-dna-seq/civic.",
    ),
    commit_message: str | None = typer.Option(None, "--message", "-m", help="Commit message."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be uploaded without contacting HuggingFace.",
    ),
) -> None:
    """Upload a built CIViC snapshot to a HuggingFace dataset repo (publisher/dev).

    **This one does not refuse, and the contrast with `pubmind publish` is the point.** CIViC's content
    is CC0 1.0 — a public-domain dedication with no share-alike, no bar on sale and attribution
    requested rather than required — so there is no permission to establish before passing the bytes
    on. PubMind's command exists in order to say no because its terms are unstated; PharmVar's cache is
    unpublishable because its terms forbid it. Nothing here is in either position.

    What the snapshot carries is a *derivation* of CIViC's release, not a copy of it: the germline
    direction rows, placed on GRCh38 through identifiers CIViC itself publishes. `release.json` records
    which dated release it came from and the `accepted` status basis, so a consumer can tell what they
    are looking at without re-deriving it.

    **The ClinGen Allele Registry's answers are NOT in here**, and that is deliberate rather than an
    oversight: the registry states no terms, and a lookup performed at draft time is a read, while
    baking its responses into a published file would be redistribution of bytes nobody has established
    we may pass on. The snapshot carries the CAID; resolving it stays the consumer's own fetch.
    """
    from just_dna_enricher.upload import (
        DEFAULT_CIVIC_REPO_ID,
        plan_reference_snapshot,
        publish_reference_snapshot,
    )

    repo_id = repo_id or DEFAULT_CIVIC_REPO_ID
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
    typer.secho(f"Published {len(plan.files)} file(s) to {plan.repo_id}", fg=typer.colors.GREEN)



@civic_app.command("reproduce")
def civic_reproduce_(
    release: str = typer.Option(
        "01-Aug-2026", "--release",
        help="Dated CIViC release to reproduce, e.g. 01-Aug-2026.",
    ),
    out: Path = typer.Option(
        Path("civic-reproduce"), "--out", file_okay=False,
        help="Working directory. The release files and two independent builds land here.",
    ),
    keep: bool = typer.Option(
        False, "--keep", help="Leave the downloaded release files in place for inspection.",
    ),
    offline: bool = typer.Option(
        False, "--offline",
        help="Skip the reference cross-check. The build and determinism checks still run.",
    ),
    submitted: bool = typer.Option(
        False, "--submitted",
        help=(
            "Reproduce the wider basis: also download the release's "
            "civic_accepted_and_submitted.vcf and build with it, so the submitted rows and their "
            "coordinates go through every check below rather than only the accepted ones."
        ),
    ),
) -> None:
    """Build the CIViC snapshot from a dated release and check it, end to end.

    **Five checks, and the third is the one worth the network.** The first two are about us; the third
    is about whether the coordinates we produced are real.

    1. **The release downloads and its bytes are recorded** — a sha256 per file, so a rerun that
       disagrees is a finding about the source rather than a mystery.
    2. **Two independent builds are byte-identical** (Principle 7). A parquet has no inherent row
       order, so this is the check that the sort is doing its job.
    3. **Every placed coordinate is cross-checked against the GRCh38 reference sequence.** This is the
       external validation: the snapshot's positions come from RefSeq accessions inside ClinVar HGVS,
       and this asks an unrelated service (refget/seqrepo) whether the reference base at each of those
       positions is what we wrote. A wrong-build or off-by-one placement fails here and nowhere else.
    4. **The drop registry closes** — every input row kept or counted, an equality over a walked set.
    5. **The published file list is exactly what the publisher would upload.**

    Exits non-zero if any check fails, so it is usable in CI.
    """
    from just_dna_format.resolution import ResolutionRow

    from just_dna_enricher.civic_build import (
        CIVIC_COLUMNS,
        CIVIC_EVIDENCE_FILE,
        CIVIC_PROFILE_FILE,
        CIVIC_VARIANT_FILE,
        build_snapshot,
        civic_release_url,
        download_civic_file,
    )
    from just_dna_enricher.civic_vcf import CIVIC_VCF_FILE
    from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME
    from just_dna_enricher.sequences import SequenceProxy, verify_reference_alleles
    from just_dna_enricher.upload import DEFAULT_CIVIC_REPO_ID, plan_reference_snapshot

    failures: list[str] = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        typer.secho(
            f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}",
            fg=typer.colors.GREEN if ok else typer.colors.RED,
        )
        if not ok:
            failures.append(label)

    out.mkdir(parents=True, exist_ok=True)
    typer.echo(f"CIViC release {release}")

    # 1 ── the release, with its bytes recorded
    typer.echo("\n1. Downloading the dated release")
    paths, shas = [], {}
    wanted = [CIVIC_EVIDENCE_FILE, CIVIC_VARIANT_FILE, CIVIC_PROFILE_FILE]
    if submitted:
        # Hashed like every other input, because the whole point of reading it from the dated release
        # rather than the API is that its bytes can be pinned.
        wanted.append(CIVIC_VCF_FILE)
    for filename in wanted:
        got = download_civic_file(out / filename, civic_release_url(release, filename))
        paths.append(got.path)
        shas[filename] = got.sha256
        typer.echo(f"     {filename:38s} {got.sha256[:16]}…  {got.path.stat().st_size:>9,} bytes")
    check(all(shas.values()), "every input file hashed")
    vcf_path = paths.pop() if submitted else None

    # 2 ── two builds, byte for byte
    typer.echo("\n2. Building twice")
    first = build_snapshot(*paths, out / "build-a", release=release,
                           evidence_sha256=shas[CIVIC_EVIDENCE_FILE],
                           variant_sha256=shas[CIVIC_VARIANT_FILE],
                           profile_sha256=shas[CIVIC_PROFILE_FILE],
                           vcf=vcf_path, vcf_sha256=shas.get(CIVIC_VCF_FILE))
    second = build_snapshot(*paths, out / "build-b", release=release, vcf=vcf_path)
    typer.echo(f"     {first.record_count} rows on {first.variants} variants "
               f"({first.status_basis})")
    if first.status_counts:
        typer.echo("     " + " · ".join(f"{k} {v}" for k, v in sorted(first.status_counts.items())))
    check(
        first.parquet_file.read_bytes() == second.parquet_file.read_bytes(),
        "a rebuild is byte-identical (P7)",
    )

    # 4 ── the accounting (run before the slow check, so a broken build fails fast)
    total_dropped = sum(first.dropped.values())
    check(
        first.record_count + total_dropped == first.input_rows,
        "the drop registry accounts for every input row",
        f"{first.input_rows} = {first.record_count} kept + {total_dropped} dropped",
    )
    for reason, count in first.dropped.items():
        typer.echo(f"     dropped {reason:24s} {count:>6,}")

    # 5 ── what would be published
    plan = plan_reference_snapshot(first.out_dir, DEFAULT_CIVIC_REPO_ID)
    expected = {f"data/{first.parquet_file.name}", RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME}
    check(set(plan.files) == expected, "the publish plan is data + release.json + LICENSE",
          ", ".join(sorted(plan.files)))

    frame = pl.read_parquet(first.parquet_file) if (pl := _polars()) else None
    if frame is not None:
        check(list(frame.columns) == list(CIVIC_COLUMNS), "the emitted column order is the fixed one")

    # 3 ── the external check, and the reason this command needs a network
    typer.echo("\n3. Cross-checking placed coordinates against the GRCh38 reference")
    if offline or frame is None:
        typer.secho("     SKIPPED (--offline) — a check that did not run is not a check that passed",
                    fg=typer.colors.YELLOW)
    else:
        placed = frame.filter(pl.col("chrom").is_not_null() & pl.col("ref").is_not_null())
        rows = [
            ResolutionRow(
                variant_key=f"{r['chrom']}:{r['start']}:{r['ref']}",
                status="resolved", chrom=r["chrom"], start=r["start"], ref=r["ref"],
            )
            for r in placed.iter_rows(named=True)
        ]
        result = verify_reference_alleles(rows, sequences=SequenceProxy())
        if result.not_checked:
            typer.secho(
                f"     SKIPPED — {result.not_checked}. A check that could not run is not a check "
                f"that passed.", fg=typer.colors.YELLOW,
            )
        else:
            # `subjects` rather than `len(rows)`: a row the service answered nothing about is outside
            # the denominator rather than inside it with a clean bill, and reporting the wider number
            # would claim coverage the check did not have.
            check(
                not result.mismatches,
                "every placed ref matches the GRCh38 reference sequence",
                f"{result.subjects} of {len(rows)} coordinate(s) read, "
                f"{len(result.mismatches)} mismatch(es)",
            )
            for m in result.mismatches[:5]:
                typer.secho(f"     {m}", fg=typer.colors.RED)

    if not keep:
        for path in paths:
            path.unlink(missing_ok=True)

    typer.echo("")
    if failures:
        typer.secho(f"REPRODUCTION FAILED: {len(failures)} check(s) — {'; '.join(failures)}",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Reproduced {release}: {first.record_count} rows, all checks passed",
                fg=typer.colors.GREEN)


def _polars():
    """polars if the [dev] extra is present, else `None` — the builder needs it, a reader does not."""
    try:
        import polars

        return polars
    except ImportError:  # pragma: no cover - only where [dev] is absent
        return None



pubmind_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the PubMind literature-derived snapshot. Operator-built and inject-only; "
        "never published."
    ),
    no_args_is_help=True,
)
app.add_typer(pubmind_app, name="pubmind")

#: The refusal `pubmind publish` prints. Pinned by a test because a refusal's *reason* is the whole
#: value of a command that exists in order to say no (`@warning-text-is-api`).
PUBMIND_PUBLISH_REFUSAL = (
    "pubmind publish is refused by design. The ANNOVAR-distributed PubMind table states no data "
    "terms of its own: CHOP's LICENSE.md covers the software (academic, non-commercial), the paper "
    "is CC BY-NC-ND 4.0, and nobody publishes a licence for those bytes. An unestablished permission "
    "is not a permission, so a bulk file arriving under terms we cannot establish is not a file we "
    "may pass on — the same rule that leaves PharmVar's snapshot unpublishable. Build your own with "
    "`pubmind build` and point at it with $JUST_DNA_PUBMIND_CACHE. Lifting this needs an answer from "
    "WGLab and CHOP's Office of Technology Transfer, in writing, not a flag."
)


@pubmind_app.command("build")
def pubmind_build_(
    table: Path | None = typer.Option(
        None, "--table", exists=True, dir_okay=False,
        help="Local hg38_pubmind_db.txt.gz. Omit and pass --download to fetch it from ANNOVAR.",
    ),
    download: bool = typer.Option(
        False, "--download", help="Download the ANNOVAR-distributed PubMind table into --out first.",
    ),
    out: Path = typer.Option(
        Path("pubmind"), "--out", file_okay=False,
        help="Output snapshot directory (writes data/pubmind.parquet + release.json).",
    ),
) -> None:
    """Reduce the ANNOVAR-distributed PubMind table to the parquet snapshot the checks read.

    **There is no `--use` flag, and its absence is the design.** PubMind's data terms could not be
    established, and unknown terms warn rather than gate (`commercial_use=None` never taints a
    module). A declared-use gate here would refuse every build unconditionally, and a flag feeding a
    gate that never gates is a flag that does nothing. What the unknown terms do gate is *publishing*
    a snapshot or a module carrying these bytes — see `pubmind publish`, which refuses.
    """
    if table is None and not download:
        typer.secho("Provide --table PATH or --download.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    fetched = None
    # `PubMindBuildError` covers the download too: it translates `httpx` into `PubMindUnavailable`, a
    # subclass, so this one arm catches a moved bulk URL as well as a malformed table. Without that,
    # ANNOVAR rotating the file — the rot the source's own lack of a cadence invites — printed a
    # traceback instead of this line.
    try:
        if table is None:
            fetched = download_pubmind_table(out / "hg38_pubmind_db.txt.gz")
        result = build_pubmind_snapshot(
            fetched.path if fetched is not None else table,
            out,
            source_url=fetched.url if fetched is not None else None,
            source_sha256=fetched.sha256 if fetched is not None else None,
            source_etag=fetched.etag if fetched is not None else None,
            source_last_modified=fetched.last_modified if fetched is not None else None,
        )
    except (FileNotFoundError, ImportError, PubMindBuildError) as exc:
        typer.secho(f"PUBMIND BUILD FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"pubmind snapshot: {result.parquet_file}", fg=typer.colors.GREEN)
    typer.echo(
        f"kept: {result.record_count} of {result.input_rows} row(s)  "
        f"dataset: {result.dataset}  "
        + "  ".join(f"{name}: {count}" for name, count in sorted(result.derivations.items()))
    )
    typer.secho(
        "  dropped: "
        + ", ".join(f"{name} {count}" for name, count in result.dropped.items()),
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        f"  {result.multi_pvid_keys} of {result.allele_keys} coordinate(s) carry several PVIDs "
        f"(worst {result.max_pvids_per_key}), and {result.contested_keys} of those disagree. Every "
        f"PVID is kept as its own row: choosing a winner would be an ordering nobody defined.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        "  data terms unestablished: operator-built and inject-only, never published.",
        fg=typer.colors.YELLOW,
    )


@pubmind_app.command("publish")
def pubmind_publish_() -> None:
    """Refuse to publish the PubMind snapshot, and say why.

    The command exists in order to refuse. A missing one reads as an oversight somebody will helpfully
    add, and the reason belongs where a reader looks for it rather than only in a design document.
    """
    typer.secho(f"REFUSED: {PUBMIND_PUBLISH_REFUSAL}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


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


def _mint_record(result: MintResult) -> VerificationRecord:
    """What a minting run can honestly attest about `vrs_allele_id` (RM45).

    The member names the **cross-check** — a source's own `ga4gh:VA.…` against the one minted here —
    and its input is `mint_resolution_rows(source_ids=…)`, a map this command has nothing to fill
    from: `resolution.csv` records the ids the tier minted and never where an id came from, so the
    question was not put. That is a skip, not a clean pass. Recording `subjects` as the alleles the
    run *named* would say the opposite of what happened, which is the F4 shape — an attestation
    asserting a comparison nobody made — and it is the reading a coverage figure invites, since this
    pass does end with a number out of a number.

    The coverage counts still travel, in `detail`: they are what the run did do, and they are grouped
    by reason class by `MintResult` rather than listed per allele. They are not this record's
    numbers, though — the compiler publishes them, as `manifest.compilation.vrs_alleles` and
    `vrs_alleles_identified`, which is where a consumer already reads them.
    """
    detail = (
        "no source-reported allele id accompanies this resolution.csv, so nothing was compared "
        f"against the ids minted here; {result.identified}/{result.alleles} allele(s) now carry one"
    )
    gaps = result.coverage_warnings()[1:]
    if gaps:
        detail += ". Not named: " + "; ".join(line.strip() for line in gaps)
    return skipped("vrs_allele_id", "nothing_to_check", detail=detail)


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

    path = sidecar_path(spec_dir, "resolution.csv", error=EnrichmentError)
    if not path.exists():
        typer.secho(f"no resolution.csv in {spec_dir} — run `enrich` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    rows, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
    if errors:
        typer.secho(f"{path.name} is invalid: {errors[0]}", fg=typer.colors.RED, err=True)
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
    try:
        record_verification([_mint_record(result)], spec_dir, error=EnrichmentError)
    except EnrichmentError as exc:
        # The mint did **not** fail — the ids are on disk and the line above says so. What failed is
        # the attestation, and the only way this raises is a module carrying `verification.json` in
        # both legal places, which is a defect in the module's layout rather than in this run. Naming
        # the mint here would tell the author the opposite of what happened.
        typer.secho(f"MINTED, BUT NOT ATTESTED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


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
    pubmind_cache: Path | None = typer.Option(
        None, "--pubmind-cache",
        help="Explicit PubMind snapshot (see `pubmind build`); $JUST_DNA_PUBMIND_CACHE otherwise.",
    ),
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
        ensembl_cache=ensembl_cache, clinvar_cache=clinvar_cache, pubmind_cache=pubmind_cache,
    )
    if as_json:
        typer.echo(json.dumps({
            "rsid": hint.rsid,
            "rsid_status": str(hint.rsid_status) if hint.rsid_status else None,
            "loci": hint.loci,
            "rsid_candidates": hint.rsid_candidates,
            "populations": hint.populations,
            "clin_sig": hint.clin_sig,
            "pubmind": hint.pubmind,
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
    # One line per PubMind record, never a rolled-up verdict: several records can describe one
    # position and their calls are allowed to differ, which is the finding rather than untidiness.
    for record in hint.pubmind:
        typer.echo(
            f"pubmind\t{record.get('clin_sig')}\t{record.get('pvid')}"
            f"\tconfidence={record.get('confidence')}\tderivation={record.get('derivation')}"
        )
    _echo_hint(hint)


@hint_app.command("recover")
def hint_recover_(
    chrom: str = typer.Option(..., "--chrom", help="Chromosome of the old coordinate."),
    start: int = typer.Option(..., "--start", help=f"1-based {GRCH37_BUILD} position."),
    ref: str | None = typer.Option(None, "--ref", help="Reference allele, to narrow the answer."),
    alts: str | None = typer.Option(None, "--alts", help="Alt allele(s), comma-separated."),
    offline: bool = typer.Option(False, "--offline", help="Skip the lookup and say so."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Which rs-number GRCh37 dbSNP records at an hg19/GRCh37 coordinate.

    For a paper that predates GRCh38. Author the **rs-number**, not a converted position: an
    rs-number resolves into a coordinate the compiler can cross-examine, where a lifted-over position
    becomes the row's only witness to itself. Nothing is written — the rs-number is the row's
    identity, and a machine filling one migrates `variant_key` with no authored edit anywhere.
    """
    hint = lookup_old_assembly(
        chrom=chrom, start=start, ref=ref, alts=alts, offline=offline
    )
    if as_json:
        typer.echo(json.dumps({
            "chrom": hint.recovery.chrom,
            "start": hint.recovery.start,
            "genome_build": GRCH37_BUILD,
            "outcome": hint.recovery.outcome,
            "rsids": hint.recovery.rsids,
            "candidates": hint.recovery.candidates,
            "advisory": as_report_rows(hint),
            "findings": [f"{f.level}: {f.message}" for f in hint.findings],
        }, indent=2, default=str))
        return
    for candidate in hint.recovery.candidates:
        typer.echo(
            f"candidate\t{candidate['rsid']}\t{GRCH37_BUILD} {hint.recovery.chrom}:"
            f"{candidate['start']}-{candidate['end']}\t{'/'.join(candidate['alleles'])}"
        )
    _echo_hint(hint)


@hint_app.command("citation")
def hint_citation_(
    pmid: str | None = typer.Option(None, "--pmid", help="PubMed id to check."),
    doi: str | None = typer.Option(None, "--doi", help="DOI to check (the one you authored)."),
    pmcid: str | None = typer.Option(
        None, "--pmcid", help="PubMed Central id (PMC…) to resolve to the PubMed id tables key on."
    ),
    offline: bool = typer.Option(False, "--offline", help="Skip the check and say so."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine answer."),
) -> None:
    """Does this citation exist, and **is it the paper you meant**?

    A paywall hides the fulltext, never the PubMed record, so existence is answerable for paywalled
    work; Crossref covers what PubMed does not index at all. Every answer is tri-state — `unknown`
    means the registry could not be asked, which is not the same as "no such paper".

    **Existence is not identity.** PMIDs are densely allocated, so a recalled or invented number is
    very likely to be a real record for a different article, and `pmid_exists` alone cannot catch a
    fabricated citation. The title, journal, year and first author come back in the same response and
    are printed for exactly that comparison (S12).

    **`--pmcid` goes the other way.** Every `pmid` in the schema keys on the PubMed id — `studies.csv`,
    a binning row's and a `pharm_variants.csv` row's alike — and a curator holding only a `PMC…` id
    had no route to it: the schema refused the cell and named no remedy. This resolves it and then asks PubMed which paper that is. The id is **reported,
    never written**: filling `pmid` from NCBI would make the existence check compare NCBI with itself.
    """
    if pmid is None and doi is None and pmcid is None:
        typer.secho("give --pmid, --doi or --pmcid", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    hint = lookup_citation(pmid=pmid, doi=doi, pmcid=pmcid, offline=offline)
    if as_json:
        typer.echo(json.dumps({
            "pmid": hint.pmid,
            "doi": hint.doi,
            "pmid_exists": hint.pmid_exists,
            "doi_exists": hint.doi_exists,
            "registry_doi": hint.registry_doi,
            "pmcid": hint.pmcid,
            "open_access": hint.open_access,
            "abstract_available": hint.abstract_available,
            "title": hint.title,
            "journal": hint.journal,
            "year": hint.year,
            "first_author": hint.first_author,
            "advisory": as_report_rows(hint),
            "findings": [f"{f.level}: {f.message}" for f in hint.findings],
        }, indent=2, default=str))
        return
    for label, value in (("pmid_exists", hint.pmid_exists), ("doi_exists", hint.doi_exists)):
        typer.echo(f"{label}\t{'unknown' if value is None else value}")
    if hint.pmcid:
        typer.echo(f"pmcid\t{hint.pmcid}")
    # Printed unconditionally when known: the whole point is that a caller reading prose can compare
    # what the record says against the paper they had in mind.
    for label, value in (
        ("title", hint.title),
        ("journal", hint.journal),
        ("year", hint.year),
        ("first_author", hint.first_author),
    ):
        if value:
            typer.echo(f"{label}\t{value}")
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
    gene: list[str] = typer.Option([], "--gene", help="Only annotations naming this gene (repeatable)."),
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


#: Which authority `draft-panel` may draft from. A closed set, and the members reach an author's
#: `sources.csv` through `SourceRow.source`, so they are named after the source and nothing else.
PANEL_SOURCES: frozenset[str] = frozenset({"clinvar", "pubmind", "civic"})


@app.command("draft-panel")
def draft_panel_(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    gene: list[str] = typer.Option(..., "--gene", help="Gene to draft rows for (repeatable)."),
    source: str = typer.Option(
        "clinvar", "--source",
        help=(
            "Which authority to draft the calls from: clinvar (the default); pubmind — an LLM's "
            "reading of the literature, which needs an operator-built snapshot and still reads the "
            "ClinVar one for its gene attribution; or civic — curated cancer interpretations, which "
            "writes the DIRECTION axis rather than clin_sig and needs a `civic build` snapshot."
        ),
    ),
    civic_cache: Path | None = typer.Option(
        None, "--civic-cache", exists=True, file_okay=False,
        help=(
            "Built CIViC snapshot (see `civic build`). Only read under --source civic; omit it and "
            "$JUST_DNA_CIVIC_CACHE is used."
        ),
    ),
    snapshot: Path | None = typer.Option(
        None, "--snapshot", exists=True, file_okay=False,
        help=(
            "Built ClinVar snapshot (see `clinvar build`). Omit it and the cache is used, or the "
            "published snapshot downloaded — the citations table comes with it, which is what a panel "
            "needs to compile. Read for its gene attribution under --source pubmind, which publishes "
            "no gene column of its own."
        ),
    ),
    pubmind_cache: Path | None = typer.Option(
        None, "--pubmind-cache", exists=True, file_okay=False,
        help=(
            "Built PubMind snapshot (see `pubmind build`), for --source pubmind. Omit it and "
            "$JUST_DNA_PUBMIND_CACHE is read; there is no published one to download."
        ),
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use a local snapshot only: never download one.",
    ),
    download: bool = typer.Option(
        True, "--download/--no-download",
        help="Provision the published snapshot when no local one is found. Fetching it is this "
             "command's only network use, so --no-download coincides with --offline today; it is a "
             "separate switch because it says 'do not go and get one', not 'make no request'.",
    ),
    clin_sig: str | None = typer.Option(
        None, "--clin-sig",
        help="Comma-separated calls to include. Default: pathogenic,likely_pathogenic.",
    ),
    min_review_stars: int = typer.Option(
        2, "--min-review-stars", min=0, max=4,
        help="Review-status floor, --source clinvar only. 2 = multiple submitters, no conflicts.",
    ),
    max_citations: int = typer.Option(
        3, "--max-citations", min=0,
        help="Study rows to draft per variant from ClinVar's literature links. 0 disables. "
             "--source clinvar only: PubMind's channel carries no PMID.",
    ),
    min_confidence: int = typer.Option(
        DEFAULT_MIN_CONFIDENCE, "--min-confidence", min=0, max=3,
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
    if source not in PANEL_SOURCES:
        typer.secho(
            f"--source {source!r} is not an authority this command drafts from. "
            f"Known: {', '.join(sorted(PANEL_SOURCES))}.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    calls = (
        frozenset(c.strip() for c in clin_sig.split(",") if c.strip()) if clin_sig else None
    )
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
                f"  warning: {dial} is a --source {belongs} dial and does nothing under "
                f"--source {source}",
                fg=typer.colors.YELLOW, err=True,
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
            fg=typer.colors.YELLOW, err=True,
        )
    try:
        if source == "civic":
            result = draft_panel_from_civic(
                spec_dir, gene, snapshot=civic_cache,
                declared_use=_use(use), offline=offline, dry_run=dry_run,
            )
        elif source == "pubmind":
            result = draft_gene_panel_from_pubmind(
                spec_dir, gene, snapshot=snapshot, pubmind_snapshot=pubmind_cache,
                offline=offline, download=download,
                **({"clin_sig": calls} if calls else {}),
                min_confidence=min_confidence, declared_use=_use(use), dry_run=dry_run,
            )
        else:
            result = draft_gene_panel(
                spec_dir, gene, snapshot=snapshot, offline=offline, download=download,
                **({"clin_sig": calls} if calls else {}),
                min_review_stars=min_review_stars, max_citations=max_citations,
                declared_use=_use(use), dry_run=dry_run,
            )
    except (ClinVarDraftError, PubMindDraftError, *_DRAFT_PRECONDITION_ERRORS) as exc:
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


# ── MANE snapshot (build, publisher/dev surface) — RM168 ───────────────────────────────────────

mane_app = typer.Typer(
    add_completion=False,
    help=(
        "Build the MANE transcript snapshot — the numbering frame, cached and pinned instead of "
        "downloaded by hand and cited in prose."
    ),
    no_args_is_help=True,
)
app.add_typer(mane_app, name="mane")


@mane_app.command("build")
def mane_build_(
    download: bool = typer.Option(
        False, "--download",
        help=(
            "Fetch the release from NCBI. Without --release the newest version is discovered from "
            "current/README_versions.txt and then pinned to its versioned directory."
        ),
    ),
    release: str | None = typer.Option(
        None, "--release",
        help="MANE version to pin, e.g. 1.5. Resolves to release_<version>/, never current/.",
    ),
    summary: Path | None = typer.Option(
        None, "--summary", exists=True, dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.summary.txt.gz. Use instead of --download to build offline.",
    ),
    changed: Path | None = typer.Option(
        None, "--changed", exists=True, dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.changed_select_accessions.txt.gz.",
    ),
    not_in_mane: Path | None = typer.Option(
        None, "--not-in-mane", exists=True, dir_okay=False,
        help="Local MANE.GRCh38.v<ver>.protein_coding_genes_not_in_mane.txt.gz.",
    ),
    versions: Path | None = typer.Option(
        None, "--versions", exists=True, dir_okay=False,
        help=(
            "Local README_versions.txt. Optional, and the only way an offline build can name its "
            "release: a filename is never parsed for one."
        ),
    ),
    out: Path = typer.Option(
        Path("mane"), "--out", file_okay=False,
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
    every gating axis is unknown, and a declared-use gate fed an unknown refuses every build
    unconditionally, which is a flag that does nothing (`@acquisition-gate-is-not-a-read-gate`).

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

    local = {"summary": summary, "changed_select_accessions": changed,
             "protein_coding_genes_not_in_mane": not_in_mane}
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

    downloads: dict = {}
    versions_file = versions
    try:
        if download:
            pinned = release or discover_current_release()
            out.mkdir(parents=True, exist_ok=True)
            fetched_versions = download_mane_file(
                out / MANE_VERSIONS_FILENAME, mane_versions_url(pinned)
            )
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
    typer.secho(
        "  MANE is the default, not the answer: it shows a gene's second clinical transcript where "
        "there is one, and says nothing about isoforms it does not carry.",
        fg=typer.colors.YELLOW,
    )


# **Last line of the file, and that is the whole of this fix (RM100).** It used to sit at line 1688,
# above the `hint` sub-app, `draft-clinpgx`, `draft-panel` and `clinvar citations` -- so
# `python -m just_dna_enricher.cli` ran `app()` before those registrations executed and exposed 23 of
# the 26 top-level commands. Harmless through the `[project.scripts]` entry point, which imports the
# module fully and then calls `app()`, and wrong for anyone invoking the module directly.
if __name__ == "__main__":
    app()

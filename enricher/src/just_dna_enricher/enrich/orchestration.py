"""The run itself: `enrich()` takes the spec lock and `_run_enrichment` walks the resolver chain,
the verification passes and the commit (RM260 split this out of the former single-file `enrich.py`).

`_run_enrichment` is one function, so this module is larger than its siblings; splitting it would be a
logic edit, not a move.
"""

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import _restamp_for_build, load_csv_rows
from just_dna_compiler.resolution import contradiction_reason, hosting_verdict, undecided_reason
from just_dna_format.alleles import strand_flip_explains
from just_dna_format.base import merge_key
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher import clinvar
from just_dna_enricher.civic_citations import check_evidence_status_currency, read_studies
from just_dna_enricher.civic_refutation import RefutationFinding, compare_refutations
from just_dna_enricher.clinical import (
    ClinSigComparison,
    ClinSigConflict,
    ConcordanceRecord,
    answered_call_shift,
    clin_sig_concordance,
    compare_clin_sig,
    concordance_notes,
    concordance_sentences,
    tautology_reason,
)
from just_dna_enricher.concordance import (
    AnsweredCallReport,
    answered_call_notes,
    answered_call_sentences,
    write_concordance_tables,
)
from just_dna_enricher.currency import (
    CurrencyCheck,
    ReleaseProbe,
    check_dataset_currency,
    summarize_currency,
    unchecked_sentences,
)
from just_dna_enricher.download import ensure_clinvar_snapshot, ensure_snapshot
from just_dna_enricher.enrich.build_declaration import spec_genome_build
from just_dna_enricher.enrich.outcome import (
    EnrichmentError,
    EnrichmentResult,
    SubjectDrift,
    _rederived_drift,
    _subject_key,
)
from just_dna_enricher.enrich.resolution_csv import _write_resolution_csv
from just_dna_enricher.enrich.subjects import (
    _authored_alt,
    _check_authored_pairs,
    collect_subjects,
    select_par_representative,
)
from just_dna_enricher.enrich.verification_records import _verification_records
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.gnomad import GnomadClient, GnomadError
from just_dna_enricher.grch37 import Grch37Client, diagnose_wrong_build, summarize_build_diagnoses
from just_dna_enricher.identifiers import IdentifierUnavailable, RsidStatus, check_rsids
from just_dna_enricher.licensing import (
    overlay_answers,
    read_sources_file,
    record_source_terms,
    require_sources_file,
    resolution_authority,
    sidecar_path,
)
from just_dna_enricher.locations import (
    resolve_civic_reference,
    resolve_clinvar_reference,
    resolve_ensembl_reference,
    resolve_pubmind_reference,
)
from just_dna_enricher.resolver import AlleleMismatch, lookup_loci
from just_dna_enricher.sequences import (
    RefCheck,
    SequenceProxy,
    summarize_ref_mismatches,
    verify_reference_alleles,
)
from just_dna_enricher.transaction import ResolutionJournal, SubjectProgress, spec_lock
from just_dna_enricher.verification import examples, record_verification
from just_dna_enricher.vrs import MintResult, VrsMinter, mint_resolution_rows

logger = logging.getLogger("just_dna_enricher.enrich")


def enrich(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    ensembl_cache: Path | None = None,
    clinvar_cache: Path | None = None,
    pubmind_cache: Path | None = None,
    civic_cache: Path | None = None,
    use_clinvar: bool = True,
    use_gnomad: bool = True,
    download: bool = True,
    genome_build: str | None = None,
    write: bool = True,
    mint_vrs: bool = True,
    verify_ref: bool = True,
    verify_clinsig: bool = True,
    verify_rsids: bool = True,
    verify_datasets: bool = True,
    keep_par_twin: bool = False,
    rederive: bool = False,
    keep_staging: bool = False,
    progress: Callable[[int, int], None] | None = None,
    resolver: EnsemblResolver | None = None,
    gnomad_client: Optional["GnomadClient"] = None,
    grch37_client: Grch37Client | None = None,
    release_probes: Mapping[str, ReleaseProbe] | None = None,
) -> EnrichmentResult:
    """Resolve a spec's variants into `resolution.csv`. See the module docstring for the chain/modes.

    The chain is: existing rows → Ensembl cache → ClinVar cache (`use_clinvar`, stamps
    `source="clinvar"`) → live Ensembl → live gnomAD (`use_gnomad`, stamps `source="gnomad"`). Each
    later link fills only what the earlier ones missed, so whichever link *first* knows a variant
    decides its `alts` — and since `alts` is a fact column, that decides the compiled bytes. The
    ordering is therefore chosen so no already-compiled module's `artifact.digest` can move when a new
    link is added. `--offline` clamps the chain to the two local caches (zero egress).

    `mint_vrs` stamps a `ga4gh:VA.…` allele id onto every resolved row (see `vrs.mint_resolution_rows`).
    Substitutions mint offline with no dependency; indels need the sequence, so they mint only when the
    run is online.

    `verify_ref` checks each authored/resolved `ref` against the actual reference sequence and reports
    disagreements — enrichment is partly *validation* of authored data, and this tier is the only one
    that can perform it (see `sequences.verify_reference_alleles`). It never repairs, and severity
    follows the mode, mirroring the compiler's VRS verify pass: `strict` treats a mismatch as fatal
    (its contract is a reproducible artifact, and a wrong `ref` can silently mint a *different* allele
    id), while `best_effort` warns and carries on. Needs sequence access, so it is skipped offline.

    A mismatch is then asked one further question, over those rows **only**: does the coordinate read
    as GRCh37 rather than as a wrong cell? That needs the live GRCh37 service, so it is skipped
    offline, it is bounded (`grch37.DEFAULT_DIAGNOSIS_LIMIT` — a systematic wrong build answers the
    same on every row), and `grch37_client` injects the client the way `resolver`/`gnomad_client` do.
    It adds no flag of its own: `verify_ref` gates the family and `--offline` is the egress switch.

    `verify_clinsig` compares each authored `clin_sig` against the ClinVar snapshot's own. It is
    offline-capable (the snapshot is local) and is the **one check whose severity does not follow the
    mode**: it warns in `strict` too, because failing a compile would make the format arbitrate a
    clinical disagreement. See `clinical.verify_clin_sig` for the full argument.

    `verify_datasets` compares every release this module records having been drafted from
    (`SourceRow.dataset`) against the one that source publishes now, and reports the gap (RM85). It is
    `rederive`'s cheap neighbour: both ask *has the world moved*, one about the rows and one about the
    release **label**, so this is the question you put first — it costs one request per source and
    tells you whether the full re-derivation is worth running. It reads and never writes; repairing a
    stale label is a re-draft, which is an author's decision and a different command. Severity follows
    the mode. `--offline` makes it `unchecked`, never *up to date*, and an unreachable source is never
    escalated by `strict` — nothing an author can edit clears a failed request. `release_probes`
    injects the registry the way `resolver`/`gnomad_client` inject theirs.

    `keep_par_twin` keeps both spellings of a pseudoautosomal locus. By default only the X one is
    recorded, because every annotation source uses X and a standard GRCh38 analysis set hard-masks the
    Y PAR — see `select_par_representative` for the probe behind that. Set it for a consumer whose
    reference is unmasked. The switch belongs here and could not live on the compiler: `resolution.csv`
    is injected data that travels with the module, so the choice is *recorded* and
    `compile → reverse → compile` stays a fixed point either way, whereas a compiler flag would not
    survive `reverse_module` rebuilding the spec from parquet alone (Principle 7).

    **The run is a transaction.** What the sources answer is staged to disk as the run proceeds, in the
    target's own directory (`transaction.ResolutionJournal`), and the table itself is written once — at
    the gate, through a writer that renames into place. Two properties follow, and the second is the
    one the item was really about. A kill at minute 29 leaves the staged answers, so the next run
    resumes instead of paying the thirty minutes again. And **a refused `strict` run commits nothing**:
    every refusal below raises before the write block, so the module is left exactly as it was — a
    written promise rather than an accident of statement order. `keep_staging` leaves the staged
    answers behind after a successful commit, for debugging; the default removes them.

    The whole run is one read-modify-write window over `resolution.csv`, so it is held under an
    advisory `flock` on the spec directory (`transaction.spec_lock`) — two concurrent runs were
    last-writer-wins over a merge with neither able to see the other, and a shorter table is
    indistinguishable from a module whose author resolved less. A second run refuses rather than
    waiting; a platform or filesystem that will not take the lock degrades with a warning that says so.
    `write=False` takes no lock and stages nothing: with nothing written there is no window to exclude,
    which keeps the flag meaning one thing everywhere.

    `rederive` re-asks the sources about **every** subject, including the ones already recorded, and
    reports which of them changed value (`EnrichmentResult.rederived`). That is the drift canary: an
    ordinary run gap-fills and never re-asks, so a source that silently revised an answer moves
    nothing an author could notice. A recorded subject this run could not ask about keeps its recorded
    rows — re-deriving must never be a way to shorten the table, which is the very incident this
    transaction exists for.

    `progress` is called `(done, total)` over **subjects**, `total` known before the first call. It
    exists for a caller with an idle timeout: what such a caller needs is a keepalive with monotonic
    progress, which a phase counter cannot give (a twenty-nine-minute phase emits nothing) and a link
    counter cannot promise (its total is not known until resolution finds the links). Exceptions from
    the callback are not swallowed; under the transaction that costs nothing, since the staged answers
    survive an abort exactly as they survive a kill.
    """
    spec_dir = Path(spec_dir)
    # The lock spans the whole window — from the read of the recorded table to the commit — so it is
    # taken here and not inside the run. A `write=False` caller touches no file and takes none.
    with spec_lock(spec_dir, enabled=write, error=EnrichmentError):
        return _run_enrichment(
            spec_dir,
            mode=mode,
            offline=offline,
            ensembl_cache=ensembl_cache,
            clinvar_cache=clinvar_cache,
            pubmind_cache=pubmind_cache,
            civic_cache=civic_cache,
            use_clinvar=use_clinvar,
            use_gnomad=use_gnomad,
            download=download,
            genome_build=genome_build,
            write=write,
            mint_vrs=mint_vrs,
            verify_ref=verify_ref,
            verify_clinsig=verify_clinsig,
            verify_rsids=verify_rsids,
            verify_datasets=verify_datasets,
            keep_par_twin=keep_par_twin,
            rederive=rederive,
            keep_staging=keep_staging,
            progress=progress,
            resolver=resolver,
            gnomad_client=gnomad_client,
            grch37_client=grch37_client,
            release_probes=release_probes,
        )


def _run_enrichment(
    spec_dir: Path,
    *,
    mode: str,
    offline: bool,
    ensembl_cache: Path | None,
    clinvar_cache: Path | None,
    pubmind_cache: Path | None,
    civic_cache: Path | None,
    use_clinvar: bool,
    use_gnomad: bool,
    download: bool,
    genome_build: str | None,
    write: bool,
    mint_vrs: bool,
    verify_ref: bool,
    verify_clinsig: bool,
    verify_rsids: bool,
    verify_datasets: bool,
    keep_par_twin: bool,
    rederive: bool,
    keep_staging: bool,
    progress: Callable[[int, int], None] | None,
    resolver: EnsemblResolver | None,
    gnomad_client: Optional["GnomadClient"],
    grch37_client: Grch37Client | None,
    release_probes: Mapping[str, ReleaseProbe] | None,
) -> EnrichmentResult:
    """The run itself, with the advisory lock already held. Every argument is `enrich`'s; see it.

    Split out rather than indented under a `with` so the chain below reads as one straight sequence of
    links and passes, which is how every comment in it is written.
    """
    if genome_build is None:
        genome_build = spec_genome_build(spec_dir)
    variants: list[VariantRow] = []
    variants_path = spec_dir / "variants.csv"
    if variants_path.exists():
        variants, errors, _ = load_csv_rows(variants_path, VariantRow, "variants.csv")
        if errors:
            raise EnrichmentError(f"variants.csv is invalid: {errors[0]}")
        # The **third** load site for `variants.csv`, and it needs the same re-stamp the compiler's two
        # already do. `VariantRow._freeze_identity` runs at construction with no module in scope, so it
        # always takes `derive_variant_key`'s GRCh38 default; the compiler fixes that after load in
        # both `validate_spec` and `compile_module`, and this loader was simply never added to the list.
        # The consequence was not cosmetic: `enrich` writes `variant_key` into `resolution.csv`, so a
        # GRCh37 module got a table keyed by `ga4gh:VA.…` GRCh38 ids while the compiler keyed the same
        # rows `6:26093141:G:A` — a resolution table that could not join to the module it was produced
        # for, silently. Warnings are dropped here on purpose: the compiler emits the same ones from its
        # own copy, and repeating them would double every message an author sees for one cause.
        _restamp_for_build(variants, genome_build)

    # Existing/human rows are authoritative — merge, never clobber. Keyed by `base.merge_key`,
    # which returns a **tuple** — the annotation said `str` and nothing reads it, but a wrong one
    # beside a new lookup is how the next reader learns the key shape wrong.
    existing: dict[tuple, list[ResolutionRow]] = {}
    # Through the shared resolver, so the pass writes back to wherever the module keeps this table —
    # root or `derived/`, whatever it is called. Reading one copy and writing another would leave the
    # module carrying two, which is the collision (RM49/RM51).
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=EnrichmentError)
    if write:
        # Fail on a placeholder or half-edited licence table now, before the fetch (S98, RM231).
        require_sources_file(spec_dir, error=EnrichmentError)
    if resolution_path.exists():
        rows, errors, _ = load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
        if errors:
            raise EnrichmentError(f"existing {resolution_path.name} is invalid: {errors[0]}")
        for row in rows:
            # Keyed by the row's declared *subject* — `ResolutionRow._KEY_FIELDS`, whose rule is
            # `subject` rather than `equality` because one rsID legitimately resolves to several loci
            # and this pass replaces the group whole (S51).
            existing.setdefault(merge_key(row), []).append(row)

    # What the chain treats as already answered. Ordinarily that is every recorded subject —
    # merge-not-clobber, unchanged. Under `rederive` it is nothing at all, so every subject re-enters
    # the worklist and the recorded rows survive only as the baseline the report is computed against
    # and as the carry-forward for a subject this run cannot ask about.
    covered: Mapping[tuple, list[ResolutionRow]] = {} if rederive else existing
    # The staged answers, in the target's own directory. `write=False` stages nothing: a caller that
    # touches no file has nothing to commit toward, and staging would leave droppings behind instead.
    journal = ResolutionJournal(resolution_path, genome_build=genome_build, enabled=write, rederive=rederive)
    staged = journal.resume()

    if genome_build != genome_build.strip() or genome_build != "GRCh38":
        logger.warning(
            # Scoped to *coordinate* resolution, because that is all it was ever true of. The
            # unqualified "no lookup runs" reads as a promise about the whole run, and the same run
            # asks dbSNP whether each authored rsID is current — legitimately, since an rsID names a
            # variant without naming an assembly, so its currency is a build-free question. A module
            # that authors rsIDs therefore got a banner saying nothing was looked up beside a
            # `verification.json` recording an rsID check over real subjects.
            "Coordinate resolution is GRCh38-bound; the module declares genome_build=%r, so no "
            "position is looked up and no lookup result is recorded (RM15). Every resolver link "
            "below is gated on GRCh38 — resolving against Ensembl and stamping the answer under %r "
            "would record a coordinate from a different assembly as this module's own. Authored "
            "coordinates are still transcribed verbatim, and build-free checks (rsID currency) still "
            "run.",
            genome_build,
            genome_build,
        )

    # Every table that can ask for a coordinate, not just variants.csv (a PGx module has none).
    subjects = collect_subjects(spec_dir, variants, genome_build)
    # The progress unit. Constructed here because this is the first moment `total` is knowable, and it
    # reports `(0, total)` immediately so a caller rendering a bar has the denominator before any work
    # starts. Subjects that share an rsID settle together, which is why the map is built once.
    tracker = SubjectProgress(len(subjects), progress)
    subjects_of_rsid: dict[str, list[str]] = {}
    for v in subjects:
        if v.rsid:
            subjects_of_rsid.setdefault(v.rsid, []).append(v.variant_key)
    tracker.settle(v.variant_key for v in subjects if _subject_key(v) in covered)

    # Partition the subjects that still need work (skip those an existing row already covers).
    need_pos = [
        v for v in subjects if v.rsid is not None and v.chrom is None and _subject_key(v) not in covered
    ]
    need_rsid = [
        v for v in subjects if v.rsid is None and v.chrom is not None and _subject_key(v) not in covered
    ]
    # Rows that authored BOTH halves of the identity. They need no resolution, which is exactly why
    # nothing used to look at them: they fall through to the verbatim branch below. But an authored
    # pair is a *claim* — this rsID sits at this coordinate — and this tier is the only one that can
    # compare it with a reference (`rsid_coordinate_agreement`). Deliberately **not** exempted by an
    # existing `resolution.csv` row: that row is machine-written or hand-corrected, not the reference,
    # so skipping the pairs it covers would compare the module against itself.
    verify_pairs = [
        (v.rsid, v.chrom, v.start, v.ref)
        for v in subjects
        if v.rsid is not None and v.chrom is not None and v.start is not None
    ]

    rsid_to_loci: dict[str, list[dict]] = {}
    source_of_rsid: dict[str, str] = {}
    # A snapshot that is present and will not answer. Distinct from having none: the pair check below
    # reports `no_reference` either way, but a run that had no snapshot and one whose snapshot is
    # broken are different remedies, so the sentence differs and the log names the file.
    snapshot_unusable = False
    # rsIDs the live link could not put a question to at all — a failed request, not an empty answer.
    unreachable_rsids: set[str] = set()
    unconsulted_rsids: set[str] = set()  # nobody looked (RM98) — see the EnrichResult field
    # The source answered and every locus it gave was rejected by the allele-aware filter (S85). A
    # list rather than a set: it carries a finding per subject, not a bare id.
    allele_mismatches: list[AlleleMismatch] = []
    # Reverse (position→rsid) back-fill is allele-aware and keeps ALL candidates per authored allele,
    # so we can take a deterministic pick and flag a genuine multi-rsid allele as ambiguous rather than
    # guessing an allele-blind label (which was the mis-attribution / reverse-round-trip drift).
    # Initialized before the lookup, not inside it: the call can fail (a present-but-unqueryable
    # cache) and the loops below still have to have something to iterate.
    pos_candidates: dict[tuple, list[str]] = {}
    rev_candidates: dict[tuple, list[str]] = {}  # (chrom,start,ref,alt) -> sorted candidate rsids
    rev_source: dict[tuple, str] = {}  # which link produced the candidates
    positions = [(v.chrom, v.start, v.ref, _authored_alt(v)) for v in need_rsid]

    # ── Ensembl cache link (offline, first) ────────────────────────────────────────────────────
    reference = resolve_ensembl_reference(ensembl_cache)
    if reference is None and not offline and download:
        try:
            ensure_snapshot(ensembl_cache)
            reference = resolve_ensembl_reference(ensembl_cache)
        except Exception as exc:  # provisioning is best-effort; degrade to live/offline
            logger.warning("Snapshot provisioning failed (%s); continuing without cache.", exc)
    if reference is not None and (need_pos or need_rsid or verify_pairs) and genome_build == "GRCh38":
        # The verify rsIDs ride in the batch this call was already making, which is the whole cost of
        # the pair check. `verify_pairs` is in the gate too: a module where *every* row authors both
        # halves has empty `need_pos` and `need_rsid`, so the snapshot would never be opened and the
        # check would silently never run on exactly the modules it exists for.
        rsids = [v.rsid for v in need_pos if v.rsid] + [rsid for rsid, _, _, _ in verify_pairs]
        try:
            rsid_to_loci, pos_candidates, _ = lookup_loci(reference, rsids, positions)
        except Exception as exc:
            # A *located* cache can still be unusable — a stale snapshot, or a parquet a different
            # tool wrote — and the query then raises rather than returning nothing. That was fatal
            # before this block was widened, and it stays fatal for a run that needed the coordinates:
            # nothing here changes the severity of a broken cache for a module that was going to open
            # it anyway. What must not happen is the *check* making it fatal — this pass gates nothing
            # and costs nothing, so a module needing no resolution at all must not start failing
            # because an optional comparison went looking. Same argument the ClinVar link below makes,
            # applied to the only case this widening created.
            if need_pos or need_rsid:
                raise
            snapshot_unusable = True
            logger.warning(
                "Ensembl reference at %s is present but not queryable (%s); the rsID↔coordinate "
                "check is recorded as unrun. Rebuild it with `just-dna-enricher cache pull`.",
                reference,
                exc,
            )
        for rsid in rsid_to_loci:
            source_of_rsid[rsid] = "cache"
        for pt, cands in pos_candidates.items():
            if cands:
                rev_candidates[pt] = cands
                rev_source[pt] = "cache"
        tracker.settle(k for rsid in rsid_to_loci for k in subjects_of_rsid.get(rsid, ()))

    # ── ClinVar cache link (offline, after Ensembl cache, before live) ─────────────────────────
    # Fills only what the Ensembl cache missed, stamping source="clinvar". Placing it after the
    # Ensembl cache keeps a both-caches variant on source="cache"/Ensembl `alts`, so no compiled
    # module's artifact.digest moves. Offline uses a local ClinVar cache only (no download).
    # Located once rather than inside the link, because the clin_sig cross-check below needs the same
    # snapshot even when every variant is already resolved and the link itself has nothing to do.
    clinvar_ref: Path | None = None
    if (use_clinvar or verify_clinsig) and genome_build == "GRCh38":
        clinvar_ref = resolve_clinvar_reference(clinvar_cache)
        if clinvar_ref is None and not offline and download:
            try:
                ensure_clinvar_snapshot(clinvar_cache)
                clinvar_ref = resolve_clinvar_reference(clinvar_cache)
            except Exception as exc:  # provisioning is best-effort; degrade to live/offline
                logger.warning("ClinVar snapshot provisioning failed (%s); continuing without it.", exc)

    # The PubMind snapshot is the concordance check's *second* authority (RM134 § B), and it is
    # located beside ClinVar's for the same reason ClinVar's is located outside its own link: one
    # resolution, read by the pass that needs it. It is **not** a resolver link and never becomes one
    # — PubMind's coordinates are back-mappings of extracted text (`@source-vs-authority`) — so this
    # sits after the link above rather than inside it. **No `ensure_*` beside it, deliberately**: the
    # snapshot is operator-built and `pubmind publish` refuses, so nothing provisions it for you and
    # a missing one reads `unchecked` rather than becoming a download this run should attempt.
    pubmind_ref: Path | None = None
    if verify_clinsig and genome_build == "GRCh38":
        pubmind_ref = resolve_pubmind_reference(pubmind_cache)

    if use_clinvar and genome_build == "GRCh38" and (need_pos or need_rsid):  # noqa: SIM102
        # Kept nested: the outer clause is the build/mode gate, the inner is whether a cache resolved.
        if clinvar_ref is not None:
            cv_rsids = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
            cv_positions = [pt for pt in positions if not rev_candidates.get(pt)]
            cv_rsid_to_loci: dict[str, list[dict]] = {}
            cv_pos_candidates: dict[tuple, list[str]] = {}
            if cv_rsids or cv_positions:
                # A *located* cache can still be unusable: a stale snapshot, a hand-built parquet, or
                # one produced by a different tool has different columns, and the query then raises
                # rather than returning nothing. That must degrade to "this link had no answer" like
                # every other miss — one optional link's bad data should never sink an enrichment that
                # the Ensembl cache and the live chain can still complete. (Failing hard here was a
                # real crash for anyone whose cache dir held a foreign ClinVar parquet.)
                try:
                    cv_rsid_to_loci, cv_pos_candidates, _ = clinvar.lookup_loci(
                        clinvar_ref, cv_rsids, cv_positions
                    )
                except Exception as exc:
                    logger.warning(
                        "ClinVar reference at %s is present but not queryable (%s); continuing "
                        "without the ClinVar link. Rebuild it with `just-dna-enricher clinvar build`.",
                        clinvar_ref,
                        exc,
                    )
            if cv_rsid_to_loci or cv_pos_candidates:
                for rsid, loci in cv_rsid_to_loci.items():
                    if rsid not in rsid_to_loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = "clinvar"
                for pt, cands in cv_pos_candidates.items():
                    if cands and not rev_candidates.get(pt):
                        rev_candidates[pt] = cands
                        rev_source[pt] = "clinvar"
                tracker.settle(k for rsid in cv_rsid_to_loci for k in subjects_of_rsid.get(rsid, ()))

    # ── staged answers from an interrupted run, between the caches and the live links ──────────
    # Placed exactly here, and the position is the whole reason a resumed run reproduces an
    # uninterrupted one. Only the *live* links journal, so a staged answer is by construction one no
    # cache had; seeding it after the caches lets a snapshot provisioned between the kill and the
    # resume win the variant it would have won on a first run, and seeding it before the live links
    # keeps the request from being made a second time. Nothing derived from an answer is staged — the
    # hosting filter, the pseudoautosomal selection, `locus_index` and the minted ids all recompute —
    # so a flag that changed between the two runs changes the table, exactly as it would have.
    #
    # **A staged answer is honoured only if the link that produced it would run this time.** The two
    # gates below are the live links' own — the same names decide whether each block executes — so a
    # `--no-gnomad` or `--offline` resume drops what that link had already answered instead of
    # stamping a `source="gnomad"` row a first run with those flags would never have written. `alts`
    # is a fact column, so honouring a disabled link would move the compiled digest too.
    live_ensembl_runs = not offline and genome_build == "GRCh38"
    gnomad_runs = use_gnomad and not offline and genome_build == "GRCh38"
    dropped_link: list[str] = []
    for rsid, (staged_source, staged_loci) in staged.items():
        if not (gnomad_runs if staged_source == "gnomad" else live_ensembl_runs):
            dropped_link.append(staged_source)
            continue
        if rsid not in rsid_to_loci:
            rsid_to_loci[rsid] = staged_loci
            source_of_rsid[rsid] = staged_source
        tracker.settle(subjects_of_rsid.get(rsid, ()))
    if dropped_link:
        logger.info(
            "%d staged answer(s) are not seeded because the link that produced them is switched off "
            "this run (%s): a resume must reproduce the run its flags describe, not the run that was "
            "killed. Their subjects go back to the chain.",
            len(dropped_link),
            ", ".join(sorted(set(dropped_link))),
        )

    # ── live Ensembl link (V2→V1), for cache misses, unless offline ────────────────────────────
    if live_ensembl_runs:
        missing = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
        if missing:
            owned = resolver is None
            client = resolver or EnsemblResolver()
            try:
                for rsid in missing:
                    loci, src = client.resolve_rsid(rsid)
                    if loci is None:
                        # Could not ask (S20). Distinct from an empty answer, and the distinction has
                        # to survive to the row-writing loop below, which would otherwise record
                        # `status="not_found", source="ensembl"` — a negative nobody established.
                        unreachable_rsids.add(rsid)
                    elif loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = src or "ensembl"
                        # Staged before the next request is made, which is what makes minute 29
                        # recoverable: everything answered so far is already on disk when the kill
                        # arrives. Only a positive answer is staged — a request that failed is
                        # unchecked rather than absent, and freezing that into the journal would turn
                        # a transient outage into a permanent negative on every future run.
                        journal.record(rsid, src or "ensembl", loci)
                        tracker.settle(subjects_of_rsid.get(rsid, ()))
            finally:
                if owned:
                    client.close()

    # ── live gnomAD link (LAST), for what nothing else could resolve ───────────────────────────
    # Last place is deliberate and load-bearing, for the same reason ClinVar sits after the Ensembl
    # cache: `alts` is in RESOLUTION_FACT_FIELDS, so whichever link wins a variant decides that
    # variant's alt list and therefore its `weights.parquet` bytes. gnomAD reports only the alleles
    # *observed in gnomAD*, not every allele dbSNP knows, so promoting it would narrow some already-
    # compiled module's alts and move its artifact.digest. Going last means it can only ever add
    # variants nothing else had — a strictly additive link.
    if gnomad_runs:
        missing = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
        if missing:
            owned = gnomad_client is None
            client = gnomad_client or GnomadClient()
            try:
                for rsid, loci in client.resolve_rsids(missing).items():
                    if loci and rsid not in rsid_to_loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = "gnomad"
                        journal.record(rsid, "gnomad", loci)
                        tracker.settle(subjects_of_rsid.get(rsid, ()))
            except GnomadError as exc:  # a last-resort link must not sink the whole enrichment
                logger.warning("gnomAD link failed (%s); continuing without it.", exc)
            finally:
                if owned:
                    client.close()

    # ── assemble the table (a row for every subject; expansion → N rows) ───────────────────────
    # **Was any rsID link consulted at all?** (RM98.) Every one of them is gated: the two caches on
    # having resolved to a snapshot, the live Ensembl and gnomAD links on `not offline`. When all four
    # gates are shut — `--offline` on a machine with no cache is the case that guarantees it — nothing
    # was asked, and a `not_found` row below would be a fabricated negative rather than a fact. This is
    # deliberately a *run*-level question, not a per-rsID one: the branch it guards is reached only for
    # a subject no link produced a locus for, and if no link ran there is no per-rsID answer to have.
    rsid_links_consulted = reference is not None or clinvar_ref is not None or not offline
    out: list[ResolutionRow] = []
    unresolved: list[str] = []
    # Collected across the loop and reported once. A per-row line here would be one line per variant —
    # ten for the SHOX panel — which buries every other finding a run produces.
    par_twins_dropped: list[tuple[str, str, int]] = []
    for v in subjects:
        key = v.variant_key
        subject = _subject_key(v)
        # Every subject reaches this loop exactly once, whichever branch it takes, so counting here is
        # what makes the last progress report `(total, total)` rather than stopping wherever the links
        # happened to run out.
        tracker.settle((key,))
        if subject in covered:
            out.extend(covered[subject])
            if not any(r.chrom is not None for r in covered[subject]):
                unresolved.append(key)
            continue
        if v.rsid is not None and (v.chrom is None or v.rsid in rsid_to_loci):
            # **A row that authored both halves takes this branch too, once the reference has
            # answered for its rsID (S104).** The pair check above already looked the rsID up — the
            # verify rsIDs ride in the cache batch — and then the verbatim branch at the bottom
            # copied the authored coordinate into the table and threw the answer away: no `ref`, no
            # `alts`, so nothing to mint a VRS id from, and every CPIC-drafted module compiled with
            # "VRS allele identity covers 0/N". Recording the reference's loci instead gives the
            # compiler two *independent* values to compare, which is what its `_verify` was written
            # for and could never see while the table was a photocopy of the module. The authored
            # coordinate is untouched: it is the row's identity (`authored_ident`), the compiler
            # keeps it, and a disagreement with the locus recorded here is the finding, not a repair.
            # An rsID the reference does not know still falls through to the verbatim branch — no
            # link was asked live for a pair, so there is no answer to record and no negative to
            # fabricate.
            #
            # Forward resolution is allele-aware, exactly as the reverse (position→rsid) back-fill
            # already is. An rsID is a position/multi-allelic tag, so one id routinely names several
            # records — `rs281864532` is `G>GT`, `GT>G` *and* `GTT>G` at one position in ClinVar — and
            # the module's own genotype says which of them it is about. Recording the others would
            # hand the compiler a locus it can only drop, which costs a reproducible `strict` compile
            # for facts the module cannot use. This selects; it does not repair: every authored value
            # is untouched, and each skipped record is reported.
            # A subject with no constraint (a pharm annotation that named no genotype) keeps every
            # locus: nothing is known about which allele it is about, and dropping loci for lack of
            # evidence would invent a selection the row never made.
            all_loci = rsid_to_loci.get(v.rsid, [])
            loci = []
            subject = "allele" if v.origin == "haplotypes.csv" else "genotype"
            for lo in all_loci:
                verdict = (
                    True
                    if v.constraint is None
                    else hosting_verdict(v.constraint, lo.get("ref"), lo.get("alts"))
                )
                if verdict is not False:
                    loci.append(lo)
                if verdict is None:
                    # **Kept, and named for what it is.** The predicate reconciles the two common
                    # spellings of one indel by stripping the flank they share — a SHOX deletion drafted
                    # from ClinVar as `X:634689 CAG>C` now matches the `X:634690 AGAG>AG` Ensembl
                    # publishes, which is the same 2 bp AG deletion anchored one base earlier. What it
                    # cannot do is re-anchor inside a repeat, so a same-size different-content pair is
                    # reported as undecided rather than as a contradiction. This tier *can* settle it —
                    # `vrs.py` has seqrepo — and doing that automatically is the remaining half of RM31.
                    #
                    # The *reason* comes from the shared `undecided_reason` rather than being spelled
                    # here, because `None` has four causes and this sentence used to assert one of them
                    # for all four — including for a call that observed nothing, which no reference can
                    # settle, while the closing advice said to check one.
                    logger.warning(
                        "%s: whether %s:%s %s>%s can host the authored %s %s could not be decided from "
                        "the allele strings — %s. The locus is KEPT.",
                        v.rsid,
                        lo.get("chrom"),
                        lo.get("start"),
                        lo.get("ref"),
                        lo.get("alts"),
                        subject,
                        v.constraint,
                        undecided_reason(v.constraint, lo.get("ref"), lo.get("alts")),
                    )
                elif verdict is False:
                    # **The verdict is right and the old sentence was not.** `hosting_verdict` returns
                    # a confident `False` from two different arms — step 6 (the locus is a substitution
                    # or MNV, so there is no flank and no spelling freedom) and step 8 (an event length
                    # the locus does not offer) — and this message asserted step 8's reason for both.
                    # On the case that actually arrives, a strand-flipped SNV, "the event sizes differ"
                    # is a false claim about two 1 bp substitutions, and it sends the author to look for
                    # a second variant sharing the rsID rather than at the strand they authored on.
                    # `@warning-text-is-api`: the phrase is pinned in the symptom guide, so it moves
                    # there in the same change.
                    logger.warning(
                        "%s: %s:%s %s>%s cannot host the authored %s %s, and is left out of "
                        "resolution.csv. %s",
                        v.rsid,
                        lo.get("chrom"),
                        lo.get("start"),
                        lo.get("ref"),
                        lo.get("alts"),
                        subject,
                        v.constraint,
                        contradiction_reason(v.constraint, lo.get("ref"), lo.get("alts")),
                    )
            if all_loci and not loci:
                # **The source answered and every locus was rejected** — the fourth state (S85). Only
                # recorded where `all_loci` is non-empty: with nothing returned there was no answer to
                # reject, and that row is a genuine `not_found` the branches below handle. Built here,
                # beside the per-locus warnings above, so the finding and the log cannot disagree about
                # which loci were compared.
                allele_mismatches.append(
                    AlleleMismatch(
                        rsid=v.rsid,
                        genotype=v.constraint or "",
                        loci=tuple(
                            f"{lo.get('chrom')}:{lo.get('start')} {lo.get('ref')}>{lo.get('alts')}"
                            for lo in all_loci
                        ),
                        offered=tuple(f"{lo.get('ref')}>{lo.get('alts')}" for lo in all_loci),
                        strand_flip=v.constraint is not None
                        and any(
                            strand_flip_explains(v.constraint, lo.get("ref"), lo.get("alts"))
                            for lo in all_loci
                        ),
                    )
                )
            if loci and not keep_par_twin:
                # One place on two contigs: keep the X spelling every annotation source uses. Runs
                # after the allele-aware filter above so it only ever sees loci this row can host.
                loci, twins = select_par_representative(loci, build=genome_build)
                par_twins_dropped.extend(
                    (v.rsid, str(t.get("chrom")), int(t.get("start") or 0)) for t in twins
                )
            if loci:
                src = source_of_rsid.get(v.rsid, "cache")
                for i, locus in enumerate(loci):
                    out.append(
                        ResolutionRow(
                            variant_key=key,
                            rsid=v.rsid,
                            genome_build=genome_build,
                            locus_index=i,
                            source=src,
                            status="resolved",
                            **locus,
                        )
                    )
            elif v.chrom is not None:
                # The reference knows the rsID but at no locus that can host the authored allele
                # (S104, the pair case of S85). The row still has an authored coordinate, so it is
                # neither `not_found` nor unresolved: it is recorded as authored, exactly as it was
                # before the reference was consulted, and the allele mismatch above is the finding.
                out.append(
                    ResolutionRow(
                        variant_key=key,
                        rsid=v.rsid,
                        chrom=v.chrom,
                        start=v.start,
                        ref=v.ref,
                        alts=v.alts,
                        genome_build=genome_build,
                        source="authored",
                        status="resolved",
                    )
                )
            elif genome_build == "GRCh38" and v.rsid in unreachable_rsids:
                # The live link was asked and never answered (S20), so this row has the same shape as
                # the non-GRCh38 case below and gets the same treatment: no row at all. Writing
                # `not_found` here would state, in the artifact, that Ensembl was asked and does not
                # have this rsID — the one reading the run cannot support, and the fingerprint of a
                # fabricated identifier. The key stays `unresolved`, so `strict` still refuses and
                # `best_effort` still warns; what changes is that neither claims a source said no.
                unresolved.append(key)
            elif genome_build == "GRCh38" and not rsid_links_consulted:
                # **No link ran, so there is no answer to record** (RM98). This branch used to write
                # `status="not_found", source="cache"` unconditionally, which under `--offline` on a
                # machine with no Ensembl and no ClinVar cache named a cache that was never opened and
                # asserted that it does not have this rsID — a negative nobody established, about a
                # question never put. It sat between the two branches on either side of it, both of
                # which spell out in their own comments why that is forbidden.
                #
                # `--offline` is where it matters most, because that is the mode a consumer runs when
                # they *cannot* reach the source: the fabricated negative is guaranteed there rather
                # than incidental. `@unreachable-not-absent`.
                #
                # Named **separately** from `unreachable_rsids` rather than folded into it: that list
                # means "the live request was made and failed", and its warning says so in those
                # words. "Nothing was asked" and "the asking failed" are two different states of the
                # world, and collapsing them would replace one small untruth with another.
                unconsulted_rsids.add(v.rsid)
                unresolved.append(key)
            elif genome_build == "GRCh38":
                out.append(
                    ResolutionRow(
                        variant_key=key,
                        rsid=v.rsid,
                        genome_build=genome_build,
                        source="ensembl" if not offline else "cache",
                        status="not_found",
                    )
                )
                unresolved.append(key)
            else:
                # No link ran at all (every one is gated on GRCh38), so there is no answer to record.
                # `not_found` would say "the source was asked and does not have this rsID" — a negative
                # nobody established, about a question never put. `VALID_RESOLUTION_STATUS` has no
                # `unchecked` member to write instead, and inventing one to describe a row that carries
                # no fact is worse than writing no row: the position is simply still unset, which the
                # unresolved list already says and the compiler already warns about.
                unresolved.append(key)
        elif v.rsid is None and v.chrom is not None:
            # Allele-aware back-fill (Tier 0/1/3): 0 candidates → leave rsid null (coordinate is the
            # identity, don't guess); 1 → attach it; ≥2 (genuine dbSNP merge at the exact allele) →
            # deterministic pick + status="ambiguous" + the full candidate list, never a silent guess.
            pt = (v.chrom, v.start, v.ref, _authored_alt(v))
            cands = rev_candidates.get(pt, [])
            if not cands:
                rsid, status, alternates, src = None, "resolved", None, "authored"
            elif len(cands) == 1:
                rsid, status, alternates, src = cands[0], "resolved", None, rev_source[pt]
            else:
                rsid, status, alternates, src = cands[0], "ambiguous", ",".join(cands), rev_source[pt]
            out.append(
                ResolutionRow(
                    variant_key=key,
                    rsid=rsid,
                    chrom=v.chrom,
                    start=v.start,
                    ref=v.ref,
                    alts=v.alts,
                    genome_build=genome_build,
                    source=src,
                    status=status,
                    rsid_alternates=alternates,
                )
            )
        else:
            # Already complete with no reference answer to record, or a position with no rsID to ask
            # about — the authored record is the whole fact. A pair whose rsID the reference knows
            # never reaches here since S104; one it does not know, or one enriched with no Ensembl
            # snapshot, still does, and stays `authored` rather than gaining a fabricated negative.
            out.append(
                ResolutionRow(
                    variant_key=key,
                    rsid=v.rsid,
                    chrom=v.chrom,
                    start=v.start,
                    ref=v.ref,
                    alts=v.alts,
                    genome_build=genome_build,
                    source="authored",
                    status="resolved",
                )
            )

    # The subject keys the carry-forward below puts back, so the report can leave them out of its own
    # denominator: they are in `out` by then, and a subject nothing asked must not be counted as one
    # that was re-asked.
    carried_keys: set[tuple] = set()
    if rederive:
        # **Re-deriving must never be a way to shorten the table.** A recorded subject the sources
        # could not be asked about this run produces no fresh row at all — the three branches above
        # that deliberately write nothing for an unanswerable subject — and committing that table
        # would overwrite a full one with a shorter one, which is the incident this whole transaction
        # exists for wearing a new flag. Such a subject keeps exactly the rows it had; only an
        # *answered* one (including answered-and-absent, which does write a `not_found` row) replaces.
        fresh_keys = {merge_key(row) for row in out}
        # Only subjects the spec still names. A recorded row for a variant the author has since
        # deleted is dropped by an ordinary run — the assembly loop iterates `subjects` and nothing
        # else — so carrying it forward here would make `--rederive` resurrect rows a plain re-run
        # prunes, which is a second behaviour nobody asked this flag for.
        in_scope = {_subject_key(v) for v in subjects}
        carried: list[str] = []
        still_resolved: set[str] = set()
        for subject_key, recorded in existing.items():
            if subject_key in fresh_keys or subject_key not in in_scope:
                continue
            out.extend(recorded)
            carried_keys.add(subject_key)
            carried.append(recorded[0].variant_key)
            if any(r.chrom is not None for r in recorded):
                still_resolved.add(recorded[0].variant_key)
        unresolved = [k for k in unresolved if k not in still_resolved]
        if carried:
            logger.warning(
                "Re-derivation kept the recorded rows for %d subject(s) no source could be asked "
                "about this run (%s): a re-derivation that dropped them would replace a longer table "
                "with a shorter one, which nothing downstream can tell from a module whose author "
                "resolved less. They are unchanged rather than re-derived, so the report below says "
                "nothing about them.",
                len(carried),
                examples(sorted(carried)),
            )

    # One line for the whole run, grouped by reason and counted. These are not findings about the
    # module — they are the resolver's second spelling of a place the module already names — so a line
    # per variant would be pure volume.
    if par_twins_dropped:
        logger.info(
            "Pseudoautosomal: kept the X spelling of %d locus/loci and left the Y twin out of "
            "resolution.csv (%s). PAR1 and PAR2 are shared between X and Y, so dbSNP maps one rsID to "
            "both, but ClinVar records no PAR variant on Y, gnomAD excludes the Y PAR from its callset, "
            "and standard GRCh38 analysis sets hard-mask it — so the Y row could match nothing. Pass "
            "--keep-par-twin to record both.",
            len(par_twins_dropped),
            ", ".join(f"{rsid} {chrom}:{start}" for rsid, chrom, start in par_twins_dropped),
        )

    # Content-addressed allele identity, stamped after the chain has settled the coordinates (there is
    # nothing to mint from before that). Existing ids are never overwritten.
    # One proxy, one read cache, shared by minting and the reference check below.
    sequences = SequenceProxy(offline=offline)
    mint_result: MintResult | None = None
    if mint_vrs:
        mint_result = mint_resolution_rows(out, minter=VrsMinter(offline=offline, sequences=sequences))
        logger.info(
            "VRS: minted %d id(s) (%d stdlib, %d normalized), %d unmintable, %d already present",
            mint_result.minted,
            mint_result.minted_stdlib,
            mint_result.minted_normalized,
            mint_result.skipped_unmintable,
            mint_result.already_present,
        )
        # The success count alone reads as a clean bill on a table that is half anonymous. Coverage is
        # a WARNING because an identity scheme with an unstated shortfall is the thing a consumer keys
        # on and gets wrong — and it stays a warning (never a refusal) because the usual causes, an
        # indel offline or a build with no refget table, are fixable by no authored edit.
        for line in mint_result.coverage_warnings():
            logger.warning("VRS coverage — %s", line)

    # Validation pass: does the authored data agree with the genome? (Reported, never repaired.)
    ref_check = (
        verify_reference_alleles(out, sequences=sequences, offline=offline)
        if verify_ref
        else RefCheck([], 0, "not_requested")
    )
    ref_mismatches = ref_check.mismatches
    for line in summarize_ref_mismatches(ref_mismatches):
        logger.warning("Reference-allele mismatch — %s", line)

    # Why does the ref disagree? A shifted `start` is one answer and `_read_with_neighbours` already
    # gives it; the other, which no offline check can reach, is that the whole coordinate is on the
    # old assembly. Asked of the mismatched rows **only** — that set is the cost control, and a module
    # whose refs agree makes no request here at all (RM48).
    #
    # The client is a parameter for the reason `resolver`/`gnomad_client` are: a network dependency
    # constructed inside this function cannot be replaced, so a *unit* test of some neighbouring
    # behaviour egresses whether or not it means to, and the suite's opt-in-network rule quietly
    # becomes advisory. Passing `None` still lets the pass build and close its own.
    build = diagnose_wrong_build(ref_mismatches, offline=offline, client=grch37_client)
    if build.not_checked == "skipped_offline":
        logger.info(
            "Wrong-build diagnosis skipped: --offline. The GRCh37 service is the only thing that can "
            "tell an old-assembly coordinate from a wrong ref, and there is no local GRCh37 data."
        )
    if build.sampled:
        logger.warning(
            "Old-assembly diagnosis looked at %d of %d mismatched row(s): a systematic wrong build "
            "gives the same answer on every row, so the pass is bounded rather than paying two paced "
            "requests each. Fix what it names and re-run to see the rest.",
            build.examined,
            build.total,
        )
    for line in summarize_build_diagnoses(build.diagnoses):
        logger.warning("Old-assembly coordinate — %s", line)

    # Second validation pass: does the module's clinical call agree with ClinVar's? Offline-capable
    # (the snapshot is local), and — unlike every other check here — it stays a warning in `strict`
    # too. See `clinical.verify_clin_sig`: escalating would make the format arbitrate a clinical
    # disagreement, and a curator is allowed to disagree with a one-star submission.
    # It is also **skipped when it cannot fail**: a module that declares it was drafted from this very
    # snapshot would be compared against its own source, and reporting "0 conflicts" for a structurally
    # guaranteed result looks like evidence without being any (S4). The skip states its reason rather
    # than quietly returning the same empty list a real pass returns.
    # The skip is a MODE LADDER since RM4, because the module-level skip has a hole in it: a cell
    # edited by hand after the draft is no longer a copy of anything, and no module-level fact can see
    # that. `best_effort` keeps the cheap skip and names the hole; `strict` pays the look-up and
    # reports the split — copied / authored by hand / conflicting — which is what "never a meaningless
    # zero" costs. Deciding per row in both modes was the obvious repair and it re-spends the whole
    # 90% saving, since deciding whether a value is still a copy *is* the look-up.
    clin_sig_conflicts: list[ClinSigConflict] = []
    clin_sig_not_checked: str | None = None
    clin_sig_comparison: ClinSigComparison | None = None
    # Read once for the whole clinical pass, because both the two-way skip and every leg of the
    # concordance record ask the same licence table the same question.
    recorded_sources = read_sources_file(spec_dir)
    # What the comparison was evaluated OVER, for the attestation (RM45). `None` until the look-up
    # runs, and never a zero standing in for it: `ClinSigComparison.compared` is the count the check itself
    # arrived at, and re-deriving one here from `variants` would be the recomputation RM40/RM41 rules
    # out — the two could disagree, and then the manifest's own halves would.
    clin_sig_compared: int | None = None
    # Which closed `VALID_VERIFICATION_SKIPS` key the prose reason above maps onto. Recorded beside the
    # sentence rather than parsed back out of it, which is the whole point of RM45's vocabularies.
    clin_sig_skip: str | None = None
    if not verify_clinsig:
        clin_sig_not_checked = "not_requested"
        clin_sig_skip = "not_requested"
    elif clinvar_ref is None:
        clin_sig_not_checked = "no_snapshot"
        clin_sig_skip = "no_reference"
    else:
        # **No mode branch any more (RM73).** The skip used to be `best_effort`-only, because deciding
        # per row whether a value was still a copy needed exactly the look-up the skip existed to
        # avoid, so `strict` paid for it. `tautology_reason` now recomputes the drafter's digest over
        # the `clin_sig` column and answers that offline, so the skip is sound in both modes and the
        # ladder — along with the per-row audit under it — is gone.
        drafted_from_it = tautology_reason(recorded_sources, clinvar_ref, spec_dir)
        if drafted_from_it is not None:
            clin_sig_not_checked = drafted_from_it
            clin_sig_skip = "tautology"
            logger.info("ClinVar clin_sig cross-check not run: %s.", drafted_from_it)
        else:
            comparison = compare_clin_sig(variants, out, reference=clinvar_ref)
            if comparison is None:
                clin_sig_not_checked = "unusable_snapshot"
                clin_sig_skip = "no_reference"
            else:
                clin_sig_conflicts = comparison.conflicts
                clin_sig_compared = comparison.compared
                clin_sig_comparison = comparison
    for conflict in clin_sig_conflicts:
        logger.warning("ClinVar clin_sig %s — %s", "conflict" if conflict.opposed else "difference", conflict)

    # RM170 — the CIViC refutation leg. Folded in here rather than given its own command for the
    # reason the `clin_sig` leg is: a hand-authored module that never ran `civic_draft` has to meet
    # this somewhere, and `enrich` is the one pass everybody runs. It reads an operator-built snapshot
    # and fetches nothing, so `--offline` does not gate it; a missing snapshot is `no_reference`, which
    # is not a pass (`@unreachable-not-absent`).
    refutation_findings: list[RefutationFinding] = []
    refutation_not_checked: str | None = None
    refutation_skip: str | None = None
    refutation_subjects: int | None = None
    refutation_basis: str | None = None
    civic_ref = resolve_civic_reference(civic_cache)
    refutation = compare_refutations(variants, out, reference=civic_ref)
    if refutation is None:
        refutation_not_checked = "no_snapshot" if civic_ref is None else "unusable_snapshot"
        refutation_skip = "no_reference"
    else:
        refutation_findings = refutation.findings
        refutation_subjects = refutation.subjects
        refutation_basis = refutation.status_basis
    # RM160 — the CIViC citation canary. It sits here rather than in `civic citations` because the
    # question is not *what did the API say today*, it is *has what this module already recorded moved
    # since*: a module can be drafted once and enriched for a year, and only the pass everybody runs
    # will notice. It is a live read, so `--offline` is a real skip; a module that never ran
    # `civic citations` has no recorded status and is `nothing_to_check`, which is not a pass.
    evidence_status = check_evidence_status_currency(
        variants, out, read_studies(spec_dir), reference=civic_ref, offline=offline
    )
    for moved in evidence_status.findings:
        # Warned in both modes, escalated in neither, and the row is left exactly as authored: CIViC
        # re-curating its own evidence is a fact about CIViC (`@a-source-recuring-is-not-a-strict-
        # matter`), and rewriting an authored cell from a live read is the one thing this tier may not
        # do (`@enrichment-is-validation`).
        logger.warning("CIViC %s — %s", moved.code, moved.restate())

    for finding in refutation_findings:
        # Warned in both modes, escalated in neither. The neighbours say so for the same reason
        # (`@clinsig-never-escalates`), and the row is deliberately left exactly as authored: a
        # refutation withholds a claim rather than establishing its opposite, so there is nothing here
        # for the tier to write even if it were allowed to.
        logger.warning("CIViC %s — %s", finding.code, finding.restate())

    # The concordance record (RM130's sidecar, widened to N authorities by RM134 § B). Built from the
    # comparison that already ran rather than from a second pass over the snapshot: re-asking would
    # cost the whole look-up again, and a second implementation of the record-selection rule is a
    # second place for it to drift from the one that decided the conflicts above.
    #
    # It is **computed here and written at the commit**, like every other product of this run. A
    # refused `strict` run must leave the module exactly as it was, and a record written before the
    # gates would survive a refusal.
    clin_sig_record: ConcordanceRecord | None = None
    if verify_clinsig:
        clin_sig_record = clin_sig_concordance(
            variants,
            out,
            reference=clinvar_ref,
            pubmind_reference=pubmind_ref,
            sources=recorded_sources,
            spec_dir=spec_dir,
            checked_at=now_utc_iso(),
            clinvar_comparison=clin_sig_comparison,
        )
    for line in concordance_sentences(clin_sig_record):
        # Warned in BOTH modes and escalated in neither (`@clinsig-never-escalates`), with more force
        # here than for ClinVar alone: a disagreement with a literature miner's aggregate is a
        # statement about that extraction's limits at least as often as about the module. `discordant`
        # is a fact about the field, not a defect in the module, and gating on it would have the
        # format arbitrate a clinical dispute.
        logger.warning("clin_sig concordance — %s", line)
    for line in concordance_notes(clin_sig_record):
        # INFO, because none of these is a finding about the module: an authority nobody could ask,
        # and one this module's own rows were drafted from. Said out loud all the same — a leg that
        # silently did not run reads as a leg that found nothing.
        #
        # Skipping a line the two-way check has already said, matched on the sentence rather than on
        # a skip key: `clin_sig_not_checked` carries the ClinVar tautology's exact prose and so does
        # that leg's `reason`, since both come from `tautology_reason`. Comparing the strings means a
        # reworded sentence stays deduped, where keying on `clin_sig_skip` would silently start
        # printing both the day either wording moved.
        if line == clin_sig_not_checked:
            continue
        logger.info("clin_sig concordance — %s", line)

    # RM151's half of the RM117 pair: not *is this subject still contested* — the compiler answers
    # that from the record alone — but *is the disagreement the author answered still the one on
    # record*. It needs the archive's value now against its value at record time, and the only
    # baseline this format keeps is the previous run's `clin_sig_authority_calls.csv`. So it is read
    # HERE, before the commit rewrites it, and it is the last thing this pass can still ask.
    #
    # Silent on every module with no overlay answers, which is every module today.
    answered_calls: AnsweredCallReport | None = None
    if verify_clinsig:
        answered_calls = answered_call_shift(
            spec_dir, clin_sig_record.calls if clin_sig_record is not None else None
        )
        for line in answered_call_sentences(answered_calls):
            # Warned in both modes and escalated in neither, with more force than the concordance
            # record itself: nothing here is a disagreement, it is a note that the record an author
            # reasoned over was rewritten underneath their reasoning. Gating a build on it would
            # make an artifact refuse over an archive's release schedule.
            logger.warning("clin_sig answers — %s", line)
        for line in answered_call_notes(answered_calls):
            # A comparison that quietly did not run reads as one that found nothing, which is the
            # failure the whole tri-state exists to prevent.
            logger.info("clin_sig answers — %s", line)

    # Third validation pass: is the rsID a module keys on still the one dbSNP serves? Needs the live
    # API (NCBI is the oracle — Ensembl 400s on some merges), so `--offline` skips it. The verdict is
    # STAMPED onto the rows' provenance columns and reported; the authored label is never replaced,
    # because doing so would migrate `variant_key` by network lookup. See `identifiers.check_rsids`.
    stale_rsids: list[RsidStatus] = []
    rsid_subjects = 0
    if verify_rsids and not offline:
        asked = sorted({r.rsid for r in out if r.rsid})
        rsid_subjects = len(asked)
        try:
            statuses = check_rsids(asked)
        except IdentifierUnavailable as exc:
            # The same rule as the gnomAD block above, and it had no handler at all (RM97): this is a
            # *validation* pass that runs after every other pass has finished and before
            # `resolution.csv` is written, so letting NCBI's availability abort the run throws away
            # work that already succeeded. Until RM97 the escaping type was a raw `httpx` exception
            # rather than even `EutilsError`, so nothing up the stack could have caught it either.
            #
            # `IdentifierUnavailable` since RM101, and the walk from `httpx.HTTPStatusError` to
            # `EutilsError` to here is the whole item in one handler: each step moved the type one
            # layer closer to the thing the caller actually called. `check_rsids` is `identifiers`'
            # function, so `EutilsError` — another module's client — was never the type this line
            # should have named, and it only worked because the pass let it through untranslated.
            #
            # Withholding is the correct outcome, not a fallback: `rsid_status` stays unset on every
            # row, which says *nobody asked dbSNP*. Stamping `absent` here would assert a negative the
            # run never established — `@unreachable-not-absent`, one column over.
            logger.warning("dbSNP rsID check failed (%s); continuing without rsID verdicts.", exc)
            statuses = []
        by_rsid = {s.rsid: s for s in statuses}
        for row in out:
            status = by_rsid.get(row.rsid or "")
            if status is not None:
                row.rsid_status = status.state
                row.rsid_current = status.current
        stale_rsids = [s for s in statuses if not s.is_current]
        for status in stale_rsids:
            logger.warning("Stale rsID — %s", status)
    elif verify_rsids:
        logger.info("rsID currency check skipped: --offline (dbSNP has no offline merge table).")

    # Fourth validation pass: for a row that authored both an rsID and a coordinate, does the pair
    # agree with the reference? This is the enricher's half of a question the compiler also asks —
    # `resolution._verify` puts it over the injected table, this one puts it against the snapshot the
    # chain already opened — so there is one question, two tiers and one attestation name.
    #
    # A warning in BOTH modes, and the difference from the compiler's half is not an oversight. There,
    # the authored value wins and the table's position is lost on a reverse, so a contradiction is an
    # instability in the artifact; here nothing is dropped or rewritten and the likely causes — a dbSNP
    # merge, a coordinate from another build — are not cleared by any authored edit this run can name
    # (P5, the `not_covered` class).
    #
    # One consequence worth naming, because the sibling passes have to work for it: there is **no
    # severity gate reading this**, so nothing can disagree with the record. `pair_check` is the run's
    # only reading of the question — the log line, `EnrichmentResult.rsid_coordinates` and the
    # attestation are all built from that one object — where a check with a `strict` refusal has two
    # readers that can drift apart, and then a `--strict` run refuses over a set its own
    # `verification.json` does not describe.
    pair_check = _check_authored_pairs(
        verify_pairs,
        rsid_to_loci,
        genome_build=genome_build,
        reference=reference,
        offline=offline,
        unusable=snapshot_unusable,
        # The author's recorded answers, read-only (RM136). The compiler applies the overlay before
        # any check reads a row; this is the enricher doing the same for the one finding an overlay
        # row can actually answer, so a correction stops coming back on every run.
        answered=overlay_answers(spec_dir, "resolution.csv"),
    )
    if pair_check.disagreements:
        # One line for the run, naming them, on the `unreachable_rsids` model: a line per row would be
        # one per variant on a fully coordinate-authored panel.
        logger.warning(
            "rsid↔coordinate disagreement — %d of %d authored pair(s) name a coordinate the injected "
            "Ensembl snapshot does not give for that rsID: %s Reported, never repaired: which half is "
            "wrong is not knowable here.",
            len(pair_check.disagreements),
            pair_check.subjects,
            " ".join(pair_check.disagreements),
        )
    if pair_check.answered:
        # Counted, never silent: the module and the source still differ here, and a run that said
        # nothing at all would report a cleaner module than there is. What the author gets is the
        # acknowledgement that was missing — the correction is recorded and honoured, not ignored.
        logger.info(
            "rsid↔coordinate: %d authored pair(s) disagree with the snapshot and are already answered "
            "in overrides.csv, so they are counted rather than reported again. The overlay is applied "
            "at compile, so the artifact carries your value; delete the overlay row to see the finding "
            "again.",
            pair_check.answered,
        )
    if pair_check.unknown:
        logger.info(
            "rsid↔coordinate: %d authored pair(s) were not compared — the injected Ensembl snapshot "
            "carries no record for %s. Not in the snapshot is not 'not in Ensembl'; the pair is "
            "unchecked rather than disagreeing.",
            len(pair_check.unknown),
            examples(sorted(set(pair_check.unknown))),
        )
    if pair_check.undecided:
        logger.info(
            "rsid↔coordinate: %d authored pair(s) could not be decided — %s name an indel, and one "
            "deletion has several valid spellings whose anchors sit a base or two apart (RM31), so a "
            "differing position is not a contradiction. Undecided, never reported as a disagreement.",
            len(pair_check.undecided),
            examples(sorted(set(pair_check.undecided))),
        )

    # Which licensed source each link speaks for (RM33). **Derived, never fetched** — read off the
    # row's own `source` — and filled only where empty, so a hand-written authority survives exactly as
    # a hand-written `vrs_id` does. A link with no mapping (`authored`, `reversed`, `manual`) keeps
    # `None`, which is the answer rather than a gap: there is no external source to declare.
    for row in out:
        if row.authority is None:
            row.authority = resolution_authority(row.source)

    out.sort(key=lambda r: (r.variant_key, r.locus_index))

    # The drift canary, and it fires only where a baseline exists. `rm` plus a re-run destroys the old
    # values before the fresh ones arrive, so nothing holds both sides and that path re-derives
    # silently and correctly; here the recorded table is still in memory and the fresh one has not
    # been committed, so the comparison costs nothing. `None` when nobody re-derived — an empty list
    # means every recorded subject was re-asked and every one still answers the same, which is a very
    # different statement and the only one of the two that is a clean bill.
    rederived: list[SubjectDrift] | None = None
    if rederive:
        rederived, compared = _rederived_drift(existing, out, skip=carried_keys)
        if rederived:
            # The denominator travels with the finding: "3 subjects moved" is unreadable without the
            # number re-asked. Nothing is printed when nothing moved — a comparison whose empty result
            # is the normal case must not announce a zero as though it were evidence.
            logger.warning(
                "Re-derivation: %d of %d re-asked subject(s) now answer differently from the "
                "recorded table — %s. The fresh answer is committed and the old one is not kept; a "
                "value you decided rather than derived belongs in overrides.csv, where re-deriving "
                "cannot reach it.",
                len(rederived),
                compared,
                "; ".join(str(d) for d in rederived),
            )

    # Fifth validation pass, and the only one whose subject is a claim the module makes about its own
    # provenance rather than about a variant (RM85). Read off `sources.csv` **as it stands** — the
    # licence rows this run writes are at the resolution layer and carry no `dataset`, so nothing here
    # is comparing the module against something this same run just derived. That is the trap next
    # door: a check satisfied by the value it is checking agrees with itself, which is how a
    # re-derivation once reported a clean bill for exactly the subjects it had rewritten.
    dataset_currency: CurrencyCheck | None = None
    if verify_datasets:
        dataset_currency = check_dataset_currency(
            read_sources_file(spec_dir), probes=release_probes, offline=offline
        )
        if dataset_currency.behind:
            # One sentence for the run, aggregated by reason; warned in BOTH modes, with `strict`'s
            # refusal below over the same set. It comes first so the sentence an author reads is the
            # same one either way.
            logger.warning(
                "Dataset currency: %s. Re-draft from the current release to move the label, and "
                "consider --rederive to see whether any answer actually changed.",
                summarize_currency(dataset_currency)[0],
            )
        for line in unchecked_sentences(dataset_currency):
            # INFO, not WARNING, and the level is the judgement: this is not a finding about the
            # module, and an offline run of any drafted module would otherwise carry a warning on
            # every pass — which is how a channel stops being read. Said out loud all the same,
            # because silence here would read as "checked, all clear" (S4).
            logger.info("Dataset currency: %s — unchecked is not up to date.", line)
        if dataset_currency.not_checked is not None:
            logger.info(
                "Dataset currency: not checked (%s). No source was asked which release it publishes, "
                "so every recorded dataset is unchecked rather than current.",
                dataset_currency.not_checked,
            )

    sources = sorted({r.source for r in out if r.source})
    result = EnrichmentResult(
        rows=out,
        unresolved=sorted(set(unresolved)),
        sources=sources,
        mode=mode,
        ref_mismatches=ref_mismatches,
        clin_sig_conflicts=clin_sig_conflicts,
        clin_sig_not_checked=clin_sig_not_checked,
        clin_sig_comparison=clin_sig_comparison,
        refutation_findings=refutation_findings,
        refutation_not_checked=refutation_not_checked,
        evidence_status=evidence_status,
        build_diagnoses=build.diagnoses,
        build_not_diagnosed=build.not_checked,
        stale_rsids=stale_rsids,
        par_twins_dropped=sorted(par_twins_dropped),
        vrs=mint_result,
        unreachable_rsids=sorted(unreachable_rsids),
        unconsulted_rsids=sorted(unconsulted_rsids),
        allele_mismatches=allele_mismatches,
        rsid_coordinates=pair_check,
        rederived=rederived,
        dataset_currency=dataset_currency,
        clin_sig_record=clin_sig_record,
        answered_calls=answered_calls,
    )

    if unreachable_rsids:
        # Warned in BOTH modes, and not escalated by `strict`: nothing an author can edit clears a
        # failed request, and `strict` means "reproducible artifact" (P5). What it does change is the
        # reading of the run — an unresolved key here may well resolve on the next one.
        logger.warning(
            "%d rsID(s) could not be asked of live Ensembl (the request failed, so the answer is "
            "unchecked rather than empty): %s. Re-run before treating these as rsIDs Ensembl does "
            "not have.",
            len(unreachable_rsids),
            ", ".join(sorted(unreachable_rsids)),
        )

    if allele_mismatches:
        # **One aggregated line, not one per subject** — the rule this repo has needed four times, and
        # the per-locus warnings above already say which locus was dropped and why. What this adds is
        # the reading of the run: these rsIDs are ones the source HAS, so an author who greps for
        # `not_found` and concludes "the source has never heard of these" is being misled by the row.
        # Warned in BOTH modes: `strict` already refuses on `unresolved`, and in `best_effort` this is
        # the line that stops the author debugging the wrong question.
        flipped = [m for m in allele_mismatches if m.strand_flip]
        logger.warning(
            "%d rsID(s) resolved to a locus the authored genotype cannot host, so they are recorded "
            "as unresolved: %s. The source HAS these variants — what did not match is the alleles, "
            "so this is not an rsID the source lacks.%s",
            len(allele_mismatches),
            ", ".join(sorted(m.rsid for m in allele_mismatches)),
            (
                f" {len(flipped)} of them fit on the other strand ("
                + ", ".join(sorted(m.rsid for m in flipped))
                + "), which is what a supplementary table published against an older assembly "
                "usually carries: check the strand your alleles are written on."
            )
            if flipped
            else "",
        )

    if unconsulted_rsids:
        # Warned in BOTH modes, like its neighbour above and for the same reason: nothing an author
        # can edit makes a cache appear, and `strict` already refuses the run on `unresolved`. What
        # this line adds is the *why*, which is the whole of RM98 — before it, these keys silently
        # acquired a `not_found` row naming a cache nobody opened, and an author reading the artifact
        # would have concluded that Ensembl does not have their rsID.
        logger.warning(
            "%d rsID(s) were not asked of any source: no Ensembl or ClinVar cache is present and "
            "every live link is disabled%s, so no row is written for them — their absence from "
            "resolution.csv means unchecked, never 'the source does not have it'. %s. Provision a "
            "cache with `just-dna-enricher cache pull`, or re-run without --offline.",
            len(unconsulted_rsids),
            " (--offline)" if offline else "",
            ", ".join(sorted(unconsulted_rsids)),
        )

    if mode == "strict" and ref_mismatches:
        # Deliberately checked BEFORE the unresolved gate: a wrong `ref` is a worse diagnosis than a
        # missing position (it can mint a well-formed id for the wrong allele), so it should be the
        # error the author sees first.
        # The build diagnosis travels **inside** the refusal, not beside it. It is computed above in
        # both modes, and a `strict` run raises here and returns nothing — so a diagnosis left on the
        # result object would be visible only to the mode that does not need it, and invisible to the
        # one whose whole output is this sentence.
        because = " " + "; ".join(summarize_build_diagnoses(build.diagnoses)) + "." if build.diagnoses else ""
        raise EnrichmentError(
            f"strict enrichment: {len(ref_mismatches)} row(s) disagree with the {genome_build} "
            f"reference sequence. "
            + "; ".join(summarize_ref_mismatches(ref_mismatches))
            + "."
            + because
            + " Fix the authored coordinates (a shifted position, or a wrong ref length, silently "
            "mints a different allele id), or enrich with mode='best_effort' to record them as "
            "warnings."
        )

    withdrawn = [s for s in result.stale_rsids if s.is_fatal]
    if withdrawn:
        # Fatal in BOTH modes, unlike every other rsID finding — see `RsidStatus.is_fatal`. Never
        # produced by the automated check; this fires on a curator-recorded retraction.
        raise EnrichmentError(
            f"{len(withdrawn)} authored rsID(s) have been WITHDRAWN from dbSNP: "
            f"{[str(s) for s in withdrawn]}. A retracted variant may leave the annotation describing "
            f"nothing, so this refuses in best_effort too — re-key onto a coordinate, or remove the row."
        )

    if mode == "strict" and result.stale_rsids:
        # Checked after the ref/allele gates and before the unresolved one: a stale label is a real
        # defect but a milder diagnosis than a row contradicting the genome. Not escalated beyond
        # strict, because `absent` has benign causes too (a very new rsID, or API lag).
        raise EnrichmentError(
            f"strict enrichment: {len(result.stale_rsids)} authored rsID(s) are no longer current in "
            f"dbSNP: {[str(s) for s in result.stale_rsids]}. An all-or-nothing artifact should not be "
            f"built on an identifier its own source has retired — fix the identifier in variants.csv, "
            f"or author the coordinate instead (a VRS allele id cannot drift). Use "
            f"mode='best_effort' to record these as warnings."
        )

    if mode == "strict" and result.unresolved:
        raise EnrichmentError(
            f"strict enrichment: {len(result.unresolved)} variant(s) unresolved after the chain "
            f"(cache/Ensembl): {result.unresolved}. Provide a complete cache/online access, add the "
            f"loci by hand to resolution.csv, or enrich with mode='best_effort'."
        )

    if mode == "strict" and dataset_currency is not None and dataset_currency.behind:
        # Last of the gates, because it is the mildest diagnosis of the five: nothing here contradicts
        # the genome or leaves a variant unplaced, it says the module is describing an older release
        # than the one its source serves today.
        #
        # **Over `behind` alone**, never over the unchecked legs. An unreachable source and an
        # `--offline` run both leave every leg unchecked, and refusing on those would make `--offline
        # --strict` impossible forever over something no author can edit — the `unreachable_rsids`
        # rule, which warns in both modes and escalates in neither.
        superseded = dataset_currency.behind
        raise EnrichmentError(
            f"strict enrichment: {len(superseded)} of {dataset_currency.subjects} recorded "
            f"release(s) have been superseded — "
            + "; ".join(str(c) for c in superseded)
            + ". An all-or-nothing artifact should not silently describe a release its source has "
            "moved past: re-draft from the current one (which rewrites `sources.csv`'s dataset), or "
            "enrich with mode='best_effort' to record this as a warning. `--rederive` is the next "
            "question — whether any answer actually changed — and `--no-verify-datasets` turns this "
            "check off."
        )

    # ── the commit ─────────────────────────────────────────────────────────────────────────────
    # Everything above this line is staging. Every refusal above raises before it, which is what makes
    # *a refused strict run changes nothing* a promise rather than an accident of statement order —
    # and it is asserted on the bytes on disk by test, not on a return value.
    if write:
        # The licence rows land inside the table's commit (S98, RM231): `enrich()` was the only pass
        # that consulted sources and recorded none — the reason `VALID_SOURCE_LAYERS` reserves a
        # `"resolution"` member nothing ever wrote. Keyed on the authority rather than the link, so
        # the row joins `sources.csv` (RM33).
        _write_resolution_csv(
            out,
            resolution_path,
            before_commit=lambda: record_source_terms(
                {row.authority for row in out if row.authority},
                "resolution",
                spec_dir,
                error=EnrichmentError,
            ),
        )
        if clin_sig_record is not None:
            # Rewritten whole rather than merged: a subject the authorities stopped contesting has to
            # *leave* the record, since a conflict that stops being reported is how an author learns
            # the archive caught up with them. A run where nobody could be consulted returns `None`
            # above and writes nothing, so a previous run's record survives a run that could not
            # replace it.
            write_concordance_tables(spec_dir, clin_sig_record.parents, clin_sig_record.calls)
        # The attestation (RM45), written once for the whole run — the proof-of-work binds the
        # document, so recording per check would pay it once per check for one guarantee. It goes after
        # `resolution.csv` and before the licence rows for no reason but reading order; the binding is
        # over the **authored** files, which none of these writes touch.
        record_verification(
            _verification_records(
                offline=offline,
                verify_ref=verify_ref,
                ref_check=ref_check,
                build=build,
                verify_clinsig=verify_clinsig,
                clin_sig_compared=clin_sig_compared,
                clin_sig_conflicts=clin_sig_conflicts,
                clin_sig_skip=clin_sig_skip,
                clin_sig_detail=clin_sig_not_checked,
                clinvar_ref=clinvar_ref,
                refutation_findings=refutation_findings,
                refutation_subjects=refutation_subjects,
                refutation_skip=refutation_skip,
                refutation_detail=refutation_not_checked,
                refutation_basis=refutation_basis,
                evidence_status=evidence_status,
                civic_ref=civic_ref,
                verify_rsids=verify_rsids,
                rsid_subjects=rsid_subjects,
                stale_rsids=stale_rsids,
                pairs=pair_check,
                ensembl_ref=reference,
                currency=dataset_currency,
            ),
            spec_dir,
            error=EnrichmentError,
        )
        # Committed, so the staged answers have served their purpose. Kept only on request, and the
        # request says where they are — a debugging aid nobody can find is not one.
        if keep_staging:
            logger.info(
                "keep_staging: the staged answers this run resolved are left at %s. They are read by "
                "the next run of this spec directory, so delete them once you are done reading them.",
                journal.path,
            )
        else:
            journal.discard()
    return result

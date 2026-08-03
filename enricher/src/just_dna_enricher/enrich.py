"""`enrich` — fill the source-independent resolution table for a module spec, then hand off to compile.

The resolver chain, first-hit-wins: an existing/human-authored row (authoritative, never clobbered) →
the local cache (a downloaded snapshot, offline) → live Ensembl (V2 GraphQL → V1 REST). It writes
`resolution.csv` beside the spec; the compiler then consumes it with no source knowledge and no
network. Two modes: `best_effort` fills what it can and records the rest as `not_found`; `strict`
fails unless every in-scope variant resolves to a position (the network analogue of the compiler's
`strict=True`). `--offline` clamps the chain to the cache alone (guaranteed zero egress).
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import _load_csv_rows
from just_dna_compiler.resolution import hosting_verdict
from just_dna_format.base import derive_variant_key
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher import clinvar
from just_dna_enricher.clinical import ClinSigConflict, verify_clin_sig
from just_dna_enricher.download import ensure_clinvar_snapshot, ensure_snapshot
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.identifiers import RsidStatus, check_rsids
from just_dna_enricher.gnomad import GnomadClient, GnomadError
from just_dna_enricher.licensing import record_source_terms, resolution_authority
from just_dna_enricher.locations import resolve_clinvar_reference, resolve_ensembl_reference
from just_dna_enricher.resolver import lookup_loci
from just_dna_enricher.sequences import RefMismatch, SequenceProxy, verify_reference_alleles
from just_dna_enricher.vrs import VrsMinter, mint_resolution_rows

logger = logging.getLogger(__name__)

_FIELDNAMES = [
    "variant_key", "rsid", "chrom", "start", "ref", "alts",
    "genome_build", "locus_index", "vrs_id", "vrs_spec", "caid",
    "source", "authority", "status", "rsid_alternates", "rsid_current", "rsid_status", "fetched_at",
]


@dataclass(frozen=True)
class _Subject:
    """One row asking for a coordinate, normalized across the tables allowed to ask.

    Resolution used to read `variants.csv` alone, so a PGx module — which by design carries **no**
    `variants.csv` (one CSV = one concern) — enriched to an empty `resolution.csv` and shipped with no
    coordinates at all. The chain itself was never variant-specific; only its input was. Normalizing
    to a subject lets `pharm_variants.csv` and `haplotypes.csv` through the *unchanged* resolver,
    caches, ordering and back-fill.

    `constraint` is whatever the row knows about which alleles must be present at the locus, fed to
    the shared `hosting_verdict` predicate so a one-to-many rsID drops the loci the row cannot be
    about (and reports, rather than drops, the ones it cannot decide):

    - a `VariantRow`/`PharmVariantRow` supplies its **genotype** (`C/T`);
    - a `HaplotypeRow` supplies its single defining **allele** (`G`) — the same membership question
      asked of one allele instead of two, which is why it reuses the same predicate rather than a
      parallel one;
    - `None` (a `PharmVariantRow` with no authored genotype) constrains nothing and keeps every locus.
    """

    variant_key: str
    rsid: Optional[str]
    chrom: Optional[str]
    start: Optional[int]
    ref: Optional[str]
    alts: Optional[str]
    constraint: Optional[str]
    origin: str


def _subject_of_variant(v: VariantRow) -> _Subject:
    key = v.variant_key or derive_variant_key(v.rsid, v.chrom, v.start, v.ref, v.alts)
    return _Subject(key, v.rsid, v.chrom, v.start, v.ref, v.alts, v.genotype, "variants.csv")


def _collect_subjects(spec_dir: Path, variants: list[VariantRow]) -> list[_Subject]:
    """Every row in the spec that needs a coordinate, `variants.csv` first, deduped by `variant_key`.

    Order and precedence are load-bearing. `variants.csv` goes first so that when the same variant is
    named by two tables, the SNP row wins — it is the only one carrying `alts`, which is a resolution
    *fact* and therefore decides the compiled bytes. Letting a PGx row win would move an already
    compiled module's `artifact.digest`, the same hazard the link ordering in the chain below exists
    to avoid. Within that, first occurrence wins, so the emitted order is the authored order.

    The PGx tables key **without** `alts` (`PharmVariantRow.variant_key` is that property, and a
    `HaplotypeRow` key is derived the same way): a pharm annotation or a haplotype junction matches a
    variant at `chrom:start:ref` regardless of allele. Mixing that up would mint a VRS allele id for a
    row that never named an allele.
    """
    subjects: list[_Subject] = [_subject_of_variant(v) for v in variants]

    pharm_path = spec_dir / "pharm_variants.csv"
    if pharm_path.exists():
        rows, errors, _ = _load_csv_rows(pharm_path, PharmVariantRow, "pharm_variants.csv")
        if errors:
            raise EnrichmentError(f"pharm_variants.csv is invalid: {errors[0]}")
        subjects.extend(
            _Subject(r.variant_key, r.rsid, r.chrom, r.start, r.ref, None, r.genotype,
                     "pharm_variants.csv")
            for r in rows
        )

    hap_path = spec_dir / "haplotypes.csv"
    if hap_path.exists():
        rows, errors, _ = _load_csv_rows(hap_path, HaplotypeRow, "haplotypes.csv")
        if errors:
            raise EnrichmentError(f"haplotypes.csv is invalid: {errors[0]}")
        subjects.extend(
            _Subject(derive_variant_key(r.rsid, r.chrom, r.start, r.ref),
                     r.rsid, r.chrom, r.start, r.ref, None, r.allele, "haplotypes.csv")
            for r in rows
        )

    deduped: dict[str, _Subject] = {}
    for s in subjects:
        deduped.setdefault(s.variant_key, s)
    return list(deduped.values())


def _authored_alt(v: _Subject) -> Optional[str]:
    """The single authored ALT for allele-aware reverse resolution, or None when absent or
    multi-allelic (fall back to position/ref-level matching, which may resolve as ambiguous)."""
    if v.alts and "," not in v.alts:
        return v.alts
    return None


class EnrichmentError(RuntimeError):
    """Raised in strict mode when the chain cannot fully resolve the module."""


@dataclass
class EnrichmentResult:
    rows: list[ResolutionRow]
    unresolved: list[str] = field(default_factory=list)  # variant_keys with no resolved position
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    # Authored data that disagrees with the reference genome. Reported, never repaired — see
    # `sequences.verify_reference_alleles`. Empty when the check could not run (offline).
    ref_mismatches: list[RefMismatch] = field(default_factory=list)
    # Authored `clin_sig` values ClinVar's own records do not support. Warnings in BOTH modes on
    # purpose — see `clinical.verify_clin_sig`. Empty when no snapshot was provisioned.
    clin_sig_conflicts: list[ClinSigConflict] = field(default_factory=list)
    # Authored rsIDs dbSNP has merged away or has no record of. Recorded onto the rows' provenance
    # columns and reported; never substituted — see `identifiers.check_rsids`.
    stale_rsids: list[RsidStatus] = field(default_factory=list)

    @property
    def fully_resolved(self) -> bool:
        return not self.unresolved


def enrich(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    ensembl_cache: Optional[Path] = None,
    clinvar_cache: Optional[Path] = None,
    use_clinvar: bool = True,
    use_gnomad: bool = True,
    download: bool = True,
    genome_build: str = "GRCh38",
    write: bool = True,
    mint_vrs: bool = True,
    verify_ref: bool = True,
    verify_clinsig: bool = True,
    verify_rsids: bool = True,
    resolver: Optional[EnsemblResolver] = None,
    gnomad_client: Optional["GnomadClient"] = None,
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

    `verify_clinsig` compares each authored `clin_sig` against the ClinVar snapshot's own. It is
    offline-capable (the snapshot is local) and is the **one check whose severity does not follow the
    mode**: it warns in `strict` too, because failing a compile would make the format arbitrate a
    clinical disagreement. See `clinical.verify_clin_sig` for the full argument.
    """
    spec_dir = Path(spec_dir)
    variants: list[VariantRow] = []
    variants_path = spec_dir / "variants.csv"
    if variants_path.exists():
        variants, errors, _ = _load_csv_rows(variants_path, VariantRow, "variants.csv")
        if errors:
            raise EnrichmentError(f"variants.csv is invalid: {errors[0]}")

    # Existing/human rows are authoritative — merge, never clobber.
    existing: dict[str, list[ResolutionRow]] = {}
    resolution_path = spec_dir / "resolution.csv"
    if resolution_path.exists():
        rows, errors, _ = _load_csv_rows(resolution_path, ResolutionRow, "resolution.csv")
        if errors:
            raise EnrichmentError(f"existing resolution.csv is invalid: {errors[0]}")
        for row in rows:
            existing.setdefault(row.variant_key, []).append(row)

    if genome_build != genome_build.strip() or genome_build != "GRCh38":
        logger.warning("Enrichment is GRCh38-bound; genome_build=%r resolves nothing (RM15).", genome_build)

    # Every table that can ask for a coordinate, not just variants.csv (a PGx module has none).
    subjects = _collect_subjects(spec_dir, variants)

    # Partition the subjects that still need work (skip those an existing row already covers).
    need_pos = [
        v for v in subjects
        if v.rsid is not None and v.chrom is None and v.variant_key not in existing
    ]
    need_rsid = [
        v for v in subjects
        if v.rsid is None and v.chrom is not None and v.variant_key not in existing
    ]

    rsid_to_loci: dict[str, list[dict]] = {}
    source_of_rsid: dict[str, str] = {}
    # Reverse (position→rsid) back-fill is allele-aware and keeps ALL candidates per authored allele,
    # so we can take a deterministic pick and flag a genuine multi-rsid allele as ambiguous rather than
    # guessing an allele-blind label (which was the mis-attribution / reverse-round-trip drift).
    rev_candidates: dict[tuple, list[str]] = {}  # (chrom,start,ref,alt) -> sorted candidate rsids
    rev_source: dict[tuple, str] = {}            # which link produced the candidates
    positions = [(v.chrom, v.start, v.ref, _authored_alt(v)) for v in need_rsid]

    # ── Ensembl cache link (offline, first) ────────────────────────────────────────────────────
    reference = resolve_ensembl_reference(ensembl_cache)
    if reference is None and not offline and download:
        try:
            ensure_snapshot(ensembl_cache)
            reference = resolve_ensembl_reference(ensembl_cache)
        except Exception as exc:  # provisioning is best-effort; degrade to live/offline
            logger.warning("Snapshot provisioning failed (%s); continuing without cache.", exc)
    if reference is not None and (need_pos or need_rsid) and genome_build == "GRCh38":
        rsids = [v.rsid for v in need_pos if v.rsid]
        rsid_to_loci, pos_candidates, _ = lookup_loci(reference, rsids, positions)
        for rsid in rsid_to_loci:
            source_of_rsid[rsid] = "cache"
        for pt, cands in pos_candidates.items():
            if cands:
                rev_candidates[pt] = cands
                rev_source[pt] = "cache"

    # ── ClinVar cache link (offline, after Ensembl cache, before live) ─────────────────────────
    # Fills only what the Ensembl cache missed, stamping source="clinvar". Placing it after the
    # Ensembl cache keeps a both-caches variant on source="cache"/Ensembl `alts`, so no compiled
    # module's artifact.digest moves. Offline uses a local ClinVar cache only (no download).
    # Located once rather than inside the link, because the clin_sig cross-check below needs the same
    # snapshot even when every variant is already resolved and the link itself has nothing to do.
    clinvar_ref: Optional[Path] = None
    if (use_clinvar or verify_clinsig) and genome_build == "GRCh38":
        clinvar_ref = resolve_clinvar_reference(clinvar_cache)
        if clinvar_ref is None and not offline and download:
            try:
                ensure_clinvar_snapshot(clinvar_cache)
                clinvar_ref = resolve_clinvar_reference(clinvar_cache)
            except Exception as exc:  # provisioning is best-effort; degrade to live/offline
                logger.warning("ClinVar snapshot provisioning failed (%s); continuing without it.", exc)

    if use_clinvar and genome_build == "GRCh38" and (need_pos or need_rsid):
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
                        clinvar_ref, exc,
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

    # ── live Ensembl link (V2→V1), for cache misses, unless offline ────────────────────────────
    if not offline and genome_build == "GRCh38":
        missing = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
        if missing:
            owned = resolver is None
            client = resolver or EnsemblResolver()
            try:
                for rsid in missing:
                    loci, src = client.resolve_rsid(rsid)
                    if loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = src or "ensembl"
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
    if use_gnomad and not offline and genome_build == "GRCh38":
        missing = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
        if missing:
            owned = gnomad_client is None
            client = gnomad_client or GnomadClient()
            try:
                for rsid, loci in client.resolve_rsids(missing).items():
                    if loci and rsid not in rsid_to_loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = "gnomad"
            except GnomadError as exc:  # a last-resort link must not sink the whole enrichment
                logger.warning("gnomAD link failed (%s); continuing without it.", exc)
            finally:
                if owned:
                    client.close()

    # ── assemble the table (a row for every subject; expansion → N rows) ───────────────────────
    out: list[ResolutionRow] = []
    unresolved: list[str] = []
    for v in subjects:
        key = v.variant_key
        if key in existing:
            out.extend(existing[key])
            if not any(r.chrom is not None for r in existing[key]):
                unresolved.append(key)
            continue
        if v.rsid is not None and v.chrom is None:
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
                    True if v.constraint is None
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
                    logger.warning(
                        "%s: whether %s:%s %s>%s can host the authored %s %s could not be decided from "
                        "the allele strings — the two spellings describe events of the same size but "
                        "different content, so it is either one indel re-anchored inside a repeat or two "
                        "different variants. The locus is KEPT; check it against the reference.",
                        v.rsid, lo.get("chrom"), lo.get("start"), lo.get("ref"), lo.get("alts"),
                        subject, v.constraint,
                    )
                elif verdict is False:
                    logger.warning(
                        "%s: %s:%s %s>%s cannot host the authored %s %s, and is left out of "
                        "resolution.csv. The event sizes differ, which re-anchoring cannot change, so "
                        "this is a different variant sharing the rsID rather than another spelling.",
                        v.rsid, lo.get("chrom"), lo.get("start"), lo.get("ref"), lo.get("alts"),
                        subject, v.constraint,
                    )
            if loci:
                src = source_of_rsid.get(v.rsid, "cache")
                for i, locus in enumerate(loci):
                    out.append(ResolutionRow(
                        variant_key=key, rsid=v.rsid, genome_build=genome_build,
                        locus_index=i, source=src, status="resolved", **locus,
                    ))
            else:
                out.append(ResolutionRow(variant_key=key, rsid=v.rsid, genome_build=genome_build,
                                         source="ensembl" if not offline else "cache", status="not_found"))
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
            out.append(ResolutionRow(
                variant_key=key, rsid=rsid, chrom=v.chrom, start=v.start, ref=v.ref, alts=v.alts,
                genome_build=genome_build, source=src, status=status, rsid_alternates=alternates,
            ))
        else:
            # already complete, or has a position — a full record, nothing to resolve
            out.append(ResolutionRow(
                variant_key=key, rsid=v.rsid, chrom=v.chrom, start=v.start, ref=v.ref, alts=v.alts,
                genome_build=genome_build, source="authored", status="resolved",
            ))

    # Content-addressed allele identity, stamped after the chain has settled the coordinates (there is
    # nothing to mint from before that). Existing ids are never overwritten.
    # One proxy, one read cache, shared by minting and the reference check below.
    sequences = SequenceProxy(offline=offline)
    if mint_vrs:
        mint_result = mint_resolution_rows(
            out, minter=VrsMinter(offline=offline, sequences=sequences)
        )
        logger.info(
            "VRS: minted %d id(s) (%d stdlib, %d normalized), %d unmintable, %d already present",
            mint_result.minted, mint_result.minted_stdlib, mint_result.minted_normalized,
            mint_result.skipped_unmintable, mint_result.already_present,
        )

    # Validation pass: does the authored data agree with the genome? (Reported, never repaired.)
    ref_mismatches = (
        verify_reference_alleles(out, sequences=sequences, offline=offline) if verify_ref else []
    )
    for mismatch in ref_mismatches:
        logger.warning("Reference-allele mismatch — %s", mismatch)

    # Second validation pass: does the module's clinical call agree with ClinVar's? Offline-capable
    # (the snapshot is local), and — unlike every other check here — it stays a warning in `strict`
    # too. See `clinical.verify_clin_sig`: escalating would make the format arbitrate a clinical
    # disagreement, and a curator is allowed to disagree with a one-star submission.
    clin_sig_conflicts = (
        verify_clin_sig(variants, out, reference=clinvar_ref) if verify_clinsig else []
    )
    for conflict in clin_sig_conflicts:
        logger.warning("ClinVar clin_sig %s — %s",
                       "conflict" if conflict.opposed else "difference", conflict)

    # Third validation pass: is the rsID a module keys on still the one dbSNP serves? Needs the live
    # API (NCBI is the oracle — Ensembl 400s on some merges), so `--offline` skips it. The verdict is
    # STAMPED onto the rows' provenance columns and reported; the authored label is never replaced,
    # because doing so would migrate `variant_key` by network lookup. See `identifiers.check_rsids`.
    stale_rsids: list[RsidStatus] = []
    if verify_rsids and not offline:
        statuses = check_rsids(sorted({r.rsid for r in out if r.rsid}))
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

    # Which licensed source each link speaks for (RM33). **Derived, never fetched** — read off the
    # row's own `source` — and filled only where empty, so a hand-written authority survives exactly as
    # a hand-written `vrs_id` does. A link with no mapping (`authored`, `reversed`, `manual`) keeps
    # `None`, which is the answer rather than a gap: there is no external source to declare.
    for row in out:
        if row.authority is None:
            row.authority = resolution_authority(row.source)

    out.sort(key=lambda r: (r.variant_key, r.locus_index))
    sources = sorted({r.source for r in out if r.source})
    result = EnrichmentResult(
        rows=out, unresolved=sorted(set(unresolved)), sources=sources, mode=mode,
        ref_mismatches=ref_mismatches, clin_sig_conflicts=clin_sig_conflicts,
        stale_rsids=stale_rsids,
    )

    if mode == "strict" and ref_mismatches:
        # Deliberately checked BEFORE the unresolved gate: a wrong `ref` is a worse diagnosis than a
        # missing position (it can mint a well-formed id for the wrong allele), so it should be the
        # error the author sees first.
        raise EnrichmentError(
            f"strict enrichment: {len(ref_mismatches)} row(s) disagree with the {genome_build} "
            f"reference sequence: {[str(m) for m in ref_mismatches]}. Fix the authored coordinates "
            f"(a wrong ref length silently mints a different allele id), or enrich with "
            f"mode='best_effort' to record them as warnings."
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

    if write:
        _write_resolution_csv(out, resolution_path)
        # `enrich()` was the only pass that consulted sources and recorded none — the reason
        # `VALID_SOURCE_LAYERS` reserves a `"resolution"` member nothing ever wrote. Keyed on the
        # authority rather than the link, so the row joins `sources.csv` (RM33).
        record_source_terms(
            {row.authority for row in out if row.authority},
            "resolution",
            spec_dir / "sources.csv",
            error=EnrichmentError,
        )
    return result


def _write_resolution_csv(rows: list[ResolutionRow], output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "variant_key": r.variant_key,
                    "rsid": r.rsid or "",
                    "chrom": r.chrom if r.chrom is not None else "",
                    "start": r.start if r.start is not None else "",
                    "ref": r.ref or "",
                    "alts": r.alts or "",
                    "genome_build": r.genome_build,
                    "locus_index": r.locus_index,
                    "vrs_id": r.vrs_id or "",
                    "vrs_spec": r.vrs_spec or "",
                    "caid": r.caid or "",
                    "source": r.source or "",
                    "authority": r.authority or "",
                    "status": r.status or "",
                    "rsid_alternates": r.rsid_alternates or "",
                    "rsid_current": r.rsid_current or "",
                    "rsid_status": r.rsid_status or "",
                    "fetched_at": r.fetched_at or "",
                }
            )

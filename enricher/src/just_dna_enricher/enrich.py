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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import _load_yaml, _restamp_for_build, load_csv_rows
from just_dna_compiler.resolution import hosting_verdict, undecided_reason
from just_dna_format.base import derive_variant_key
from just_dna_format.binning import HeteroplasmyRow
from just_dna_format.manifest import VerificationRecord
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import normalize_chrom, par_partner

from just_dna_enricher import clinvar
from just_dna_enricher.clinical import (
    ClinSigComparison,
    ClinSigConflict,
    compare_clin_sig,
    tautology_reason,
)
from just_dna_enricher.clinvar import clinvar_dataset_label
from just_dna_enricher.download import ensure_clinvar_snapshot, ensure_snapshot
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.eutils import EutilsError
from just_dna_enricher.gnomad import GnomadClient, GnomadError
from just_dna_enricher.grch37 import (
    BuildDiagnosis,
    BuildDiagnosisResult,
    Grch37Client,
    diagnose_wrong_build,
    summarize_build_diagnoses,
)
from just_dna_enricher.identifiers import RsidStatus, check_rsids
from just_dna_enricher.licensing import (
    read_sources_file,
    record_source_terms,
    resolution_authority,
    sidecar_path,
)
from just_dna_enricher.locations import (
    read_release,
    resolve_clinvar_reference,
    resolve_ensembl_reference,
)
from just_dna_enricher.resolver import PairCheck, check_rsid_coordinates, lookup_loci
from just_dna_enricher.sequences import (
    RefCheck,
    RefMismatch,
    SequenceProxy,
    summarize_ref_mismatches,
    verify_reference_alleles,
)
from just_dna_enricher.verification import (
    DETAIL_LIMIT,
    examples,
    ran,
    record_verification,
    skipped,
)
from just_dna_enricher.vrs import MintResult, VrsMinter, mint_resolution_rows

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
    rsid: str | None
    chrom: str | None
    start: int | None
    ref: str | None
    alts: str | None
    constraint: str | None
    origin: str


def _subject_of_variant(v: VariantRow, genome_build: str = "GRCh38") -> _Subject:
    """The subject a `variants.csv` row asks about, keyed on the identity it already carries.

    `variant_key` is always set (`_freeze_identity` is a model validator) and `enrich` re-stamps it for
    the module's build before this runs, so the fallback is belt-and-braces — and it takes `genome_build`
    anyway, because a fallback that mints a GRCh38 id on a GRCh37 module would be wrong in exactly the
    way this whole path was.
    """
    key = v.variant_key or derive_variant_key(
        v.rsid, v.chrom, v.start, v.ref, v.alts, build=genome_build
    )
    return _Subject(key, v.rsid, v.chrom, v.start, v.ref, v.alts, v.genotype, "variants.csv")


def _collect_subjects(
    spec_dir: Path, variants: list[VariantRow], genome_build: str = "GRCh38"
) -> list[_Subject]:
    """Every row in the spec that needs a coordinate, `variants.csv` first, deduped by `variant_key`.

    Order and precedence are load-bearing. `variants.csv` goes first so that when the same variant is
    named by two tables, the SNP row wins — it is the only one carrying `alts`, which is a resolution
    *fact* and therefore decides the compiled bytes. Letting a PGx row win would move an already
    compiled module's `artifact.digest`, the same hazard the link ordering in the chain below exists
    to avoid. Within that, first occurrence wins, so the emitted order is the authored order.

    The PGx tables key **without** `alts`: a pharm annotation or a haplotype junction matches a
    variant at `chrom:start:ref` regardless of allele. Mixing that up would mint a VRS allele id for a
    row that never named an allele. `heteroplasmy.csv` is the exception and keys *with* `alts`,
    because its own `variant_key` does — see the block below.

    All three tables carry `variant_key` as a **stamped field** since 0.6 (RM43) — it was a property
    on two of them and absent from `HaplotypeRow` entirely, which is why the block below derives one
    inline. The stamped value is the same expression, frozen at load from the authored columns, so
    nothing here changes; and `PharmVariantRow.alts`, added by the same item, is deliberately not read
    here because it is compiler-filled data rather than an authored fact.
    """
    subjects: list[_Subject] = [_subject_of_variant(v, genome_build) for v in variants]

    pharm_path = spec_dir / "pharm_variants.csv"
    if pharm_path.exists():
        rows, errors, _ = load_csv_rows(pharm_path, PharmVariantRow, "pharm_variants.csv")
        if errors:
            raise EnrichmentError(f"pharm_variants.csv is invalid: {errors[0]}")
        subjects.extend(
            _Subject(r.variant_key, r.rsid, r.chrom, r.start, r.ref, None, r.genotype,
                     "pharm_variants.csv")
            for r in rows
        )

    hap_path = spec_dir / "haplotypes.csv"
    if hap_path.exists():
        rows, errors, _ = load_csv_rows(hap_path, HaplotypeRow, "haplotypes.csv")
        if errors:
            raise EnrichmentError(f"haplotypes.csv is invalid: {errors[0]}")
        subjects.extend(
            _Subject(derive_variant_key(r.rsid, r.chrom, r.start, r.ref),
                     r.rsid, r.chrom, r.start, r.ref, None, r.allele, "haplotypes.csv")
            for r in rows
        )

    # `heteroplasmy.csv` is the third table that can ask, and it was left out of the 0.5 round for no
    # reason anyone recorded: its coordinates are optional exactly like the PGx ones, so an
    # rsid-authored heteroplasmy module resolved to nothing and the compiler's positional-joinability
    # warning would have named a gap no tool could close.
    #
    # Two differences from the blocks above, both load-bearing. It **passes `alts`**, because
    # `HeteroplasmyRow.variant_key` mints one the same way `VariantRow` does (verified equal for both
    # the rsid and the coordinate shape), and a subject whose key carries an allele must carry the
    # allele. That makes the key **build-dependent**, so the load takes `genome_build` — the RM36
    # trap, and the reason the two blocks above rightly do not. Its `constraint` is `None`: a
    # heteroplasmy row is a measurement band over a locus, not a claim about a genotype, so it
    # constrains no locus out of a one-to-many expansion.
    het_path = spec_dir / "heteroplasmy.csv"
    if het_path.exists():
        rows, errors, _ = load_csv_rows(
            het_path, HeteroplasmyRow, "heteroplasmy.csv", genome_build=genome_build
        )
        if errors:
            raise EnrichmentError(f"heteroplasmy.csv is invalid: {errors[0]}")
        subjects.extend(
            _Subject(
                r.variant_key or derive_variant_key(
                    r.rsid, r.chrom, r.start, r.ref, r.alts, build=genome_build
                ),
                r.rsid, r.chrom, r.start, r.ref, r.alts, None, "heteroplasmy.csv",
            )
            for r in rows
        )

    deduped: dict[str, _Subject] = {}
    for s in subjects:
        deduped.setdefault(s.variant_key, s)
    return list(deduped.values())


def _authored_alt(v: _Subject) -> str | None:
    """The single authored ALT for allele-aware reverse resolution, or None when absent or
    multi-allelic (fall back to position/ref-level matching, which may resolve as ambiguous)."""
    if v.alts and "," not in v.alts:
        return v.alts
    return None


# The aggregation rule for a record's `detail` — `verification.DETAIL_LIMIT` / `verification.examples`.
# It moved there when `identifiers` became the second attesting pass that wanted it (RM72): a
# formatting rule with two copies has one that is about to be wrong.


def _check_authored_pairs(
    pairs: Sequence[tuple[str, str | None, int | None, str | None]],
    rsid_loci: Mapping[str, Sequence[dict]],
    *,
    genome_build: str,
    reference: Path | None,
    offline: bool,
    unusable: bool = False,
) -> PairCheck:
    """The rsid↔coordinate pass, with the reason it did not run when it did not (RM45).

    The comparison itself is `resolver.check_rsid_coordinates`; what lives here is the ladder that
    decides whether it could be put at all, because only the caller knows the module's build and
    whether a snapshot was ever opened. Five ways it does not run, and each is a different sentence:

    * **`nothing_to_check`** — the module authors no pair, which is exactly what that member means: no
      row this check applies to. **Tested first**, ahead of the build, because a module with no pair
      has no assembly question to answer either, and answering `unsupported` there would describe a
      claim the module never made.
    * **`unsupported`** — coordinate resolution is GRCh38-bound (RM15), so every link was gated off
      and there is nothing this tier could compare the pair against. A permanent limit, not a
      connectivity one, which is why it outranks the two below: a GRCh37 module run offline satisfies
      both, and reporting `offline` would promise that a re-run with egress answers it.
    * **`offline` / `no_reference`** — no snapshot was opened. Offline that is cleared by egress (the
      run would have provisioned one); online it is a provisioning failure, which egress will not fix.
      A snapshot that is present and will not answer (`unusable`) is `no_reference` too — it is not a
      connectivity problem, and the log names the file.
    * **`no_reference` again, for a snapshot that carries none of the pairs, or can settle none.** Zero
      comparisons is not `ran(0, 0)`: a record saying a check ran over nothing reads as a clean bill,
      which is F4 in this same batch. What it could not place, and what it could not decide, are named
      in the record's detail either way.
    """
    if not pairs:
        return PairCheck(not_checked="nothing_to_check")
    if genome_build != "GRCh38":
        return PairCheck(not_checked="unsupported")
    if reference is None or unusable:
        no_snapshot = "offline" if offline and not unusable else "no_reference"
        return PairCheck(not_checked=no_snapshot)
    check = check_rsid_coordinates(pairs, rsid_loci)
    if check.subjects == 0:
        return PairCheck(
            unknown=check.unknown, undecided=check.undecided, not_checked="no_reference"
        )
    return check


def _locus_alleles(locus: dict) -> tuple[str, frozenset[str]]:
    """A locus's alleles in a comparable form: `(ref, {alts})`, order- and whitespace-insensitive."""
    alts = str(locus.get("alts") or "")
    return str(locus.get("ref") or ""), frozenset(a.strip() for a in alts.split(",") if a.strip())


def select_par_representative(
    loci: list[dict], *, build: str = "GRCh38"
) -> tuple[list[dict], list[dict]]:
    """Split a one-to-many expansion into `(kept, y_par_twins)`, preferring the X spelling.

    A pseudoautosomal locus is **one place on two contigs** — PAR1 and PAR2 are the stretches X and Y
    share, so dbSNP maps one rsID to both and the expansion emits two rows for one finding. Probed
    2026-08-04, every annotation source places PAR annotation on **X** and only the coordinate resolver
    disagrees: ClinVar has zero records in either PAR on Y (all 677 of its Y records lie outside the
    PARs), gnomAD v4 excludes the Y PAR from its callset outright (X PAR1 640000-641500 serves 880
    variants, the same interval on Y serves none), and the ClinGen Allele Registry does mint a Y allele
    id but leaves the record a stub — a dbSNP cross-reference and nothing else, no ClinVar, no gnomAD,
    and a title that degrades to the bare genomic HGVS. Standard GRCh38 analysis sets then hard-mask the
    Y PAR, so the Y row cannot match a call either.

    So keeping it records **the sources' own convention**, not the consumer's analysis set — which is
    the distinction that makes this the enricher's decision to take (Principle 2: this is the only tier
    permitted to hold a source convention). The caller keeps both with `keep_par_twin`.

    This **selects; it does not repair** — the same contract as the allele-aware `hosting_verdict`
    filter beside it. Every authored value is untouched, and the caller reports what was left out.

    Two things it deliberately will not do:

    * **Fuse on geometry alone.** A Y locus is dropped only when its `par_partner` X position is present
      *and* carries the same `ref`/`alts`. Partner coordinates say "same place"; they do not say "same
      variant", and a same-place different-allele pair is a real finding rather than a duplicate — so it
      is kept, and both rows survive.
    * **Judge a gene.** The verdict is per locus, because a real gene can straddle a PAR boundary: **XG**
      runs out of PAR1 (X:2,751,798-2,816,500 crosses the boundary at 2,781,479) and **SPRY3** runs into
      PAR2 (X:155,612,298-155,782,459 crosses 155,701,383). Any module- or gene-scoped policy would be
      wrong for half of either one.
    """
    by_place: dict[tuple[str, int, str, frozenset[str]], dict] = {}
    for locus in loci:
        chrom, start = normalize_chrom(locus.get("chrom")), locus.get("start")
        if chrom is None or start is None:
            continue
        ref, alts = _locus_alleles(locus)
        by_place[(chrom, int(start), ref, alts)] = locus

    kept: list[dict] = []
    twins: list[dict] = []
    for locus in loci:
        chrom, start = normalize_chrom(locus.get("chrom")), locus.get("start")
        partner = (
            par_partner(chrom, int(start), build=build)
            if chrom == "Y" and start is not None
            else None
        )
        ref, alts = _locus_alleles(locus)
        if partner is not None and (partner[0], partner[1], ref, alts) in by_place:
            twins.append(locus)
        else:
            kept.append(locus)
    return kept, twins


class EnrichmentError(RuntimeError):
    """Raised in strict mode when the chain cannot fully resolve the module."""


def spec_genome_build(spec_dir: Path) -> str:
    """The build the module itself declares, which is the only build enrichment may resolve against.

    `enrich()` took `genome_build` as a plain parameter defaulting to `"GRCh38"` and **nothing ever
    passed it** — no CLI flag, no caller — so the GRCh38 gate on every link below was unreachable and a
    `genome_build: GRCh37` module was resolved against GRCh38 Ensembl, its GRCh38 coordinates written
    into `resolution.csv` labelled `GRCh38`, and GRCh38 VRS ids minted for them. The compiler then
    (correctly) refused to use any of it. The guard existed; the value never arrived — the same shape as
    the `VariantRow` re-stamp bug, where a `build` parameter and its fall-through both existed and were
    never reached.

    A spec with no `module_spec.yaml` gets the format's own default. That is not a guess: `enrich` is
    routinely pointed at a bare table directory in tests and by hand, and `ModuleSpecConfig.genome_build`
    defaults to `"GRCh38"`, so this returns what compiling that directory would assume. A spec whose
    yaml is *present but unreadable* is a different case and raises — enrichment writes facts into that
    directory, and picking a build for a module whose declaration cannot be read is exactly the
    invention this function exists to remove.
    """
    if not (spec_dir / "module_spec.yaml").exists():
        return "GRCh38"
    config, errors, _ = _load_yaml(spec_dir / "module_spec.yaml")
    if config is None:
        raise EnrichmentError(
            f"cannot read the module's genome_build: {errors[0] if errors else 'module_spec.yaml is '
            'unreadable'}. Enrichment resolves against one assembly and records the answer under the "
            f"module's declared build, so it will not choose one for you — fix module_spec.yaml, or "
            f"pass genome_build= explicitly."
        )
    return config.genome_build


def source_build_mismatch(spec_dir: Path, source: str, source_build: str = "GRCh38") -> str | None:
    """A warning when a drafting provider is about to write `source_build` coordinates into a module
    that declares a different one — or `None` when the builds agree.

    **The gap this closes is that `spec_genome_build` had exactly one caller.** It was written for the
    bug where "the guard existed; the value never arrived", and then `draft`, `draft-panel` and
    `draft-clinpgx` all shipped without asking it. Every source these providers read serves GRCh38 —
    CPIC's `allele_definitions`, the ClinVar snapshot, the ClinPGx annotations — so drafting into a
    `genome_build: GRCh37` module writes `10,94942290` for `rs1799853`, whose GRCh37 position is
    `96702047`, and nothing anywhere says a word. The compiler cannot catch it: a coordinate is legal
    on either build, it is simply a different place. The whole point of `reference_examples/grch37_build`
    is that this family of defect is *silent by construction*, and this is its ninth instance.

    **Reported, not repaired, and not refused.** The provider still writes the row: refusing would
    make the three drafting commands unusable on a non-GRCh38 module rather than merely
    unhelpful, and stripping the coordinate to leave an rsid-only row is a *different* row than the
    author asked for — both are design decisions with real trade-offs, and the enricher's standing
    rule is that a pass which finds a disagreement says so and changes nothing. Which of the two the
    providers should eventually do is filed rather than decided here.

    Returns `None` for the agreeing case, which is nearly every call — the house tri-state applies to
    the *answer*, and "the builds agree" is not a finding.
    """
    declared = spec_genome_build(spec_dir)
    if declared == source_build:
        return None
    return (
        f"{source} publishes {source_build} coordinates and this module declares "
        f"genome_build={declared!r}: every chrom/start drafted below names a {source_build} position, "
        f"recorded as though it were {declared}. Nothing downstream can detect this — a coordinate is "
        f"valid on either assembly, it is simply a different base — so either re-declare the module as "
        f"{source_build}, or delete the drafted coordinates and keep the rsIDs, which name a variant "
        f"without naming an assembly (`just-dna-enricher hint recover` converts in that direction)."
    )


@dataclass
class EnrichmentResult:
    rows: list[ResolutionRow]
    unresolved: list[str] = field(default_factory=list)  # variant_keys with no resolved position
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    # Authored data that disagrees with the reference genome. Reported, never repaired — see
    # `sequences.verify_reference_alleles`. Empty when the check could not run (offline).
    ref_mismatches: list[RefMismatch] = field(default_factory=list)
    # Which of those mismatched rows read as GRCh37 coordinates in a GRCh38 module (RM48). Computed
    # only over `ref_mismatches`, so a module whose refs agree costs no request at all, and grouped by
    # evidence class rather than by row.
    build_diagnoses: list[BuildDiagnosis] = field(default_factory=list)
    # Why the diagnosis above did not run, or `None` when it did. Same rule as `clin_sig_not_checked`:
    # an empty list otherwise means both "asked, and nothing points at another build" and "never
    # asked", and only one of those is a clean bill. `no_ref_mismatches` (nothing to diagnose) and
    # `skipped_offline` are the two ways it does not run.
    build_not_diagnosed: str | None = None
    # Authored `clin_sig` values ClinVar's own records do not support. Warnings in BOTH modes on
    # purpose — see `clinical.verify_clin_sig`. Empty when no snapshot was provisioned.
    clin_sig_conflicts: list[ClinSigConflict] = field(default_factory=list)
    # Why the cross-check above did not run, or `None` when it did. An empty `clin_sig_conflicts` says
    # two opposite things on its own — "compared everything, nothing disagreed" and "never compared" —
    # and a consumer reading the first when the second happened is being told a check passed that was
    # never put. So the skip carries its reason (S4): `not_requested`, `no_snapshot`, or the
    # drafted-from-this-release tautology, which is the one that used to report a confident zero, and
    # `unusable_snapshot` for a reference that is present but not queryable.
    clin_sig_not_checked: str | None = None
    # The per-row split behind that tautology, and **only** there: `strict` over a module whose licence
    # row says it was drafted from this very snapshot looks every value up and reports how many are
    # still copies, how many a human wrote, and how many conflict (RM4). `None` — never an audit of
    # zeros — on every other run: `best_effort` deliberately does not pay for it (the reason is in
    # `clin_sig_not_checked`), and for a module that never claimed a draft the copied/authored split
    # would assert a provenance nobody established.
    clin_sig_comparison: ClinSigComparison | None = None
    # Authored rsIDs dbSNP has merged away or has no record of. Recorded onto the rows' provenance
    # columns and reported; never substituted — see `identifiers.check_rsids`.
    stale_rsids: list[RsidStatus] = field(default_factory=list)
    # `(rsid, chrom, start)` of each Y pseudoautosomal locus left out in favour of its X spelling.
    # Surfaced rather than only logged: the table is half the size an author might expect, and a
    # selection nobody can see is indistinguishable from a silent repair. See
    # `select_par_representative`. Empty with `keep_par_twin`, and on every non-PAR module.
    par_twins_dropped: list[tuple[str, str, int]] = field(default_factory=list)
    # What the VRS minting pass did (RM40) — the same `MintResult` whose two counters `compile_module`
    # later stamps into `manifest.compilation.vrs_alleles` / `vrs_alleles_identified`, plus
    # `unmintable_reasons`, the grouped breakdown that is the actionable half.
    #
    # It was computed here and thrown away, so a consumer wanting to read coverage **before** a compile
    # — which is what a publish dry run is — had to re-implement the counting, and had to get two
    # non-obvious rules right to agree with the manifest a publish would produce: count per **ALT slot**
    # (`vrs_id` is a parallel array of `alts`), and treat an *absent* cell as `len(alts)` unnamed slots
    # rather than zero, or a table where nothing minted reports flawless coverage out of a denominator
    # of nothing. A number this workspace computed and discarded gets recomputed by every consumer, and
    # a recomputation is a place to drift.
    #
    # `None` — never a coverage of zero — when the pass did not run (`mint_vrs=False`). The house rule.
    vrs: MintResult | None = None
    # rsIDs the live Ensembl link could not be asked about — a failed request, never an empty answer
    # (S20). Separate from `unresolved`, which says a key has no position and is silent about why: a
    # row that failed to resolve because egress broke and one with genuinely no locus to find are the
    # same entry there, and only one of them is worth re-running. Same reason `clin_sig_not_checked`
    # exists beside an empty conflict list. Empty offline, since nothing was asked in the first place.
    unreachable_rsids: list[str] = field(default_factory=list)
    # What the rsid↔coordinate pass did (`resolver.check_rsid_coordinates`): the pairs it compared,
    # the ones the reference could not place, and the disagreements. Surfaced for the RM40/RM41 reason
    # — the run computes it and a consumer would otherwise recompute it from the log — and because the
    # denominator is the half a bare list of disagreements cannot state. `None` only for a caller that
    # built the result by hand; `enrich()` always sets it, carrying `not_checked` when the pass could
    # not run rather than an empty finding list that reads as a clean bill.
    rsid_coordinates: PairCheck | None = None

    @property
    def fully_resolved(self) -> bool:
        return not self.unresolved


def enrich(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    ensembl_cache: Path | None = None,
    clinvar_cache: Path | None = None,
    use_clinvar: bool = True,
    use_gnomad: bool = True,
    download: bool = True,
    genome_build: str | None = None,
    write: bool = True,
    mint_vrs: bool = True,
    verify_ref: bool = True,
    verify_clinsig: bool = True,
    verify_rsids: bool = True,
    keep_par_twin: bool = False,
    resolver: EnsemblResolver | None = None,
    gnomad_client: Optional["GnomadClient"] = None,
    grch37_client: Grch37Client | None = None,
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

    `keep_par_twin` keeps both spellings of a pseudoautosomal locus. By default only the X one is
    recorded, because every annotation source uses X and a standard GRCh38 analysis set hard-masks the
    Y PAR — see `select_par_representative` for the probe behind that. Set it for a consumer whose
    reference is unmasked. The switch belongs here and could not live on the compiler: `resolution.csv`
    is injected data that travels with the module, so the choice is *recorded* and
    `compile → reverse → compile` stays a fixed point either way, whereas a compiler flag would not
    survive `reverse_module` rebuilding the spec from parquet alone (Principle 7).
    """
    spec_dir = Path(spec_dir)
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

    # Existing/human rows are authoritative — merge, never clobber.
    existing: dict[str, list[ResolutionRow]] = {}
    # Through the shared resolver, so the pass writes back to wherever the module keeps this table —
    # root or `derived/`, whatever it is called. Reading one copy and writing another would leave the
    # module carrying two, which is the collision (RM49/RM51).
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=EnrichmentError)
    if resolution_path.exists():
        rows, errors, _ = load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
        if errors:
            raise EnrichmentError(f"existing {resolution_path.name} is invalid: {errors[0]}")
        for row in rows:
            existing.setdefault(row.variant_key, []).append(row)

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
            genome_build, genome_build,
        )

    # Every table that can ask for a coordinate, not just variants.csv (a PGx module has none).
    subjects = _collect_subjects(spec_dir, variants, genome_build)

    # Partition the subjects that still need work (skip those an existing row already covers).
    need_pos = [
        v for v in subjects
        if v.rsid is not None and v.chrom is None and v.variant_key not in existing
    ]
    need_rsid = [
        v for v in subjects
        if v.rsid is None and v.chrom is not None and v.variant_key not in existing
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
    # Reverse (position→rsid) back-fill is allele-aware and keeps ALL candidates per authored allele,
    # so we can take a deterministic pick and flag a genuine multi-rsid allele as ambiguous rather than
    # guessing an allele-blind label (which was the mis-attribution / reverse-round-trip drift).
    # Initialized before the lookup, not inside it: the call can fail (a present-but-unqueryable
    # cache) and the loops below still have to have something to iterate.
    pos_candidates: dict[tuple, list[str]] = {}
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
                reference, exc,
            )
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
    clinvar_ref: Path | None = None
    if (use_clinvar or verify_clinsig) and genome_build == "GRCh38":
        clinvar_ref = resolve_clinvar_reference(clinvar_cache)
        if clinvar_ref is None and not offline and download:
            try:
                ensure_clinvar_snapshot(clinvar_cache)
                clinvar_ref = resolve_clinvar_reference(clinvar_cache)
            except Exception as exc:  # provisioning is best-effort; degrade to live/offline
                logger.warning("ClinVar snapshot provisioning failed (%s); continuing without it.", exc)

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
                    if loci is None:
                        # Could not ask (S20). Distinct from an empty answer, and the distinction has
                        # to survive to the row-writing loop below, which would otherwise record
                        # `status="not_found", source="ensembl"` — a negative nobody established.
                        unreachable_rsids.add(rsid)
                    elif loci:
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
    # Collected across the loop and reported once. A per-row line here would be one line per variant —
    # ten for the SHOX panel — which buries every other finding a run produces.
    par_twins_dropped: list[tuple[str, str, int]] = []
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
                    #
                    # The *reason* comes from the shared `undecided_reason` rather than being spelled
                    # here, because `None` has four causes and this sentence used to assert one of them
                    # for all four — including for a call that observed nothing, which no reference can
                    # settle, while the closing advice said to check one.
                    logger.warning(
                        "%s: whether %s:%s %s>%s can host the authored %s %s could not be decided from "
                        "the allele strings — %s. The locus is KEPT.",
                        v.rsid, lo.get("chrom"), lo.get("start"), lo.get("ref"), lo.get("alts"),
                        subject, v.constraint,
                        undecided_reason(v.constraint, lo.get("ref"), lo.get("alts")),
                    )
                elif verdict is False:
                    logger.warning(
                        "%s: %s:%s %s>%s cannot host the authored %s %s, and is left out of "
                        "resolution.csv. The event sizes differ, which re-anchoring cannot change, so "
                        "this is a different variant sharing the rsID rather than another spelling.",
                        v.rsid, lo.get("chrom"), lo.get("start"), lo.get("ref"), lo.get("alts"),
                        subject, v.constraint,
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
                    out.append(ResolutionRow(
                        variant_key=key, rsid=v.rsid, genome_build=genome_build,
                        locus_index=i, source=src, status="resolved", **locus,
                    ))
            elif genome_build == "GRCh38" and v.rsid in unreachable_rsids:
                # The live link was asked and never answered (S20), so this row has the same shape as
                # the non-GRCh38 case below and gets the same treatment: no row at all. Writing
                # `not_found` here would state, in the artifact, that Ensembl was asked and does not
                # have this rsID — the one reading the run cannot support, and the fingerprint of a
                # fabricated identifier. The key stays `unresolved`, so `strict` still refuses and
                # `best_effort` still warns; what changes is that neither claims a source said no.
                unresolved.append(key)
            elif genome_build == "GRCh38":
                out.append(ResolutionRow(variant_key=key, rsid=v.rsid, genome_build=genome_build,
                                         source="ensembl" if not offline else "cache", status="not_found"))
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
        mint_result = mint_resolution_rows(
            out, minter=VrsMinter(offline=offline, sequences=sequences)
        )
        logger.info(
            "VRS: minted %d id(s) (%d stdlib, %d normalized), %d unmintable, %d already present",
            mint_result.minted, mint_result.minted_stdlib, mint_result.minted_normalized,
            mint_result.skipped_unmintable, mint_result.already_present,
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
            build.examined, build.total,
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
        drafted_from_it = tautology_reason(read_sources_file(spec_dir), clinvar_ref, spec_dir)
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
        logger.warning("ClinVar clin_sig %s — %s",
                       "conflict" if conflict.opposed else "difference", conflict)

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
        except EutilsError as exc:
            # The same rule as the gnomAD block above, and it had no handler at all (RM97): this is a
            # *validation* pass that runs after every other pass has finished and before
            # `resolution.csv` is written, so letting NCBI's availability abort the run throws away
            # work that already succeeded. Until RM97 the escaping type was a raw `httpx` exception
            # rather than even `EutilsError`, so nothing up the stack could have caught it either.
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
        verify_pairs, rsid_to_loci, genome_build=genome_build, reference=reference,
        offline=offline, unusable=snapshot_unusable,
    )
    if pair_check.disagreements:
        # One line for the run, naming them, on the `unreachable_rsids` model: a line per row would be
        # one per variant on a fully coordinate-authored panel.
        logger.warning(
            "rsid↔coordinate disagreement — %d of %d authored pair(s) name a coordinate the injected "
            "Ensembl snapshot does not give for that rsID: %s Reported, never repaired: which half is "
            "wrong is not knowable here.",
            len(pair_check.disagreements), pair_check.subjects,
            " ".join(pair_check.disagreements),
        )
    if pair_check.unknown:
        logger.info(
            "rsid↔coordinate: %d authored pair(s) were not compared — the injected Ensembl snapshot "
            "carries no record for %s. Not in the snapshot is not 'not in Ensembl'; the pair is "
            "unchecked rather than disagreeing.",
            len(pair_check.unknown), examples(sorted(set(pair_check.unknown))),
        )
    if pair_check.undecided:
        logger.info(
            "rsid↔coordinate: %d authored pair(s) could not be decided — %s name an indel, and one "
            "deletion has several valid spellings whose anchors sit a base or two apart (RM31), so a "
            "differing position is not a contradiction. Undecided, never reported as a disagreement.",
            len(pair_check.undecided), examples(sorted(set(pair_check.undecided))),
        )

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
        clin_sig_not_checked=clin_sig_not_checked, clin_sig_comparison=clin_sig_comparison,
        build_diagnoses=build.diagnoses, build_not_diagnosed=build.not_checked,
        stale_rsids=stale_rsids, par_twins_dropped=sorted(par_twins_dropped),
        vrs=mint_result, unreachable_rsids=sorted(unreachable_rsids),
        rsid_coordinates=pair_check,
    )

    if unreachable_rsids:
        # Warned in BOTH modes, and not escalated by `strict`: nothing an author can edit clears a
        # failed request, and `strict` means "reproducible artifact" (P5). What it does change is the
        # reading of the run — an unresolved key here may well resolve on the next one.
        logger.warning(
            "%d rsID(s) could not be asked of live Ensembl (the request failed, so the answer is "
            "unchecked rather than empty): %s. Re-run before treating these as rsIDs Ensembl does "
            "not have.",
            len(unreachable_rsids), ", ".join(sorted(unreachable_rsids)),
        )

    if mode == "strict" and ref_mismatches:
        # Deliberately checked BEFORE the unresolved gate: a wrong `ref` is a worse diagnosis than a
        # missing position (it can mint a well-formed id for the wrong allele), so it should be the
        # error the author sees first.
        # The build diagnosis travels **inside** the refusal, not beside it. It is computed above in
        # both modes, and a `strict` run raises here and returns nothing — so a diagnosis left on the
        # result object would be visible only to the mode that does not need it, and invisible to the
        # one whose whole output is this sentence.
        because = (
            " " + "; ".join(summarize_build_diagnoses(build.diagnoses)) + "."
            if build.diagnoses
            else ""
        )
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

    if write:
        _write_resolution_csv(out, resolution_path)
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
                verify_rsids=verify_rsids,
                rsid_subjects=rsid_subjects,
                stale_rsids=stale_rsids,
                pairs=pair_check,
                ensembl_ref=reference,
            ),
            spec_dir,
            error=EnrichmentError,
        )
        # `enrich()` was the only pass that consulted sources and recorded none — the reason
        # `VALID_SOURCE_LAYERS` reserves a `"resolution"` member nothing ever wrote. Keyed on the
        # authority rather than the link, so the row joins `sources.csv` (RM33).
        record_source_terms(
            {row.authority for row in out if row.authority},
            "resolution",
            spec_dir,
            error=EnrichmentError,
        )
    return result


def _verification_records(
    *,
    offline: bool,
    verify_ref: bool,
    ref_check: RefCheck,
    build: BuildDiagnosisResult,
    verify_clinsig: bool,
    clin_sig_compared: int | None,
    clin_sig_conflicts: list[ClinSigConflict],
    clin_sig_skip: str | None,
    clin_sig_detail: str | None,
    clinvar_ref: Path | None,
    verify_rsids: bool,
    rsid_subjects: int,
    stale_rsids: list[RsidStatus],
    pairs: PairCheck,
    ensembl_ref: Path | None,
) -> list[VerificationRecord]:
    """The five checks this pass puts, as records `verification.json` can carry (RM45).

    Every count comes from the check that produced it — never re-derived here. That is the whole
    reason `verify_reference_alleles` and `verify_clin_sig` now return what they compared: a
    denominator recomputed beside a check is a denominator that can disagree with it, and a manifest
    field whose two halves disagree is worse than no field.

    `not_requested` is recorded rather than omitted, and the difference matters: an omitted check is
    one nobody has said anything about, while a recorded `not_requested` says this run deliberately
    did not put it. Only the first is what a re-run with the flag on would fill in.
    """
    records: list[VerificationRecord] = []

    # Reference allele. The reason comes off the check, which is the only thing that knows whether the
    # sequence service answered — `offline` is the caller's request, not the outcome.
    if not verify_ref:
        records.append(skipped("reference_allele", "not_requested"))
    elif ref_check.not_checked is not None:
        # The detail follows the reason rather than assuming one: `unsupported` is not a sequence
        # failure at all — the service was fine and the *assembly* has no refget table, so saying
        # "no sequence access" would send an author looking for a network problem they do not have.
        records.append(
            skipped(
                "reference_allele",
                ref_check.not_checked,
                detail=(
                    "this tier has a refget table for GRCh38 only, so an authored ref on another "
                    "assembly has nothing to be compared against (RM15)"
                    if ref_check.not_checked == "unsupported"
                    else "no sequence access this run, so no authored ref was compared"
                ),
                source="seqrepo",
            )
        )
    else:
        records.append(
            ran(
                "reference_allele",
                subjects=ref_check.subjects,
                findings=len(ref_check.mismatches),
                source="seqrepo",
                detail="; ".join(summarize_ref_mismatches(ref_check.mismatches)) or None,
            )
        )

    # Wrong build (RM48). Its subject set is the ref-mismatched rows and nothing else — the pass is
    # *bounded* on purpose (`DEFAULT_DIAGNOSIS_LIMIT`), so `examined` is the honest denominator and
    # `total` is not: recording the larger number would claim rows the pass deliberately did not ask
    # about. `sampled` is why that distinction has to be kept rather than smoothed over, and the detail
    # line says so where it applies.
    #
    # It rides on the reference-allele check having run at all: with no mismatches there is nothing to
    # diagnose, which the pass itself reports as `no_ref_mismatches` — recorded as `nothing_to_check`,
    # because "no row was in scope" is exactly what that member means, and it is emphatically not a
    # finding of zero wrong builds.
    if build.not_checked is not None:
        # **`no_ref_mismatches` alone does not mean the refs agreed.** `diagnose_wrong_build([])`
        # answers it for an empty list whatever emptied the list — a ref check that ran and found
        # nothing, *or* one that never ran at all. Reading it as the first would publish "no authored
        # ref disagreed with the reference" beside a `reference_allele` record saying nothing was
        # compared: one document contradicting itself, with the false half being exactly the
        # answered-absence-versus-unasked-question collapse S20 exists to prevent. So whatever stopped
        # the ref check propagates here, and `nothing_to_check` is reachable only when it really ran.
        # **A permanent limit outranks a transient one, so `unsupported` is tested first.** Offline,
        # a `genome_build: GRCh37` module satisfies both branches — the GRCh37 service was not asked
        # *and* the ref check could not run on an assembly with no refget table — and reporting
        # `offline` there says a re-run with a network would answer it. It would not: the ref check
        # produces no mismatched rows on that build whatever the connectivity, so this pass has no
        # subjects either way. Same ordering rule RM48 applies to its own two readings — the one that
        # does not rest on a transient condition supersedes.
        if ref_check.not_checked == "unsupported":
            reason, detail = "unsupported", (
                "the reference-allele check cannot run on this module's assembly, so no row was ever "
                "a candidate for a build diagnosis — this is not a connectivity problem and a re-run "
                "online reports the same thing"
            )
        elif build.not_checked == "skipped_offline":
            reason, detail = "offline", (
                "the GRCh37 service is the only thing that can tell an old-assembly coordinate from "
                "a wrong ref, and there is no local GRCh37 data"
            )
        elif ref_check.not_checked is not None:
            reason, detail = ref_check.not_checked, (
                "the reference-allele check did not run, so there was no mismatched row to diagnose "
                "— this says nothing about whether the coordinates are on the declared assembly"
            )
        else:
            reason, detail = "nothing_to_check", (
                "no authored ref disagreed with the reference, so no row needed a build diagnosis"
            )
        records.append(
            skipped("genome_build_agreement", reason, detail=detail, source="ensembl-grch37")
        )
    else:
        records.append(
            ran(
                "genome_build_agreement",
                subjects=build.examined,
                findings=len(build.diagnoses),
                source="ensembl-grch37",
                detail=(
                    f"bounded sample: {build.examined} of {build.total} mismatched row(s) asked about"
                    if build.sampled
                    else None
                ),
            )
        )

    # Clinical significance. `release` is the snapshot's own `release.json` answer, which is what a
    # consumer needs to know *which* ClinVar the calls were weighed against — the same reason a
    # frequency row carries its `dataset`. `None` when the snapshot cannot state one, never a guess.
    clinvar_release = _clinvar_release(clinvar_ref)
    if clin_sig_compared is None:
        # The look-up did not run, and `clin_sig_skip` says which of the closed reasons applies. Keyed
        # on the *count being absent* rather than on re-testing the flags, so the record cannot claim a
        # comparison the pass did not make: there is no path where a look-up ran and left it `None`.
        records.append(
            skipped(
                "clinical_significance",
                clin_sig_skip or "not_requested",
                # The prose reason beside the machine key, never instead of it: `tautology_reason`
                # writes a good sentence and this is where it survives the run.
                detail=clin_sig_detail,
                source="clinvar",
            )
        )
    else:
        records.append(
            ran(
                "clinical_significance",
                subjects=clin_sig_compared,
                findings=len(clin_sig_conflicts),
                source="clinvar",
                release=clinvar_release,
            )
        )

    # rsID currency. dbSNP publishes a build number per record rather than a release for the service,
    # so there is nothing true to put in `release` — the same call `LiteratureRow` made about `dataset`.
    if not verify_rsids:
        records.append(skipped("rsid_currency", "not_requested", source="dbsnp"))
    elif offline:
        records.append(
            skipped(
                "rsid_currency",
                "offline",
                detail="dbSNP has no offline merge table, so currency cannot be established locally",
                source="dbsnp",
            )
        )
    else:
        records.append(
            ran(
                "rsid_currency",
                subjects=rsid_subjects,
                findings=len(stale_rsids),
                source="dbsnp",
            )
        )
    # rsID ↔ coordinate. This tier's half of a question the compiler asks too (`resolution._verify`
    # over the injected table), so one name covers both and this record covers **this** half: the
    # authored pair against the Ensembl snapshot the chain opened. `source` is the authority the
    # licence table joins on, not the link that answered — the `gene_metrics.csv` rule from RM33.
    unplaced = examples(sorted(set(pairs.unknown)))
    unsettled = examples(sorted(set(pairs.undecided)))
    # What was not compared, and why, in one sentence per reason — never one per row.
    not_compared = [
        note for note in (
            f"the injected Ensembl snapshot carries no record for {len(pairs.unknown)} of them "
            f"({unplaced}), and absent from this snapshot is not absent from Ensembl"
            if pairs.unknown else "",
            f"{len(pairs.undecided)} name an indel ({unsettled}), whose spelling can move the "
            f"coordinate legitimately, so no verdict was reached"
            if pairs.undecided else "",
        ) if note
    ]
    if pairs.not_checked is not None:
        if pairs.not_checked == "unsupported":
            detail = (
                "coordinate resolution is GRCh38-bound, so an authored rsID+coordinate pair on "
                "another assembly has nothing to be compared against (RM15)"
            )
        elif pairs.not_checked == "nothing_to_check":
            detail = (
                "no row authors both an rsID and a coordinate, so the module makes no pair claim to "
                "compare — this is not a comparison that found nothing"
            )
        elif not_compared:
            # A snapshot was read and settled nothing. Distinct from having no snapshot at all, and the
            # pairs are named because *which* ones went unchecked is what a re-run against a fuller
            # snapshot — or an online run that can normalize an indel — would change.
            detail = "no authored pair could be compared: " + "; ".join(not_compared)
        else:
            detail = (
                "no Ensembl snapshot was opened this run, so no authored pair was compared"
                + (" — a run with egress provisions one" if pairs.not_checked == "offline" else "")
            )
        records.append(
            skipped("rsid_coordinate_agreement", pairs.not_checked, detail=detail, source="ensembl")
        )
    else:
        # What was NOT compared travels with what was: coverage of an unstated fraction is the defect
        # `_vrs_coverage` exists for, one check over.
        notes = list(pairs.disagreements[:DETAIL_LIMIT])
        if len(pairs.disagreements) > DETAIL_LIMIT:
            notes.append(
                f"({len(pairs.disagreements) - DETAIL_LIMIT} further disagreement(s) not listed "
                f"here; the run's log names every one.)"
            )
        if not_compared:
            notes.append(
                "Further authored pairs were not compared: " + "; ".join(not_compared) + "."
            )
        records.append(
            ran(
                "rsid_coordinate_agreement",
                subjects=pairs.subjects,
                findings=len(pairs.disagreements),
                source="ensembl",
                release=_snapshot_release(ensembl_ref),
                detail=" ".join(notes) or None,
            )
        )

    # Deliberately takes neither `variants` nor `rows`: nothing here may count anything itself, and a
    # function that cannot see the tables cannot be tempted to. The denominators come in already
    # computed, from the checks that computed them.
    return records


def _snapshot_release(reference: Path | None) -> str | None:
    """The label a snapshot's own `release.json` states, or `None` when it states none.

    The `dataset` key, which is the one every builder writes and `cache status` prints, so a reader of
    the attestation and a reader of the cache see the same string. No fallback and no guess: a
    snapshot that cannot name its release is an unknown, and an unknown is withheld rather than
    written as a label something could match — the same call `clinvar_dataset_label` makes for its own
    (richer) source. ClinVar has its own function because its release is a *file date* with a digest
    fallback; nothing equivalent is published for the Ensembl variation snapshot.
    """
    if reference is None:
        return None
    release = read_release(Path(reference))
    if not release:
        return None
    return str(release.get("dataset") or "").strip() or None


def _clinvar_release(reference: Path | None) -> str | None:
    """The ClinVar release a snapshot states, or `None` when it states none.

    Delegates to `clinvar.clinvar_dataset_label` rather than re-reading `clinvar_file_date`, because a
    second spelling of one label is the drift that function's own docstring exists to prevent — and it
    had already started: this hand-read dropped the `clinvar_` prefix, so `verification.checks[].release`
    and `sources[].dataset` named the same snapshot two ways, and it dropped the digest fallback, so a
    snapshot built from a VCF with no header date recorded "the source publishes none" when it could
    name its release exactly. `None` stays the honest answer for a snapshot that genuinely cannot say.
    """
    return clinvar_dataset_label(reference)


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

"""The subjects a run asks about: `collect_subjects` over every table that names a variant, the
authored-pair check, and the pseudoautosomal representative (RM260 split this out of the former
single-file `enrich.py`).
"""

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import derive_variant_key
from just_dna_format.binning import HeteroplasmyRow
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import normalize_chrom, par_partner

from just_dna_enricher.enrich.outcome import EnrichmentError
from just_dna_enricher.resolver import PairCheck, check_rsid_coordinates


@dataclass(frozen=True)
class Subject:
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


def _subject_of_variant(v: VariantRow, genome_build: str = "GRCh38") -> Subject:
    """The subject a `variants.csv` row asks about, keyed on the identity it already carries.

    `variant_key` is always set (`_freeze_identity` is a model validator) and `enrich` re-stamps it for
    the module's build before this runs, so the fallback is belt-and-braces — and it takes `genome_build`
    anyway, because a fallback that mints a GRCh38 id on a GRCh37 module would be wrong in exactly the
    way this whole path was.
    """
    key = v.variant_key or derive_variant_key(v.rsid, v.chrom, v.start, v.ref, v.alts, build=genome_build)
    return Subject(key, v.rsid, v.chrom, v.start, v.ref, v.alts, v.genotype, "variants.csv")


def collect_subjects(
    spec_dir: Path, variants: list[VariantRow], genome_build: str = "GRCh38"
) -> list[Subject]:
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
    subjects: list[Subject] = [_subject_of_variant(v, genome_build) for v in variants]

    pharm_path = spec_dir / "pharm_variants.csv"
    if pharm_path.exists():
        rows, errors, _ = load_csv_rows(pharm_path, PharmVariantRow, "pharm_variants.csv")
        if errors:
            raise EnrichmentError(f"pharm_variants.csv is invalid: {errors[0]}")
        subjects.extend(
            Subject(r.variant_key, r.rsid, r.chrom, r.start, r.ref, None, r.genotype, "pharm_variants.csv")
            for r in rows
        )

    hap_path = spec_dir / "haplotypes.csv"
    if hap_path.exists():
        rows, errors, _ = load_csv_rows(hap_path, HaplotypeRow, "haplotypes.csv")
        if errors:
            raise EnrichmentError(f"haplotypes.csv is invalid: {errors[0]}")
        subjects.extend(
            Subject(
                derive_variant_key(r.rsid, r.chrom, r.start, r.ref),
                r.rsid,
                r.chrom,
                r.start,
                r.ref,
                None,
                r.allele,
                "haplotypes.csv",
            )
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
            Subject(
                r.variant_key
                or derive_variant_key(r.rsid, r.chrom, r.start, r.ref, r.alts, build=genome_build),
                r.rsid,
                r.chrom,
                r.start,
                r.ref,
                r.alts,
                None,
                "heteroplasmy.csv",
            )
            for r in rows
        )

    deduped: dict[str, Subject] = {}
    for s in subjects:
        deduped.setdefault(s.variant_key, s)
    return list(deduped.values())


def _authored_alt(v: Subject) -> str | None:
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
    answered: AbstractSet[tuple[str, str]] = frozenset(),
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
    check = check_rsid_coordinates(pairs, rsid_loci, answered)
    if check.subjects == 0:
        return PairCheck(unknown=check.unknown, undecided=check.undecided, not_checked="no_reference")
    return check


def _locus_alleles(locus: dict) -> tuple[str, frozenset[str]]:
    """A locus's alleles in a comparable form: `(ref, {alts})`, order- and whitespace-insensitive."""
    alts = str(locus.get("alts") or "")
    return str(locus.get("ref") or ""), frozenset(a.strip() for a in alts.split(",") if a.strip())


def select_par_representative(loci: list[dict], *, build: str = "GRCh38") -> tuple[list[dict], list[dict]]:
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
        partner = par_partner(chrom, int(start), build=build) if chrom == "Y" and start is not None else None
        ref, alts = _locus_alleles(locus)
        if partner is not None and (partner[0], partner[1], ref, alts) in by_place:
            twins.append(locus)
        else:
            kept.append(locus)
    return kept, twins

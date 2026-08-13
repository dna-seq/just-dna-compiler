"""
The measure → phenotype binning primitive (0.4 — see docs/CHANGELOG.md).

One declarative shape shared by every quantity-carrying locus: a per-locus table that maps a
*measured quantity* (activity score, copy number, repeat count, heteroplasmy fraction, PRS
percentile) to a phenotype by range. The tables differ only in **which** quantity is measured and
in their explicit key columns (multicolumn keying — never a packed tuple; the keying stance is a
coding standard, see CLAUDE.md). Aligning the column vocabulary gives a consumer one "bin-a-measure"
code path.

**Data-agnostic (design north star — see CLAUDE.md).** These rows are pure annotation: a lookup
table declaring range→phenotype. The module contains **no measurement** — the measured quantity is
supplied by the consumer at query time; the table never sees a sample. The bins themselves are a
generalization over a practical subset of real loci/ranges, not an all-encompassing model, so a data
item that doesn't fit is a schema gap to widen additively.

**Ranges are inclusive `[measure_min, measure_max]`**: `min == max` is a *sharp* value (e.g. exactly
0 copies), `min < max` is a range (HTT 36–39 CAG), and `measure_max = None` is open-ended (≥40 CAG,
3+ copies). There is no `copy_number` column — a sharp copy number is `measure_min == measure_max`.

**On a continuous measure, two adjacent bins may share an endpoint, and the higher bin owns it.**
The lookup rule, which a consumer implements once: *select the row with the greatest `measure_min ≤ x`*
(within the group). Written out for `allele_fraction` bins `0.0–0.1`, `0.1–0.3`, `0.3–1.0`, a
heteroplasmy of exactly `0.1` selects the MIDD bin and `1.0` selects the top one.

This is a rule about *tiling*, not a second meaning for `measure_max`, and it exists because the
alternative was unsatisfiable (RM35). Inclusive-at-both-ends, overlap-is-an-error and
any-positive-hole-is-a-warning cannot all hold on a dense domain: two adjacent continuous bins either
share an endpoint or leave a gap, so **every** `allele_fraction`/`prs_percentile` table carried a finding
forever — a check that could not be satisfied rather than one that was failing. No epsilon escapes it
(`[0, 0.0999999]` + `[0.1, 1.0]` still warns). Half-open `[min, max)` for continuous kinds was the other
candidate and lost on authorship: it makes one column mean two things depending on `measure_kind`, the
number written in the cell is then not in the bin, and a bounded domain's top value (AF = 1.0 is
homoplasmy, and real) becomes unreachable unless the last bin is authored open. Here `measure_max` means
the same thing on every kind and the top bin stays closed.

**Discrete kinds are unaffected, which is why this was missed.** `repeat_count`/`copy_number` tile
exactly under inclusive bounds — HTT `[6,35]`, `[36,39]`, `[40,∞)` is genuinely gapless because the
domain is integral — so for them a shared endpoint remains a real **overlap** and stays an error.

**…except that the domain is not integral, and the spec says so (RM55, 0.6 warns and does nothing
else).** VCF 4.4 §7.2 *"Redefined INFO and FORMAT CN to support non-integer copy numbers"* and its worked
examples are fractional throughout (`CN=3,0.9666`, `CN=1.25`); §5.6 leaves the granularity of a copy
number deliberately undefined and allows a segment mean *"at a highly granular megabase level of
resolution"*. §3 types `RUC`, the repeat count VCF 4.4 standardises, as a **Float**. So the premise the
paragraph above rests on was withdrawn for **both** integer kinds, and the consequence is worse than the
`allele_fraction` case RM35 fixed: an integer tiling `[0,0] [1,1] [2,2] [3,∞)` is accepted with no
warning at all, a measured `2.4` matches no bin, and the module compiles green under `--strict`. A hole
of exactly one is invisible to the gap check by construction.

The honest description is that the implementation landed prematurely and is wrong, not that a feature is
missing — but the correction is a **retype** (`CopyNumberRow.modifier_cn: int` → float) plus a change to
what already-published bin tilings *mean*, and retyping is reserved for a major. So 0.6 makes the defect
**loud** (`measurement_shape_warnings` below), 0.7 adds the usable, additive half — a parallel float
column beside the integer one, integer deprecated — and 1.0 removes it. Two repairs were considered and
refused here: moving the kinds into `_DENSE_KINDS` is one line and silently retypes every existing table
(`[2,2]` beside `[3,3]` is a legal integer tiling today, and both the shared-endpoint rule and the gap
warning change meaning under dense semantics), and it answers the wrong question anyway, since the two
kind-sets separately decide *"can a hole be arbitrarily small?"* and *"can two bins touch?"*; and a
per-table quantised declaration or a sixth measure kind both *add around* an implementation that is
simply incorrect.

**A measurement can also span several bins, and there is no state for that (RM56).** `RUC` travels with
`CIRUC` and `CN` with `CICN`, and the spec is explicit that the upper bound may be missing and then means
unbounded (§3: *"a reasonable limit of total length of the repeat could not be determined"*). §5.7's
canonical CAG form is `RUS=CAG;RUC=65;CIRUC=-15,.`, and says why: *"Many of these techniques result in
imprecise variant calls."* Imprecision is the normal case. The consumer contract below has exactly three
states — a bin matched, no bin matched, or the measurement absent — and none of them is *the measurement
spans bins*. `reference_examples/htt_repeat_expansion` has thresholds at 26/27, 35/36 and 39/40, so a
real `RUC=38, CIRUC=-5,5` spans `[33,43]` and crosses all three: benign, uncertain **and** fully
penetrant, with no honest answer among them.

The policy vocabulary that settles it — withhold / take the worst bin / take the point estimate — lands
with the rest of the repeat work, when a real caller VCF is in hand, and its grain (per table or per row)
is deliberately undecided. Until then the stated placeholder behaviour is the house default: **a
consumer that reads an interval spanning two or more bins withholds.** It does not pick among them, and
it does not fall back to the `unresolved` sentinel either — that row means *no measurement was
available*, and here one was. Note what is **not** on the table: widening the measurement itself into an
interval puts a measurement in the module, which the data-agnostic north star forbids outright. What
belongs here is the *rule* for an interval that spans bins, which is annotation.

**`unresolved` (T1) is mandatory.** A table can state the outcome for *measurement absent / not
callable*, and the consumer contract is that a missing measurement selects the `unresolved` row,
**never the lowest/reference bin** (no activity score ⇒ not "Normal Metabolizer"; no CN ⇒ not "2
copies"; no heteroplasmy read ⇒ not "homoplasmic reference"). An `unresolved` row carries no bounds.
A measurement that is *present but matches no bin* is a distinct third state ("no matching bin", not
`unresolved`); `validate_bins` below rejects overlaps and flags coverage gaps so a table stays
coherent (consumer round-2 C1).

**`source_field` (round-2 3a) is a declarative *pointer*, not code.** It optionally names the VCF
`FORMAT`/`INFO` field the consumer extracts the measure from (`REPCN`, `AF`, `CN|DS`) — pure
indirection/addressing, deliberately constrained to a bare field-name token (optionally `|`-alternated)
so it can never become an expression. That keeps it inside Principle 1 (declarative, non-Turing): a
name that says *where the measurement lives*, never a transform that computes one. The module still
holds no measurement.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import ClassVar

from pydantic import Field, field_validator, model_validator

from just_dna_format.base import AuthoredModel, derive_variant_key, vocabulary
from just_dna_format.vocab import check_vocab, validate_finite

# Open, additive vocabulary of measured quantities (the `frozenset[str]` idiom, Principle 6). New
# quantities are added in a future release; unknown values are rejected (closed-validated).
VALID_MEASURE_KINDS: frozenset[str] = frozenset(
    {"activity_score", "copy_number", "repeat_count", "allele_fraction", "prs_percentile"}
)


# Which measure kinds have a meaningful numeric coverage gap. Integer counts are contiguous when
# bins are adjacent (`[27,35]`,`[36,39]`); truly continuous fractions are not. `activity_score` is a
# consumer-summed quantized quantity, so interior "gaps" are not meaningful — excluded.
_INTEGER_KINDS: frozenset[str] = frozenset({"repeat_count", "copy_number"})
_CONTINUOUS_GAP_KINDS: frozenset[str] = frozenset({"allele_fraction", "prs_percentile"})

# Which kinds are **dense**, i.e. where a shared endpoint between adjacent bins is a *boundary* rather
# than an overlap (see the module docstring, RM35). Deliberately the same set as the gap kinds and
# deliberately spelled separately: they answer two different questions about a measure — "can a hole be
# arbitrarily small?" and "can two bins touch?" — and a future kind could plausibly answer them
# differently (a quantized-but-fine measure). `activity_score` is in neither: it is consumer-summed onto
# a coarse grid, so bins do not touch and interior holes are not meaningful.
_DENSE_KINDS: frozenset[str] = _CONTINUOUS_GAP_KINDS

#: For each kind this schema tiles as integral, the VCF 4.4 field a consumer reads the measurement from,
#: the field carrying its confidence interval, and the clause of the spec that contradicts the integer
#: treatment. Both entries are wrong in the same two ways (RM55 fractional, RM56 interval), which is why
#: they are one table rather than two lists: they were put in `_INTEGER_KINDS` on one premise and the
#: spec withdrew it for both, and fixing one while leaving the other would leave the next reader to
#: rediscover why they differ. Spec-derived and fixed, so it is not the source convention P2 forbids.
_VCF_MEASURE_FIELDS: dict[str, tuple[str, str, str]] = {
    "copy_number": (
        "CN",
        "CICN",
        "VCF 4.4 §7.2 redefined INFO/FORMAT CN to support non-integer copy numbers, and §5.6 leaves "
        "the granularity of the interval a copy number is defined over deliberately undefined",
    ),
    "repeat_count": (
        "RUC",
        "CIRUC",
        "VCF 4.4 §3 types RUC — the repeat unit count it standardises — as a Float",
    ),
}

#: **The two fragments below are the only surviving record of these findings for a consumer reading a
#: published `manifest.json`**, since `compile_module` copies its warnings there and a catalog
#: reindexing from a manifest has no spec directory left. They are named rather than inlined so that
#: rewording them is a deliberate act with an audience, the way `compiler.UNJOINABLE_PHRASE` is —
#: with one honest difference: that phrase is pinned by a shipped consumer today, and these are not.
#: The rest of each sentence is free to improve.
FRACTIONAL_MEASURE_PHRASE = "is not a whole number in VCF 4.4"
SPANNING_MEASUREMENT_PHRASE = "one measurement can span several bins"


class MeasureBinRow(AuthoredModel):
    """Base row of a binning table: a measured quantity range → the same orthogonal axes a
    `VariantRow` carries. Subclasses add the explicit key columns for their quantity.

    Inherits `AuthoredModel` (and passes it to its subclasses): `extra="forbid"` + the
    reserved-namespace guard, and the shared `direction`/`clin_sig`/`trait_efo_id` validators.
    """

    # Subclasses pin their measure_kind via this ClassVar (see `_validate_measure_kind`).
    _EXPECTED_KIND: ClassVar[str | None] = None
    # The explicit key columns for this quantity (used by `validate_bins` to group rows). The unit
    # is part of the key (T3): a measurement is only comparable within its motif/reference/modifier.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ()

    measure_kind: str = Field(
        json_schema_extra=vocabulary("measure_kind", VALID_MEASURE_KINDS),
        description="Measured quantity; one of VALID_MEASURE_KINDS",
    )
    measure_min: float | None = Field(
        default=None,
        description=(
            "Inclusive lower bound; None = open below. On a continuous measure this is also the "
            "tie-break: a value two bins share belongs to the one with the greater measure_min."
        ),
    )
    measure_max: float | None = Field(
        default=None,
        description=(
            "Inclusive upper bound; None = open above. Inclusive on every measure_kind — on a "
            "continuous measure the next bin may start on it, and then that bin owns the value."
        ),
    )
    direction: str | None = Field(
        default=None, description="Effect direction: protective|risk|neutral|unknown"
    )
    clin_sig: str | None = Field(
        default=None, description="ClinVar/ACMG clinical significance (VEP CLIN_SIG vocabulary)"
    )
    phenotype: str | None = Field(default=None, description="Associated trait or phenotype")
    trait_efo_id: str | None = Field(
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s)"
    )
    conclusion: str = Field(description="Human-readable interpretation for this bin")
    unresolved: bool = Field(
        default=False,
        description="True on the sentinel row a consumer selects when the measurement is absent.",
    )
    source_field: str | None = Field(
        default=None,
        description=(
            "Optional VCF FORMAT/INFO field the consumer extracts this measure from (e.g. REPCN, "
            "AF, CN|DS). A declarative pointer (bare field-name token, optionally |-alternated), "
            "never an expression — an extraction hint; the measurement still comes from the consumer."
        ),
    )

    # `source_field`'s pointer grammar is validated on `AuthoredModel` — it is shared with
    # `VariantRow.callable_from`, and a validator used by two models lives on the base.

    @field_validator("measure_min", "measure_max")
    @classmethod
    def _validate_bound_finite(cls, v: float | None) -> float | None:
        return validate_finite(v, "measure bound")

    @field_validator("measure_kind")
    @classmethod
    def _validate_measure_kind(cls, v: str) -> str:
        check_vocab(v, VALID_MEASURE_KINDS, "measure_kind")
        expected = cls._EXPECTED_KIND
        if expected is not None and v != expected:
            raise ValueError(f"{cls.__name__} requires measure_kind={expected!r}, got: {v!r}")
        return v

    @model_validator(mode="after")
    def _validate_range(self) -> "MeasureBinRow":
        if self.unresolved:
            if self.measure_min is not None or self.measure_max is not None:
                raise ValueError(
                    "an unresolved row carries no measure_min/measure_max (it is the sentinel a "
                    "consumer selects when no measurement is available)"
                )
            return self
        if self.measure_min is None and self.measure_max is None:
            raise ValueError(
                "a resolved bin needs at least one of measure_min/measure_max "
                "(set unresolved=True for the measurement-absent sentinel)"
            )
        if (
            self.measure_min is not None
            and self.measure_max is not None
            and self.measure_min > self.measure_max
        ):
            raise ValueError(
                f"measure_min must be <= measure_max (min == max is a sharp value), got "
                f"[{self.measure_min}, {self.measure_max}]"
            )
        return self


class ActivityPhenotypeRow(MeasureBinRow):
    """PGx metabolizer phenotype by activity score, per gene (CYP2D6 PM/IM/NM/UM). The score is a
    consumer call (Σ activity×copies over the diplotype); this table only bins it."""

    _EXPECTED_KIND: ClassVar[str] = "activity_score"
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("gene",)

    gene: str = Field(description="Gene symbol, e.g. CYP2D6")
    measure_kind: str = Field(
        default="activity_score",
        # A one-member vocabulary under its OWN name, not `VALID_MEASURE_KINDS`:
        # `_validate_measure_kind` pins this subclass to `_EXPECTED_KIND`, so offering the full
        # set would offer values this very model rejects. It needs a distinct name because a
        # vocabulary name must map to one option set — `measure_kind` is already the open choice
        # on the base, and this is the narrowed one.
        json_schema_extra=vocabulary("measure_kind_activity_score", frozenset({"activity_score"})),
        description="Fixed: activity_score",
    )


class CopyNumberRow(MeasureBinRow):
    """Whole-gene dosage phenotype by copy number (SMN1 SMA). Sharp dosages are
    `measure_min == measure_max` (0 copies = [0, 0]); `3+` is `measure_min=3, measure_max=None`.

    Optional `modifier_gene`/`modifier_cn` express a second dosage locus read in context (SMN1
    phenotype depends on SMN2 copy number) — explicit named columns (multicolumn keying), never a
    tuple. Both are set together or both left null.
    """

    _EXPECTED_KIND: ClassVar[str] = "copy_number"
    # The modifier is part of the key: SMN1=0 with SMN2=3 vs SMN2=1 are distinct bins, not an overlap.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("gene", "modifier_gene", "modifier_cn")

    gene: str = Field(description="Gene symbol whose copy number is binned, e.g. SMN1")
    modifier_gene: str | None = Field(
        default=None, description="Optional modifier locus read in context, e.g. SMN2"
    )
    modifier_cn: int | None = Field(
        default=None, description="Copy number of the modifier locus (set with modifier_gene)"
    )
    measure_kind: str = Field(
        default="copy_number",
        # A one-member vocabulary under its OWN name, not `VALID_MEASURE_KINDS`:
        # `_validate_measure_kind` pins this subclass to `_EXPECTED_KIND`, so offering the full
        # set would offer values this very model rejects. It needs a distinct name because a
        # vocabulary name must map to one option set — `measure_kind` is already the open choice
        # on the base, and this is the narrowed one.
        json_schema_extra=vocabulary("measure_kind_copy_number", frozenset({"copy_number"})),
        description="Fixed: copy_number",
    )

    @model_validator(mode="after")
    def _validate_modifier(self) -> "CopyNumberRow":
        if (self.modifier_gene is None) != (self.modifier_cn is None):
            raise ValueError(
                "modifier_gene and modifier_cn are set together or both left null, got "
                f"modifier_gene={self.modifier_gene!r}, modifier_cn={self.modifier_cn!r}"
            )
        return self


class RepeatAlleleRow(MeasureBinRow):
    """VNTR/STR phenotype by repeat count, keyed on `(gene, repeat_unit)` — the motif is part of
    the identity (T3): a count is only comparable within its motif definition. The count is a
    consumer call (ExpansionHunter / adVNTR / a span genotyper) that MUST state the motif it
    counted."""

    _EXPECTED_KIND: ClassVar[str] = "repeat_count"
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("gene", "repeat_unit")

    gene: str = Field(description="Gene symbol, e.g. HTT")
    repeat_unit: str = Field(description="Repeat motif, part of the key, e.g. CAG")
    measure_kind: str = Field(
        default="repeat_count",
        # A one-member vocabulary under its OWN name, not `VALID_MEASURE_KINDS`:
        # `_validate_measure_kind` pins this subclass to `_EXPECTED_KIND`, so offering the full
        # set would offer values this very model rejects. It needs a distinct name because a
        # vocabulary name must map to one option set — `measure_kind` is already the open choice
        # on the base, and this is the narrowed one.
        json_schema_extra=vocabulary("measure_kind_repeat_count", frozenset({"repeat_count"})),
        description="Fixed: repeat_count",
    )


# The known-dangerous legacy mtDNA reference lineage: NC_001807 silently disagrees with rCRS
# (NC_012920) coordinates and bases, yielding a *confidently-wrong* haplogroup (consumer round-2 Q3).
# Not a closed allow-list (future refs exist) — the validator rejects only this enumerated landmine.
LEGACY_MT_REFERENCE_BASES: frozenset[str] = frozenset({"NC_001807"})
CANONICAL_MT_REFERENCE_SEQUENCES: frozenset[str] = frozenset({"NC_012920.1"})


class HeteroplasmyRow(MeasureBinRow):
    """mtDNA phenotype by heteroplasmy allele fraction (0–1), keyed on
    `(gene, reference_sequence, tissue)`. The reference sequence is part of the key (A3): rCRS/
    NC_012920 vs legacy NC_001807 disagree and `genome_build` does not disambiguate. Bounds are
    constrained to `[0, 1]`.

    `tissue`/`assay_context` are optional but load-bearing (round-2 Q6): heteroplasmy bins are
    **tissue-conditional** — a blood-derived fraction systematically under-represents the
    affected-tissue burden, and the penetrance threshold itself shifts by tissue, so the *same*
    fraction bins to different phenotypes across tissues. A heteroplasmy table with no tissue context
    is quietly unsafe; state the tissue the bins assume.

    **The variant identity is part of the key too (0.5.1), and it was missing.** A mitochondrial gene
    carries several pathogenic variants with genuinely different thresholds — MT-TL1 has m.3243A>G
    *and* m.3271T>C, both causing MELAS; MT-ATP6 has m.8993T>G and m.9176T>C. Keyed on the gene alone,
    their bins landed in one group and `validate_bins` rejected the module outright with "overlapping
    bins", which is an **error**, not a warning, so the module could not compile at all. There was no
    honest way out: `trait_efo_id` is in the group key and would have separated them, but only by
    giving one disease two ontology ids. The documented example never showed two variants in a gene,
    so the limitation was invisible rather than decided.

    The columns mirror `PharmVariantRow` exactly — rsid, else `chrom`+`start`(+`ref`/`alts`) — and are
    **optional**, so an existing single-variant table groups as it always did (P3/P8). They enter the
    key through the derived `variant_key` property rather than one-by-one, so all the identity shapes
    collapse to the format's own notion of which variant a row is about."""

    _EXPECTED_KIND: ClassVar[str] = "allele_fraction"
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene", "reference_sequence", "tissue", "variant_key",
    )

    gene: str = Field(description="MT locus/gene, e.g. MT-TL1")
    # Optional on purpose: required would invalidate every already-authored heteroplasmy table
    # (Principle 8 — a new field may not be unconditionally required), and a single-variant gene has
    # nothing to disambiguate. No `chromosome` vocabulary marker, matching the other tables that run
    # no chrom validator.
    rsid: str | None = Field(
        default=None, description="dbSNP id of the variant these bins are about, when it has one"
    )
    chrom: str | None = Field(default=None, description="Contig (MT), for a position-only variant")
    start: int | None = Field(
        default=None, description="Position of the variant, e.g. 3243 for m.3243A>G"
    )
    ref: str | None = Field(default=None, description="Reference allele, e.g. A")
    alts: str | None = Field(default=None, description="Alternate allele(s), e.g. G")
    reference_sequence: str = Field(
        description="MT reference accession, part of the key, e.g. NC_012920.1 (rCRS)"
    )
    tissue: str | None = Field(
        default=None, description="Tissue the bins assume, e.g. blood, muscle (bins are tissue-conditional)"
    )
    assay_context: str | None = Field(
        default=None, description="Optional assay context, e.g. WGS, chip, amplicon"
    )
    measure_kind: str = Field(
        default="allele_fraction",
        # A one-member vocabulary under its OWN name, not `VALID_MEASURE_KINDS`:
        # `_validate_measure_kind` pins this subclass to `_EXPECTED_KIND`, so offering the full
        # set would offer values this very model rejects. It needs a distinct name because a
        # vocabulary name must map to one option set — `measure_kind` is already the open choice
        # on the base, and this is the narrowed one.
        json_schema_extra=vocabulary("measure_kind_allele_fraction", frozenset({"allele_fraction"})),
        description="Fixed: allele_fraction",
    )

    @property
    def variant_key(self) -> str | None:
        """Which variant these bins are about, or `None` when the table names only a gene.

        `None` is the pre-0.5 shape and groups exactly as it always did. A property rather than a
        stamped field, like `PharmVariantRow.variant_key`: a heteroplasmy row is never resolved or
        expanded, so there is nothing to freeze.

        **Keyed against the build the loader injected** (`AuthoredModel._genome_build`, RM36). This
        passes `alts`, so it can mint a `ga4gh:VA.…`, and a VA names its reference sequence by refget
        accession — so it must know the assembly or it will claim the wrong one. A property cannot be
        re-stamped the way `VariantRow.variant_key` is (that is a stored *field*; this is recomputed on
        every access), so the build is told to the row at load instead of corrected after it. Before
        that, one locus on a `genome_build: GRCh37` module got two identities: `6:26093141:G:A` from
        `variants.csv` and a GRCh38 VA from here. `PharmVariantRow.variant_key` and the `HaplotypeRow`
        key never had the problem — they omit `alts`, so they are build-independent by construction."""
        if self.rsid is None and self.start is None:
            return None
        return derive_variant_key(
            self.rsid, self.chrom, self.start, self.ref, self.alts, build=self._genome_build
        )

    @field_validator("reference_sequence")
    @classmethod
    def _reject_legacy_reference(cls, v: str) -> str:
        if v.split(".")[0] in LEGACY_MT_REFERENCE_BASES:
            raise ValueError(
                f"reference_sequence {v!r} is the legacy NC_001807 lineage, which disagrees with "
                f"rCRS (NC_012920) coordinates/bases and yields a confidently-wrong haplogroup; "
                f"use NC_012920.1"
            )
        return v

    @model_validator(mode="after")
    def _validate_fraction_bounds(self) -> "HeteroplasmyRow":
        for bound in (self.measure_min, self.measure_max):
            if bound is not None and not (0.0 <= bound <= 1.0):
                raise ValueError(
                    f"allele_fraction bounds must be within [0, 1], got {bound}"
                )
        return self


def _bin_groups(rows: Sequence[MeasureBinRow]) -> dict[tuple, list[MeasureBinRow]]:
    """Resolved rows grouped the way a consumer's lookup groups them: explicit key columns + trait.

    One definition, two callers (`validate_bins` and `measurement_shape_warnings`), for the reason a
    second copy always earns: the second check is *about* how many bins a measurement could land in, and
    it would be answering that question against a different partition than the one the overlap rule
    enforces. `unresolved` sentinels carry no range and are not bins.
    """
    groups: dict[tuple, list[MeasureBinRow]] = defaultdict(list)
    for r in rows:
        if r.unresolved:
            continue
        group_key = tuple(getattr(r, f, None) for f in r._KEY_FIELDS) + (r.trait_efo_id,)
        groups[group_key].append(r)
    return groups


def measurement_shape_warnings(rows: Sequence[MeasureBinRow]) -> list[str]:
    """What a table of integer-tiled bins cannot express about its own source measurement (RM55/RM56).

    Both findings are stated against the *kind*, once per table, never per row or per group: the defect
    is in the schema, so a per-row line would be the same sentence repeated as many times as the author
    wrote bins. See the module docstring for the spec quotations and the three-release route.

    * **RM55** — `copy_number` and `repeat_count` sit in `_INTEGER_KINDS`, and VCF 4.4 makes both `CN`
      and `RUC` non-integral. A fractional measurement *between two adjacent bins* therefore matches
      neither, and the coverage-gap check cannot see the hole because on an integer kind it only
      reports one wider than a whole number. Note the exposure is at the boundaries and on a sharp
      tiling, not everywhere: a fraction inside a wide range bin is answered fine, which is why this is
      stated against the kind rather than derived per bound. Fires on any table of these kinds.
    * **RM56** — the same two fields travel with a confidence interval whose upper bound may be
      unbounded, so a measurement is an interval and can cross a threshold. Fires only where there is a
      threshold to cross: two or more resolved bins in one group. With a single bin there is nothing to
      span, and saying so anyway would be a finding about a table that does not have the problem. The
      count is of **bins**, and the message says only that — an earlier draft called them *adjacent*,
      which is a property this function never computes and which `[0,0]` beside `[50,60]` falsifies.
      Adjacency is also not what matters here: an interval crosses two bins whether or not there is a
      hole between them, and where there is one the hole is `validate_bins`' finding, not this one.

    **Warnings in both modes, and deliberately never a `strict` error** — the `not_covered` /
    VRS-coverage class. No authored edit clears either: RM55 needs a schema column that does not exist
    yet and RM56 needs a policy vocabulary that has not been designed, so refusing would make a correct
    module uncompilable for a reason its author cannot act on, and `strict` means *reproducible
    artifact*, an unrelated axis (P5). Both reproduce exactly.
    """
    warnings: list[str] = []
    groups = _bin_groups(rows)
    kinds = {r.measure_kind for grp in groups.values() for r in grp} & set(_VCF_MEASURE_FIELDS)
    for kind in sorted(kinds):
        value_field, ci_field, spec_note = _VCF_MEASURE_FIELDS[kind]
        of_kind = {
            key: grp for key, grp in groups.items() if any(r.measure_kind == kind for r in grp)
        }
        warnings.append(
            f"{kind} bins are tiled as whole numbers, but the field a consumer reads the measurement "
            f"from ({value_field}) {FRACTIONAL_MEASURE_PHRASE}: {spec_note}. A fractional measurement "
            f"falling between two adjacent bins matches neither — `[0,0] [1,1] [2,2] [3,∞)` is a legal "
            f"tiling here and answers nothing at all for a 2.4 — and the coverage-gap check cannot "
            f"report the hole, because on an integer kind it only flags one wider than a whole number. "
            f"So the table is green and silently unanswerable at every one of its own boundaries. No "
            f"authored edit fixes it: the schema is wrong here, a parallel float column is queued for "
            f"0.7 and the integer column goes at 1.0 (RM55). Until then, expect an answer only from a "
            f"caller that rounds, and none from a segment mean."
        )
        widest = max(len(grp) for grp in of_kind.values())
        if widest >= 2:
            warnings.append(
                f"{kind} bins: {SPANNING_MEASUREMENT_PHRASE}, and nothing in this format says what to "
                f"do with one (RM56). A {value_field} call travels with {ci_field}, whose missing upper "
                f"bound means *unbounded*, so the measurement is an interval — and the widest group "
                f"here states {widest} bins for it to cross. The consumer contract has three "
                f"states (a bin matched, no bin matched, the measurement absent) and none of them is "
                f"this one. Not implemented, and stated rather than left silent: until the policy "
                f"vocabulary lands, a conforming consumer **withholds** — it does not pick among the "
                f"bins the interval touches, and it does not fall back to the `unresolved` row, which "
                f"means no measurement was available and is a different claim."
            )
    return warnings


def validate_bins(rows: Sequence[MeasureBinRow]) -> list[str]:
    """Table-level coherence check for a set of binning rows of one kind (consumer round-2 C1).

    Rows are grouped by their explicit key columns (`_KEY_FIELDS`) plus `trait_efo_id`. Within a
    group of *resolved* rows — a consumer measurement selects at most one — inclusive ranges
    `[measure_min, measure_max]` (a null bound = -inf/+inf) **must not overlap**; an overlap would
    select two phenotypes for one measurement and raises ``ValueError``. Overlap *across* different
    `trait_efo_id` is allowed (pleiotropy — the same measurement legitimately binning to two traits).
    `unresolved` sentinel rows carry no range and are ignored.

    **What counts as an overlap depends on whether the measure is dense** (RM35, see the module
    docstring). On a discrete kind, adjacent bins sharing an endpoint really do both claim that integer,
    so `lo <= prev_hi` is the error. On a dense kind the two bins are *touching*, which is the only way
    to tile a dense domain at all, so the error is `lo < prev_hi` and the shared value belongs to the
    higher bin. Two bins sharing a *lower* bound refuse on every kind: the boundary rule picks the
    greatest `measure_min` at or below the measurement, and there is nothing to pick between equals.

    Returns a list of **warnings** for interior coverage gaps (a value between two authored bins that
    matches no row): for integer kinds a hole spanning ≥1 uncovered integer, for continuous fractions
    any positive hole. `activity_score` is consumer-summed/quantized, so interior gaps are not
    meaningful and are not flagged. Edge coverage *below* the lowest bin (the "author the reference
    bin" contract, C1) is a consumer-contract matter, not auto-detected here — it would false-positive
    without a known domain floor. Callers decide what to do with the warnings (log, fail, ignore).
    """
    warnings: list[str] = []
    groups = _bin_groups(rows)

    for group_key, grp in groups.items():
        spans = sorted(
            (
                (
                    -math.inf if r.measure_min is None else r.measure_min,
                    math.inf if r.measure_max is None else r.measure_max,
                )
                for r in grp
            ),
            key=lambda t: (t[0], t[1]),
        )
        kind = grp[0].measure_kind
        dense = kind in _DENSE_KINDS
        for i in range(1, len(spans)):
            prev_lo, prev_hi = spans[i - 1]
            lo, hi = spans[i]
            if lo < prev_hi or (lo == prev_hi and not dense):
                raise ValueError(
                    f"overlapping bins for key {group_key}: [{prev_lo}, {prev_hi}] and "
                    f"[{lo}, {hi}] both select a phenotype for a measurement in the overlap"
                )
            if lo == prev_lo:
                # Equal *lower* bounds, which the boundary rule cannot resolve: it selects the greatest
                # `measure_min` at or below the measurement, and these two are the same. Only reachable
                # on a dense kind and only when the earlier bin is a single point (anything wider would
                # have tripped `lo < prev_hi` above) — e.g. `[0.1, 0.1]` beside `[0.1, 0.3]`, where a
                # measurement of exactly 0.1 has two answers and no rule to pick between them. That is
                # an ambiguous selection, so it refuses like any other overlap rather than warning.
                raise ValueError(
                    f"bins with the same lower bound for key {group_key}: [{prev_lo}, {prev_hi}] and "
                    f"[{lo}, {hi}] both start at {lo}, so a measurement of {lo} selects two phenotypes "
                    f"and the shared-endpoint rule (the higher bin owns it) cannot separate them"
                )
            hole = lo - prev_hi
            is_gap = (kind in _INTEGER_KINDS and hole > 1 + 1e-9) or (
                kind in _CONTINUOUS_GAP_KINDS and hole > 1e-9
            )
            if is_gap:
                warnings.append(
                    f"coverage gap for key {group_key}: no bin covers ({prev_hi}, {lo})"
                )
    return warnings

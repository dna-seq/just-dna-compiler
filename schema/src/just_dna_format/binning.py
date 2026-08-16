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

**Discrete kinds tile the other way.** `repeat_count`/`copy_number` tile exactly under inclusive bounds
— HTT `[6,35]`, `[36,39]`, `[40,∞)` is gapless *if* the domain is integral — so for them a shared
endpoint is a real **overlap** and stays an error.

**…except that the domain is not integral, and the spec says so (RM55).** VCF 4.4 §7.2 *"Redefined INFO
and FORMAT CN to support non-integer copy numbers"* and its worked examples are fractional throughout
(`CN=3,0.9666`, `CN=1.25`); §5.6 leaves the granularity of a copy number deliberately undefined and
allows a segment mean *"at a highly granular megabase level of resolution"*. §3 types `RUC`, the repeat
count VCF 4.4 standardises, as a **Float**. So the premise the paragraph above rests on was withdrawn
for both kinds, and the consequence was worse than the `allele_fraction` case RM35 fixed: a tiling
`[0,0] [1,1] [2,2] [3,∞)` was accepted with no warning at all, a measured `2.4` matched no bin, and the
module compiled green under `--strict`. A hole of exactly one is invisible to the gap check by
construction — and, the half nobody had written down, the schema also **refused the tiling that would
fix it**, since a shared endpoint on these kinds was an overlap error.

**How 0.6 closes it: tiling becomes its own axis.** `measure_tiling` (`{quantised, continuous}`,
optional, `VALID_MEASURE_TILINGS`) says *how the axis is divided*, which is a different question from
`measure_kind`'s *what is measured* — folding the two would be the overloaded-field anti-pattern (P5),
and a product rather than a sum. The shared-endpoint and gap rules read the group's **effective**
tiling (`resolve_tiling`): the declared value, else `continuous` where the kind would default to
`quantised` and the group carries a value no grid of whole numbers can hold, else the kind's default
(`DEFAULT_MEASURE_TILING`). **Absence means the kind's default, never a value**, which is what makes the
column additive — every module published before 0.6 keeps its exact meaning, and an author meets the
column only when departing from it. The inference announces itself and runs one way only:
fractional-ness contradicts a stated grid, integer-ness contradicts nothing, since `[0,1] [2,3]` is what
a continuous measure looks like when its author has only seen whole-number data.

Three repairs were refused. Moving the kinds into `_DENSE_KINDS` is one line and silently re-reads every
published table (`[2,2]` beside `[3,3]` is a legal quantised tiling, and both rules change meaning under
dense semantics) with no notice and no way to say otherwise. A sixth `measure_kind` is the wrong axis,
above. And deriving the tiling from the rows with no column at all fails on the half that has to be
right: absence of a fractional value implies nothing, so it would read the ambiguous table one way,
silently, and leave the curator no way to correct it.

The one genuine `int` here is `CopyNumberRow.modifier_cn`, a *modifier's* dosage rather than a bound,
and it gets the parallel-float treatment the roadmap entry had proposed for the bounds:
`modifier_copy_number` beside it, read through `effective_modifier_copy_number`, both-set refused,
`modifier_cn` **deprecated in 0.6 and removed at 1.0**. So 1.0 inherits a removal, not a retype.

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

**`pmid` grounds the BOUNDARY, and the line is: the bin row cites, the citation table describes**
(RM47, 0.6). A threshold is the most interpretive claim this format carries — where 36 rather than 35
CAG becomes "reduced penetrance" is a clinical judgement drawn from a specific paper — and until 0.6
nothing could point at one: `studies.csv` identifies its subject by rsid or `chrom`, while a
`repeat_alleles.csv` row is keyed `(gene, repeat_unit)`. One optional column on this base reaches all
four kinds and answers the question actually asked, which is *why 36* rather than *why this table*.
It carries a **pointer only**. Everything about the paper — population, `p_value_num`, `effect_size`,
`provenance_quote` — stays in `studies.csv`, whose subject requirement was relaxed in the same release
so a citation row may exist without naming a variant. Copying that column set here one column at a
time would restate the bin inside its own evidence, which is exactly what killed the alternative
designs (a `bin_evidence.csv` join table keys on the thresholds, and they are floats).

**`source_field` (round-2 3a) is a declarative *pointer*, not code.** It optionally names the VCF
field the consumer extracts the measure from (`FORMAT/REPCN`, `FORMAT/AF`, `INFO/CN|FORMAT/DS`) —
pure indirection/addressing, deliberately constrained to a field-name key (optionally namespace-
qualified, optionally `|`-alternated) so it can never become an expression. That keeps it inside
Principle 1 (declarative, non-Turing): a name that says *where the measurement lives*, never a
transform that computes one. The module still holds no measurement.

**A VCF field is identified by namespace and described by cardinality, and `source_field` used to
carry neither** (RM53/RM54, 0.6). INFO and FORMAT are two reserved-key tables that collide on `DP`,
`AD`, `ADF`, `ADR`, `MQ`, `AF` and — since 4.4 — `CN`, so `AF` alone names the cohort frequency of an
ALT *or* this sample's fraction of it, and both are floats in `[0, 1]` that bin without complaint.
`Number` then decides how many values come back: a pointer at a `Number=R` field returns one value
per allele, reference first, of which none is the answer. So the namespace goes in the pointer
(`FORMAT/AF`, bare still legal and still meaning unqualified) and the element goes in `source_element`
— a closed set of **named rules** rather than an index, because `AD[1]` is the first line of an
expression grammar and Principle 1 refuses it.

"Element" is one of the values the field carries for a record, which is wider than a `Number` slot on
purpose: ExpansionHunter reports both repeat alleles in a single `REPCN` cell as `17/42`, and a rule
that only spoke about `Number` would have nothing to say about the case it was built for
(`reference_examples/htt_repeat_expansion`, where the clinical rule is *the larger of the two*). How a
caller encodes multiplicity is the caller's business and this tier holds no opinion on it (Principle
2); which value the annotation means is the module's, and that is all this column states.
"""

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import ClassVar, NamedTuple

from pydantic import Field, field_validator, model_validator

from just_dna_format.base import AuthoredModel, stamped_identity_field, vocabulary
from just_dna_format.spec import validate_pmid_cell
from just_dna_format.vocab import check_vocab, validate_finite

# Open, additive vocabulary of measured quantities (the `frozenset[str]` idiom, Principle 6). New
# quantities are added in a future release; unknown values are rejected (closed-validated).
VALID_MEASURE_KINDS: frozenset[str] = frozenset(
    {"activity_score", "copy_number", "repeat_count", "allele_fraction", "prs_percentile"}
)


# How an axis is divided, independently of what is measured on it (RM55, 0.6). Two members, closed:
# `quantised` — the axis is a grid, so two bins sharing an endpoint really do both claim it and a hole
# narrower than one step is not a hole; `continuous` — the axis is dense, so adjacent bins *touch* and
# the higher one owns the shared value, and any positive hole strands a measurement.
#
# This is a different question from `measure_kind`, which answers *what* is measured (P5: a field must
# not pile up independent axes). A sixth measure kind spelling the same product — `copy_number_continuous`
# — was refused for exactly that reason.
VALID_MEASURE_TILINGS: frozenset[str] = frozenset({"quantised", "continuous"})

# Which measure kinds have a meaningful numeric coverage gap. Integer counts are contiguous when
# bins are adjacent (`[27,35]`,`[36,39]`); truly continuous fractions are not. `activity_score` is a
# consumer-summed quantized quantity, so interior "gaps" are not meaningful — excluded.
_INTEGER_KINDS: frozenset[str] = frozenset({"repeat_count", "copy_number"})
_CONTINUOUS_GAP_KINDS: frozenset[str] = frozenset({"allele_fraction", "prs_percentile"})

# Which kinds are **dense**, i.e. where a shared endpoint between adjacent bins is a *boundary* rather
# than an overlap (see the module docstring, RM35). Deliberately spelled out rather than aliased to
# `_CONTINUOUS_GAP_KINDS`: they answer two different questions about a measure — "can a hole be
# arbitrarily small?" and "can two bins touch?" — even though every kind so far answers both the same
# way. (It was literally the same object until 0.6, which made "spelled separately" a comment rather
# than a fact.) `activity_score` is in neither: it is consumer-summed onto a coarse grid, so bins do
# not touch and interior holes are not meaningful.
_DENSE_KINDS: frozenset[str] = frozenset({"allele_fraction", "prs_percentile"})

#: The tiling a kind is read under when no row declares one — **absence means this, never a value**,
#: which is what keeps `measure_tiling` additive: every module published before 0.6 keeps its exact
#: meaning. Derived from the three sets above rather than restated beside them, because those sets are
#: now *inputs to this default* and no longer decide a rule directly.
#:
#: `None` is a third answer and it is `activity_score`'s: neither dense nor gap-checked, i.e. a shared
#: endpoint is an overlap error *and* interior holes are not reported. The two-member vocabulary names
#: the two combinations an author can ask for; the third is a kind's default only, and a kind that
#: genuinely answered the two questions apart would need a third vocabulary member — additive, and a
#: deliberate act rather than a silent one, which is the whole reason the sets stay separate.
DEFAULT_MEASURE_TILING: dict[str, str | None] = {
    kind: (
        "continuous"
        if kind in _DENSE_KINDS or kind in _CONTINUOUS_GAP_KINDS
        else "quantised"
        if kind in _INTEGER_KINDS
        else None
    )
    for kind in sorted(VALID_MEASURE_KINDS)
}

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
    # Both bounds are float64, parsed from the decimal the author typed, while VCF 4.4 §1.3 makes
    # every `Float` a 32-bit value (RM62). Widening a float32 back to float64 is exact but not
    # value-preserving against that decimal, and **which way it moves depends on the decimal**: a
    # VCF `0.3` arrives as 0.300000011920928955…, above the authored bound, while a VCF `0.9`
    # arrives as 0.899999976158142…, below it. Compared naively, the first is missed by an inclusive
    # `measure_max` of `0.3` and the second falls out of the bottom of a bin starting at `0.9` — so
    # neither bound is the safe one, and "measure_min is harmless" holds only for the decimals that
    # round upward.
    #
    # The repair belongs to the comparison rather than to the cell, and it is to compare **in
    # float32**: narrow the bound the same way the measurement was narrowed
    # (`struct.unpack("f", struct.pack("f", bound))[0]`) and compare the two. float32 rounding is
    # monotone, so where the measurement really is a float32 read the comparison is exact whichever
    # way the decimal moved; against a float64-precise value it is a narrowing rather than an
    # identity, erring toward admitting the boundary, which is the safe direction for an inclusive
    # bound. Narrowing only the bound is not the rule, and that is the direction that loses a row —
    # against a measurement that never went through float32 it shrinks a downward-rounding bin and
    # drops a value the naive comparison would have matched. An epsilon is not the rule either: it
    # is a guess about magnitude where the representation is exactly known. The bounds stay decimal
    # because the DSL exists for the human and the parquet already carries the machine form.
    #
    # The rule is stated on `measure_max`'s description, not only in docs/SCHEMAS.md, because
    # `describe`/`requirements`/`reference` print these strings and that is what an author writes a
    # table from (D6-1).
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
            "continuous measure the next bin may start on it, and then that bin owns the value. "
            "Author the decimal you mean: a VCF Float is 32-bit, so a measured 0.3 reads as just "
            "above an authored 0.3 (and a measured 0.9 as just below). The comparison is done in "
            "float32 — narrow the bound the same way the measurement was narrowed — never with an "
            "epsilon."
        ),
    )
    measure_tiling: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("measure_tiling", VALID_MEASURE_TILINGS),
        description=(
            "How this measure's axis is divided: quantised (a grid — two bins may not share an "
            "endpoint, and a hole narrower than one step is not a hole) or continuous (dense — "
            "adjacent bins share an endpoint and the higher one owns it, and any positive hole is "
            "reported). Leave empty for the kind's default: quantised for copy_number and "
            "repeat_count, continuous for allele_fraction and prs_percentile, neither for "
            "activity_score. Constant within a bin group. A group left empty on a kind that defaults "
            "to quantised is read as continuous anyway if it carries a fractional bound — nothing on "
            "a grid of whole numbers can hold one — and the compiler says when it did that."
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
            "Optional VCF field the consumer extracts this measure from, best written with its "
            "namespace (e.g. FORMAT/REPCN, FORMAT/AF, INFO/CN|FORMAT/DS). A declarative pointer "
            "(field-name key, optionally qualified INFO/ or FORMAT/, optionally |-alternated), never "
            "an expression — an extraction hint; the measurement still comes from the consumer. A "
            "bare key means unqualified, and INFO and FORMAT define different fields under DP, AD, "
            "ADF, ADR, MQ, AF and CN."
        ),
    )
    source_element: str | None = Field(
        default=None,
        description=(
            "Which of `source_field`'s values this bin is measured against, when the field carries "
            "more than one for a record: largest|largest_alt|smallest|smallest_alt|sum|sum_alt|"
            "annotated_alt|reference. A named rule, never an index. 'More than one' covers both the "
            "spec's multi-valued cardinalities (VCF Number=A/R/G/P/.) and a caller that packs several "
            "into one cell — ExpansionHunter's REPCN reports both repeat alleles as 17/42 — since "
            "the encoding is the caller's business and which value the annotation means is the "
            "module's. On a Number=R field the reference is element zero, which is why each ranging "
            "rule comes in a pair: the bare name counts it, the _alt name does not. Leave empty when "
            "the field carries a single value."
        ),
    )

    pmid: str | None = Field(
        default=None,
        description=(
            "Optional PubMed id grounding THIS boundary — the literature the threshold is drawn "
            "from. Free-form like `StudyRow.pmid` (`9545397`, `[PMID: 9545397]`, a `;`-joined list). "
            "The bin row cites; studies.csv describes."
        ),
    )

    # `source_field`'s pointer grammar and `source_element`'s vocabulary are both validated on
    # `AuthoredModel` — they are shared with `VariantRow.callable_from`/`callable_element` and
    # `quality_from`/`quality_element`, and a validator used by more than one model lives on the base.

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str | None) -> str | None:
        # Shared with `StudyRow.pmid` (see `spec.validate_pmid_cell`); optional here, required there.
        return validate_pmid_cell(v, "pmid", required=False)

    @field_validator("measure_min", "measure_max")
    @classmethod
    def _validate_bound_finite(cls, v: float | None) -> float | None:
        return validate_finite(v, "measure bound")

    @field_validator("measure_tiling")
    @classmethod
    def _validate_measure_tiling(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_MEASURE_TILINGS, "measure_tiling")

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

    Optional `modifier_gene` plus a modifier dosage express a second locus read in context (SMN1
    phenotype depends on SMN2 copy number) — explicit named columns (multicolumn keying), never a
    tuple. The gene and the dosage are set together or both left null.

    **The dosage has two spellings and one meaning (RM55, 0.6).** `modifier_copy_number` is the
    float column; `modifier_cn` is the original `int` one, **deprecated in 0.6 and removed at 1.0**.
    VCF 4.4 §7.2 redefined `CN` to support non-integer copy numbers, so an `int` cannot hold a real
    modifier dosage — and retyping the column is major-only, which is what the companion exists to
    avoid. Everything reads `effective_modifier_copy_number`, including `_KEY_FIELDS`: a coalesced
    value is **one** spelling by the time grouping and dedup see it, so the key never holds two
    spellings of one number. Setting both is an error rather than a precedence rule.
    """

    _EXPECTED_KIND: ClassVar[str] = "copy_number"
    # The modifier is part of the key: SMN1=0 with SMN2=3 vs SMN2=1 are distinct bins, not an overlap.
    # It enters through the **effective** value rather than either column, so the two spellings of one
    # dosage cannot split a group (both grouping sites read `_KEY_FIELDS` with `getattr`, which
    # resolves the property).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene", "modifier_gene", "effective_modifier_copy_number",
    )

    gene: str = Field(description="Gene symbol whose copy number is binned, e.g. SMN1")
    modifier_gene: str | None = Field(
        default=None, description="Optional modifier locus read in context, e.g. SMN2"
    )
    modifier_cn: int | None = Field(
        default=None,
        description=(
            "DEPRECATED since 0.6, removed at 1.0 — use modifier_copy_number, which holds the "
            "fractional dosages VCF 4.4 §7.2 allows. Still read and still behaves exactly as before; "
            "set one or the other, never both. Copy number of the modifier locus (set with "
            "modifier_gene)."
        ),
    )
    modifier_copy_number: float | None = Field(
        default=None,
        description=(
            "Copy number of the modifier locus (set with modifier_gene), as a number that may be "
            "fractional — VCF 4.4 §7.2 redefined CN to allow one. Replaces the deprecated integer "
            "modifier_cn; setting both is an error."
        ),
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

    @field_validator("modifier_copy_number")
    @classmethod
    def _validate_modifier_finite(cls, v: float | None) -> float | None:
        return validate_finite(v, "modifier_copy_number")

    @property
    def effective_modifier_copy_number(self) -> float | None:
        """The modifier dosage, from whichever column carries it — the only reader of the pair.

        `is not None` rather than `or`, because **0 is a legal dosage**: SMN2 = 0 copies is a real
        row, and a truthiness fallback would silently read it as "unset" and then fall through to
        the deprecated column. (The boolean `effective_pathogenic`/`effective_benign` aliases are
        the precedent here, not the string `effective_direction`, which may use `or` because an
        empty string is not a legal value there.)

        A fixed point by construction — coalescing an already-coalesced value returns it unchanged
        (P7 idempotency).
        """
        if self.modifier_copy_number is not None:
            return self.modifier_copy_number
        if self.modifier_cn is not None:
            return float(self.modifier_cn)
        return None

    @model_validator(mode="after")
    def _validate_modifier(self) -> "CopyNumberRow":
        # Both set is a refusal, not a precedence rule: two spellings that can disagree, with a rule
        # for picking a winner, is the `vrs_id` desync shape.
        if self.modifier_cn is not None and self.modifier_copy_number is not None:
            raise ValueError(
                "modifier_cn and modifier_copy_number are two spellings of one dosage and exactly "
                "one may be set (modifier_cn is deprecated — prefer modifier_copy_number), got "
                f"modifier_cn={self.modifier_cn!r}, "
                f"modifier_copy_number={self.modifier_copy_number!r}"
            )
        if (self.modifier_gene is None) != (self.effective_modifier_copy_number is None):
            raise ValueError(
                "modifier_gene and the modifier copy number (modifier_copy_number, or the "
                "deprecated modifier_cn) are set together or both left null, got "
                f"modifier_gene={self.modifier_gene!r}, "
                f"modifier copy number={self.effective_modifier_copy_number!r}"
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
    #: The locus these bins are about. See `AuthoredModel.ALLELE_COLUMNS`.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "alts")
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

    variant_key: str | None = stamped_identity_field(
        "Which variant these bins are about (rsid, else a coordinate key that includes `alts`), or "
        "empty when the table names only a gene — the pre-0.5 shape, which groups exactly as it "
        "always did. Stamped at load from the columns the author supplied, and re-derived when the "
        "loader injects the module's build, because this key passes `alts` and can therefore mint a "
        "`ga4gh:VA.…`, which names its reference sequence by refget accession and must know the "
        "assembly or it will claim the wrong one (RM36). Part of `_KEY_FIELDS`, so all the identity "
        "shapes collapse to one notion of which variant a row is about. Compiler-managed."
    )
    authored_ident: list[str] | None = stamped_identity_field(
        "Which identity columns the author actually supplied, from {rsid, chrom, start, ref, alts}. "
        "Stamped at load like `variant_key`, so the compiler can fill a resolved coordinate into the "
        "parquet while `reverse_module` re-emits the authored shape — which is what keeps "
        "`content_signature` stable across a round-trip (RM43). Compiler-managed."
    )
    #: The one positional table whose key includes `alts` — it always did, and narrowing it now would
    #: re-key every published mtDNA module. See `AuthoredModel._KEY_INCLUDES_ALTS`.
    _KEY_INCLUDES_ALTS: ClassVar[bool] = True

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


def _fractional_values(row: MeasureBinRow) -> list[tuple[str, float]]:
    """The numbers on one row that a quantised reading cannot hold, in a fixed column order.

    `float.is_integer()` rather than `% 1` or an epsilon: the question is exactly *does this decimal
    name a grid point*, and the representation answers it. Non-finite values are already refused at
    load, so the guard here is belt-and-braces for a row built in code.
    """
    candidates: list[tuple[str, float | None]] = [
        ("measure_min", row.measure_min),
        ("measure_max", row.measure_max),
    ]
    if isinstance(row, CopyNumberRow):
        candidates.append(("modifier copy number", row.effective_modifier_copy_number))
    return [
        (name, float(v))
        for name, v in candidates
        if v is not None and math.isfinite(v) and not float(v).is_integer()
    ]


class TilingResolution(NamedTuple):
    """How one bin group's tiling was decided, and from what — so a caller can say which it was.

    `value` is the effective tiling the rules run under: `"continuous"`, `"quantised"`, or `None`
    for the kind (`activity_score`) that is neither. The other four members are the evidence:
    `declared` is the authored `measure_tiling` if any row carried one, `default` is what the kind
    would have been read under, `fractional` is the first value that no quantised reading can hold
    (with the column it sits in), and `disagreement` names two rows of one group that declared
    different tilings.
    """

    value: str | None
    declared: str | None
    default: str | None
    fractional: tuple[str, float] | None
    disagreement: tuple[str, str] | None

    @property
    def inferred(self) -> bool:
        """A fractional value **moved** the group off its kind's default — announce it."""
        return (
            self.declared is None
            and self.fractional is not None
            and self.value != self.default
        )

    @property
    def contradicted(self) -> bool:
        """An explicit `quantised` sits beside a value quantised semantics cannot hold."""
        return self.declared == "quantised" and self.fractional is not None


def resolve_tiling(grp: Sequence[MeasureBinRow]) -> TilingResolution:
    """The effective tiling for one bin group: declared, else inferred, else the kind's default.

    One resolution with two callers (`validate_bins` for the shared-endpoint and gap rules,
    `measurement_shape_warnings` for the RM55 finding), because a second copy would answer the same
    question against a different reading of the same rows.

    Order matters. **Agreement is checked first** — with two rows declaring different tilings there
    is no declared value to read — and it is *returned* rather than raised so the warning path cannot
    be crashed by a table the error path is about to refuse anyway. `None` beside a declared value is
    absence, not disagreement: the house algebra is three-valued and `None` is never a value.

    **The inference runs one way only.** Fractional-ness *implies* continuous — a value between two
    grid points is incompatible with quantised semantics — while integer-ness implies nothing, since
    `[0,1] [2,3]` is exactly what a continuous measure looks like when its author has only ever seen
    whole-number data. That asymmetry is why one direction can be automatic and the other has to be
    declared. An explicit `quantised` beside a fractional value **stands**: the author said something
    the data contradicts, and picking a winner silently is what a three-valued algebra exists to
    avoid, so the caller warns instead.

    **And it fires only against a `quantised` default, because that is the only reading a fractional
    value contradicts.** `quantised` asserts a step, which is what lets the gap rule tolerate a hole
    of one, and a fractional bound falsifies the assertion. The other two defaults assert nothing a
    fraction can falsify: `continuous` is already what the evidence would say, and `activity_score`'s
    `None` makes **no** claim about the grid at all — it reports no interior hole precisely because
    the score is consumer-summed onto a grid this schema does not know the step of. Reading a
    fractional activity score as continuous would therefore invent findings rather than reveal them:
    `reference_examples/cyp2d6_structural` states bins at 0.25/0.5/1.25/2.25, and under continuous
    rules those produce three "coverage gap" warnings for intervals no activity score can land in.
    The rule is *the data contradicts the reading*, not *the data is fractional*.
    """
    declared_rows = [r.measure_tiling for r in grp if r.measure_tiling is not None]
    disagreement: tuple[str, str] | None = None
    declared: str | None = None
    distinct = sorted(set(declared_rows))
    if len(distinct) > 1:
        disagreement = (distinct[0], distinct[1])
    elif distinct:
        declared = distinct[0]

    fractional: tuple[str, float] | None = None
    for row in grp:
        found = _fractional_values(row)
        if found:
            fractional = found[0]
            break

    default = DEFAULT_MEASURE_TILING.get(grp[0].measure_kind)
    if declared is not None:
        value = declared
    elif fractional is not None and default == "quantised":
        value = "continuous"
    else:
        value = default
    return TilingResolution(value, declared, default, fractional, disagreement)


def measurement_shape_warnings(rows: Sequence[MeasureBinRow]) -> list[str]:
    """What a table of quantised bins cannot express about its own source measurement (RM55/RM56).

    Both findings are stated against the *kind*, once per table, never per row or per group: the finding
    is about how the axis is divided, so a per-row line would be the same sentence repeated as many
    times as the author wrote bins. See the module docstring for the spec quotations.

    * **RM55** — VCF 4.4 makes both `CN` and `RUC` non-integral, so a fractional measurement *between
      two adjacent quantised bins* matches neither, and the coverage-gap check does not see the hole
      because under quantised tiling it only reports one wider than a step. Note the exposure is at
      the boundaries and on a sharp tiling, not everywhere: a fraction inside a wide range bin is
      answered fine, which is why this is stated against the kind rather than derived per bound.
      **Fires only where it is still true** — a kind VCF 4.4 types as fractional *and* at least one
      group of that kind whose effective tiling is `quantised`. A table that declares
      `measure_tiling: continuous`, or that carries a fractional bound and is read as continuous
      because of it, answers its own boundaries and is silent here. A group declaring `quantised`
      beside a fractional value keeps the declaration, so it keeps this finding too — which is the
      right reading: the author has said the axis is a grid and written a value that is not on it.
    * **RM56** — the same two fields travel with a confidence interval whose upper bound may be
      unbounded, so a measurement is an interval and can cross a threshold. Fires only where there is a
      threshold to cross: two or more resolved bins in one group. With a single bin there is nothing to
      span, and saying so anyway would be a finding about a table that does not have the problem. The
      count is of **bins**, and the message says only that — an earlier draft called them *adjacent*,
      which is a property this function never computes and which `[0,0]` beside `[50,60]` falsifies.
      Adjacency is also not what matters here: an interval crosses two bins whether or not there is a
      hole between them, and where there is one the hole is `validate_bins`' finding, not this one.
      Unaffected by tiling: an interval spans bins however the axis is divided.

    **Warnings in both modes, and deliberately never a `strict` error** — the `not_covered` /
    VRS-coverage class. RM56 needs a policy vocabulary that has not been designed, so no authored edit
    clears it at all. RM55 now *does* have an authored answer where the measure really is continuous,
    and still does not escalate, for a different reason: a genuinely quantised catalog count is
    **correct**, the default is quantised precisely so no published table is silently re-read, and
    refusing would refuse a correct module over a property of its source's type. `strict` means
    *reproducible artifact*, an unrelated axis (P5), and both tables reproduce exactly.
    """
    warnings: list[str] = []
    groups = _bin_groups(rows)
    kinds = {r.measure_kind for grp in groups.values() for r in grp} & set(_VCF_MEASURE_FIELDS)
    for kind in sorted(kinds):
        value_field, ci_field, spec_note = _VCF_MEASURE_FIELDS[kind]
        of_kind = {
            key: grp for key, grp in groups.items() if any(r.measure_kind == kind for r in grp)
        }
        if any(resolve_tiling(grp).value == "quantised" for grp in of_kind.values()):
            warnings.append(
                f"{kind} bins here are tiled as whole numbers, but the field a consumer reads the "
                f"measurement from ({value_field}) {FRACTIONAL_MEASURE_PHRASE}: {spec_note}. A "
                f"fractional measurement falling between two adjacent bins matches neither — "
                f"`[0,0] [1,1] [2,2] [3,∞)` is a legal quantised tiling and answers nothing at all "
                f"for a 2.4 — and the coverage-gap check does not report the hole, because under "
                f"quantised tiling it only flags one wider than a step. If this measure really is "
                f"continuous, say so: `measure_tiling: continuous` on these rows makes adjacent bins "
                f"able to share an endpoint (the higher one owns it) and makes any positive hole "
                f"reportable, and the bounds are already floats so nothing else has to change. A "
                f"group carrying a fractional bound is read as continuous without being asked. Left "
                f"as a grid, expect an answer only from a caller that rounds, and none from a "
                f"segment mean."
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


#: The fragment naming the one deprecated binning column, for the same reason the two phrases above
#: are named: a published `manifest.json` carries the prose and no field.
DEPRECATED_MODIFIER_PHRASE = "`modifier_cn` is deprecated"


def deprecation_warnings(rows: Sequence[MeasureBinRow]) -> list[str]:
    """Columns this release still reads and behaves exactly as before on, and an author should stop
    writing (Principle 3's two-step retirement: deprecate in a minor, remove at the next major).

    **Once per table, never once per row.** A copy-number table states one dosage per SMN2 copy
    number and the sentence is the same for every one of them; the repeated-warning rule and the
    embedded-count rule both apply, so the line carries no count and is emitted at most once for the
    rows handed over.

    The warning is **actionable**, which is the 0.6 cadence amendment's own condition for deprecating
    inside a minor: `modifier_copy_number` exists in this same release, holds everything the integer
    column held, and an author can move the value the day they read this.
    """
    if any(isinstance(r, CopyNumberRow) and r.modifier_cn is not None for r in rows):
        return [
            f"{DEPRECATED_MODIFIER_PHRASE} and is removed at 1.0: write the dosage in "
            f"`modifier_copy_number` instead, which is a float and can hold the non-integer copy "
            f"numbers VCF 4.4 §7.2 allows. It still reads and behaves exactly as before until then, "
            f"a whole number stays a whole number, and setting both columns is an error."
        ]
    return []


def validate_bins(rows: Sequence[MeasureBinRow]) -> list[str]:
    """Table-level coherence check for a set of binning rows of one kind (consumer round-2 C1).

    Rows are grouped by their explicit key columns (`_KEY_FIELDS`) plus `trait_efo_id`. Within a
    group of *resolved* rows — a consumer measurement selects at most one — inclusive ranges
    `[measure_min, measure_max]` (a null bound = -inf/+inf) **must not overlap**; an overlap would
    select two phenotypes for one measurement and raises ``ValueError``. Overlap *across* different
    `trait_efo_id` is allowed (pleiotropy — the same measurement legitimately binning to two traits).
    `unresolved` sentinel rows carry no range and are ignored.

    **Both rules read the group's effective tiling** (`resolve_tiling`), which since 0.6 is the
    declared `measure_tiling`, else the reading a fractional value forces, else the kind's default
    (RM55). Under `continuous` two bins are *touching*, which is the only way to tile a dense domain
    at all, so the error is `lo < prev_hi` and the shared value belongs to the higher bin, and any
    positive hole is reported. Under `quantised` adjacent bins sharing an endpoint really do both
    claim that grid point, so `lo <= prev_hi` is the error, and only a hole wider than one step is a
    hole. Under neither (`activity_score`, which is consumer-summed onto a coarse grid) a shared
    endpoint is an overlap and interior holes are not reported at all. Two bins sharing a *lower*
    bound refuse in every case: the boundary rule picks the greatest `measure_min` at or below the
    measurement, and there is nothing to pick between equals.

    Three findings come out of the tiling itself. Two rows of one group declaring **different**
    tilings raise — there is no group tiling to run the rules under. A tiling **inferred** from a
    fractional value emits an informational line naming the group, the value and the rules it
    applied, because an inference a reader cannot see is the thing this repo distrusts about
    inference. And an explicit `quantised` beside a fractional value warns that the data contradicts
    the declaration, while the declaration **stands** — neither side silently overrides the other.

    Returns a list of **warnings** (the two tiling notices above, plus interior coverage gaps: a
    value between two authored bins that matches no row). Edge coverage *below* the lowest bin (the
    "author the reference bin" contract, C1) is a consumer-contract matter, not auto-detected here —
    it would false-positive without a known domain floor. Callers decide what to do with the
    warnings (log, fail, ignore).
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
        tiling = resolve_tiling(grp)
        if tiling.disagreement is not None:
            first, second = tiling.disagreement
            raise ValueError(
                f"conflicting measure_tiling for key {group_key}: the rows of one bin group are "
                f"read under one tiling and these declare two, got {first!r} and {second!r} "
                f"(leave the column empty on the rows that do not state it — empty means the "
                f"kind's default, not a third answer)"
            )
        dense = tiling.value == "continuous"
        if tiling.inferred:
            column, value = tiling.fractional
            warnings.append(
                f"tiling inferred for key {group_key}: {column} is {value}, which no quantised "
                f"reading can hold, so this group was read as continuous — adjacent bins may share "
                f"an endpoint (the higher one owns it) and any positive hole is reported. Declare "
                f"`measure_tiling` on these rows to state it rather than have it read off the data."
            )
        elif tiling.contradicted:
            column, value = tiling.fractional
            warnings.append(
                f"measure_tiling for key {group_key} is declared 'quantised' and the data "
                f"contradicts it: {column} is {value}, which is not a grid point. The declaration "
                f"stands — nothing here overrides it either way — so these bins are still read "
                f"under the quantised rules and that value sits between two of them."
            )
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
            # One step wide is not a hole on a grid, and any hole at all is one on a dense axis. The
            # third state reports neither: `activity_score` is summed onto a coarse grid the schema
            # does not know the step of, so a hole there is not a claim this tier can make.
            if tiling.value == "continuous":
                is_gap = hole > 1e-9
            elif tiling.value == "quantised":
                is_gap = hole > 1 + 1e-9
            else:
                is_gap = False
            if is_gap:
                warnings.append(
                    f"coverage gap for key {group_key}: no bin covers ({prev_hi}, {lo})"
                )
    return warnings

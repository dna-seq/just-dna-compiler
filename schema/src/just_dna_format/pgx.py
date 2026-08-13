"""
PGx star-allele model (0.4 — see docs/CHANGELOG.md). Three definition/lookup tables that, with the
per-gene `ActivityPhenotypeRow` binning table (`binning.py`), form the four-table model validated
against the Aldy / Cyrius / PharmCAT stack:

1. `HaplotypeRow`      — junction: variant ↔ allele is many-to-many (one allele = many variants;
                         one variant recurs across many alleles). One row per (haplotype × variant).
2. `AlleleFunctionRow` — allele-unit → activity value + function category. The **star-string is the
                         canonical identity, stored verbatim** (`*4`, `*1x2`, `*36+*10`); copy
                         number / SV are attributes of the *cis* allele-unit, optional parsed
                         conveniences (the string is truth — PharmVar has no structured SV field).
3. `DiplotypeRow`      — the safe canonical fallback for structural/duplication/unphased cases,
                         keyed on a canonicalized haplotype pair.

Data-agnostic (design north star — see CLAUDE.md): the format supplies these tables; a **consumer**
star-allele caller supplies the phased diplotype + CN/SV calls and computes the phenotype. Copy number attaches
to a specific *cis* allele-unit, so `*2x2/*4` (AS 2 → NM) ≠ `*2/*4x2` (AS 1 → IM) — a consumer that
multiplies by *total* CN gets it wrong.
"""

import re
from typing import ClassVar

from pydantic import Field, ValidationInfo, field_validator, model_validator

from just_dna_format.base import AuthoredModel, derive_variant_key, vocabulary
from just_dna_format.vocab import (
    VALID_PHENOTYPE_CATEGORIES,
    VALID_RECOMMENDATION_STRENGTH,
    check_vocab,
    validate_allele,
    validate_finite,
    validate_phenotype_categories,
)

# Star-allele string, stored verbatim as the canonical identity. Permissive by design (the string
# is truth): a leading `*` then digits/letters and the sub-allele/duplication/tandem punctuation
# PharmVar uses (`.`, `+`, `x`/`×`), e.g. `*4`, `*4.001`, `*1x2`, `*36+*10`.
STAR_ALLELE_PATTERN: re.Pattern[str] = re.compile(r"^\*[0-9A-Za-z][0-9A-Za-z.\-+x×*]*$")
# A haplotype **name**. Deliberately permissive: a name is an identity, not a grammar.
#
# `STAR_ALLELE_PATTERN` below is the *star-allele* spelling and stays available for providers that
# genuinely draft star alleles (`pgx_draft` checks it at four sites). It is **not** the rule for
# naming a haplotype, and using it as one was an inconsistency rather than a policy: it was enforced
# on `AlleleFunctionRow.allele` and on neither `HaplotypeRow.haplotype_name` nor
# `DiplotypeRow.haplotype_a`/`haplotype_b`, so `e4` was legal in two of the three PGx tables and
# illegal in the third. APOE is the case that exposes it — ε2/ε3/ε4 are haplotypes by every meaning
# of the word and carry no `*` — and the 0.5.1 cross-table check made it worse: an author working
# around it with `*4` in one table and `e4` in another gets "used but not defined", with no legal
# spelling that satisfies both.
#
# The floor is only what a name cannot do without: be empty, or contain whitespace that would make
# two spellings of one allele look distinct. Rejecting those is a tightening on the two columns that
# had no rule at all, and a negligible one — neither could ever have named a real haplotype.
HAPLOTYPE_NAME_PATTERN: re.Pattern[str] = re.compile(r"^\S+$")


def validate_haplotype_name(value: str, field_name: str) -> str:
    """One rule for a haplotype name, shared by all three PGx tables so they cannot disagree."""
    if not HAPLOTYPE_NAME_PATTERN.match(value or ""):
        raise ValueError(
            f"{field_name} must be a non-empty haplotype name without whitespace (e.g. *4, e4, "
            f"\u03b54), got: {value!r}"
        )
    return value


# CPIC/PharmVar allele function categories (closed vocabulary, Principle 6).
VALID_FUNCTION_STATUS: frozenset[str] = frozenset(
    {
        "no_function",
        "decreased_function",
        "normal_function",
        "increased_function",
        "uncertain_function",
        "unknown_function",
    }
)


class HaplotypeRow(AuthoredModel):
    """Junction row: one defining variant of a named haplotype/allele. Many rows per haplotype;
    a variant recurs across many haplotypes (CYP2D6 rs1065852 is core-defining in 22 alleles).

    Inherits `AuthoredModel` (reserved-namespace guard + shared `rsid` validator)."""

    #: rsid, or a full coordinate. Mirrors `_validate_identification` below.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = (
        frozenset({"rsid"}),
        frozenset({"chrom", "start"}),
    )

    haplotype_name: str = Field(description="Named haplotype/allele, e.g. *4 or e4")
    rsid: str | None = Field(default=None, description="dbSNP id of the defining variant")
    # No `chromosome` vocabulary marker here on purpose: unlike `VariantRow.chrom`/`StudyRow.chrom`,
    # these two models run no chrom validator, so the set is not enforced. A marker claims "a
    # validator rejects anything outside this", and attaching one where nothing rejects would be the
    # same closedness drift `actionability` already had, pointing the other way. (That the PGx tables
    # do not validate `chrom` while the SNP core does is a real inconsistency, but closing it is a
    # validation *tightening* — Principle 3 — not a marker change.)
    chrom: str | None = Field(default=None, description="Chromosome (position-only variants)")
    start: int | None = Field(
        default=None,
        description="1-based position, VCF POS convention (position-only) — CPIC/PharmVar publish "
        "this convention and it is stored as-is; do not subtract one",
    )
    ref: str | None = Field(default=None, description="Reference allele (position-only)")
    allele: str = Field(
        description=(
            "The defining (variant) allele on this haplotype — bases, or a symbolic/structural "
            "allele carrying its length (e.g. <DEL:1500> for a whole-gene deletion)"
        )
    )
    gene: str | None = Field(default=None, description="Gene symbol, e.g. CYP2D6")
    #: `ref` (the locus) and `allele` (the defining variant). See `AuthoredModel.ALLELE_COLUMNS`.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "allele")

    @field_validator("allele")
    @classmethod
    def _validate_allele(cls, v: str) -> str:
        validate_allele(v, "allele")  # raises on a non-nucleotide; the value is a required str
        return v

    @field_validator("haplotype_name")
    @classmethod
    def _validate_haplotype_name(cls, v: str) -> str:
        return validate_haplotype_name(v, "haplotype_name")

    @model_validator(mode="after")
    def _validate_identification(self) -> "HaplotypeRow":
        if self.rsid is None and (self.chrom is None or self.start is None):
            raise ValueError(
                "a haplotype variant needs an identifier: rsid, or chrom + start"
            )
        return self


class AlleleFunctionRow(AuthoredModel):
    """Allele-unit → activity value + function category. The star-string `allele` is the required
    canonical key. `suballele` is optional-extra (Aldy's `Minor`, e.g. 1.001); the core star is the
    identity. `copy_number`/`sv_type`/`hybrid_orientation` are optional parsed conveniences of the
    *cis* allele-unit — the star-string remains truth.

    Inherits `AuthoredModel` (reserved-namespace guard)."""

    gene: str = Field(description="Gene symbol, e.g. CYP2D6")
    allele: str = Field(description="Star-allele string, verbatim canonical identity, e.g. *4")
    activity_value: float | None = Field(
        default=None, description="Per-allele activity value (e.g. *1=1.0, *10=0.25, *4=0)"
    )
    function_status: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("function_status", VALID_FUNCTION_STATUS),
        description="CPIC function category (VALID_FUNCTION_STATUS)",
    )
    suballele: str | None = Field(
        default=None, description="Optional finer sub-allele, e.g. 1.001 (core star is the key)"
    )
    copy_number: int | None = Field(
        default=None, description="Optional cis copy number of the allele-unit (e.g. *1x2 → 2)"
    )
    sv_type: str | None = Field(
        default=None, description="Optional parsed SV type (duplication/deletion/hybrid)"
    )
    hybrid_orientation: str | None = Field(
        default=None, description="Optional parsed tandem/hybrid orientation, e.g. *36+*10"
    )

    @field_validator("allele")
    @classmethod
    def _validate_allele(cls, v: str) -> str:
        # A name, not a star-allele grammar — see `HAPLOTYPE_NAME_PATTERN`. This column used to be the
        # only one of the three that demanded a leading `*`, which made APOE's ε alleles unstateable
        # here while being perfectly legal in the other two tables.
        return validate_haplotype_name(v, "allele")

    @field_validator("activity_value")
    @classmethod
    def _validate_activity_value(cls, v: float | None) -> float | None:
        return validate_finite(v, "activity_value")

    @field_validator("function_status")
    @classmethod
    def _validate_function_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_FUNCTION_STATUS, "function_status")


class DiplotypeRow(AuthoredModel):
    """Canonical fallback: a diplotype (haplotype pair) → phenotype. The pair is canonicalized
    (`haplotype_a <= haplotype_b`) so a lookup is order-independent; multiple rows per pair are
    allowed (a pleiotropic diplotype affecting several traits).

    Inherits `AuthoredModel` (reserved-namespace guard + shared `direction`/`clin_sig`/
    `evidence_level`/`trait_efo_id` validators)."""

    gene: str = Field(description="Gene symbol, e.g. CYP2D6")
    haplotype_a: str = Field(description="First haplotype of the pair (canonicalized a <= b)")
    haplotype_b: str = Field(description="Second haplotype of the pair")
    trait_efo_id: str | None = Field(
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s)"
    )
    direction: str | None = Field(default=None, description="Effect direction")
    clin_sig: str | None = Field(default=None, description="Clinical significance")
    phenotype: str | None = Field(default=None, description="Metabolizer phenotype, e.g. PM/NM")
    conclusion: str = Field(description="Human-readable interpretation for this diplotype")

    # ── Optional PharmGKB drug context (item 9) — a diplotype → drug response. Diplotype-keyed, so it
    # rides here; single-variant drug response lives in the separate PharmVariantRow. ──
    drug: str | None = Field(default=None, description="Drug the response is about, e.g. codeine")
    response: str | None = Field(default=None, description="Drug response / phenotype, free-form")
    evidence_level: str | None = Field(
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )
    # ── 0.5: CPIC's own grading of the prescribing action, a THIRD axis beside `response` (what to
    # do) and `evidence_level` (how well established the association is). CPIC classifies the
    # strength of the recommendation itself, and a well-evidenced association can still carry an
    # optional action — so the two grades are not interchangeable and must not share a column. ──
    recommendation_strength: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("recommendation_strength", VALID_RECOMMENDATION_STRENGTH),
        description=(
            "How firmly the guideline recommends the action: strong|moderate|optional|"
            "no_recommendation (CPIC's classification). Empty when the source did not classify."
        ),
    )

    # ── 0.5.1: RM29(b), the clinical-context cofactor. In `_TABLE_DUPE_KEYS`, so contexts coexist. ──
    #
    # **CPIC scopes a recommendation to a setting, and the settings disagree.** Clopidogrel carries
    # three (`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`) and the same Poor Metabolizer diplotype is
    # graded `strong` in one and `moderate` in another. Without a column for it, drafting all three
    # collided on the duplicate-row key and picking one asserted a clinical setting the author never
    # chose — which is why `draft --drug` used to refuse and list the choices. With the column, all
    # three are distinct rows and the *consumer* selects its setting at query time.
    #
    # **Not `population`, and the name matters.** `FrequencyRow.population` is an ancestry group with
    # its own validated vocabulary; this is not ancestry in any sense. Probed against CPIC's live
    # `recommendation` table (2,115 rows, 2026-08-03), the real values are indication (`CVI ACS PCI`,
    # `NVI`), age band (`pediatrics`, `adults`, `child >40kg_adult`), prior-treatment status
    # (`PHT naive`, `CBZ use >3mos`, `OXC naive`) and dose band (`<= 1g per day`) — with `general` on
    # 1,912 of them. Reusing `population` would put two unrelated axes under one name across two
    # tables, and would spend the name ancestry will want on `DiplotypeRow` later (P5).
    #
    # Open, not a vocabulary: CPIC's own set is open-ended and every other guideline body (DPWG, CPNDS)
    # scopes differently. A closed set here would reject the next authority's contexts.
    clinical_context: str | None = Field(
        default=None,
        description=(
            "Clinical setting this row applies to — indication, age band, prior treatment, dose "
            "(e.g. 'CVI ACS PCI', 'pediatrics', 'PHT naive'). Empty means the row is unscoped. "
            "Free text: guideline bodies scope differently and a closed set would reject the next "
            "one. Part of the row key, so contexts that disagree coexist and the consumer picks."
        ),
    )

    @field_validator("recommendation_strength")
    @classmethod
    def _validate_recommendation_strength(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RECOMMENDATION_STRENGTH, "recommendation_strength")

    @field_validator("clinical_context")
    @classmethod
    def _normalize_clinical_context(cls, v: str | None) -> str | None:
        # CPIC ships trailing whitespace in three of its sixteen values (`'CVI ACS PCI '`,
        # `'CBZ use >3mos '`, `'OXC use >3 mos'`), and the column is part of the row key: unstripped,
        # `'CVI ACS PCI '` and `'CVI ACS PCI'` are two rows describing one setting.
        if v is None:
            return None
        return v.strip() or None

    @field_validator("haplotype_a", "haplotype_b")
    @classmethod
    def _validate_haplotype_names(cls, v: str, info: ValidationInfo) -> str:
        return validate_haplotype_name(v, info.field_name or "haplotype")

    @model_validator(mode="after")
    def _canonicalize_pair(self) -> "DiplotypeRow":
        # Order-independent key: store the lexicographically smaller haplotype first, so a lookup
        # of (a, b) and (b, a) hit the same row.
        if self.haplotype_a > self.haplotype_b:
            self.haplotype_a, self.haplotype_b = self.haplotype_b, self.haplotype_a
        return self


class PharmVariantRow(AuthoredModel):
    """Single-variant PharmGKB drug-response annotation (item 9) — `pharm_variants.csv`.

    A **distinct rowtype** rather than columns on `VariantRow`, so the SNP core stays free of the
    drug-response domain: a module includes this table only when it carries drug annotations (one CSV
    = one concern; no empty `variants.csv`). Diplotype-keyed drug response instead rides on
    `DiplotypeRow`'s optional drug columns. A row maps a variant → a **drug** → a **response** +
    a PharmGKB **evidence level** (1A…4) — a different axis from a risk weight (why it is not a
    `VariantRow`).

    **`genotype` is part of the identity, not decoration (0.5).** A PharmGKB clinical annotation is
    published *per genotype*: the summary row names the variant and drug, and a child table gives one
    annotation per call — 4,618 of 5,113 annotations carry exactly three. They are not variations on
    one finding but distinct, sometimes opposed, ones: for rs4149056/simvastatin, CC and CT read
    "decreased response" while TT reads "increased". Modelling only (variant, drug) collapsed them,
    and the compiler's duplicate-row check rejected the real data outright — the axis is therefore in
    the dedup key `(variant_key, drug, genotype)`, mirroring the SNP core's (variant, genotype) rule.
    It is not derivable: nothing else on this row distinguishes the calls but free text.

    The grammar is the shared one on `AuthoredModel`, so a genotype means here exactly what it means
    on a `VariantRow`. Two shapes upstream deliberately do **not** land in this column: a
    haplotype-keyed annotation (`*1`, `*1xN`) belongs on `DiplotypeRow`, which already models a
    haplotype pair, and a symbolic allele (`C/del`, `del/del`) is RM5 and is skipped rather than
    coerced. PharmGKB writes a diploid call concatenated (`CC`); the canonical form here is sorted and
    slash-separated (`C/C`), since `CC` would otherwise read as a single two-base allele.

    Inherits `AuthoredModel` (reserved-namespace guard + shared `rsid`/`evidence_level`/
    `trait_efo_id`/`genotype` validators)."""

    rsid: str | None = Field(default=None, description="dbSNP id of the variant, e.g. rs9923231")
    # No `chromosome` vocabulary marker here on purpose: unlike `VariantRow.chrom`/`StudyRow.chrom`,
    # these two models run no chrom validator, so the set is not enforced. A marker claims "a
    # validator rejects anything outside this", and attaching one where nothing rejects would be the
    # same closedness drift `actionability` already had, pointing the other way. (That the PGx tables
    # do not validate `chrom` while the SNP core does is a real inconsistency, but closing it is a
    # validation *tightening* — Principle 3 — not a marker change.)
    chrom: str | None = Field(default=None, description="Chromosome (position-only variants)")
    start: int | None = Field(
        default=None,
        description="1-based position, VCF POS convention (position-only) — CPIC/PharmVar publish "
        "this convention and it is stored as-is; do not subtract one",
    )
    ref: str | None = Field(default=None, description="Reference allele (position-only)")
    gene: str | None = Field(default=None, description="Gene symbol, e.g. VKORC1")
    genotype: str | None = Field(
        default=None,
        description=(
            "Genotype the response applies to, canonical sorted form, e.g. C/T. An allele is bases, "
            "or a symbolic/structural allele carrying its length (<DEL:1500>/C)"
        ),
    )
    #: `ref` (the locus) and `genotype` (what the response applies to).
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "genotype")
    #: rsid, or a full coordinate. Mirrors `_validate_identification` below.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = (
        frozenset({"rsid"}),
        frozenset({"chrom", "start"}),
    )

    drug: str = Field(description="Drug the response annotation is about, e.g. warfarin")
    phenotype_category: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("phenotype_category", VALID_PHENOTYPE_CATEGORIES),
        description=(
            "What kind of effect this is (VALID_PHENOTYPE_CATEGORIES; multi-valued via [,;|]). "
            "Part of the identity — one variant+drug carries separate efficacy, toxicity and "
            "metabolism annotations."
        ),
    )
    annotation_id: str | None = Field(
        default=None,
        description=(
            "The source's own accession for this annotation, e.g. a PharmGKB clinical-annotation id. "
            "Optional, and the tie-break of last resort in the duplicate key — like `PgsRow.pgs_id`, "
            "a source accession is a legitimate identity for a curated record."
        ),
    )
    response: str | None = Field(
        default=None, description="Drug response / phenotype, free-form (e.g. 'reduced dose requirement')"
    )
    evidence_level: str | None = Field(
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )
    trait_efo_id: str | None = Field(
        default=None, description="Optional trait ontology id(s), for cross-module join"
    )
    conclusion: str = Field(description="Human-readable interpretation")

    @field_validator("phenotype_category")
    @classmethod
    def _validate_phenotype_category(cls, v: str | None) -> str | None:
        return validate_phenotype_categories(v)

    @property
    def variant_key(self) -> str:
        """Stable key matching VariantRow.variant_key (never resolved/expanded, so a property)."""
        return derive_variant_key(self.rsid, self.chrom, self.start, self.ref)

    @model_validator(mode="after")
    def _validate_identification(self) -> "PharmVariantRow":
        if self.rsid is None and (self.chrom is None or self.start is None):
            raise ValueError("a pharm variant needs an identifier: rsid, or chrom + start")
        return self

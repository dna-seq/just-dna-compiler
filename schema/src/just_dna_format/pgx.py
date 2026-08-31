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

from just_dna_format.base import AuthoredModel, since, stamped_identity_field, vocabulary
from just_dna_format.spec import validate_pmid_cell
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

    haplotype_name: str = Field(json_schema_extra=since("0.4.0"), description="Named haplotype/allele, e.g. *4 or e4")
    rsid: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="dbSNP id of the defining variant")
    # No `chromosome` vocabulary marker here on purpose: unlike `VariantRow.chrom`/`StudyRow.chrom`,
    # these two models run no chrom validator, so the set is not enforced. A marker claims "a
    # validator rejects anything outside this", and attaching one where nothing rejects would be the
    # same closedness drift `actionability` already had, pointing the other way. (That the PGx tables
    # do not validate `chrom` while the SNP core does is a real inconsistency, but closing it is a
    # validation *tightening* — Principle 3 — not a marker change.)
    chrom: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Chromosome (position-only variants)")
    start: int | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        ge=0,  # 1-based VCF POS; POS 0 is legal for a telomeric breakend (RM96, VCF_4_4_AUDIT s9)
        description="1-based position, VCF POS convention (position-only) — CPIC/PharmVar publish "
        "this convention and it is stored as-is; do not subtract one",
    )
    ref: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Reference allele (position-only)")
    alts: str | None = stamped_identity_field(
        "Alternate allele(s) at this locus, comma-separated — **filled by the compiler** from the "
        "injected resolution table, never authored (RM43). Distinct from `allele`, which is the one "
        "allele that *defines this haplotype*: a locus may offer several ALTs and the haplotype names "
        "one of them. It is here so `reverse_module` can rebuild `resolution.csv` from this parquet "
        "without dropping the allele list the injected table carried. Parquet-only; outside the key."
    , first_seen="0.6.0")
    allele: str = Field(json_schema_extra=since("0.4.0"), 
        description=(
            "The defining (variant) allele on this haplotype — bases, or a symbolic/structural "
            "allele carrying its length (e.g. <DEL:1500> for a whole-gene deletion)"
        )
    )
    gene: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Gene symbol, e.g. CYP2D6")
    # ── 0.7 (RM70): the callability claim, on the two PGx tables that name a locus. ──
    # `VariantRow` has carried `requires_callable` since 0.4, and a star-allele module could not state
    # it at all: CPIC's system assumes a position it did not call is reference, which is the whole
    # basis of a `*1` call, and the assumption lived only in the upstream's prose. `callable_from`
    # deliberately does **not** travel with it — the two are different axes ("a proof is required" vs
    # "here is where the proof lives"), and a row may require one without knowing where the evidence
    # sits. Optional, tri-state, outside the key.
    requires_callable: bool | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "True when a consumer must prove this position was callable before reading the *absence* "
            "of the defining allele as reference — i.e. before assigning the reference haplotype at "
            "this locus. False records the opposite claim, which is the one CPIC's star-allele system "
            "makes: an uncalled position is taken as reference. Empty says nothing either way, and is "
            "not False. Per locus rather than per module: one gene can hold a common allele defined "
            "by a single SNP beside one defined partly by a structural event, and the two do not have "
            "the same callability requirement."
        ),
    )
    variant_key: str | None = stamped_identity_field(
        "Frozen machine identity (rsid, else chrom:start:ref), stamped at load from the columns the "
        "author supplied and never re-derived. `HaplotypeRow` had none at all before 0.6, so "
        "`enrich._collect_subjects` and the compiler each derived one inline; materializing it to "
        "haplotypes.parquet gives a consumer the same key `weights.parquet` carries (RM43). "
        "Compiler-managed: not authored, never written back by reverse_module."
    , first_seen="0.6.0")
    authored_ident: list[str] | None = stamped_identity_field(
        "Which identity columns the author actually supplied, from {rsid, chrom, start, ref}. "
        "Stamped at load like `variant_key`, so the compiler can fill a resolved coordinate into the "
        "parquet while `reverse_module` re-emits the authored shape — which is what keeps "
        "`content_signature` stable across a round-trip. Compiler-managed."
    , first_seen="0.6.0")
    #: `ref` (the locus) and `allele` (the defining variant). See `AuthoredModel.ALLELE_COLUMNS`.
    #:
    #: **The compiler-filled `alts` above is deliberately NOT here**, on `ALLELE_COLUMNS`' own rule:
    #: it excludes the fact sidecars because "a check that drops rows must never rewrite injected
    #: facts", and this column *is* an injected fact — copied out of `resolution.csv` by RM43's fill.
    #: It is also a no-op in practice, since the symbolic check runs before that fill, and stating the
    #: reason is what keeps someone from "completing" the tuple later.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "allele")
    #: What makes two rows the same row. Declared rather than left implicit in the compiler's dupe
    #: lambda, which is what `_TABLE_DUPE_KEYS` now derives itself from — one source of truth, so a
    #: public `hints.key_fields` can name the columns without a consumer reading our source (S48).
    #: `variant_key` is the *stamped* identity (RM43): the key reads what the author wrote rather than
    #: whatever the resolution fill has since put in the cells.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("haplotype_name", "variant_key", "allele")
    #: A haplotype junction matches a variant at chrom:start:ref regardless of allele — the key the
    #: enricher has always derived for this table, kept byte-identical so nothing re-keys.
    _KEY_INCLUDES_ALTS: ClassVar[bool] = False

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

    #: What makes two rows the same row (see `HaplotypeRow._KEY_FIELDS`).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("gene", "allele")

    gene: str = Field(json_schema_extra=since("0.4.0"), description="Gene symbol, e.g. CYP2D6")
    allele: str = Field(json_schema_extra=since("0.4.0"), description="Star-allele string, verbatim canonical identity, e.g. *4")
    activity_value: float | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Per-allele activity value (e.g. *1=1.0, *10=0.25, *4=0)"
    )
    function_status: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("function_status", VALID_FUNCTION_STATUS), **since("0.4.0")},
        description="CPIC function category (VALID_FUNCTION_STATUS)",
    )
    suballele: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Optional finer sub-allele, e.g. 1.001 (core star is the key)"
    )
    copy_number: int | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Optional cis copy number of the allele-unit (e.g. *1x2 → 2)"
    )
    sv_type: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Optional parsed SV type (duplication/deletion/hybrid)"
    )
    hybrid_orientation: str | None = Field(json_schema_extra=since("0.4.0"), 
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

    **No `requires_callable` here, and the absence is the decision (RM70, 0.7).** The column landed on
    `HaplotypeRow` and `PharmVariantRow` because each of those rows *names a locus*, so a callability
    claim on one is about a position the row states — exactly what the column means on `VariantRow`.
    A diplotype names a star-allele **pair**, not a locus, so the same column here could only mean
    "the variants defining these two haplotypes were callable", which is a fact about `haplotypes.csv`
    rows restated one table over and free to drift the moment a definition is edited. One concept, one
    home. `extra="forbid"` on `AuthoredModel` is what enforces it, and a test pins the refusal.

    Inherits `AuthoredModel` (reserved-namespace guard + shared `direction`/`clin_sig`/
    `evidence_level`/`trait_efo_id` validators)."""

    #: What makes two rows the same row. `trait_efo_id` and `drug` keep a legitimately pleiotropic
    #: or multi-drug row from being a false duplicate; `clinical_context` joined in 0.5.1 (RM29b),
    #: because CPIC scopes one gene/drug pair to several settings whose recommendations disagree.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene", "haplotype_a", "haplotype_b", "trait_efo_id", "drug", "clinical_context",
    )

    gene: str = Field(json_schema_extra=since("0.4.0"), description="Gene symbol, e.g. CYP2D6")
    haplotype_a: str = Field(json_schema_extra=since("0.4.0"), description="First haplotype of the pair (canonicalized a <= b)")
    haplotype_b: str = Field(json_schema_extra=since("0.4.0"), description="Second haplotype of the pair")
    trait_efo_id: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s)"
    )
    direction: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Effect direction")
    clin_sig: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Clinical significance")
    phenotype: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Metabolizer phenotype, e.g. PM/NM")
    conclusion: str = Field(json_schema_extra=since("0.4.0"), description="Human-readable interpretation for this diplotype")

    # ── Optional PharmGKB drug context (item 9) — a diplotype → drug response. Diplotype-keyed, so it
    # rides here; single-variant drug response lives in the separate PharmVariantRow. ──
    drug: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Drug the response is about, e.g. codeine")
    response: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Drug response / phenotype, free-form")
    evidence_level: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )
    # ── 0.5: CPIC's own grading of the prescribing action, a THIRD axis beside `response` (what to
    # do) and `evidence_level` (how well established the association is). CPIC classifies the
    # strength of the recommendation itself, and a well-evidenced association can still carry an
    # optional action — so the two grades are not interchangeable and must not share a column. ──
    recommendation_strength: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("recommendation_strength", VALID_RECOMMENDATION_STRENGTH), **since("0.5.0")},
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
    clinical_context: str | None = Field(json_schema_extra=since("0.5.0"), 
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

    #: What makes two rows the same row — the full ClinPGx key, each member earned by real data
    #: (`@clinpgx-full-key`): PharmGKB publishes one annotation *per genotype*, and one
    #: variant+drug then carries several distinct annotations differing by category, with
    #: `annotation_id` the last-resort tie-break for those differing by neither.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (
        "variant_key", "drug", "genotype", "phenotype_category", "annotation_id",
    )

    rsid: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="dbSNP id of the variant, e.g. rs9923231")
    # No `chromosome` vocabulary marker here on purpose: unlike `VariantRow.chrom`/`StudyRow.chrom`,
    # these two models run no chrom validator, so the set is not enforced. A marker claims "a
    # validator rejects anything outside this", and attaching one where nothing rejects would be the
    # same closedness drift `actionability` already had, pointing the other way. (That the PGx tables
    # do not validate `chrom` while the SNP core does is a real inconsistency, but closing it is a
    # validation *tightening* — Principle 3 — not a marker change.)
    chrom: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Chromosome (position-only variants)")
    start: int | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        ge=0,  # 1-based VCF POS; POS 0 is legal for a telomeric breakend (RM96, VCF_4_4_AUDIT s9)
        description="1-based position, VCF POS convention (position-only) — CPIC/PharmVar publish "
        "this convention and it is stored as-is; do not subtract one",
    )
    ref: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Reference allele (position-only)")
    alts: str | None = stamped_identity_field(
        "Alternate allele(s) at this locus, comma-separated — **filled by the compiler** from the "
        "injected resolution table, never authored (RM43). It is carried as *data*, not identity: "
        "`variant_key` is still derived without it, so a pharm annotation keeps matching a variant at "
        "chrom:start:ref regardless of allele, and what the column buys is a direct VCF join, since a "
        "VCF row carries REF and ALT. Parquet-only: no CSV writer emits it."
    , first_seen="0.6.0")
    gene: str | None = Field(json_schema_extra=since("0.4.0"), default=None, description="Gene symbol, e.g. VKORC1")
    # ── 0.7 (RM70): the same callability claim as on `HaplotypeRow`, for the same reason — this is
    # the other PGx table that names a locus, so the claim is about a position the row states. It is
    # sharper here than anywhere, because this table is keyed on `genotype`: the row naming the
    # reference homozygote is unmatchable from a variant-only callset, where absence of an ALT record
    # is not evidence of that call. `callable_from` does not travel here either.
    #
    # **The two tables may disagree at one locus, and no check compares them.** That is not the
    # `DiplotypeRow` drift — the questions differ. A `HaplotypeRow` claim is about assigning the
    # *reference haplotype* there; this one is about matching *this row's genotype*. The reference
    # corpus holds exactly that shape (a haplotype default-to-reference beside a reference-homozygote
    # genotype needing a proof), so a checker asserting the two agree would refuse a correct module.
    # A test compiles the disagreeing pair clean, so the check is not added later. ──
    requires_callable: bool | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "True when a consumer must prove this position was callable before concluding that the "
            "sample carries this row's genotype — the reference-homozygote row is the case, since a "
            "variant-only callset emits no record for it and absence is not the call. False records "
            "that no such proof is needed, which is the ordinary case for a genotype carrying an "
            "alternate allele. Empty says nothing either way, and is not False."
        ),
    )
    genotype: str | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "Genotype the response applies to, canonical sorted form, e.g. C/T, or a single allele "
            "where the contig is hemizygous or haploid. An allele is bases, or a symbolic/structural "
            "allele carrying its length (<DEL:1500>/C). A pipe (C|T) is also accepted and records "
            "that the call was phased; with no phase-set column the order names no homolog, so it "
            "is phase recorded but unaddressable."
        ),
    )
    variant_key: str | None = stamped_identity_field(
        "Frozen machine identity (rsid, else chrom:start:ref), stamped at load from the columns the "
        "author supplied and never re-derived, so the compile-time coordinate fill cannot re-key the "
        "row. Materialized to pharm_variants.parquet so a consumer can join this table to "
        "weights.parquet without re-implementing the precedence rule (RM43). Compiler-managed: not "
        "authored, never written back by reverse_module."
    , first_seen="0.6.0")
    authored_ident: list[str] | None = stamped_identity_field(
        "Which identity columns the author actually supplied, from {rsid, chrom, start, ref}. "
        "Stamped at load like `variant_key`, so the compiler can fill a resolved coordinate into "
        "the parquet while `reverse_module` re-emits the authored shape — which is what keeps "
        "`content_signature` stable across a round-trip. Compiler-managed."
    , first_seen="0.6.0")
    #: `ref` (the locus) and `genotype` (what the response applies to). The compiler-filled `alts`
    #: stays out for the reason given on `HaplotypeRow.ALLELE_COLUMNS`: it is an injected fact.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "genotype")
    #: The key omits `alts` — see `stamped_identity_field` on `alts` above, and `_collect_subjects`.
    _KEY_INCLUDES_ALTS: ClassVar[bool] = False
    #: rsid, or a full coordinate. Mirrors `_validate_identification` below.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = (
        frozenset({"rsid"}),
        frozenset({"chrom", "start"}),
    )

    drug: str = Field(json_schema_extra=since("0.4.0"), description="Drug the response annotation is about, e.g. warfarin")
    phenotype_category: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("phenotype_category", VALID_PHENOTYPE_CATEGORIES), **since("0.5.0")},
        description=(
            "What kind of effect this is (VALID_PHENOTYPE_CATEGORIES; multi-valued via [,;|]). "
            "Part of the identity — one variant+drug carries separate efficacy, toxicity and "
            "metabolism annotations."
        ),
    )
    annotation_id: str | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "The source's own accession for this annotation, e.g. a PharmGKB clinical-annotation id. "
            "Optional, and the tie-break of last resort in the duplicate key — like `PgsRow.pgs_id`, "
            "a source accession is a legitimate identity for a curated record."
        ),
    )
    response: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Drug response / phenotype, free-form (e.g. 'reduced dose requirement')"
    )
    evidence_level: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )
    # ── 0.7 (RM132): the third citation site, beside `StudyRow.pmid` and `MeasureBinRow.pmid`. ──
    #
    # **A row cites when its claim is finer-grained than `studies.csv`'s key** — the rule RM47 settled
    # for the bins, reached here because this table has the same shape. `studies.csv` keys on
    # `(variant_key, pmid)`, so a study row attaches to a *variant*; this table keys on
    # `(variant_key, drug, genotype, phenotype_category, annotation_id)`, so one study row would
    # attach to every drug, genotype and phenotype category recorded for that variant at once. A
    # ClinPGx-drafted module carrying 1,482 drug-response rows had nowhere to ground any of them.
    #
    # **Not `evidence_level`, and the two sit side by side so the distinction stays visible** (P5):
    # that column carries somebody else's *grading of* the evidence and this one points at the
    # evidence. Nor the licence row's `source`/`dataset`, which state redistribution terms.
    #
    # **`provenance_quote` does not follow**, and the omission is deliberate rather than pending. The
    # binning side drew the same line: the row cites, and `studies.csv`/`literature.csv` describe —
    # which is what stops `StudyRow`'s whole provenance column set migrating here one column at a
    # time. A body of clinical claims this size is exactly where the question gets asked next.
    pmid: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "Optional PubMed id grounding THIS row's claim — the literature behind this drug/"
            "genotype response, which `studies.csv` cannot express because a study row attaches to "
            "the whole variant. Free-form like `StudyRow.pmid` (`9545397`, `[PMID: 9545397]`, a "
            "`;`-joined list). The pharm row cites; studies.csv and literature.csv describe. "
            "Separate from `evidence_level`, which grades evidence rather than pointing at it."
        ),
    )
    trait_efo_id: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="Optional trait ontology id(s), for cross-module join"
    )
    conclusion: str = Field(json_schema_extra=since("0.4.0"), description="Human-readable interpretation")

    @field_validator("phenotype_category")
    @classmethod
    def _validate_phenotype_category(cls, v: str | None) -> str | None:
        return validate_phenotype_categories(v)

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str | None) -> str | None:
        # The one grammar every citation pointer in the schema goes through (`spec.validate_pmid_cell`)
        # — optional here as on `MeasureBinRow`, required on `StudyRow`. Not lifted onto
        # `AuthoredModel`: the base would then reach `StudyRow.pmid`, where the rule is `required=True`,
        # and a shared validator that has to be overridden by the model it is loosest for is a
        # requiredness change (P8) wearing a refactor's clothes.
        return validate_pmid_cell(v, "pmid", required=False)

    @model_validator(mode="after")
    def _validate_identification(self) -> "PharmVariantRow":
        if self.rsid is None and (self.chrom is None or self.start is None):
            raise ValueError("a pharm variant needs an identifier: rsid, or chrom + start")
        return self

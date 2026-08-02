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
from typing import Optional

from pydantic import Field, field_validator, model_validator

from just_dna_format.base import AuthoredModel, derive_variant_key
from just_dna_format.vocab import (
    check_vocab,
    validate_allele,
    validate_finite,
    validate_phenotype_categories,
)

# Star-allele string, stored verbatim as the canonical identity. Permissive by design (the string
# is truth): a leading `*` then digits/letters and the sub-allele/duplication/tandem punctuation
# PharmVar uses (`.`, `+`, `x`/`×`), e.g. `*4`, `*4.001`, `*1x2`, `*36+*10`.
STAR_ALLELE_PATTERN: re.Pattern[str] = re.compile(r"^\*[0-9A-Za-z][0-9A-Za-z.\-+x×*]*$")
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

    haplotype_name: str = Field(description="Named haplotype/allele, e.g. *4 or e4")
    rsid: Optional[str] = Field(default=None, description="dbSNP id of the defining variant")
    chrom: Optional[str] = Field(default=None, description="Chromosome (position-only variants)")
    start: Optional[int] = Field(default=None, description="0-based position (position-only)")
    ref: Optional[str] = Field(default=None, description="Reference allele (position-only)")
    allele: str = Field(description="The defining (variant) allele on this haplotype, nucleotides")
    gene: Optional[str] = Field(default=None, description="Gene symbol, e.g. CYP2D6")

    @field_validator("allele")
    @classmethod
    def _validate_allele(cls, v: str) -> str:
        validate_allele(v, "allele")  # raises on a non-nucleotide; the value is a required str
        return v

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
    activity_value: Optional[float] = Field(
        default=None, description="Per-allele activity value (e.g. *1=1.0, *10=0.25, *4=0)"
    )
    function_status: Optional[str] = Field(
        default=None, description="CPIC function category (VALID_FUNCTION_STATUS)"
    )
    suballele: Optional[str] = Field(
        default=None, description="Optional finer sub-allele, e.g. 1.001 (core star is the key)"
    )
    copy_number: Optional[int] = Field(
        default=None, description="Optional cis copy number of the allele-unit (e.g. *1x2 → 2)"
    )
    sv_type: Optional[str] = Field(
        default=None, description="Optional parsed SV type (duplication/deletion/hybrid)"
    )
    hybrid_orientation: Optional[str] = Field(
        default=None, description="Optional parsed tandem/hybrid orientation, e.g. *36+*10"
    )

    @field_validator("allele")
    @classmethod
    def _validate_allele(cls, v: str) -> str:
        if not STAR_ALLELE_PATTERN.match(v):
            raise ValueError(f"allele must be a star-allele string like *4 or *36+*10, got: {v!r}")
        return v

    @field_validator("activity_value")
    @classmethod
    def _validate_activity_value(cls, v: Optional[float]) -> Optional[float]:
        return validate_finite(v, "activity_value")

    @field_validator("function_status")
    @classmethod
    def _validate_function_status(cls, v: Optional[str]) -> Optional[str]:
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
    trait_efo_id: Optional[str] = Field(
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s)"
    )
    direction: Optional[str] = Field(default=None, description="Effect direction")
    clin_sig: Optional[str] = Field(default=None, description="Clinical significance")
    phenotype: Optional[str] = Field(default=None, description="Metabolizer phenotype, e.g. PM/NM")
    conclusion: str = Field(description="Human-readable interpretation for this diplotype")

    # ── Optional PharmGKB drug context (item 9) — a diplotype → drug response. Diplotype-keyed, so it
    # rides here; single-variant drug response lives in the separate PharmVariantRow. ──
    drug: Optional[str] = Field(default=None, description="Drug the response is about, e.g. codeine")
    response: Optional[str] = Field(default=None, description="Drug response / phenotype, free-form")
    evidence_level: Optional[str] = Field(
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )

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

    rsid: Optional[str] = Field(default=None, description="dbSNP id of the variant, e.g. rs9923231")
    chrom: Optional[str] = Field(default=None, description="Chromosome (position-only variants)")
    start: Optional[int] = Field(default=None, description="0-based position (position-only)")
    ref: Optional[str] = Field(default=None, description="Reference allele (position-only)")
    gene: Optional[str] = Field(default=None, description="Gene symbol, e.g. VKORC1")
    genotype: Optional[str] = Field(
        default=None,
        description="Genotype the response applies to, canonical sorted form, e.g. C/T",
    )
    drug: str = Field(description="Drug the response annotation is about, e.g. warfarin")
    phenotype_category: Optional[str] = Field(
        default=None,
        description=(
            "What kind of effect this is (VALID_PHENOTYPE_CATEGORIES; multi-valued via [,;|]). "
            "Part of the identity — one variant+drug carries separate efficacy, toxicity and "
            "metabolism annotations."
        ),
    )
    annotation_id: Optional[str] = Field(
        default=None,
        description=(
            "The source's own accession for this annotation, e.g. a PharmGKB clinical-annotation id. "
            "Optional, and the tie-break of last resort in the duplicate key — like `PgsRow.pgs_id`, "
            "a source accession is a legitimate identity for a curated record."
        ),
    )
    response: Optional[str] = Field(
        default=None, description="Drug response / phenotype, free-form (e.g. 'reduced dose requirement')"
    )
    evidence_level: Optional[str] = Field(
        default=None, description="PharmGKB clinical-annotation evidence level (1A..4)"
    )
    trait_efo_id: Optional[str] = Field(
        default=None, description="Optional trait ontology id(s), for cross-module join"
    )
    conclusion: str = Field(description="Human-readable interpretation")

    @field_validator("phenotype_category")
    @classmethod
    def _validate_phenotype_category(cls, v: Optional[str]) -> Optional[str]:
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

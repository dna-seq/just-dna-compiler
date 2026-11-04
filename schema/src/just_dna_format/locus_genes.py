"""The two study-locus tables: which gene a GWAS locus points at, and which molecular trait shares it (0.8, RM333).

`locus_to_gene.csv` and `colocalisations.csv` are derived-fact sidecars filled by `just-dna-enricher`'s
`opentargets enrich` pass from the Open Targets Platform snapshot lane. They are the **inputs** to an
effector-gene judgement and never the judgement itself: the format does not author or compute a
causal or effector confidence label (RM323's cut). A module that wants one states its rubric over
these columns, and a corrected input goes in `overrides.csv`.

**Both are keyed on the study locus, Open Targets' own grain, and on the module variant.** A study locus
is one credible set from one study (`studyLocusId`, a hash the source mints). One variant sits in several
of them, one per study that fine-mapped the region, and each names its own candidate genes with its own
score, so a row per variant would have to pick a study on the module's behalf. Several study loci per
variant are kept and counted, never collapsed to a winner (`@multiplicity-is-a-finding`).

**Members, not lead-only (decided 2026-11-04).** A row exists for every credible set a module variant is a
**member** of, whether or not it leads it: HFE C282Y (rs1800562) sits in 82 GWAS sets of the 26.09 release
and leads none, so a lead-only table would be empty for the module the lane exists for. Two module
variants in one set each get the set's rows, so `variant_key` is in both keys. The member's own weight in
the set is its posterior on `gwas_effects.csv` (RM239), not a column here.

**Why coloc is a second table and not columns on the first.** A colocalisation pairs one GWAS study
locus with one molecular-QTL study locus, and the gene and tissue sit on the right-hand study. The
release measured 2026-11-04 (`probes/LANES_0_8.md` § built) has many right-hand loci per
`(study locus, gene)` pair (one per tissue and per QTL kind), so `h4`/`clpp` on the L2G row would
have to pick a tissue. The pair is kept at the source's own grain instead, and the gene it names is
a column a consumer joins on.

**`variant_key` is the module's own key for the member variant**, the subject the pass asked about, so
these rows join the module's weights directly. The source's own spelling of the set's lead
(`19_44908684_T_C`, or an `OTVAR_…` hash for a long allele) is kept beside it as `lead_variant_id`
for tracing back to the release, and is never parsed; it names another variant whenever the module's
variant is a member and not the lead.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import RECOMMENDED_QTL_STUDY_TYPES, validate_finite

# Fact columns feeding `integrity.locus_to_gene_signature`: everything but the provenance columns
# (`source`/`fetched_at`), so a hand-curated and a pass-filled table stating the same scores hash equal.
# `dataset` is inside for the reason it is everywhere else: Open Targets retrains L2G every release, and
# the same pair scored by a different model is a different fact.
LOCUS_TO_GENE_FACT_FIELDS: tuple[str, ...] = (
    "study_locus_id",
    "gene_id",
    "variant_key",
    "lead_variant_id",
    "study_accession",
    "l2g_score",
    "dataset",
)

# Fact columns feeding `integrity.colocalisation_signature`. `right_gene_id` and `right_biosample_id`
# are inside although they are looked up from the right-hand study rather than read off the coloc row:
# they are what the pair is ABOUT, and a coloc against a different tissue is a different claim.
COLOCALISATION_FACT_FIELDS: tuple[str, ...] = (
    "study_locus_id",
    "right_study_locus_id",
    "variant_key",
    "study_accession",
    "right_study_id",
    "right_study_type",
    "right_gene_id",
    "right_biosample_id",
    "method",
    "h4",
    "clpp",
    "colocalising_variants",
    "dataset",
)


def _required_text(value: str, name: str, why: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{name} must not be empty: {why}")
    return value


class LocusToGeneRow(BaseModel):
    """One `(study locus, gene)` pair and the locus-to-gene score the source gave it.

    Standalone (not an `AuthoredModel`) for the reason every fact row is: machine-produced reference
    fact, not an authored annotation, with `extra="forbid"` so a typo'd column is caught.
    """

    #: The source's grain, `(study locus, gene)`, per module variant in the set: a study locus names
    #: several candidate genes, each scored, and several module variants can be members of one set.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("study_locus_id", "gene_id", "variant_key")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    study_locus_id: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The source's id for one credible set from one study (Open Targets' `studyLocusId`, a "
            "32-hex hash). Part of this row's identity. Opaque: it is a join key back to the release, "
            "and it changes when the source re-runs fine-mapping."
        ),
    )
    gene_id: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "Ensembl gene accession of the candidate gene (`ENSG…`), as the source publishes it. "
            "Part of the identity. No symbol: the source's L2G table carries none, and a "
            "symbol looked up elsewhere would be another source's claim on this row."
        ),
    )
    variant_key: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The module's key for the variant the pass asked about, a member of this credible set "
            "(its lead or not): part of the identity, so two module variants in one set each get "
            "the set's rows. Joins `weights.parquet.variant_key` directly; the member's own weight "
            "in the set is its `gwas_effects.csv` posterior."
        ),
    )
    lead_variant_id: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The source's own spelling of the credible set's lead variant (`19_44908684_T_C`, or an "
            "`OTVAR_…` hash for a long allele), kept for tracing back to the release. Names another "
            "variant when `variant_key` is a member and not the lead. Never parsed: the alleles "
            "come from the source's columns, not from this id."
        ),
    )
    study_accession: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The study the credible set belongs to (`GCST…` or a FinnGen id), the same column "
            "`gwas_effects.csv` carries, so the two tables join on `(variant_key, study_accession)`."
        ),
    )

    # ── the score ──
    l2g_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        json_schema_extra=since("0.8.0"),
        description=(
            "Open Targets' locus-to-gene score for this pair, 0 to 1, verbatim. A model output, "
            "retrained each release, and comparable only within one `dataset`. The method is in the "
            "name because a score from another gene-prioritisation method is on another scale and "
            "would be a column of its own. Not an effector call: what score makes a gene the effector "
            "is the module's rubric, never this table's."
        ),
    )
    dataset: str = Field(
        json_schema_extra=since("0.8.0"),
        description="Which release this row came from, e.g. 'opentargets_26.09'. A FACT: L2G is retrained per release.",
    )

    # ── provenance (EXCLUDED from locus_to_gene_signature) ──
    source: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The licensed data source: opentargets|manual (open). Joins `sources.csv.source`.",
    )
    fetched_at: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="ISO-8601 UTC timestamp when a pass wrote this row; the release is `dataset`.",
    )

    @field_validator("study_locus_id")
    @classmethod
    def _check_study_locus_id(cls, v: str) -> str:
        return _required_text(v, "study_locus_id", "it is part of this row's identity")

    @field_validator("gene_id")
    @classmethod
    def _check_gene_id(cls, v: str) -> str:
        return _required_text(v, "gene_id", "it is part of this row's identity")

    @field_validator("variant_key")
    @classmethod
    def _check_variant_key(cls, v: str) -> str:
        return _required_text(v, "variant_key", "it is the join back to the module")

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        return _required_text(v, "dataset", "it names the release the score came from")

    @field_validator("l2g_score")
    @classmethod
    def _check_finite(cls, v: float | None) -> float | None:
        return validate_finite(v, "l2g_score")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        return normalize_utc_timestamp(v)


class ColocalisationRow(BaseModel):
    """One colocalisation between a GWAS study locus the module's variant is a member of and a molecular-QTL study locus."""

    #: The source's grain, one row per (left, right) study-locus pair, per module variant in the left set.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("study_locus_id", "right_study_locus_id", "variant_key")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    study_locus_id: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The GWAS credible set on the left of the pair (`leftStudyLocusId`), the same id "
            "`locus_to_gene.csv` keys on. Part of this row's identity."
        ),
    )
    right_study_locus_id: str = Field(
        json_schema_extra=since("0.8.0"),
        description="The molecular-QTL credible set on the right of the pair. Part of the identity.",
    )
    variant_key: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The module's key for the variant the pass asked about, a member of the left credible set "
            "(its lead or not), as in `locus_to_gene.csv`. Part of the identity."
        ),
    )
    study_accession: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The GWAS study on the left (`GCST…` or a FinnGen id).",
    )

    # ── what the right side is about ──
    right_study_id: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The source's id of the right-hand study (one gene in one tissue for an eQTL study).",
    )
    right_study_type: str | None = Field(
        default=None,
        json_schema_extra={
            **vocabulary("qtl_study_type", RECOMMENDED_QTL_STUDY_TYPES, closed=False),
            **since("0.8.0"),
        },
        description=(
            "What the right-hand study measured, verbatim: `eqtl`, `sqtl`, `pqtl`, `tuqtl`, `sceqtl`. "
            "Open, because the source adds kinds between releases."
        ),
    )
    right_gene_id: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "Ensembl gene accession the right-hand study measured (`ENSG…`), looked up from that "
            "study. The gene a consumer joins against `locus_to_gene.csv.gene_id`. Null when the "
            "source's study names none."
        ),
    )
    right_biosample_id: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The tissue or cell type of the right-hand study as an ontology id (`UBERON_…`, `CL_…`), "
            "verbatim. Why this is a row per pair: one gene colocalises in several tissues."
        ),
    )

    # ── the statistics ──
    method: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The source's method label, verbatim (`COLOC_PIP_ECAVIAR` in 26.09, one run producing "
            "both statistics below). A statistic means nothing without the method that computed it."
        ),
    )
    h4: float | None = Field(
        default=None,
        ge=0,
        le=1,
        json_schema_extra=since("0.8.0"),
        description=(
            "COLOC's posterior that both traits share one causal variant. Kept beside `clpp`, never "
            "replaced by it: the two disagree often enough that picking one is a judgement "
            "(probes/LANES_0_8.md § 1.5)."
        ),
    )
    clpp: float | None = Field(
        default=None,
        ge=0,
        le=1,
        json_schema_extra=since("0.8.0"),
        description="eCAVIAR's colocalisation posterior probability for the pair, verbatim.",
    )
    colocalising_variants: int | None = Field(
        default=None,
        ge=0,
        json_schema_extra=since("0.8.0"),
        description="How many variants the two credible sets share, as the source counts them.",
    )
    dataset: str = Field(
        json_schema_extra=since("0.8.0"),
        description="Which release this row came from, e.g. 'opentargets_26.09'.",
    )

    # ── provenance (EXCLUDED from colocalisation_signature) ──
    source: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The licensed data source: opentargets|manual (open). Joins `sources.csv.source`.",
    )
    fetched_at: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="ISO-8601 UTC timestamp when a pass wrote this row; the release is `dataset`.",
    )

    @field_validator("study_locus_id", "right_study_locus_id")
    @classmethod
    def _check_ids(cls, v: str, info) -> str:
        return _required_text(v, info.field_name or "study_locus_id", "it is part of this row's identity")

    @field_validator("variant_key")
    @classmethod
    def _check_variant_key(cls, v: str) -> str:
        return _required_text(v, "variant_key", "it is the join back to the module")

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        return _required_text(v, "dataset", "it names the release the statistics came from")

    @field_validator("h4", "clpp")
    @classmethod
    def _check_finite(cls, v: float | None, info) -> float | None:
        return validate_finite(v, info.field_name or "h4")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        return normalize_utc_timestamp(v)

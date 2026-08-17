"""The source-independent GWAS-effect table (0.6, RM90).

`gwas_effects.csv` is the seventh derived-fact sidecar. It records, per published association, the
effect size a GWAS reported for an allele — the magnitude, **the unit it is in**, which allele it is
relative to, the p-value, and the study it came from. Filled by `just-dna-enricher`'s GWAS Catalog
pass, consumed and hashed by the compiler, never fetched by it.

**Why it exists.** A consumer reported that authored `weight` values "construct nonsense" across a
corpus: the column has no unit, every module means something different by it, and published GWAS
effects are often better grounded than a hand-set curator score (S36). The obvious repair — have the
enricher fill `weight` where the authored cell is null — is barred, and not narrowly:
MODULE_LIFECYCLE § Stage 3 names `weight`/`direction`/`effect_size` in the cells no tool fills, and
every check in the tier reports rather than repairs. A null `weight` means *the author has not
modelled this*, which is the house algebra, not a hole to backfill.

So the effect goes in its own table, and `weights.parquet.weight` stays 100% authored. A module
carrying both holds an authored opinion **and** a machine-transcribed reference fact — exactly what it
already does with `frequencies` and `gene_metrics`, and nobody calls a module with a gnomAD frequency
table two modules.

**`effect_unit` is the point of the table, not a detail.** The GWAS Catalog's own payload, probed for
`rs4149056` on 2026-08-17, returns `betaUnit` `"umol/l"` on one association and `"unit"` on two others
for the same variant. A beta of 0.05 umol/l and a beta of 0.30 "unit" are not on one scale, and any
table that stored the magnitude without the unit would reproduce, one layer down, the exact defect
S36 is about.

**One row is one published association**, keyed by the archive's own `association_id`. Not one row
per variant: rs4149056 alone carries dozens, across different traits, populations and papers, and
collapsing them would pick a trait on the author's behalf.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    RECOMMENDED_EFFECT_MEASURES,
    VALID_EFFECT_DIRECTIONS,
    VALID_RESOLUTION_STATUS,
    check_vocab,
    validate_finite,
)

# Fact columns feeding `integrity.gwas_effect_signature` — everything but the provenance columns
# (`source`/`status`/`fetched_at`) and `trait`, so a hand-curated and a Catalog-filled table carrying
# the same associations hash equal.
#
# **`trait` is OUTSIDE and `trait_efo_id` is inside**, the same call `gene_validity.py` makes for
# `disease_label`: the reported trait is free prose that the Catalog re-words between releases
# ("Type 2 diabetes", "Type II diabetes mellitus") for one unchanged ontology term. The label
# describes the association for a human reading the CSV; the EFO id *is* the fact.
#
# **`rsid` is INSIDE, and the `CLINICAL_ASSERTION_FACT_FIELDS` exclusion deliberately does not
# transfer.** There the archive lookup is allele-exact on a coordinate and returns no rsID at all, so
# the column is filled from the module's own `resolution.csv` and would make two modules holding the
# same records hash differently. Here the rsID is what the Catalog is *queried by* and what it echoes
# back inside `riskAlleleName` (`rs4149056-C`), so it is part of what the source said. Copying the
# exclusion because it is the newer precedent would have been the wrong reading of it.
#
# `dataset` is inside for the reason it is everywhere else — the Catalog re-curates, and an
# association whose effect size moved between releases is a different fact.
GWAS_FACT_FIELDS: tuple[str, ...] = (
    "association_id",
    "variant_key",
    "rsid",
    "effect_allele",
    "effect_size",
    "effect_measure",
    "effect_unit",
    "effect_direction",
    "standard_error",
    "confidence_interval",
    "risk_allele_frequency",
    "p_value",
    "p_value_num",
    "trait_efo_id",
    "pmid",
    "study_accession",
    "ancestry",
    "dataset",
)


class GwasEffectRow(BaseModel):
    """One published GWAS association: the magnitude, its unit, and the allele it is relative to.

    Standalone (not an `AuthoredModel`) for the same reason every fact row is — machine-produced
    reference fact, not an authored annotation — with `extra="forbid"` so a typo'd column is caught
    rather than silently dropped.

    **This row carries no coordinates, and that is deliberate.** The Catalog's association payload has
    none: they live on the SNP object behind a link, and a coordinate copied from the module's own
    `resolution.csv` would be the module's fact rather than the source's. `variant_key` joins it to the
    weights rows; `rsid` is what the archive itself names.
    """

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    association_id: str = Field(
        description=(
            "The Catalog's own association id. Identity, the same source-accession pattern as "
            "`PgsRow.pgs_id` and `PharmVariantRow.annotation_id` — one variant carries dozens of "
            "associations and only the archive's id tells them apart."
        )
    )
    variant_key: str = Field(
        description="Coordinate-derived identity of the locus (matches the post-expansion weights key)"
    )
    rsid: str | None = Field(
        default=None,
        description=(
            "dbSNP identifier, as the Catalog itself names it. Position-level, so it names the locus "
            "rather than the allele — which is `effect_allele`'s job."
        ),
    )

    # ── the effect ──
    effect_allele: str | None = Field(
        default=None,
        description=(
            "The allele `effect_size` is stated relative to, parsed from the Catalog's "
            "`riskAlleleName` (`rs4149056-C` → `C`). **Null when the source wrote `-?`**, which it "
            "does often — 2 of the first 3 rs4149056 associations — meaning the study did not "
            "establish which allele carries the effect. An effect size relative to an unknown allele "
            "cannot be used as a weight, so the row is kept and counted rather than dropped: that is "
            "a fact a consumer needs, not a defect to hide."
        ),
    )
    effect_size: float | None = Field(
        default=None,
        description="The reported magnitude. Its meaning is `effect_measure`; its scale is `effect_unit`.",
    )
    effect_measure: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("effect_measure", RECOMMENDED_EFFECT_MEASURES, closed=False),
        description=(
            "What kind of magnitude it is — `OR` or `beta` in practice. The Catalog keeps these in "
            "two mutually exclusive fields (`orPerCopyNum`, `betaNum`) rather than the single "
            "ambiguous 'OR or BETA' column its download TSV uses, so this maps cleanly. Open, "
            "matching `StudyRow.effect_measure`."
        ),
    )
    effect_unit: str | None = Field(
        default=None,
        description=(
            "The unit a `beta` is in, verbatim from the source — 'umol/l', 'unit', 'cm'. **Kept "
            "verbatim including the uninformative ones**: 'unit' really is all many studies report, "
            "and recording that honestly is the difference between a scale a consumer can reason "
            "about and one it cannot. Null for an `OR`, which is dimensionless."
        ),
    )
    effect_direction: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("effect_direction", VALID_EFFECT_DIRECTIONS),
        description=(
            "Whether the effect allele increases or decreases the measured trait. **Not clinical "
            "direction** — `VariantRow.direction` is protective|risk|neutral|unknown and answers a "
            "different question, since increasing a trait may be good, bad or neither. Folding the "
            "two together would overload one field with two axes (Principle 5); the source keeps "
            "them apart (`betaDirection`) and so does this."
        ),
    )
    standard_error: float | None = Field(
        default=None, ge=0, description="Standard error of the effect size, when the study reported one."
    )
    confidence_interval: str | None = Field(
        default=None,
        description=(
            "The reported 95% CI, verbatim — '[0.14-0.17]', and also '[NR]' where the study reported "
            "none. A string because that is what the source publishes and the bracket forms vary; "
            "parsing it into two floats here would discard the cases that do not fit."
        ),
    )
    risk_allele_frequency: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Frequency of the effect allele in the study's sample. The source writes 'NR' for not "
            "reported, which is an ABSENCE and arrives here as null — distinct from a reported 0."
        ),
    )

    # ── the evidence ──
    p_value: str | None = Field(
        default=None, description="Raw p-value string, verbatim, mirroring `StudyRow.p_value`."
    )
    p_value_num: float | None = Field(
        default=None,
        gt=0,
        le=1,
        description=(
            "The queryable p-value, mirroring `StudyRow.p_value_num`. **The Catalog's own "
            "mantissa/exponent pair is deliberately not carried**, and the recorded 0.5 rejection has "
            "two halves of which only one still applies: 'a cost every author pays' does not transfer "
            "to a machine-written table, but 'a catalogue-of-millions problem rather than a "
            "curated-module one' does, and a module cites tens of associations, not millions."
        ),
    )
    trait: str | None = Field(
        default=None,
        description=(
            "The reported trait in the Catalog's words. Descriptive — it is re-worded between "
            "releases for an unchanged ontology term, so `trait_efo_id` is the fact and this is what "
            "makes the row readable."
        ),
    )
    trait_efo_id: str | None = Field(
        default=None, description="EFO trait id(s) — the join back to `VariantRow.trait_efo_id`."
    )
    pmid: str | None = Field(
        default=None,
        description="PubMed id of the publication, free-form under the same grammar as `StudyRow.pmid`.",
    )
    study_accession: str | None = Field(
        default=None, description="The Catalog's study accession, e.g. 'GCST001234'."
    )
    ancestry: str | None = Field(
        default=None,
        description=(
            "The study population, free text as the Catalog records it ('European', 'East Asian', "
            "'Hispanic or Latin American'). Free rather than a vocabulary because it is prose there "
            "and closing it would make a future release unloadable; and NOT merged with "
            "`PgsRow.training_ancestry`, which is a 1000G superpopulation code list — `vocab.py` "
            "forbids collapsing two ancestry vocabularies into one."
        ),
    )
    dataset: str = Field(
        description=(
            "Which Catalog release this row came from, e.g. 'gwas_catalog_2026-08-01'. A FACT: the "
            "Catalog re-curates, and an association whose effect size moved is a different fact."
        )
    )

    # ── provenance (EXCLUDED from gwas_effect_signature) ──
    source: str | None = Field(
        default=None,
        description=(
            "The licensed data source: gwas_catalog|manual|reversed (open). Joins "
            "`sources.csv.source`. Names the SOURCE, never the route."
        ),
    )
    status: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("resolution_status", VALID_RESOLUTION_STATUS),
        description=(
            "Outcome: resolved|not_found|ambiguous. `not_found` is a FACT — the Catalog was consulted "
            "and reports no association for this variant — and differs from a variant never queried, "
            "which has no row at all."
        ),
    )
    fetched_at: str | None = Field(
        default=None,
        description=(
            "ISO-8601 UTC timestamp, second resolution. Canonicalized on load; records when this row "
            "was written by a pass, not when the Catalog published anything — that is `dataset`."
        ),
    )

    @field_validator("association_id")
    @classmethod
    def _check_association_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("association_id must not be empty — it is this row's identity")
        return v

    @field_validator("variant_key")
    @classmethod
    def _check_variant_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("variant_key must not be empty")
        return v

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("dataset must name the Catalog release this row came from")
        return v

    @field_validator("effect_direction")
    @classmethod
    def _check_effect_direction(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_EFFECT_DIRECTIONS, "effect_direction")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("effect_size", "standard_error")
    @classmethod
    def _check_finite(cls, v: float | None, info) -> float | None:
        # `info.field_name`, not a hardcoded name: registered for two fields, this reported
        # "effect_size must be a finite number" for an infinite `standard_error` and sent the author
        # to the wrong column (RM96). `gene_metrics._check_finite` passes `info.field_name` across
        # nine fields, so the correct idiom was one file over.
        return validate_finite(v, info.field_name or "effect_size")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v)

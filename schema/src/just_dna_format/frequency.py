"""The source-independent allele-frequency table (0.5).

`frequencies.csv` is the variant-level sibling of `resolution.csv`: a persisted table of
already-fetched population-frequency *facts* that the compiler consumes instead of querying any
source. Filling it is the job of the separate `just-dna-enricher` network tier (its gnomAD pass); the
compiler only reads it, materializes `frequencies.parquet`, and hashes it by facts.

Three parties share the definition, like `ResolutionRow`: the enricher *produces* it, the compiler
*consumes* it, a verify-only client may *re-check* it. Dependency-light — pydantic + the stdlib
`vocab` leaf.

**One row is one (allele, ancestry group) pair.** Frequency is meaningless without saying *whose*
frequency, and ancestry group, sex, and dataset are three separate axes (Principle 5), so they are
three separate things here rather than one overloaded `population` label: the group is `population`,
the release is `dataset`, and sex-stratified counts are simply not carried in this pass (folding
`nfe_XX` into `population` would be exactly the `state`-overloading mistake 0.3 unwound).

**Counts, not a float.** `allele_count`/`allele_number` are the integers the source reports;
`allele_frequency` is a *derived property*, materialized as a real `Float64` in the parquet so a
consumer does no arithmetic, but never stored in the CSV. Integers round-trip through CSV exactly,
while a stored float invites formatting drift (`0.0482` vs `0.048200000000000004`) — a Principle 7
idempotency hazard for the price of duplicating one fact in two columns. `faf95` is the one
unavoidable stored float, and it is canonicalized on write and covered by a round-trip test.
"""


from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_FREQUENCY_STATUS,
    check_vocab,
    normalize_population,
    validate_population,
)
from just_dna_format.vrs import validate_caid, validate_vrs_allele_id

# The fact columns that feed `integrity.frequency_signature` — everything except the provenance
# columns (`source`/`status`/`fetched_at`), so a human-filled and a gnomAD-filled table carrying the
# same numbers hash equal (the same producer-independence `RESOLUTION_FACT_FIELDS` buys).
#
# `dataset` is INSIDE the fact set on purpose: a v4.1 allele frequency and a v2.1.1 one are different
# facts about the world, not two spellings of one fact, so a table that swapped releases must hash
# differently. `vrs_id`/`caid` are OUTSIDE it, matching `RESOLUTION_FACT_FIELDS` — they are
# cross-references to the same allele the coordinate already names, not independent measurements.
FREQUENCY_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "rsid",
    "chrom",
    "start",
    "ref",
    "alt",
    "population",
    "allele_count",
    "allele_number",
    "homozygote_count",
    "hemizygote_count",
    "faf95",
    "dataset",
    "genome_build",
)


class FrequencyRow(BaseModel):
    """One (allele, ancestry group) frequency fact, keyed by the coordinate-derived `variant_key`.

    Standalone (not an `AuthoredModel`), for the same reason `ResolutionRow` is: a frequency is a
    machine-produced reference fact, not an authored annotation, so it must not inherit the annotation
    validators or the reserved-namespace guard's authoring semantics. It does close its namespace with
    `extra="forbid"`, so a typo'd column in `frequencies.csv` is caught rather than silently dropped.
    """

    #: What makes two rows the same row — the key `enrich_frequencies` merges on. One variant carries
    #: a row per ancestry group, so `population` is in the key and the variant alone is not (S51).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "population")

    model_config = ConfigDict(extra="forbid")

    # ── join key ──
    # The COORDINATE-derived key, not an authored-rsid one: a one-to-many rsid is re-keyed to distinct
    # coordinate keys when the compiler expands it, so an rsid-keyed frequency row would fail to line
    # up with the weights rows it describes. The table is standalone regardless (the compiler does no
    # join, only a cross-check), but the key has to mean the same thing on both sides.
    variant_key: str = Field(
        description="Coordinate-derived identity of the allele (matches the post-expansion weights key)"
    )

    # ── the allele this row is about ──
    rsid: str | None = Field(default=None, description="dbSNP identifier, when known")
    chrom: str | None = Field(default=None, description="Chromosome without 'chr' prefix")
    start: int | None = Field(
        default=None, ge=0, description="1-based genomic position (VCF POS convention)"
    )
    ref: str | None = Field(default=None, description="Reference allele")
    alt: str | None = Field(
        default=None,
        description=(
            "The ONE alt allele this frequency is for — deliberately singular, unlike "
            "`ResolutionRow.alts`: an allele frequency is per-allele, so a multi-allelic site is "
            "several rows, never one comma-joined cell."
        ),
    )
    genome_build: str = Field(
        default="GRCh38", description="Assembly the coordinate is in (the RM15 forward hook)"
    )

    # ── the counts ──
    population: str = Field(
        description=(
            "Ancestry group the counts are for, or 'global' for the whole dataset. Open, seeded "
            "vocabulary (`vocab.RECOMMENDED_ANCESTRY_GROUPS`) — a label is interpretable only "
            "together with `dataset`."
        )
    )
    allele_count: int | None = Field(
        default=None, ge=0, description="AC — observed copies of `alt` in this group"
    )
    allele_number: int | None = Field(
        default=None, ge=0, description="AN — total called alleles in this group (the denominator)"
    )
    homozygote_count: int | None = Field(
        default=None, ge=0, description="Individuals homozygous for `alt` in this group"
    )
    hemizygote_count: int | None = Field(
        default=None, ge=0, description="Hemizygous calls (X/Y outside the PAR, and MT)"
    )
    faf95: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Filtering allele frequency, 95% CI lower bound — the number an ACMG BA1/BS1 filter "
            "actually uses. The source reports ONE faf95 with a named owning group, so it is set only "
            "on that group's row and null everywhere else (no extra column, no overloaded field)."
        ),
    )
    dataset: str = Field(
        description=(
            "Which release these counts are from, e.g. 'gnomad_v4.1_joint'. A FACT, not provenance: "
            "the same allele has different (equally correct) counts in different releases."
        )
    )

    # ── cross-references (out of the fact set, like ResolutionRow's) ──
    vrs_id: str | None = Field(default=None, description="GA4GH VRS allele id (`ga4gh:VA.…`)")
    caid: str | None = Field(
        default=None, description="ClinGen Allele Registry canonical allele id (`CA<digits>`)"
    )

    # ── provenance (EXCLUDED from frequency_signature) ──
    source: str | None = Field(
        default=None, description="Which link filled this: gnomad|manual|reversed (open)"
    )
    status: str | None = Field(
        default=None,
        description="Outcome: resolved|not_found|not_covered (VALID_FREQUENCY_STATUS)",
        json_schema_extra=vocabulary("frequency_status", VALID_FREQUENCY_STATUS),
    )
    fetched_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-03T02:03:23Z'). Canonicalized on load; records when this row was last written by a pass, not when the source published anything")

    @property
    def allele_frequency(self) -> float | None:
        """AC/AN — derived, never stored. `None` when either count is absent, and when `AN` is 0.

        An `AN` of 0 is a real and common state (a group with no coverage at this site), and it means
        "no information", not "frequency zero" — returning `None` keeps a consumer from reading an
        undefined ratio as a confident absence.
        """
        if self.allele_count is None or not self.allele_number:
            return None
        return self.allele_count / self.allele_number

    @field_validator("population")
    @classmethod
    def _validate_population(cls, v: str) -> str:
        return validate_population(normalize_population(v))

    @field_validator("vrs_id")
    @classmethod
    def _validate_vrs_id(cls, v: str | None) -> str | None:
        return validate_vrs_allele_id(v)

    @field_validator("caid")
    @classmethod
    def _validate_caid(cls, v: str | None) -> str | None:
        return validate_caid(v)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        """A closed vocabulary since 0.5.1 — it was free text, on a fact table.

        The three members are not interchangeable and the distinction is the whole point: `not_found`
        is a fact about a covered locus, `not_covered` is the absence of an answer. See
        `VALID_FREQUENCY_STATUS` for why the second exists.
        """
        return check_vocab(v, VALID_FREQUENCY_STATUS, "status")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

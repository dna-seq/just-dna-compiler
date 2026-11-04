"""The per-transcript consequence table: what a variant does to each transcript near it (0.8, RM236).

`consequences.csv` is a derived-fact sidecar filled by `just-dna-enricher`'s `opentargets enrich` pass.
One row per `(variant_key, transcript)`, which is the grain RM236 chose over the two cheaper shapes:

- **one MANE value per variant** is lossy, and a column shipped under a major cannot be retyped into a
  table later;
- **the most severe consequence across transcripts** is a ranking policy, which is an interpretation
  and stays the consumer's.

RM23's computational predictor scores have the same blocker (a score is per transcript), and inherit
this grain when they are built; one answer to "which transcript" rather than two.

**The transcript set is the source's choice, and the description says so.** Open Targets 26.09 lists
one transcript per nearby gene, every one flagged Ensembl-canonical (probes/LANES_0_8.md § 1.6), not
every transcript of every gene. `canonical` records the flag rather than the table implying it.

**The consequence is stored as Sequence Ontology accessions, verbatim** (`SO_0001583`), because that
is what the source publishes. A term label (`missense_variant`) would be a mapping this format would
own, and the name `consequence` stays free for it.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import VALID_IMPACTS, check_vocab

# Fact columns feeding `integrity.consequence_signature`: everything but `source`/`fetched_at`. `gene`
# (the symbol) is outside on `expression.py`'s reasoning turned around: here the accession `gene_id` is
# the source's identity for the gene and the symbol is a label it renames between releases.
CONSEQUENCE_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "transcript",
    "gene_id",
    "consequence_so_ids",
    "impact",
    "mane_select",
    "canonical",
    "dataset",
)


class ConsequenceRow(BaseModel):
    """One `(variant, transcript)` pair: the predicted consequence and its impact class."""

    #: RM236's grain. One variant carries a row per transcript the source annotates.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "transcript")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    variant_key: str = Field(
        json_schema_extra=since("0.8.0"),
        description="The module's key for the variant. Joins `weights.parquet.variant_key`.",
    )
    transcript: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "Ensembl transcript accession (`ENST…`), unversioned as the source publishes it. Which "
            "transcripts appear is the source's choice: Open Targets lists one canonical transcript "
            "per nearby gene, not every transcript."
        ),
    )
    rsid: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="dbSNP id of the variant as the module knows it. Descriptive, outside the fact hash.",
    )
    gene_id: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="Ensembl gene accession (`ENSG…`) the transcript belongs to.",
    )
    gene: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="HGNC symbol of that gene, as the source labels it. A label; `gene_id` is the fact.",
    )

    # ── the consequence ──
    consequence_so_ids: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "Sequence Ontology accessions of the predicted consequence on this transcript "
            "(`SO_0001583`), comma-separated in the source's order when it gives several "
            "(a splice-region variant inside an intron is two). Verbatim: accessions, not labels."
        ),
    )
    impact: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("impact", VALID_IMPACTS), **since("0.8.0")},
        description=(
            "VEP's impact class for this transcript: HIGH|MODERATE|LOW|MODIFIER. The class of the "
            "consequence on THIS transcript, never the most severe across the variant's transcripts."
        ),
    )
    mane_select: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The RefSeq accession (`NM_…`) when this transcript is the gene's MANE Select, else null. "
            "How a consumer that wants one row per gene picks it without a ranking policy."
        ),
    )
    canonical: bool | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "Whether the source flags this transcript Ensembl-canonical. True on every row of Open "
            "Targets 26.09, which is how its transcript set was chosen; recorded rather than implied."
        ),
    )
    dataset: str = Field(
        json_schema_extra=since("0.8.0"),
        description="Which release this row came from, e.g. 'opentargets_26.09' (its VEP annotation).",
    )

    # ── provenance (EXCLUDED from consequence_signature) ──
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

    @field_validator("variant_key", "transcript", "dataset")
    @classmethod
    def _check_required(cls, v: str, info) -> str:
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @field_validator("impact")
    @classmethod
    def _check_impact(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_IMPACTS, "impact")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        return normalize_utc_timestamp(v)

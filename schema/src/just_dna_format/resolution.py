"""The source-independent resolution table (0.5).

`resolution.csv` is a persisted table of already-resolved variant facts (rsid ↔ coordinate) that the
compiler consumes *instead of* querying any reference — so the compiler owns no source convention
(Ensembl, DuckDB, provisioning) and stays strictly inject-only (CONSTITUTION Principle 2). The table
is filled *before* compilation by anything: an on-disk cache, a live query, or a human. Filling it is
the job of the separate `just-dna-enricher` network tier; the compiler only reads it.

Three parties share this one definition (why it lives in the schema tier, like `manifest.FileEntry`):
the compiler *consumes* it, the enricher *produces* it, and a verify-only client may *re-check* it. It
is dependency-light — pydantic + the stdlib `vocab` leaf, no polars/duckdb/httpx.

A one-to-many rsid (one authored `variant_key` expanding to several loci) is encoded as several rows
sharing `variant_key` with distinct `locus_index`, so the compiler reproduces the expansion without
any source knowledge. The fact columns feed `integrity.resolution_signature`; the provenance columns
are deliberately excluded from it (a human-filled and an Ensembl-filled table with identical facts
must hash equal — see `RESOLUTION_FACT_FIELDS`).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.vocab import VALID_RESOLUTION_STATUS, check_vocab, validate_rsid

# The fact columns that feed `integrity.resolution_signature` — the reproducibility-relevant facts,
# deliberately EXCLUDING the provenance columns (`source`/`status`/`fetched_at`) so a human-filled and
# an Ensembl-filled table carrying identical facts hash equal. This is the structural reason the table
# is hashed by its facts (a stable, producer-independent identity) rather than by its raw bytes.
RESOLUTION_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "rsid",
    "chrom",
    "start",
    "ref",
    "alts",
    "genome_build",
    "locus_index",
)


class ResolutionRow(BaseModel):
    """One resolved (or attempted) locus for an authored variant, keyed by the frozen `variant_key`.

    Standalone (not an `AuthoredModel`/`VariantRow` subclass): a resolution fact is not an annotation
    row and must not inherit VariantRow's annotation validators. It reuses the shared `rsid` grammar so
    an rsid here obeys the same rule everywhere, and closes its namespace with `extra="forbid"` like
    the authored models so a typo'd column in `resolution.csv` is caught, not silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    # ── join key: the frozen authored identity (base.derive_variant_key) ──
    variant_key: str = Field(
        description="Frozen authored identity this row resolves (rsid, else chrom:start:ref)"
    )

    # ── resolved facts (feed resolution_signature) ──
    rsid: Optional[str] = Field(default=None, description="Resolved dbSNP identifier")
    chrom: Optional[str] = Field(default=None, description="Chromosome without 'chr' prefix")
    start: Optional[int] = Field(
        default=None,
        ge=0,
        description="1-based genomic position (VCF POS convention; matches the Ensembl and ClinVar snapshots)",
    )
    ref: Optional[str] = Field(default=None, description="Reference allele")
    alts: Optional[str] = Field(default=None, description="Alt allele(s), comma-separated")
    genome_build: str = Field(
        default="GRCh38",
        description="Assembly the coordinate is in (the RM15 forward hook; GRCh38 today)",
    )
    locus_index: int = Field(
        default=0,
        ge=0,
        description="0 for a 1:1 resolution; 0..N-1 for a one-to-many rsid expansion",
    )

    # ── provenance (EXCLUDED from resolution_signature; who/what/when filled this) ──
    source: Optional[str] = Field(
        default=None,
        description="Which link filled this: cache|ensembl-graphql|ensembl-rest|manual|reversed (open)",
    )
    status: Optional[str] = Field(
        default=None, description="Resolution outcome: resolved|not_found|ambiguous"
    )
    fetched_at: Optional[str] = Field(default=None, description="ISO-8601 UTC timestamp, advisory")

    @field_validator("rsid")
    @classmethod
    def _validate_rsid(cls, v: Optional[str]) -> Optional[str]:
        return validate_rsid(v)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

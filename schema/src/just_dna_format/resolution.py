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

from just_dna_format.vocab import (
    VALID_RESOLUTION_STATUS,
    VALID_RSID_STATUS,
    check_vocab,
    validate_rsid,
)
from just_dna_format.vrs import validate_caid, validate_vrs_id

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

    # ── cross-references (0.5; OUT of RESOLUTION_FACT_FIELDS this cycle) ──
    # Three separate identifiers for three separate registries (Principle 5 — one column each, never
    # one overloaded `identifier` field): `rsid` above is dbSNP's, `vrs_id` is GA4GH's content-addressed
    # allele name, `caid` is the ClinGen Allele Registry's. They are kept out of the fact set so adding
    # them moves no existing `resolution_signature` while the columns bed in — the identity they carry
    # reaches the artifact through `variant_key` (which derives from the VA for a resolved
    # substitution), so the fact set does not need them.
    vrs_id: Optional[str] = Field(
        default=None,
        description=(
            "GA4GH VRS allele id (`ga4gh:VA.…`). Minted locally by `vrs.derive_vrs_allele_id` for a "
            "substitution, by the enricher's [dev] normalization path for an indel, and cross-checked "
            "against a source's own id (gnomAD serves one) where available."
        ),
    )
    vrs_spec: Optional[str] = Field(
        default=None,
        description=(
            "VRS spec version the id was minted under ('2.0'). Recorded to disambiguate an embedded "
            "location id, not because the allele id drifts — a substitution's VA is identical under "
            "1.x and 2.0."
        ),
    )
    caid: Optional[str] = Field(
        default=None, description="ClinGen Allele Registry canonical allele id (`CA<digits>`)"
    )

    # ── provenance (EXCLUDED from resolution_signature; who/what/when filled this) ──
    source: Optional[str] = Field(
        default=None,
        description="Which link filled this: cache|ensembl-graphql|ensembl-rest|manual|reversed (open)",
    )
    # **Two vocabularies were living under one name** (P5, across two tables). `source` here answers
    # *which link answered* and `sources.csv`'s `source` answers *which licensed source this is* — and
    # `compiler._source_checks` set-differences the two, so every enriched module warned that
    # `ensembl-rest` has no terms recorded. Neither obvious repair works: a `SourceRow` per link makes
    # `ensembl-rest` and `ensembl-graphql` two "sources" with identical terms, and teaching the compiler
    # a link→source map hands it a source convention, which is exactly what P2's 0.5 tightening took
    # away. The missing thing was a third column recording *both*.
    #
    # `source` deliberately keeps its meaning rather than being repurposed as the authority: every
    # `resolution.csv` already written carries link values there, so re-pointing the name would silently
    # change what existing data says. The map from link to authority lives in the enricher, the only
    # tier permitted to know one.
    authority: Optional[str] = Field(
        default=None,
        description=(
            "The licensed data source the link speaks for — `ensembl` for `ensembl-rest`/"
            "`ensembl-graphql`/`cache`, `clinvar` for the snapshot, `gnomad` for the last-resort link. "
            "Joins `sources.csv.source`. Empty when there is no external authority to declare "
            "(`authored`, `reversed`, `manual`: the module's own bytes or a human)."
        ),
    )
    status: Optional[str] = Field(
        default=None, description="Resolution outcome: resolved|not_found|ambiguous"
    )
    rsid_alternates: Optional[str] = Field(
        default=None,
        description=(
            "When a reverse (position→rsid) back-fill hit several candidate rsIDs for the *same exact "
            "allele* (a genuine dbSNP merge), the full sorted candidate list (comma-separated); `rsid` "
            "carries the deterministic pick (lowest id) and `status` is 'ambiguous'. Empty otherwise. "
            "Provenance — EXCLUDED from resolution_signature (0.5, provisional)."
        ),
    )
    rsid_current: Optional[str] = Field(
        default=None,
        description=(
            "The rsID dbSNP serves today when the authored one has been merged away (e.g. `rs3051860` "
            "for an authored `rs3216883`). **Recorded, never substituted** — `weights.parquet` carries "
            "the rsID as identity, so writing the new label into the artifact would migrate "
            "`variant_key` by network lookup and break the round-trip fixed point (Principle 7)."
        ),
    )
    rsid_status: Optional[str] = Field(
        default=None,
        description=(
            "What dbSNP currently says about `rsid`: live|merged|absent|withdrawn. The automated "
            "check never emits `withdrawn` — a retracted rsID is byte-identical to a never-assigned "
            "one through every live endpoint — so it reports `absent` and names both readings. "
            "`withdrawn` is for a curator who has established the retraction by hand, and it refuses "
            "in BOTH modes where `absent` refuses only under strict, because a retracted variant may "
            "invalidate the annotation rather than merely dating it. "
            "Provenance — EXCLUDED from resolution_signature (time-varying external state)."
        ),
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

    @field_validator("rsid_current")
    @classmethod
    def _validate_rsid_current(cls, v: Optional[str]) -> Optional[str]:
        return validate_rsid(v)

    @field_validator("rsid_status")
    @classmethod
    def _validate_rsid_status(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_RSID_STATUS, "rsid_status")

    @field_validator("vrs_id")
    @classmethod
    def _validate_vrs_id(cls, v: Optional[str]) -> Optional[str]:
        return validate_vrs_id(v)

    @field_validator("caid")
    @classmethod
    def _validate_caid(cls, v: Optional[str]) -> Optional[str]:
        return validate_caid(v)

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


from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from just_dna_format.base import vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_RESOLUTION_STATUS,
    VALID_RSID_STATUS,
    check_vocab,
    validate_rsid,
)
from just_dna_format.vrs import split_vrs_ids, validate_caid, validate_vrs_id_list

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
    rsid: str | None = Field(default=None, description="Resolved dbSNP identifier")
    chrom: str | None = Field(default=None, description="Chromosome without 'chr' prefix")
    start: int | None = Field(
        default=None,
        ge=0,
        description="1-based genomic position (VCF POS convention; matches the Ensembl and ClinVar snapshots)",
    )
    ref: str | None = Field(default=None, description="Reference allele")
    alts: str | None = Field(default=None, description="Alt allele(s), comma-separated")
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
    vrs_id: str | None = Field(
        default=None,
        description=(
            "GA4GH VRS allele id (`ga4gh:VA.…`) — one per ALT, comma-joined and **positionally "
            "aligned with `alts`**, so a single-alt row carries a bare id and a multi-allelic one "
            "names each of its alleles in the same order. An empty member is a hole: that allele's id "
            "could not be minted (an indel in an offline run, an off-assembly contig). Minted locally "
            "by `vrs.derive_vrs_allele_id` for a substitution, by the enricher's normalization path "
            "for an indel, and cross-checked against a source's own id (gnomAD serves one) where "
            "available."
        ),
    )
    vrs_spec: str | None = Field(
        default=None,
        description=(
            "VRS spec version the id was minted under ('2.0'). Recorded to disambiguate an embedded "
            "location id, not because the allele id drifts — a substitution's VA is identical under "
            "1.x and 2.0."
        ),
    )
    caid: str | None = Field(
        default=None, description="ClinGen Allele Registry canonical allele id (`CA<digits>`)"
    )

    # ── provenance (EXCLUDED from resolution_signature; who/what/when filled this) ──
    source: str | None = Field(
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
    authority: str | None = Field(
        default=None,
        description=(
            "The licensed data source the link speaks for — `ensembl` for `ensembl-rest`/"
            "`ensembl-graphql`/`cache`, `clinvar` for the snapshot, `gnomad` for the last-resort link. "
            "Joins `sources.csv.source`. Empty when there is no external authority to declare "
            "(`authored`, `reversed`, `manual`: the module's own bytes or a human)."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Resolution outcome: resolved|not_found|ambiguous",
        json_schema_extra=vocabulary("resolution_status", VALID_RESOLUTION_STATUS),
    )
    rsid_alternates: str | None = Field(
        default=None,
        description=(
            "When a reverse (position→rsid) back-fill hit several candidate rsIDs for the *same exact "
            "allele* (a genuine dbSNP merge), the full sorted candidate list (comma-separated); `rsid` "
            "carries the deterministic pick (lowest id) and `status` is 'ambiguous'. Empty otherwise. "
            "Provenance — EXCLUDED from resolution_signature (0.5, provisional)."
        ),
    )
    rsid_current: str | None = Field(
        default=None,
        description=(
            "The rsID dbSNP serves today when the authored one has been merged away (e.g. `rs3051860` "
            "for an authored `rs3216883`). **Recorded, never substituted** — `weights.parquet` carries "
            "the rsID as identity, so writing the new label into the artifact would migrate "
            "`variant_key` by network lookup and break the round-trip fixed point (Principle 7)."
        ),
    )
    rsid_status: str | None = Field(
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
        json_schema_extra=vocabulary("rsid_status", VALID_RSID_STATUS),
    )
    fetched_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-03T02:03:23Z'). Canonicalized on load; records when this row was last written by a pass, not when the source published anything")

    @field_validator("rsid")
    @classmethod
    def _validate_rsid(cls, v: str | None) -> str | None:
        return validate_rsid(v)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("rsid_current")
    @classmethod
    def _validate_rsid_current(cls, v: str | None) -> str | None:
        return validate_rsid(v)

    @field_validator("rsid_status")
    @classmethod
    def _validate_rsid_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RSID_STATUS, "rsid_status")

    @field_validator("vrs_id")
    @classmethod
    def _validate_vrs_id(cls, v: str | None) -> str | None:
        return validate_vrs_id_list(v)

    @model_validator(mode="after")
    def _vrs_ids_align_with_alts(self) -> "ResolutionRow":
        """`vrs_id` is a parallel array of `alts`, so a desynced pair is caught at load.

        Positional coupling between two columns is the price of not multiplying the table into one row
        per allele, and this is what makes it safe: a human who edits `alts` and forgets `vrs_id` gets a
        refusal here rather than a silently re-pointed identity. (The compiler's `_verify_vrs_ids` is
        the second net — it recomputes every member offline, so a *reordered* pair that still counts
        right is caught there as a mismatch.)

        Only checked when both columns are filled. A `vrs_id` on a row with no `alts` is left alone: the
        enricher never writes one, but a hand-filled table naming an allele it did not record in `alts`
        is under-specified, not contradictory, and refusing it would be this tier inventing a rule.
        """
        if not self.alts or self.vrs_id is None:
            return self
        alts = self.alts.split(",")
        ids = split_vrs_ids(self.vrs_id)
        if len(ids) != len(alts):
            raise ValueError(
                f"vrs_id names {len(ids)} allele id(s) but alts names {len(alts)} allele(s) "
                f"({self.alts!r}) — vrs_id is positionally aligned with alts, one member per ALT "
                f"(empty where no id could be minted), so the two must have the same length"
            )
        return self

    @field_validator("caid")
    @classmethod
    def _validate_caid(cls, v: str | None) -> str | None:
        return validate_caid(v)

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

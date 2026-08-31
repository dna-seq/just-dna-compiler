"""The source-independent clinical-assertion table (0.6, RM25).

`clinical_assertions.csv` is the sixth derived-fact sidecar. It records, per allele, what a clinical
archive says about it **and how much review sits behind that** — the clinical call, the review status
in the archive's own words, the star rating, and the archive's stable record id. Filled by
`just-dna-enricher`'s ClinVar pass from an injected snapshot, consumed and hashed by the compiler,
never fetched by it.

**Why it exists at all.** A one-star single submission and a practice guideline are not the same
claim, and a compiled module flattened both to the same `clin_sig`. The workspace was already
computing the distinction and throwing it away twice: `clinical.ClinSigFinding.confidence` renders it
into a warning string, and `draft_gene_panel` uses the star rating as a *filter* (default 2 — multiple
submitters, no conflicts) and keeps nothing. A number this workspace computes and discards gets
recomputed by every consumer, and a recomputation is a place to drift.

**It is not the cross-check, and it does not change it.** `clinical.verify_clin_sig` compares the
*author's* `clin_sig` against ClinVar's and warns in both modes, deliberately, because failing would
make the format arbitrate a clinical dispute. This table records what ClinVar says; it adjudicates
nothing, and nothing here escalates that check.

**Why `review_stars` is a stored column and not a derived property.** The house pattern for a
convenience number is to store the exact parts and materialize the derivation (`allele_frequency` from
AC/AN, `neg_log10_p` from a mantissa and an exponent). The derivation here — CLNREVSTAT prose to a
0-to-4 rating — is a **ClinVar convention**, and Principle 2 keeps source conventions out of this tier
entirely. So both columns are stored, the enricher fills them from one mapping it owns
(`clinvar_build.review_stars`), and the schema tier holds only the bound `0 <= stars <= 4`.

**One row is one (allele, ClinVar record).** Not one row per variant: ClinVar genuinely holds several
records for one allele under different conditions, which is why `clinvar.lookup_clin_sig` returns a
list and orders it best-reviewed first. Collapsing them here would pick a condition on the author's
behalf.
"""


from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import VALID_CLIN_SIG, VALID_RESOLUTION_STATUS, check_vocab

# Fact columns feeding `integrity.clinical_assertion_signature` — everything but the provenance
# columns (`source`/`status`/`fetched_at`) and `rsid`, so a hand-curated and a ClinVar-filled table
# carrying the same assertions hash equal.
#
# **`rsid` is OUTSIDE, and the `FREQUENCY_FACT_FIELDS` precedent deliberately does not transfer.**
# There the rsID arrives in gnomAD's own payload, so it is part of what the source said. Here the
# archive lookup is allele-exact on `(chrom, start, ref, alt)` and returns no rsID at all — the column
# is filled from the module's own `resolution.csv`. Inside the fact set it would make two modules
# holding *the same ClinVar records* hash differently according to whether their resolver happened to
# attach an rsID, which is precisely the producer-dependence this tuple exists to exclude. The
# coordinate already names the allele; the rsID is a convenience for the human reading the table.
#
# `dataset` is inside for the reason it is everywhere else — a 2026-06 ClinVar release and a 2026-08
# one are different facts, and a re-review is exactly the change this table exists to make visible.
#
# `review_status` and `review_stars` are BOTH inside although one determines the other. That is not a
# duplicated fact hiding in the hash: the mapping is a ClinVar convention this tier does not hold, so
# the two columns are independent inputs here and a table whose stars disagreed with its prose would —
# rightly — hash differently from one where they agree.
CLINICAL_ASSERTION_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "chrom",
    "start",
    "ref",
    "alt",
    "genome_build",
    "clin_sig",
    "clin_sig_raw",
    "review_status",
    "review_stars",
    "condition",
    "variation_id",
    "dataset",
)


class ClinicalAssertionRow(BaseModel):
    """One archive record about one allele: the call, the review behind it, and the record's id.

    Standalone (not an `AuthoredModel`) for the same reason every fact row is — machine-produced
    reference fact, not an authored annotation — with `extra="forbid"` so a typo'd column is caught
    rather than silently dropped.
    """

    #: What makes two rows the same row — the key `enrich_clinical_assertions` merges on. One allele
    #: carries a row per archive record, so `variation_id` is in the key; a `null` there is a **value**
    #: and not an absence, carrying the `not_found` row that states the archive was consulted and has
    #: no record for this allele (S51).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "variation_id")

    model_config = ConfigDict(extra="forbid")

    # ── join key ──
    # The COORDINATE-derived key, exactly as `FrequencyRow` documents: a one-to-many rsid is re-keyed
    # to distinct coordinate keys when the compiler expands it, so an rsid-keyed row would not line up
    # with the weights rows it describes.
    variant_key: str = Field(json_schema_extra=since("0.6.0"), 
        description="Coordinate-derived identity of the allele (matches the post-expansion weights key)"
    )

    # ── the allele this record is about ──
    rsid: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "dbSNP identifier for this allele's locus, as the resolution table already established "
            "it. Descriptive: an rsID is position/multi-allelic-level, so it names the locus rather "
            "than this record's allele, and `variant_key` is what identifies the row."
        ),
    )
    chrom: str | None = Field(json_schema_extra=since("0.6.0"), default=None, description="Chromosome without 'chr' prefix")
    start: int | None = Field(json_schema_extra=since("0.6.0"), 
        default=None, ge=0, description="1-based genomic position (VCF POS convention)"
    )
    ref: str | None = Field(json_schema_extra=since("0.6.0"), default=None, description="Reference allele")
    alt: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The ONE alt allele this record is about — singular like `FrequencyRow.alt` and unlike "
            "`ResolutionRow.alts`, because a clinical call is per-allele: one rsID at one locus can "
            "carry a pathogenic, a benign and an uncertain allele (rs33922842 in HBB does)."
        ),
    )
    genome_build: str = Field(json_schema_extra=since("0.6.0"), 
        default="GRCh38",
        description=(
            "Assembly the coordinate is in. Load-bearing rather than decorative: the ClinVar snapshot "
            "is GRCh38 and its lookup key carries no assembly, so a coordinate from another build is a "
            "well-formed query that returns a different variant's record."
        ),
    )

    # ── what the archive says ──
    clin_sig: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The archive's clinical significance, normalized to the module vocabulary "
            "(`vocab.VALID_CLIN_SIG`) at the enricher boundary. A FACT about the archive, never an "
            "adjudication: this table records the call, it does not decide who is right."
        ),
    )
    clin_sig_raw: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The archive's verbatim token (`Pathogenic/Likely_pathogenic`), kept so the normalization "
            "above stays auditable and a value the mapping does not model is still visible."
        ),
    )
    review_status: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The archive's own review wording, verbatim — e.g. "
            "'criteria_provided,_multiple_submitters,_no_conflicts'. Open, not a vocabulary: it is "
            "ClinVar's phrasing and it changes on ClinVar's schedule, so closing it here would make a "
            "future release unloadable for no gain."
        ),
    )
    review_stars: int | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        ge=0,
        le=4,
        description=(
            "The 0-to-4 rating that wording maps to. Stored beside the prose rather than derived from "
            "it, because the mapping is a ClinVar convention and this tier holds no source conventions "
            "(Principle 2) — the enricher owns it. Null means the archive stated no review status; 0 "
            "is a rating ('no assertion criteria provided') and is not the same thing."
        ),
    )
    condition: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The condition the call is scoped to, as the archive names it. Descriptive: the archive "
            "holds several records per allele under different conditions, and this is what separates "
            "them for a reader."
        ),
    )
    variation_id: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The archive's stable record id (ClinVar's VariationID). The thing a consumer cites, and "
            "the join key back into the archive — which is why it is in the fact set."
        ),
    )
    dataset: str = Field(json_schema_extra=since("0.6.0"), 
        description=(
            "Which release this record is from, e.g. 'clinvar_2026-06-27'. A FACT: a re-reviewed "
            "record is a new fact, and telling the two apart is the point of this table."
        )
    )

    # ── provenance (EXCLUDED from clinical_assertion_signature) ──
    source: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The licensed data source: clinvar|manual|reversed (open). Joins `sources.csv.source`. It "
            "names the SOURCE, never the route — which release answered is `dataset`'s job."
        ),
    )
    status: str | None = Field(
        default=None,
        description=(
            "Outcome: resolved|not_found|ambiguous (the ResolutionRow vocabulary). `not_found` is a "
            "FACT — the archive was consulted and has no record for this allele — and is different "
            "from an allele that was never queried, which has no row at all."
        ),
        json_schema_extra={**vocabulary("resolution_status", VALID_RESOLUTION_STATUS), **since("0.6.0")},
    )
    fetched_at: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-13T02:03:23Z'). Canonicalized on "
            "load; records when this row was last written by a pass, not when the archive published "
            "anything — that is `dataset`."
        ),
    )

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
            raise ValueError("dataset must name the release this record came from")
        return v

    @field_validator("clin_sig")
    @classmethod
    def _check_clin_sig(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_CLIN_SIG, "clin_sig")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

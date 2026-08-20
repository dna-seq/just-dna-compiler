"""The source-independent gene-constraint table (0.5).

`gene_metrics.csv` is the **gene-level** sibling of `frequencies.csv`: population-constraint facts
(pLI, LOEUF, missense Z) for the genes a module already mentions. Filled by `just-dna-enricher`'s
gnomAD pass — from a small offline snapshot first, the live API second — consumed and hashed by the
compiler, never fetched by it.

Gene-level and variant-level facts get **separate tables** rather than gene metrics repeated on every
variant row (Principle 5, and the "one CSV = one concern" rule): a module with forty variants across
six genes carries six rows here, not forty duplicated ones, and the two axes stay independently
updatable.

Unlike the frequency table's integer counts, these are floats by nature — a constraint score has no
integer form to round-trip through — so the canonical-formatting discipline applies to the whole row
rather than to one column, and the reverse writer's round-trip is covered by a test.
"""


from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_DOSAGE_SENSITIVITY,
    VALID_RESOLUTION_STATUS,
    check_vocab,
    validate_finite,
)

# Fact columns feeding `integrity.gene_metrics_signature` — everything but `source`/`status`/
# `fetched_at`. `dataset` is inside the set for the same reason it is in `FREQUENCY_FACT_FIELDS`: a
# v2.1.1 pLI and a v4.1 pLI are different facts, and the table must hash differently when the release
# changes under it. `transcript`/`mane_select` are inside too — a constraint score is a property *of a
# transcript*, so which transcript it was computed on is part of the fact, not a note about it.
GENE_METRICS_FACT_FIELDS: tuple[str, ...] = (
    "gene",
    "gene_id",
    "transcript",
    "mane_select",
    "pli",
    "loeuf",
    "oe_lof",
    "oe_lof_lower",
    "lof_z",
    "mis_z",
    "syn_z",
    "oe_mis",
    "obs_lof",
    "exp_lof",
    "constraint_flags",
    "haploinsufficiency",
    "triplosensitivity",
    "dataset",
)


class GeneMetricsRow(BaseModel):
    """One gene's population-constraint metrics, keyed by the gene symbol a module authored.

    Standalone (not an `AuthoredModel`) for the same reason `ResolutionRow`/`FrequencyRow` are — a
    derived reference fact, not an authored annotation — with `extra="forbid"` so a typo'd column is
    caught rather than dropped.
    """

    #: What makes two rows the same row — the key both writers of this table merge on
    #: (`enrich_gene_metrics` and the ClinGen dosage pass). Keyed by (gene, dataset) and not by gene:
    #: one gene legitimately carries a row per authority, and keying on the gene alone made a second
    #: authority's row look like this pass's own work and suppressed the fetch (S51).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("gene", "dataset")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    gene: str = Field(
        description="HGNC-style symbol, matching the `gene` column authored in variants.csv"
    )
    gene_id: str | None = Field(
        default=None,
        description=(
            "Ensembl gene id (`ENSG…`) — the stable identity behind the mutable symbol. Carried "
            "because symbols are aliases that get renamed while the ENSG does not, so a module "
            "authored against an old symbol can still be matched."
        ),
    )
    transcript: str | None = Field(
        default=None, description="Ensembl transcript (`ENST…`) the metrics were computed on"
    )
    mane_select: bool | None = Field(
        default=None,
        description=(
            "Whether `transcript` is the MANE Select transcript. Load-bearing for reproducibility, "
            "not decoration: the source is per-transcript and the row pick must be deterministic."
        ),
    )

    # ── loss-of-function constraint ──
    pli: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Probability of being loss-of-function intolerant"
    )
    loeuf: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "LoF observed/expected upper bound fraction — the source's `oe_lof_upper`, stored under "
            "the name clinical readers actually ask for it by. `oe_lof`/`oe_lof_lower` sit beside it "
            "so the point estimate and the full interval are never lost."
        ),
    )
    oe_lof: float | None = Field(default=None, ge=0.0, description="LoF observed/expected ratio")
    oe_lof_lower: float | None = Field(
        default=None, ge=0.0, description="Lower bound of the LoF o/e 90% CI"
    )
    lof_z: float | None = Field(default=None, description="LoF constraint Z score")
    obs_lof: int | None = Field(default=None, ge=0, description="Observed LoF variant count")
    exp_lof: float | None = Field(default=None, ge=0.0, description="Expected LoF variant count")

    # ── missense / synonymous constraint ──
    oe_mis: float | None = Field(
        default=None, ge=0.0, description="Missense observed/expected ratio"
    )
    mis_z: float | None = Field(default=None, description="Missense constraint Z score")
    syn_z: float | None = Field(
        default=None,
        description="Synonymous constraint Z score — near zero for a well-behaved gene, so it doubles as a sanity check",
    )

    constraint_flags: str | None = Field(
        default=None,
        description=(
            "The source's own caveat list (e.g. 'no_exp_lof', 'outlier_detected'), kept verbatim and "
            "pipe-joined. A flagged gene's scores are not to be read at face value, and folding that "
            "warning away would be the format editorializing over its source."
        ),
    )
    # ── 0.5: ClinGen dosage sensitivity. Gene-keyed like everything else here, so it is columns on
    # this sidecar rather than a table of its own — the grain is the same question ("what does a
    # reference say about this gene?"), only a second authority answering it. A ClinGen row and a
    # gnomAD row are separate rows sharing the gene, each naming its own `dataset`. ──
    haploinsufficiency: str | None = Field(
        default=None,
        description=(
            "ClinGen haploinsufficiency rating: no_evidence|little_evidence|some_evidence|"
            "sufficient_evidence|autosomal_recessive|dosage_sensitivity_unlikely. NOT an ordinal — "
            "see VALID_DOSAGE_SENSITIVITY. A FACT."
        ),
        json_schema_extra=vocabulary("dosage_sensitivity", VALID_DOSAGE_SENSITIVITY),
    )
    triplosensitivity: str | None = Field(
        default=None,
        description=(
            "ClinGen triplosensitivity rating, same vocabulary. Empty where ClinGen says 'Not yet "
            "evaluated' — an absence, not a rating. A FACT."
        ),
        json_schema_extra=vocabulary("dosage_sensitivity", VALID_DOSAGE_SENSITIVITY),
    )
    dataset: str = Field(
        description="Which release these metrics are from, e.g. 'gnomad_v4.1_constraint'. A FACT."
    )

    # ── provenance (EXCLUDED from gene_metrics_signature) ──
    source: str | None = Field(
        default=None,
        description=(
            "The licensed data source these metrics came from: gnomad|clingen|manual|reversed (open). "
            "Joins `sources.csv.source`. It names the SOURCE, not the route — which release and which "
            "route answered is `dataset`'s job, and a v2.1.1 API figure and a v4.1 bulk figure are "
            "different facts precisely because `dataset` is inside the fact set and this column is not."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Outcome: resolved|not_found (the ResolutionRow vocabulary)",
        json_schema_extra=vocabulary("resolution_status", VALID_RESOLUTION_STATUS),
    )
    fetched_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-03T02:03:23Z'). Canonicalized on load; records when this row was last written by a pass, not when the source published anything")

    @field_validator("haploinsufficiency", "triplosensitivity")
    @classmethod
    def _check_dosage(cls, v: str | None, info) -> str | None:
        return check_vocab(v, VALID_DOSAGE_SENSITIVITY, info.field_name or "dosage sensitivity")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        # The field's own description named this vocabulary and nothing enforced it, so
        # `status="totally-made-up"` validated while every sibling fact table refused the same cell
        # (RM96). `@registry-completeness` from the other side: this model sat outside
        # `reference._ALL_MODELS`, so the guard that discovers an unenforced vocabulary by iterating
        # the registry could not see it. Both halves are fixed together — the model is inside the
        # registry now, which is what stops the next one.
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("gene")
    @classmethod
    def _check_gene(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("gene must not be empty")
        return v

    @field_validator("pli", "loeuf", "oe_lof", "oe_lof_lower", "lof_z", "mis_z", "syn_z",
                     "oe_mis", "exp_lof")
    @classmethod
    def _check_finite(cls, v: float | None, info) -> float | None:
        # A NaN breaks round-trip equality (NaN != NaN makes idempotency checks oscillate) and
        # serialises to the non-reloadable cell "nan" — the same rule the authored models apply to
        # `effect_size`. A genuinely absent metric is null, never NaN.
        return validate_finite(v, info.field_name)

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

"""The per-gene expression-effect table (0.7, RM194/RM200).

`expression_effects.csv` is the tenth derived-fact sidecar. It records, per `(variant, gene)` pair,
which way a variant moves that gene's predicted expression, how large the move is, how many of the
source's tissue tracks agree on the direction, and how far the variant sits from the gene. Filled by
`just-dna-enricher`'s `alphagenome expression` pass, consumed and hashed by the compiler, never
fetched by it.

**Why it exists.** The AlphaGenome AVI artifact RM191 adopted is one number per variant with the
**sign discarded** — its eighteen features are all `MAX_ABS_*`, so it can say a variant matters and
cannot say which way. The Atlas API has the direction that artifact threw away, and RM200 measured
all twenty-two scorers to find which of it is recordable. Exactly one survived: `RNA_SEQ` is the only
scorer with a gene axis, the only one whose disagreement across tracks is meaningful rather than
flat, and the only one that **attributes its own claim to a gene** — which is what
`@gene-map-is-another-sources-attribution` requires, since a gene claim must come from a source's own
per-record attribution and never from a span the caller drew. Every other scorer either restates
`AVI_SCORE` or ranks noise: the top-5 of `CAGE`'s 546 tracks carry 2–7% of the effect, and the
concentration runs *backwards* to effect size.

**Why a derived sidecar rather than an authored column.** Atlas Output is non-commercial (only the
AVI SNV scores are Permissive Use), and RM193's position is that non-commercial Output enters as a
finding and never as a stored value. A sidecar keeps that rule literally — nothing here is
**authored**, nothing enters `content_signature`, and the compile gate still reads `sources.csv` and
nothing else — while carrying an axis a finding cannot: per-gene direction survives, and a finding
would have to collapse it to prose. Half cost under Principle 9 rather than full.

**One row is one `(variant, gene)` pair.** Not one per variant: the whole reason to keep the gene
axis is that a variant genuinely raises one gene and lowers another, which is also why `RNA_SEQ`
never reaches consensus across its tracks (52–61% throughout, measured over six variants spanning
four decades of effect size). That disagreement is the signal, so a summary that collapses genes
would destroy the thing that makes this scorer worth having. And not one row per *track*: 371 tissue
tracks per gene is lossless and unreadable, and a table a human can never open is not a table this
format ships.

**This row carries coordinates, and `gwas_effects.csv` deliberately does not — same reason, opposite
outcome.** There, a coordinate would have to be copied from the module's own `resolution.csv`,
making it the module's fact rather than the source's. Here the coordinate **is** the source's fact:
the Atlas answers an interval query with the variant it scored, and the rows are locus-wide by
design — most of them name variants the module does not author, because finding the distal ones is
the entire point of the item. A row with no coordinate would be unjoinable to anything.

**What is deliberately not here.**

* **`tracks_agreeing` is a count, never a confidence.** RM200 tested consensus-as-confidence and
  killed it: `CAGE` and `PROCAP` are near-unanimous at *every* variant, 97% agreement at a `PHRED`
  of 0.007, so agreement does not separate a consequential variant from an inconsequential one. The
  count is recorded because a reader may want it; nothing in this tier gates on it, and no threshold
  withholds a direction.
* **No `gene_strand` column.** Strand is a property of the gene, recoverable from any gene
  annotation, and it is not this source's fact about this variant. Recording it beside a signed
  score would invite a consumer to "correct" the sign for a minus-strand gene, which would invert
  the claim. It is an additive optional column if a caller ever needs it (Principle 3).
* **No unit on `effect_size`, stated rather than invented.** AlphaGenome publishes no unit for a
  scorer's output, so `effect_unit` is `None` and `effect_measure` names the scorer instead. That is
  `@weight-has-no-unit` obeyed rather than dodged: the rule is that a magnitude needs its unit beside
  it, and where no unit exists the honest record is the absence plus the name of what produced the
  number. Scores are comparable within the scorer and across nothing else.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_EFFECT_DIRECTIONS,
    VALID_RESOLUTION_STATUS,
    check_vocab,
    validate_finite,
)

# Fact columns feeding `integrity.expression_effect_signature` — everything but the provenance
# columns (`source`/`status`/`fetched_at`), so a hand-curated and a pass-filled table carrying the
# same claims hash equal.
#
# **`gene` and `gene_id` are BOTH inside, and they are not a duplicate.** `gene` is the HGNC symbol
# and `gene_id` is the versioned Ensembl accession; symbols are renamed between releases while
# accessions are not, so a table that kept only the symbol would hash differently after a rename that
# changed no claim, and one that kept only the accession would be unjoinable to every authored `gene`
# column in this format. Two axes, two columns (Principle 5).
#
# **`distance_to_gene` is inside**, because it is a fact about this pair: the same variant scored
# against a different gene sits a different distance away, and RM194's whole finding is that distal
# scores run ~10x lower, so a threshold that cannot see the distance silently keeps only the
# proximal rows.
#
# **`tracks_total` is inside too, not just `tracks_agreeing`.** A fraction cannot say that its
# denominator moved — if AlphaGenome ships a model with a different track panel, 40/371 and 40/512
# are different facts and must hash differently (`@a-cell-key-carries-the-value-when-two-rows-may-
# state-two-claims`, one layer down).
#
# `dataset` is inside for the reason it is everywhere else: it names which query produced the row,
# and a re-query against a changed service is a different fact.
EXPRESSION_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "rsid",
    "chrom",
    "start",
    "ref",
    "alt",
    "gene",
    "gene_id",
    "effect_size",
    "effect_measure",
    "effect_unit",
    "effect_direction",
    "tracks_agreeing",
    "tracks_total",
    "distance_to_gene",
    "dataset",
)


class ExpressionEffectRow(BaseModel):
    """One `(variant, gene)` pair: which way the variant moves that gene, and how far away it is.

    Standalone (not an `AuthoredModel`) for the same reason every fact row is — machine-produced
    reference fact, not an authored annotation — with `extra="forbid"` so a typo'd column is caught
    rather than silently dropped.
    """

    #: What makes two rows the same row. **Per pair, not per variant**: one variant carries one row
    #: per gene it is attributed to, and collapsing them would pick a gene on the author's behalf.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "gene")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    variant_key: str = Field(
        json_schema_extra=since("0.7.0"),
        description=(
            "The variant half of this row's identity. Joins `weights.parquet.variant_key` where the "
            "module happens to author the variant — and most rows will not be joined at all, because "
            "an interval query answers for every scored variant in the window and the distal ones "
            "are what the query was for."
        ),
    )
    rsid: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "The rsID, when one is known for this position. Null is the common case and not a "
            "defect: the Atlas answers by coordinate and names no rsID at all, so this is filled "
            "only where the module or its `resolution.csv` already knew one."
        ),
    )
    chrom: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "Contig, as the module spells it — `22`, not `chr22`. The Atlas ships `chr22` and the "
            "conversion happens in the pass, which is where RM193 found a silent-wrong-answer bug: "
            "a join that matched nothing looked exactly like an uncovered region."
        ),
    )
    start: int | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        ge=0,
        description=(
            "The 1-based VCF position (`@start-1based`). Bounded `ge=0` rather than `ge=1` because "
            "VCF permits POS 0; the Atlas speaks 0-based intervals and 1-based variants, and "
            "`atlas_client` converts at its own boundary so nothing downstream has to know."
        ),
    )
    ref: str | None = Field(
        json_schema_extra=since("0.7.0"), default=None, description="Reference allele, as the source scored it."
    )
    alt: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "The single alternate allele this score is for. **One ALT per row, not a list**: the "
            "score is per substitution, and three ALTs at one position are three different claims."
        ),
    )

    # ── the gene, which is the SOURCE's attribution and not ours ──
    gene: str = Field(
        json_schema_extra=since("0.7.0"),
        description=(
            "HGNC symbol, **as AlphaGenome attributed it** — `GeneScorerMetadata.name` from the "
            "response, never a symbol looked up from a span the caller drew "
            "(`@gene-map-is-another-sources-attribution`). The gene half of this row's identity."
        ),
    )
    gene_id: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "Ensembl gene accession, **verbatim including the version** — `ENSG00000040608.14`, not "
            "`ENSG00000040608` (`@verbatim-except-order`). Upstream's own proto comment says this "
            "field is 'without version number' and the live service returns it versioned, which is "
            "why the version is recorded rather than trusted away: a consumer joining on bare "
            "accessions truncates on purpose, and one who believed the comment would have written a "
            "join that silently matches nothing."
        ),
    )

    # ── the effect ──
    effect_size: float | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "The magnitude, aggregated over the scorer's tissue tracks for this gene. Its meaning is "
            "`effect_measure`; it has no unit, and `effect_unit` says so rather than guessing one."
        ),
    )
    effect_measure: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "What kind of magnitude it is — the scorer that produced it, `RNA_SEQ` in practice. Open "
            "prose rather than a vocabulary: the Atlas publishes twenty-two scorers and RM200 "
            "adopted one, so closing this would make adopting a second a schema change rather than a "
            "pass change."
        ),
    )
    effect_unit: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "The unit the magnitude is in, verbatim from the source when it states one. **Null for "
            "every AlphaGenome row, and that is the honest record rather than a hole**: the service "
            "publishes no unit for a scorer's output, so these scores are comparable within the "
            "scorer and across nothing else. Present so a future source that does state a unit has "
            "somewhere to put it (`@weight-has-no-unit`)."
        ),
    )
    effect_direction: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("effect_direction", VALID_EFFECT_DIRECTIONS), **since("0.7.0")},
        description=(
            "Whether the variant increases or decreases this gene's predicted expression — the "
            "majority sign across the scorer's tracks. **Not clinical direction**: `VariantRow."
            "direction` is protective|risk|neutral|unknown and answers a different question, since "
            "raising a gene may be good, bad or neither. Shares `VALID_EFFECT_DIRECTIONS` with "
            "`GwasEffectRow` because it is the same axis — the sign of a magnitude, not a judgement."
        ),
    )
    tracks_agreeing: int | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        ge=0,
        description=(
            "How many of `tracks_total` carried `effect_direction`'s sign. **A record, never a "
            "confidence**: RM200 measured consensus against effect size across six variants and "
            "found it flat — `CAGE` is 97% unanimous at a `PHRED` of 0.007 — so a high count says "
            "the tracks agree and says nothing about whether the variant matters."
        ),
    )
    tracks_total: int | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        ge=0,
        description=(
            "How many tissue tracks the scorer reported for this gene — 371 for `RNA_SEQ` today. "
            "Stored beside `tracks_agreeing` rather than divided into it, because a fraction cannot "
            "say that its denominator moved."
        ),
    )
    distance_to_gene: int | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        ge=0,
        description=(
            "Base pairs from the variant to the gene's span, `0` inside it. **The reason this column "
            "exists is that a threshold without it is wrong**: AlphaGenome attributes a variant to "
            "genes across the model's whole 1 Mb input window, reaching +/-512 kb and stopping dead "
            "beyond, and distal scores run ~10x lower than scores at the gene — so a flat "
            "`--min-score` silently keeps only the proximal rows, which is exactly the failure "
            "RM194 exists to prevent. **Null is unknown, not zero**: the span comes from the MANE "
            "lane, and a deployment without that lane provisioned records the absence rather than a "
            "distance it could not compute."
        ),
    )
    dataset: str = Field(
        json_schema_extra=since("0.7.0"),
        description=(
            "Which query produced this row, e.g. 'alphagenome_atlas_2026-09-11'. A FACT, and dated "
            "rather than versioned because the service publishes no release label: AlphaGenome's "
            "Output Terms pin the applicable terms version to the date the Output was generated, so "
            "the date is a real property of the row rather than a stand-in for a missing one."
        ),
    )

    # ── provenance (EXCLUDED from expression_effect_signature) ──
    source: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "The licensed data source: alphagenome_atlas|manual (open). Joins `sources.csv.source`. "
            "**Never `alphagenome_avi`** — one name cannot carry two licence classes, and the AVI "
            "artifact is Permissive Use while this scorer's output is non-commercial."
        ),
    )
    status: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("resolution_status", VALID_RESOLUTION_STATUS), **since("0.7.0")},
        description=(
            "Outcome: resolved|not_found|ambiguous. `not_found` is a FACT — the interval was queried "
            "and the service attributed this variant to no gene — and differs from a variant never "
            "queried, which has no row at all (`@unreachable-not-absent`)."
        ),
    )
    fetched_at: str | None = Field(
        json_schema_extra=since("0.7.0"),
        default=None,
        description=(
            "ISO-8601 UTC timestamp, second resolution. Canonicalized on load; records when this row "
            "was written by a pass, not when AlphaGenome generated anything — that is `dataset`."
        ),
    )

    @field_validator("variant_key")
    @classmethod
    def _check_variant_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("variant_key must not be empty")
        return v

    @field_validator("gene")
    @classmethod
    def _check_gene(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(
                "gene must not be empty — it is half this row's identity, and it is the source's own "
                "attribution rather than something the caller may leave for later"
            )
        return v

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("dataset must name the query this row came from")
        return v

    @field_validator("effect_direction")
    @classmethod
    def _check_effect_direction(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_EFFECT_DIRECTIONS, "effect_direction")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("effect_size")
    @classmethod
    def _check_finite(cls, v: float | None, info) -> float | None:
        # `info.field_name` rather than a hardcoded name, the idiom RM96 arrived at: registered for
        # one field today, this still reports the right column the day it covers two.
        return validate_finite(v, info.field_name or "effect_size")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v)

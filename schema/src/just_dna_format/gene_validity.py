"""The source-independent gene–disease validity table (0.6, RM24).

`gene_validity.csv` is the fifth derived-fact sidecar, and the second keyed on a gene rather than a
variant. `gene_metrics.csv` answers *how constrained is this gene*; this one answers *does variation
in this gene cause this disease, and how sure is anyone*. Filled by `just-dna-enricher`'s gene-validity
pass (ClinGen gene–disease validity, GenCC's aggregate of nineteen submitters), consumed and hashed by
the compiler, never fetched by it.

**Why a table and not columns on `gene_metrics.csv`.** The grain is `gene × disease term × mode of
inheritance`, not `gene`. Dosage sensitivity went the other way in 0.5 for exactly that reason — a
haploinsufficiency rating is one value per gene, so it is two columns on the gene row — while
*RYR1* carries a definitive assertion for malignant hyperthermia and a separate one for a congenital
myopathy, and neither is a property of the gene alone. Columns cannot hold two.

**Three facts about the real files that decide the shape**, all from reading them rather than their
documentation (ClinGen's `gene-validity/download`, 3,659 rows, and GenCC's `submissions-export-csv`,
30,410 rows, both on 2026-08-13):

* **Mode of inheritance is part of the key.** 59 (gene, disease) pairs in ClinGen carry two rows that
  differ only by MOI — *ACO2* and mitochondrial disease, *ACTA1* and nemaline myopathy — and keying
  without it silently keeps one. Adding `(gene, disease, moi)` leaves zero collisions.
* **GenCC is an aggregate, so `submitter` is in the key too.** Nineteen submitters, and the same
  gene–disease pair is routinely asserted by several at different strengths (*AARS1* /
  Charcot-Marie-Tooth 2N is Definitive to ClinGen and Strong to Labcorp). One row per submitter is the
  data; picking one would be the bare-triple mistake `PharmVariantRow` already paid for once.
* **The two vocabularies disagree in spelling and agree in meaning**, so they are normalized here
  (`vocab.VALID_GENE_VALIDITY`, `vocab.VALID_INHERITANCE_MODE`) rather than stored verbatim. Verbatim
  is right for an identity — a star allele, an accession — and wrong for a value a consumer will
  filter or sort on, which is the same line ClinGen's dosage codes fall on.

**No `classification` for a source that publishes none.** A submitter can assert an association
without grading it; the cell is then empty, which is this codebase's answer to an unknown everywhere
else. It is not the same as `no_known_disease_relationship`, which is a graded verdict *against*.
"""


from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_GENE_VALIDITY,
    VALID_INHERITANCE_MODE,
    VALID_RESOLUTION_STATUS,
    check_vocab,
)

# Fact columns feeding `integrity.gene_validity_signature` — everything but the provenance columns
# (`source`/`status`/`fetched_at`) and the two *descriptive* ones, so a hand-curated and a
# ClinGen-filled table carrying the same verdicts hash equal (the producer-independence every fact
# table buys).
#
# `dataset` is INSIDE, for the reason it is in every sibling: a 2024 curation and its 2026 revision
# are different facts about the world, and a table that swapped releases must hash differently.
# `submitter` is INSIDE because on GenCC it is half the row's identity — "Ambry says Limited" and
# "ClinGen says Definitive" are two claims, not one claim recorded twice.
#
# **`report_url` and `disease_label` are OUTSIDE, on one rule: a column that *locates or describes*
# the assertion is not the assertion.** `report_url` moves when a site reorganizes; `disease_label` is
# the ontology's current wording for a term the CURIE already names, and it churns independently of
# anything a curator did. That is not hypothetical — one real export carries **MONDO:0017146** under
# two labels at once, `"sickle cell disease and related diseases"` from ClinGen and
# `"obsolete sickle cell disease and related diseases"` from GenCC. Inside the fact set, two
# submitters recording the same disease would hash differently on label vintage alone, and a MONDO
# relabel would move the signature of assertions nobody touched. `disease_id` is the identity and
# `assertion_id` the stable per-curation one; both are inside.
GENE_VALIDITY_FACT_FIELDS: tuple[str, ...] = (
    "gene",
    "gene_id",
    "disease_id",
    "moi",
    "classification",
    "classification_raw",
    "classification_date",
    "submitter",
    "assertion_id",
    "dataset",
)


class GeneValidityRow(BaseModel):
    """One curated gene–disease assertion, keyed by (gene, disease, mode of inheritance, submitter).

    Standalone (not an `AuthoredModel`) for the same reason `ResolutionRow`/`FrequencyRow`/
    `GeneMetricsRow`/`LiteratureRow` are — a machine-produced reference fact rather than an authored
    annotation — with `extra="forbid"` so a typo'd column is caught rather than silently dropped.
    """

    #: What makes two assertions the same assertion, and this key has **two levels** — the only
    #: derived table that does. `assertion_id` when the source published one: it is the source's own
    #: answer and it survives a re-worded disease label. When it did not, the source's grain decides,
    #: which is what `_KEY_FALLBACK_FIELDS` names. Never `(gene, disease)` alone, which collapses 59
    #: real ClinGen curations, and never without `submitter`, which collapses the disagreement GenCC
    #: exists to publish (S51).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("assertion_id",)
    _KEY_FALLBACK_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene",
        "disease_id",
        "moi",
        "submitter",
        "dataset",
    )

    model_config = ConfigDict(extra="forbid")

    # ── the gene ──
    gene: str = Field(json_schema_extra=since("0.6.0"), 
        description="HGNC-style symbol, matching the `gene` column authored in variants.csv"
    )
    gene_id: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "HGNC id (`HGNC:20`) — the stable identity behind the mutable symbol, which both sources "
            "publish. Carried for the reason `GeneMetricsRow.gene_id` carries the ENSG: symbols are "
            "renamed and the id is not, so a module authored against an old symbol still matches."
        ),
    )

    # ── the disease ──
    disease_id: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "CURIE for the disease term, as the source states it — `MONDO:0013212` from ClinGen and "
            "GenCC, `OMIM:…`/`ORPHA:…` from a source that publishes those. Stored verbatim: a CURIE "
            "is an identity, and rewriting one across ontologies is a claim this tier cannot make."
        ),
    )
    disease_label: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The term's human-readable name as the source publishes it, so the table is legible "
            "without resolving the CURIE. Descriptive, never the join key, and deliberately OUTSIDE "
            "the fact hash: one real export carries MONDO:0017146 under two labels at once, so a "
            "label says when it was read rather than what was asserted."
        ),
    )

    # ── the assertion ──
    moi: str | None = Field(
        default=None,
        description=(
            "Mode of inheritance the assertion is scoped to: autosomal_dominant|autosomal_recessive|"
            "x_linked|x_linked_dominant|x_linked_recessive|y_linked|mitochondrial|semidominant|"
            "undetermined. Part of the KEY, not decoration — 59 ClinGen (gene, disease) pairs carry "
            "two rows differing only here. `undetermined` is a stated finding; empty means the source "
            "has no such concept."
        ),
        json_schema_extra={**vocabulary("inheritance_mode", VALID_INHERITANCE_MODE), **since("0.6.0")},
    )
    classification: str | None = Field(
        default=None,
        description=(
            "Strength of the gene–disease assertion: definitive|strong|moderate|limited|supportive|"
            "disputed|refuted|no_known_disease_relationship|animal_model_only. Normalized from the "
            "submitter's own wording at the enricher boundary. Empty where the source asserts an "
            "association without grading it — which is NOT `no_known_disease_relationship`, a graded "
            "verdict against. A FACT, never this workspace's opinion."
        ),
        json_schema_extra={**vocabulary("gene_validity", VALID_GENE_VALIDITY), **since("0.6.0")},
    )
    classification_raw: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The submitter's verbatim wording (`Disputed Evidence`, `Definitive`), kept so the "
            "mapping above stays auditable and a term this release does not model is still visible. "
            "Same role `clin_sig_raw` plays beside `clin_sig`."
        ),
    )
    classification_date: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "ISO-8601 UTC timestamp of the curation itself — when the panel ruled, not when this row "
            "was written (that is `fetched_at`). Inside the fact set: a re-curation of the same pair "
            "is a new fact."
        ),
    )
    submitter: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "Who made the assertion — 'Charcot-Marie-Tooth Disease Gene Curation Expert Panel' from "
            "ClinGen, 'Ambry Genetics' from GenCC. Part of the key on an aggregate: one gene-disease "
            "pair routinely carries several submitters at different strengths, and they are all data."
        ),
    )
    assertion_id: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The source's own stable id for this assertion (ClinGen's `CGGV:assertion_…`, GenCC's "
            "uuid). The identity half of `report_url`, which is why that one is outside the fact set "
            "and this one is inside."
        ),
    )
    report_url: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description="Where a human can read the curation. Outside the fact set — a location, not a fact.",
    )
    dataset: str = Field(json_schema_extra=since("0.6.0"), 
        description=(
            "Which release this assertion is from, e.g. 'clingen_gene_validity_2026-08-13'. A FACT, "
            "for the reason it is one on every sibling table: two releases are two facts."
        )
    )

    # ── provenance (EXCLUDED from gene_validity_signature) ──
    source: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The licensed data source this assertion came from: clingen|gencc|manual|reversed (open). "
            "Joins `sources.csv.source`. It names the SOURCE, never the route — the release and the "
            "route are `dataset`'s job, which is why that column is inside the fact set and this is not."
        ),
    )
    status: str | None = Field(
        default=None,
        description="Outcome: resolved|not_found|ambiguous (the ResolutionRow vocabulary)",
        json_schema_extra={**vocabulary("resolution_status", VALID_RESOLUTION_STATUS), **since("0.6.0")},
    )
    fetched_at: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-13T02:03:23Z'). Canonicalized "
            "on load; records when this row was last written by a pass, not when the curation was made "
            "— that is `classification_date`."
        ),
    )

    @field_validator("gene")
    @classmethod
    def _check_gene(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("gene must not be empty")
        return v

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("dataset must name the release this assertion came from")
        return v

    @field_validator("classification")
    @classmethod
    def _check_classification(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_GENE_VALIDITY, "classification")

    @field_validator("moi")
    @classmethod
    def _check_moi(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_INHERITANCE_MODE, "moi")

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("classification_date", "fetched_at", mode="before")
    @classmethod
    def _canonical_timestamps(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`.

        `classification_date` goes through the same normalizer as `fetched_at` because ClinGen writes
        `2024-03-14T16:00:00.000Z` (millisecond precision) and GenCC writes `2018-03-30 13:31:56` (no
        zone marker at all). Two spellings of one instant in one column would hash as two facts.
        """
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))


# ── Currency: which assertion is the live one, and where nothing can say (RM108) ─────────────────
#
# ClinGen's `assertion_id` **embeds the curation timestamp**
# (`CGGV:assertion_…-2019-08-18T160312.829Z`), so a re-curated assertion arrives under a different id,
# misses `_merge_key`, and is appended beside the row it replaces. `manifest.gene_validity` then
# published a pair as far apart as `["definitive", "refuted"]` with nothing anywhere saying which is
# current, and `classification_date` and `dataset` were the only discriminators — neither of which any
# consumer read.
#
# **Nothing is stored, and that is the decision rather than an economy.** A `superseded` column would
# have to be written onto the row that is *already in the file*, which is precisely what
# merge-not-clobber forbids (`@sidecar-authoritative`): the pass may append the new curation and may
# not edit the old one, so the marker would be correct on every run except the one that created the
# ambiguity. A `superseded_by` pointer fails that way too and adds three problems of its own — GenCC
# rows may carry no `assertion_id` to point at, a row superseded twice needs a rule about immediate
# versus current successor, and a pointer is a *location* rather than an assertion, which is the
# line `GENE_VALIDITY_FACT_FIELDS` already draws to keep `report_url` outside.
#
# Currency is a total function of the rows present, so it is derived at every read instead
# (`@derived-not-stored`). Both tiers call this one function: the enricher to report, the compiler to
# warn and to build the manifest block. Nothing about the file changes, so
# `integrity.gene_validity_signature` does not move and no existing module recompiles to new bytes.

#: What makes two rows the same assertion across curations — the source's grain **without `dataset`**,
#: which is the one difference from `_KEY_FALLBACK_FIELDS`. `dataset` names the release, and a
#: re-curation is by definition a later release of the same claim, so including it would put the two
#: rows in different groups and answer "nothing was superseded" every time. Deliberately *beside*
#: `_merge_key` and never inside it: the merge must keep both rows, because the drift staying visible
#: is the property this whole item exists to preserve.
CURRENCY_GROUP_FIELDS: tuple[str, ...] = ("gene", "disease_id", "moi", "submitter")

#: A row's standing within its group. `None` is the third state and is not a failure mode: it means
#: nothing here can order the group, so no row is called current and none is called superseded. The
#: house algebra withholds rather than guessing (`None` is never `False`).
CURRENT: str = "current"
SUPERSEDED: str = "superseded"


def currency_group(row: "GeneValidityRow") -> tuple:
    """The group a row's currency is decided within. See `CURRENCY_GROUP_FIELDS`."""
    return tuple(getattr(row, name) for name in CURRENCY_GROUP_FIELDS)


def classify_currency(rows: "Sequence[GeneValidityRow]") -> list[str | None]:
    """Per row: `CURRENT`, `SUPERSEDED`, or `None` where nothing orders its group.

    **Newest `classification_date` wins, and nothing is deleted.** That is S45's answer carried to a
    weaker signal, and taking it means accepting one thing this format had not accepted before — that
    a date is authoritative for currency. The concession is narrower than it looks: the date decides
    *ordering* and nothing else. It never says a classification is right, both rows stay in the file so
    the drift stays visible, and a consumer wanting the history still has it.

    Publishing both facts and leaving the consumer to choose was the honest alternative and lost on one
    point: every consumer then implements the same date comparison, and they will not all implement it
    the same way.

    **Two edges, and both withhold** rather than inventing an order:

    * a **tie** on `classification_date` — two curations of one claim stamped the same instant, and
      nothing in the row says which came second;
    * **any row in the group carrying no date** — an undated row cannot be placed, and calling it
      superseded because a dated one exists would assert a fact about a curation on the strength of a
      cell the source left empty.

    In both cases every row in the group answers `None`. Breaking a tie on `assertion_id` was
    rejected: an identifier carries no chronology, and sorting on one would manufacture a winner out
    of a spelling.

    **A group of one is `CURRENT`**, dated or not — there is nothing to order it against, and a lone
    assertion is the live one by construction. That is what keeps this quiet on the ordinary module:
    a check that cannot fail must not report (`@tautology-zero`), and almost every real group is a
    singleton.
    """
    groups: dict[tuple, list[int]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(currency_group(row), []).append(index)

    verdicts: list[str | None] = [None] * len(rows)
    for members in groups.values():
        if len(members) == 1:
            verdicts[members[0]] = CURRENT
            continue
        dates = [rows[i].classification_date for i in members]
        if any(d is None for d in dates):
            continue          # undated row in the group — nothing can be placed
        newest = max(dates)
        if dates.count(newest) > 1:
            continue          # a tie orders nothing
        for index in members:
            verdicts[index] = (
                CURRENT if rows[index].classification_date == newest else SUPERSEDED
            )
    return verdicts


def superseded_groups(rows: "Sequence[GeneValidityRow]") -> list[tuple]:
    """The groups where a later curation replaced an earlier one, in first-seen order.

    Deterministic order because a warning built from it is a published string: insertion order is the
    order the groups were first met, never a set iteration (`@dont-discard-computed` next door — the
    ordering rules the compiler keeps).
    """
    verdicts = classify_currency(rows)
    seen: list[tuple] = []
    marked: set[tuple] = set()
    for row, verdict in zip(rows, verdicts, strict=True):
        key = currency_group(row)
        if verdict == SUPERSEDED and key not in marked:
            marked.add(key)
            seen.append(key)
    return seen


def undecidable_groups(rows: "Sequence[GeneValidityRow]") -> list[tuple]:
    """The multi-row groups nothing orders — a tie, or a member with no `classification_date`.

    Reported **separately** from the superseded ones, because they ask the reader for different
    things: a superseded row is the archive having moved on, and an unorderable group is the archive
    not having said enough to tell. Collapsing them would publish one number meaning two facts, which
    is the shape `@unreachable-not-absent` exists about.
    """
    verdicts = classify_currency(rows)
    counts: dict[tuple, int] = {}
    order: list[tuple] = []
    undecided: set[tuple] = set()
    for row, verdict in zip(rows, verdicts, strict=True):
        key = currency_group(row)
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
        if verdict is None:
            undecided.add(key)
    return [key for key in order if key in undecided and counts[key] > 1]

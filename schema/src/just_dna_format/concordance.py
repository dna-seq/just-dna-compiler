"""The clinical-significance concordance record, in two paired tables (0.7, RM130).

A check counted its findings and kept none of them. `enrich()` compares each authored `clin_sig`
against ClinVar's and reports *twenty of 141,616* — a number an author can read and not act on,
because nothing says which twenty in a form anything can join to. `clin_sig_concordance.csv` is those
rows, named.

**A conflict is a question, and an `overrides.csv` row is the answer.** That sentence is the whole
lifetime. The record is machine-written and never hand-edited: an author who has read a contested row
and decided records the decision as an overlay row against this table — with the `reason` the overlay
makes mandatory — rather than editing the finding away. Two things follow. The decision travels with
the module instead of living in a curator's head. And the terminal state becomes visible for free: an
overlay row that stops changing anything means the archive caught up with the author, which is
evidence that a judgement was vindicated and is available nowhere else in this format.

**`overrides.csv`, never `provenance.json`'s `outranks`.** Both record an authored value beating a
source with prose, and 0.7 settled the overlap as a dated succession rather than a merge: the overlay
wins and `outranks` is filed for removal at the major. Pointing new authors at the mechanism that
survives costs a sentence, so this table's documentation and the warning that reports it both name
the overlay and neither names the knob.

## Why two tables rather than one

The agreement *state* belongs to the subject and each authority's words belong to the authority, and
one row cannot hold both without either nesting a cell or keying on the authority. Keying on the
authority gives N rows per variant and leaves the state with nowhere to live; nesting gives a cell a
reader has to parse. So:

* `clin_sig_concordance.csv`, keyed `(variant_key, genotype)` — one row per contested subject, and
  the key is **stable at any number of authorities**. That stability is the point of the split: the
  earlier draft named its authority in a field (`ClinSigConflict.clinvar`), which would have cost a
  key change or a retype the moment a second authority arrived — major-only work, one item later.
* `clin_sig_authority_calls.csv`, keyed `(variant_key, genotype, authority)` — what each authority
  actually said, its raw token, and its confidence.

**The key cannot be a bare `variant_key`.** The comparison is of an authored call for a *genotype*,
and `annotations.parquet` keys on genotype for the same reason; a table keyed on the variant alone
collapses two authored calls that disagree with the archive differently.

**Confidence is not normalized across authorities.** ClinVar's `review_stars` and a literature
miner's evidence-depth count are different instruments measuring different things, and folding them
into one number is three axes in one field. So the detail row carries the value the authority
published and the name of the instrument beside it, and nothing in this tier compares two of them.

## What the record deliberately does not do

**Nothing resolves a split.** With five authorities in a two-against-three disagreement, a declared
precedence order says one thing and a majority says another, and choosing between those rules is a
judgement about how rank trades against agreement count — a weighting model. This workspace has
declined to invent one three times, and the same refusal applies here: there is no `majority` column,
no consensus call and no resolved winner. `authored_position` is a relation to the *set*, computable
with no weights and true at any topology, and the detail rows carry everything a consumer with its
own model needs.

**And it never escalates.** A disagreement with an archive is a fact about the field, not a defect in
the module: half the time the archive is the stale side, and failing a build on one would have the
format arbitrate a clinical dispute. Warning-tier in both modes, exactly like the check it records.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import (
    VALID_AUTHORED_POSITION,
    VALID_AUTHORITY_CALL_STATUS,
    VALID_AUTHORITY_CONCORDANCE,
    VALID_CLIN_SIG,
    check_vocab,
)

#: Fact columns feeding `integrity.clin_sig_concordance_signature` — the key, the authored call the
#: record is about, and the two verdicts. `checked_at` is outside for the reason `fetched_at` is
#: outside every sibling: when a comparison ran is not what it found, and a re-run that changed
#: nothing must not move a signature.
#:
#: `opposed` is **inside**. It is not a restatement of the two verdicts — `discordant` says the
#: authorities disagree and says nothing about whether the disagreement crosses the pathogenic/benign
#: line — so a module whose contested rows became opposed asserts something different from one whose
#: rows merely differ, and the two must not hash equal.
CLIN_SIG_CONCORDANCE_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "genotype",
    "authored_clin_sig",
    "authority_concordance",
    "authored_position",
    "opposed",
)

#: Fact columns feeding `integrity.clin_sig_authority_call_signature`. `dataset` is inside on the
#: rule every sibling table applies — two releases of an archive are two facts, and a record built
#: against a later ClinVar is not the same record. `checked_at` is outside, as above.
CLIN_SIG_AUTHORITY_CALL_FACT_FIELDS: tuple[str, ...] = (
    "variant_key",
    "genotype",
    "authority",
    "status",
    "clin_sig",
    "clin_sig_raw",
    "confidence",
    "confidence_unit",
    "dataset",
)


class ClinSigConcordanceRow(BaseModel):
    """One contested subject: how the authorities sit, and where the module's own call sits.

    Standalone rather than an `AuthoredModel`, like every other machine-produced fact row: a human
    writes no row of this table, and `extra="forbid"` catches a typo'd column instead of dropping it.

    **The two verdicts are separate fields because they are separate questions** (Principle 5), and
    that separation is what makes both vocabularies five members at two authorities and five at five.
    A single field would have to name the authority inside the member to say the same thing, which is
    the combinatorial explosion a stress test at five sources found.
    """

    #: What makes two records the same record. Genotype is in it because the comparison is of an
    #: authored call for a genotype: a site whose reference call the module reads one way and whose
    #: homozygous call it reads another disagrees with the archive twice, differently.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "genotype")

    model_config = ConfigDict(extra="forbid")

    variant_key: str = Field(json_schema_extra=since("0.7.0"), 
        description="The subject's `variant_key`, matching the one in variants.csv and weights.parquet"
    )
    genotype: str = Field(json_schema_extra=since("0.7.0"), 
        description=(
            "The authored genotype the clinical call was made for, spelled as variants.csv spells it. "
            "Part of the KEY: one variant carries one record per genotype the module annotates."
        )
    )

    authored_clin_sig: str | None = Field(
        default=None,
        description=(
            "The module's own `effective_clin_sig` for this subject at the time of the comparison. "
            "Empty where the module makes no clinical claim, which is the `absent` position rather "
            "than a disagreement with anybody."
        ),
        json_schema_extra={**vocabulary("clin_sig", VALID_CLIN_SIG), **since("0.7.0")},
    )
    authority_concordance: str = Field(
        description=(
            "Whether the authorities agree with EACH OTHER: concordant|discordant|single|none|"
            "unchecked. Says nothing about the module's call — that is `authored_position`. "
            "`unchecked` means an authority could not be consulted at all, and is never agreement."
        ),
        json_schema_extra={**vocabulary("authority_concordance", VALID_AUTHORITY_CONCORDANCE), **since("0.7.0")},
    )
    authored_position: str = Field(
        description=(
            "Where the module's own call sits relative to the authorities that spoke: matches_all|"
            "matches_some|matches_none|absent|unchecked. A relation to the SET, at camp granularity "
            "— nothing here picks a winner among disagreeing authorities, because picking needs a "
            "weighting model this format does not have."
        ),
        json_schema_extra={**vocabulary("authored_position", VALID_AUTHORED_POSITION), **since("0.7.0")},
    )
    opposed: bool | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "True when two of the calls in play sit in OPPOSITE camps — a pathogenic-class call "
            "against a benign-class one, counting the module's own — rather than merely differing. "
            "`None` where the camps could not be established, which is not `False`: a subject nobody "
            "could be asked about has not been shown to be uncontroversial. Stored rather than "
            "derived because the camp map lives in the enricher and no consumer can reach it."
        ),
    )

    # ── provenance (EXCLUDED from clin_sig_concordance_signature) ──
    checked_at: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "ISO-8601 UTC timestamp, second resolution, of the comparison that wrote this row. "
            "Canonicalized on load. Records when the question was put, never what the answer was, "
            "which is why it is outside the fact set."
        ),
    )

    @field_validator("variant_key", "genotype")
    @classmethod
    def _check_key_cell(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("variant_key and genotype both identify the subject and must be set")
        return v

    @field_validator("authored_clin_sig")
    @classmethod
    def _check_authored_clin_sig(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_CLIN_SIG, "authored_clin_sig")

    @field_validator("authority_concordance")
    @classmethod
    def _check_authority_concordance(cls, v: str) -> str:
        checked = check_vocab(v, VALID_AUTHORITY_CONCORDANCE, "authority_concordance")
        if checked is None:
            raise ValueError("authority_concordance must be set")
        return checked

    @field_validator("authored_position")
    @classmethod
    def _check_authored_position(cls, v: str) -> str:
        checked = check_vocab(v, VALID_AUTHORED_POSITION, "authored_position")
        if checked is None:
            raise ValueError("authored_position must be set")
        return checked

    @field_validator("checked_at", mode="before")
    @classmethod
    def _check_checked_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))


class ClinSigAuthorityCallRow(BaseModel):
    """What one authority said about one subject, in that authority's own terms.

    The detail half of the record, keyed `(variant_key, genotype, authority)` — so a subject carries
    one row per authority consulted, and adding an authority adds rows rather than columns.

    **It has no `source` column**, and the omission is structural rather than an oversight. `authority`
    already names the annotation source this row came from, and a second column holding the same
    string would be two spellings of one fact — the overloading Principle 5 forbids. The consequence
    is that this table is exempt from the orphan check that asks which declared licence rows a module's
    tables actually use, which is correct: the pass that consulted the authority writes its own
    `sources.csv` row, and that is where the licence position is recorded.

    **An authority's words are not the author's to correct**, which is why this table is outside the
    overlay's covered set while its parent is inside. The author answers the question; they do not get
    to rewrite what an archive published.
    """

    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "genotype", "authority")

    model_config = ConfigDict(extra="forbid")

    variant_key: str = Field(json_schema_extra=since("0.7.0"), description="The subject's `variant_key`; joins clin_sig_concordance.csv")
    genotype: str = Field(json_schema_extra=since("0.7.0"), 
        description="The authored genotype; the second half of the join onto clin_sig_concordance.csv"
    )
    authority: str = Field(json_schema_extra=since("0.7.0"), 
        description=(
            "Which annotation authority this call is from: clinvar|pubmind|manual (open). An "
            "authoritative ANNOTATION source in the sense ClinVar is one — never resolution.csv's "
            "`authority`, which names whoever supplied a coordinate."
        )
    )

    status: str = Field(
        description=(
            "What happened when this authority was consulted: recorded|no_record|unchecked. "
            "`no_record` is an established absence — asked, and it has nothing here. `unchecked` is "
            "nobody-asked: no snapshot was provisioned, or one was present and not queryable. The "
            "two are never interchangeable, and neither is agreement."
        ),
        json_schema_extra={**vocabulary("authority_call_status", VALID_AUTHORITY_CALL_STATUS), **since("0.7.0")},
    )
    clin_sig: str | None = Field(
        default=None,
        description=(
            "The authority's classification, normalized to this format's own vocabulary by the one "
            "shared significance normalizer every snapshot builder calls. Empty on `no_record` and "
            "on `unchecked`: an unknown is withheld, never written down as a negative."
        ),
        json_schema_extra={**vocabulary("clin_sig", VALID_CLIN_SIG), **since("0.7.0")},
    )
    clin_sig_raw: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "The authority's verbatim wording (`Conflicting_classifications_of_pathogenicity`, "
            "`Uncertain significance`), kept so the normalization above stays auditable and a term "
            "this release does not model is still visible."
        ),
    )
    confidence: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "How much the authority stands behind this call, in ITS OWN units and unconverted — "
            "ClinVar's gold-star count, a miner's evidence-depth count. A string because the "
            "instruments are not the same quantity, so a numeric column would invite an arithmetic "
            "nobody can justify. Meaningless without `confidence_unit` beside it."
        ),
    )
    confidence_unit: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "Which instrument `confidence` is measured on, e.g. 'review_stars'. Required whenever "
            "`confidence` is set: a magnitude with no unit beside it is a number nothing can read, "
            "and this format has paid for that once already on `weight`."
        ),
    )
    dataset: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "Which release of the authority answered, e.g. 'clinvar_2026-08-01'. A FACT, on the rule "
            "every sibling applies: two releases are two facts about the world."
        ),
    )

    # ── provenance (EXCLUDED from clin_sig_authority_call_signature) ──
    checked_at: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "ISO-8601 UTC timestamp of the consultation that wrote this row. Canonicalized on load, "
            "and outside the fact set for the reason `fetched_at` is outside every sibling."
        ),
    )

    @field_validator("variant_key", "genotype", "authority")
    @classmethod
    def _check_key_cell(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(
                "variant_key, genotype and authority together identify the call and must all be set"
            )
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        checked = check_vocab(v, VALID_AUTHORITY_CALL_STATUS, "status")
        if checked is None:
            raise ValueError("status must be set")
        return checked

    @field_validator("clin_sig")
    @classmethod
    def _check_clin_sig(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_CLIN_SIG, "clin_sig")

    @field_validator("checked_at", mode="before")
    @classmethod
    def _check_checked_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

    @field_validator("confidence_unit")
    @classmethod
    def _check_confidence_unit(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    def model_post_init(self, __context: object) -> None:
        """Refuse a magnitude with no unit, and a call with no classification.

        Two coherence rules the field validators cannot see on their own, both of them the same
        mistake in different clothes — a cell that reads as an answer and is not one.

        `confidence` without `confidence_unit` is the `weight` lesson restated: nothing downstream can
        read `2` without being told it is a gold-star count, and the two authorities this record is
        built for publish numbers on the same scale that mean different things.

        `status='recorded'` with no `clin_sig` claims an authority classified this subject while
        naming no classification, which is the shape an unknown takes when it is written down as an
        answer. `no_record` and `unchecked` are how a consultation with nothing to report is said.
        """
        if self.confidence is not None and self.confidence_unit is None:
            raise ValueError(
                f"confidence={self.confidence!r} names a magnitude with no instrument beside it — "
                f"set confidence_unit (e.g. 'review_stars'), because two authorities publish numbers "
                f"on scales that are not the same quantity"
            )
        if self.status == "recorded" and self.clin_sig is None:
            raise ValueError(
                "status='recorded' says this authority classified the subject, so clin_sig must "
                "carry the classification; an authority that was consulted and had nothing is "
                "'no_record', and one that could not be consulted at all is 'unchecked'"
            )
        if self.status != "recorded" and self.clin_sig is not None:
            raise ValueError(
                f"status={self.status!r} says this authority stated no classification, so clin_sig "
                f"must be empty — an unknown is withheld, never filled in with a value nobody gave"
            )

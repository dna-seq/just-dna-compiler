"""The source-independent literature table (0.5).

`literature.csv` is the third derived-fact sidecar, and the first that is **not keyed on a variant**.
`frequencies.csv` describes an allele and `gene_metrics.csv` describes a gene; a literature row
describes a *citation* — the paper itself, not any variant that happens to cite it. Filled by
`just-dna-enricher`'s literature pass (PubMed esummary, the PMC ID converter, Europe PMC), consumed
and hashed by the compiler, never fetched by it.

**Why the citation is the grain.** A DOI, a PMCID and "does PubMed have this record" are properties of
the article. A module with three hundred variants citing five papers carries five rows here, not three
hundred with the same DOI repeated — the same argument that put gene constraint in its own table
rather than on every variant row (Principle 5, and the one-CSV-one-concern rule). It also keeps the
file legible to the human author the DSL exists for: five lines they can read.

**Two departures from the drafted column set, both decided by probing rather than by taste.**

*No `dataset`.* Every other fact table carries one because gnomAD ships numbered releases and a v4.1
count is a different fact from a v2.1.1 count. PubMed and Europe PMC publish no release identifier at
all — they are continuously updated — so the column could only ever be null or a fabricated label.
`fetched_at` is this table's currency marker instead.

**The article's licence lives here, per article, and there is deliberately no `pubmed` row in the
licence table** (0.6, RM46). The pass that writes this file introduces `pubmed` as a source and the
tier has no terms constant for it — because a literature source's terms are *per article, not per
source*. PubMed's metadata is one thing; the article belongs to its publisher, and Europe PMC's open
subset spans CC-BY, CC-BY-NC and bronze. A single `sources.csv` row reading "pubmed, fine" would be
right for a module citing only ids and **wrong** for one carrying a `provenance_quote` lifted from a
CC-BY-NC article — wrong in the dangerous direction, since that quote is publisher text in the
module's own *annotation* layer, which is exactly where the compile gate bites. So the terms are
recorded on the row that names the article, and the compiler reads them from here rather than joining
`sources.csv`. Quoting a non-commercial article **warns and never gates**: the format arbitrating
copyright is the same class of overreach as it arbitrating a clinical dispute.

*Quote checking is two counts, not one boolean.* A quote is authored per *study row*, while this table's
grain is the citation, and two study rows may cite one paper with different quotes. A single
`quote_found` flag would therefore have to lie about one of them. Integers round-trip through CSV
exactly — the same reasoning that keeps `allele_count`/`allele_number` integral in `frequencies.csv`
rather than storing a float.
"""


from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.spec import DOI_PATTERN
from just_dna_format.vocab import VALID_QUOTE_SOURCE, VALID_RESOLUTION_STATUS, check_vocab

# Fact columns feeding `integrity.literature_signature`. Deliberately narrow, and the exclusions carry
# the argument:
#
# `is_open_access` is **out** — an embargo lifting is the outside world changing, not the module. In
# the fact set it would move the signature with no authored edit anywhere, which is exactly the
# property that makes a fact-hash worth having.
#
# `license` / `share_alike` / `commercial_use` / `redistribution` are **out for the same reason**
# (0.6, RM46): a publisher re-licensing an article, or Europe PMC learning terms it did not hold last
# month, changes the world rather than the module. They sit beside `is_open_access`, not beside the
# identifiers.
#
# `quotes_authored` / `quotes_found` are **out** for two reasons: the first is derivable from
# `studies.csv` (so storing it as a fact duplicates one fact in two files), and the second depends on
# whether a fulltext happened to be retrievable on the day the pass ran.
#
# What remains is stable identity: which article this is, and whether the registry has it.
LITERATURE_FACT_FIELDS: tuple[str, ...] = (
    "pmid",
    "doi",
    "pmcid",
    "exists",
)


class LiteratureRow(BaseModel):
    """One cited article, keyed by its PubMed id.

    Standalone (not an `AuthoredModel`) for the same reason `ResolutionRow`/`FrequencyRow`/
    `GeneMetricsRow` are — a machine-produced reference fact rather than an authored annotation — with
    `extra="forbid"` so a typo'd column is caught rather than silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    pmid: str = Field(
        description=(
            "PubMed id, digits only. Normalized from `StudyRow.pmid`, which is free-form and may "
            "carry several ids or a `[PMID: N]` wrapper (`spec.extract_pmids` does the extraction)."
        )
    )

    # ── cross-registry identifiers (facts: which article this is) ──
    doi: str | None = Field(
        default=None,
        description=(
            "Digital Object Identifier for this PMID, as the registry reports it. Filled here rather "
            "than written back into `studies.csv`: the enricher does not edit authored files, because "
            "`content_signature` is defined as reference-independent."
        ),
    )
    pmcid: str | None = Field(
        default=None,
        description="PubMed Central id (`PMC…`) when the article is in PMC — the key to fulltext.",
    )
    exists: bool | None = Field(
        default=None,
        description=(
            "Whether PubMed returned a document summary for this id. False is a FACT (the citation "
            "does not resolve), distinct from null (never checked)."
        ),
    )

    # ── provenance and time-varying state (excluded from the fact hash) ──
    is_open_access: bool | None = Field(
        default=None,
        description=(
            "Whether Europe PMC reports retrievable open-access fulltext. Outside the fact set: "
            "embargoes lift, so this describes the world's state rather than the module's."
        ),
    )
    license: str | None = Field(
        default=None,
        description=(
            "The article's own licence, verbatim as the source spells it (Europe PMC writes `cc by`, "
            "`cc by-nc`, `cc by-nc-nd`, `cc0`). Per ARTICLE, never per source: PubMed's metadata and "
            "the publisher's text are different property, and the open subset spans all of those."
        ),
    )
    share_alike: bool | None = Field(
        default=None,
        description=(
            "Whether the article's licence is viral (the `-SA` family). Null when the terms could "
            "not be established — never false, which would state that they permit something."
        ),
    )
    commercial_use: bool | None = Field(
        default=None,
        description=(
            "Whether the article's licence permits commercial reuse (`-NC` makes it false). This is "
            "what a module quoting the article in `provenance_quote` has to answer for, since that "
            "quote is publisher text sitting in the module's own annotation layer."
        ),
    )
    redistribution: bool | None = Field(
        default=None,
        description=(
            "Whether the article's licence permits passing the text on. A third axis, not a reading "
            "of the other two: CC BY-NC forbids sale and allows sharing."
        ),
    )
    quotes_authored: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many study rows cite this article with a `provenance_quote`/`provenance_regex`. "
            "Derivable from studies.csv; carried here so the coverage figure is readable in one place."
        ),
    )
    quotes_found: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many of those were located. **Null means not checked** (nothing retrievable), which "
            "is materially different from 0 (something was read and the quote was not in it). Read it "
            "with `quote_source`: a 0 against `abstract` means only the abstract was searched, so the "
            "quote may still be in the body."
        ),
    )
    quote_source: str | None = Field(
        default=None,
        description=(
            "What the quotes were matched against: fulltext|abstract. Null when neither could be "
            "retrieved. A hit is conclusive from either, but a *miss* is only conclusive against "
            "fulltext — which is why the two are recorded rather than collapsed."
        ),
    )
    doi_exists: bool | None = Field(
        default=None,
        description=(
            "Whether the authored/derived DOI resolves in Crossref. Independent of `exists`, which is "
            "PubMed's answer: a preprint, book or dataset has a DOI and no PMID, so this is the check "
            "that covers citations PubMed does not index at all."
        ),
    )
    source: str | None = Field(
        default=None,
        description="Which service answered: pubmed|pmc-idconv|europepmc (open, like every source column).",
    )
    status: str | None = Field(
        default=None, description="Lookup outcome: resolved|not_found|ambiguous"
    )
    fetched_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC timestamp, second resolution (e.g. '2026-08-03T02:03:23Z'). Canonicalized on load; records when this row was last written by a pass, not when the source published anything",
    )

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str) -> str:
        v = str(v).strip()
        if not v.isdigit():
            raise ValueError(
                f"pmid must be digits only here (the free-form authored form belongs in "
                f"studies.csv; use spec.extract_pmids to normalize it), got: {v!r}"
            )
        return v

    @field_validator("doi")
    @classmethod
    def _validate_doi(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not DOI_PATTERN.search(v):
            raise ValueError(f"doi must contain a DOI token (10.<registrant>/<suffix>), got: {v!r}")
        return v

    @field_validator("pmcid")
    @classmethod
    def _validate_pmcid(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip().upper()
        if not v.startswith("PMC") or not v[3:].isdigit():
            raise ValueError(f"pmcid must look like 'PMC1234567', got: {v!r}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESOLUTION_STATUS, "status")

    @field_validator("quote_source")
    @classmethod
    def _validate_quote_source(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_QUOTE_SOURCE, "quote_source")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        """One spelling, enforced on load — see `normalize.normalize_utc_timestamp`."""
        return normalize_utc_timestamp(v if v is None or isinstance(v, str) else str(v))

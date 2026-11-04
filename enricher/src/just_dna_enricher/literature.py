"""`enrich-literature` — the fourth pass: citations in, `literature.csv` out.

Closes the reachable part of the compiler's *"does the cited study support the row?"* blind spot. Three
questions, in increasing ambition and decreasing coverage:

1. **Does the citation exist?** PubMed `esummary`, batched. A nonexistent PMID comes back as a record
   carrying an `error` key, so this is a clean yes/no.
2. **Do the identifiers agree?** The DOI and PMCID arrive free in the same response. An *absent*
   authored DOI is filled here in the sidecar; an authored DOI that **contradicts** the registry is a
   finding. Neither is ever written back into `studies.csv` — the enricher does not edit authored files,
   because `content_signature` is defined as reference-independent, and a network fetch that could
   change it would make that documented property false.
3. **Does the quoted passage appear in the article?** Only for the open-access subset, and honestly
   labelled as such.

**All three are attested** (RM45): the pass writes `citation_existence`, `citation_identifier` and
`provenance_quote` into `verification.json` on its way out, including on the offline return, so a
module can say which of the three was put and over how many citations. Until 0.6 the answers reached
a log line and the result object and died there, which left a module whose citations had been checked
indistinguishable from one where the command was never run.

**Coverage is partial by nature, and saying so is part of the check.** A pass that reported "0 quotes
found" for an article it could not read would be describing its own reach as if it were a property of
the module. So the result separates *checked and not found* from *never retrievable* — `quotes_found`
is **null** rather than zero when no fulltext could be read — and, since dogfooding caught the
conflation, also from *nothing to check*: a citation with no authored quote asked no question and is
not counted against coverage. The same distinctions are carried into `manifest.literature`.

**Corrections to the drafted plan, made under probing rather than assumed:**

* The **PMC ID converter is not used**, though the plan budgeted for it. `esummary` already returns
  both `doi` and `pmc` in `articleids`, and Europe PMC's `search` returns `doi`/`pmcid` too — so the
  converter is a third request for data already in hand. Worse, it answers a *different question*: for
  PMID 12345678 (a real, indexed PubMed record) it replies `status: error, "Identifier not found in
  PMC"`, which is about PMC membership, not existence. Wiring it in as an existence check would report
  every paywalled article as a broken citation.
* **Europe PMC is not an existence oracle either.** Asked for three ids where one does not exist, it
  returns two results and simply omits the third — no error, no marker. Absence there is
  indistinguishable from "not indexed", so PubMed decides existence and Europe PMC only decides
  retrievability.

**On running `provenance_regex` here.** The charter requires a linear-time / ReDoS-safe engine for
pattern matching, written when the match was specified as *consumer-side* — arbitrary patterns meeting
arbitrary documents. Here the pattern comes from the module being enriched and the document from a
public archive, on the author's own machine, so the threat model is a curator writing a slow pattern by
accident rather than an attacker. That is worth a bound rather than a compiled dependency — so the
match runs under a wall-clock timeout, and a timeout is recorded as **not checked**.

That bound is enforced with a *child process*, not a thread, and the reason is worth stating because
the thread version looks correct: `re` cannot be interrupted, threads cannot be killed, and the
interpreter joins pool threads at exit — so a thread-based timeout returns on schedule and then hangs
the process on the way out. See `regex_matches`.
"""

import csv
import logging
import multiprocessing
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_citing_rows, load_csv_rows, table_citations
from just_dna_format.base import merge_key
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.literature import LiteratureRow, settled_quotes
from just_dna_format.manifest import VerificationRecord
from just_dna_format.normalize import now_utc_iso
from just_dna_format.spec import StudyRow, extract_pmcids, extract_pmids
from just_dna_format.spelling import doi_key, doi_token
from tenacity import (
    retry,
    wait_exponential_jitter,
)

from just_dna_enricher.eutils import EutilsClient, EutilsError, is_missing
from just_dna_enricher.licensing import article_terms, sidecar_path
from just_dna_enricher.locations import env_value
from just_dna_enricher.net import (
    GONE,
    RETIRED,
    UNREACHABLE,
    EndpointRetired,
    PacingGate,
    Withholding,
    aggregate_reason,
    attempt_floor,
    batched,
    could_not_ask_reason,
    dedupe,
    raise_if_retired,
    retired_message,
    retry_if_transient,
    withheld_reason,
)
from just_dna_enricher.verification import examples, ran, record_verification, skipped

logger = logging.getLogger(__name__)

DEFAULT_EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
#: Europe PMC's preprint full-text repository (RM349). Not the documented REST service: its
#: `/{id}/fullTextXML` answered 500 for every `PPR` id probed on 2026-11-04 (four of four, with and
#: without a full text), while this route, which the europepmc.org reader itself calls, served the
#: JATS. Named on its own because it is a different host, so a test double can route on it.
DEFAULT_EUROPEPMC_REPO_URL = "https://europepmc.org/api/fulltextRepo"
DEFAULT_CROSSREF_BASE = "https://api.crossref.org"
#: The current address of NCBI's PMC ID converter. The long-published
#: `www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` 301-redirects here (probed 2026-08-13); named rather
#: than relied on as a redirect so a client that follows none still lands in the right place.
DEFAULT_PMC_IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
#: PMC's BioC service, JSON flavour; the pmcid and the `unicode` encoding are appended per request.
DEFAULT_PMC_BIOC_URL = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json"

#: Derived from the model, never hand-kept. `SOURCES_FIELDNAMES` was a literal and quietly omitted
#: `redistribution`, so every `sources.csv` ever written recorded *unknown* for an axis the constants
#: state — the same shape this list had, and the same bug it would have grown on the RM46 columns.
#: `LiteratureRow` carries no compiler-stamped fields, so `model_fields` is exactly the authored
#: surface here (the `SourceRow` precedent).
_FIELDNAMES: list[str] = list(LiteratureRow.model_fields)

#: Seconds a single `provenance_regex` match may run before it is recorded as unchecked.
DEFAULT_REGEX_TIMEOUT = 5.0

#: The `source` a row written by this pass carries, and the only value the identifier cross-check
#: will compare against. A merged row spelling anything else — `manual`, a curator's correction —
#: holds the curator's own identifiers, and calling a disagreement with those "the registry's" would
#: be a false attribution. Named once so the writer and the comparison cannot drift apart.
_REGISTRY_SOURCE = "pubmed"

_WHITESPACE = re.compile(r"\s+")

#: The one status a fulltext service answers "no copy" with: an embargoed or author-manuscript-only
#: record is a 404 on Europe PMC. Every other 4xx, a 429 and a 5xx never answered the question (RM361).
FULLTEXT_ABSENT_STATUS = 404
#: How PMC's BioC service opens its 200 "no copy" body, recorded in `assets/pmc_bioc_no_result.txt`.
#: Only this body is an answer; any other 200 that is not JSON (a maintenance page) is not (RM361).
BIOC_NO_RESULT_PREFIX = "[Error] : No result can be found."


class LiteratureEnrichmentError(RuntimeError):
    """Raised in strict mode when a citation does not resolve, or contradicts its own identifiers."""


class LiteratureUnavailable(LiteratureEnrichmentError):
    """PubMed could not be reached, so no citation question was put at all (RM101).

    A subclass rather than a second exception, so every existing `except LiteratureEnrichmentError`
    still catches it (P3 — additive within a major). It separates **the source was asked and never
    answered** from a citation that genuinely does not resolve under `strict`. Only this one means
    nothing was established either way.

    Before RM101 an `EutilsError` travelled straight out of `enrich_literature` through a
    `try/finally` with no `except`, so a caller's `except LiteratureEnrichmentError` was silent for
    exactly the failure it was written for.

    Scoped to the eutils leg on purpose. `EuropePmcClient.fulltext` and `CrossrefClient.exists`
    already answer a transport failure with `None` rather than an exception — the tri-state withhold
    this codebase uses for "could not be retrieved" — and turning either into an error here would
    convert a withheld answer into a failed run.
    """


class FulltextUnavailable(LiteratureUnavailable):
    """A fulltext request never got an answer: a 5xx or a transport failure, after retries (RM258).

    Raised by `EuropePmcClient.fetch_fulltext` and `PmcBiocClient.fetch_fulltext`, the three-way form
    of the question. It is the *unreachable* arm, kept apart from a `None` return, which is *absent*
    (the service holds no copy). The two used to be one `None`, and the pass pinned an outage as an
    abstract-only row that merge-not-clobber never asked about again. A subclass, so an existing
    `except LiteratureUnavailable` still catches it.
    """


class LiteratureRetired(LiteratureUnavailable, EndpointRetired):
    """Europe PMC answered HTTP 410: it retired the endpoint asked (RM354).

    A fact about the source, not an outage, and not retried; a `LiteratureUnavailable` so every
    existing handler still catches it. Raised by `EuropePmcClient.lookup` only: the fulltext routes
    raise `FulltextRetired`, which their callers already catch as `FulltextUnavailable`.
    """


class FulltextRetired(FulltextUnavailable, EndpointRetired):
    """A fulltext service answered HTTP 410 for the route asked (RM361).

    Before RM361 every status below 500 read as *absent*, so a retired route wrote a permanent
    `fulltext_status="absent"` about every article it was asked for. A `FulltextUnavailable`, so the
    pass's handler still catches it; the pass records `retired` and asks again on the next run.
    """


def _yes_no(flag: object) -> bool | None:
    """Europe PMC's `'Y'`/`'N'` flag as a tri-state: `None` when the record does not carry it (RM361).

    `str(flag or "").upper() == "Y"` read a missing flag as `N`, so a record silent about open access
    was written to `literature.csv` as closed, and the pass skipped Europe PMC's fulltext for it.
    """
    said = str(flag).strip().upper() if flag is not None else ""
    return {"Y": True, "N": False}.get(said)


def _fulltext_absent_or_raise(exc: httpx.HTTPStatusError, service: str, subject: str) -> None:
    """Return when `exc` is a service's "no copy" answer (a 404); raise the right error otherwise (RM361).

    The one status mapping every fulltext route goes through: a 410 is `FulltextRetired`, and a 429,
    any other 4xx and a 5xx are `FulltextUnavailable`, a question that was never answered. A 429 and a
    5xx reach here only after the transient retries.
    """
    status = exc.response.status_code
    if status == FULLTEXT_ABSENT_STATUS:
        logger.info("No retrievable fulltext for %s from %s (HTTP %s)", subject, service, status)
        return
    if status == GONE:
        raise FulltextRetired(retired_message(service, exc.response)) from exc
    raise FulltextUnavailable(f"{service} answered {status} for {subject}'s fulltext") from exc


@dataclass
class DoiConflict:
    """An authored DOI that disagrees with the one the registry reports for the same PMID."""

    pmid: str
    authored: str
    registry: str

    def __str__(self) -> str:
        return (
            f"PMID {self.pmid}: authored doi {self.authored!r} disagrees with the registry's "
            f"{self.registry!r} — reported, never rewritten; one of the two citations is the wrong "
            f"paper, and only the author knows which"
        )


@dataclass
class PmcidConflict:
    """An authored PMC id that disagrees with the one PubMed reports for the same PMID (RM50).

    The `DoiConflict` shape, for the other cross-registry identifier. It costs no request — the PMC id
    is already in the `esummary` `articleids` block that answered existence — and it catches the case
    the schema guard cannot see: a cell like `21551363 (PMC3110567)` carries a real PubMed id, so
    nothing refuses it, while the two halves name different articles.
    """

    pmid: str
    authored: str
    registry: str

    def __str__(self) -> str:
        return (
            f"PMID {self.pmid}: authored {self.authored} disagrees with the PMC id PubMed reports "
            f"for it, {self.registry} — reported, never rewritten; the two identifiers name "
            f"different articles and only the author knows which one the claim rests on"
        )


@dataclass(frozen=True)
class DoiCitation:
    """What one run learned about a work cited by DOI alone, through `pmid=NONE` (RM349).

    One per distinct DOI (`spelling.doi_key`), however many rows cite it and in whatever spelling.
    **Not written to `literature.csv`**, whose rows are keyed on a PubMed id and feed a published
    parquet the compiler reads by PMID; so it is not pinned either, and every online run asks again.
    What it records goes into `verification.json`, which is the durable half.

    * `exists` is Crossref's tri-state (`None`: not asked under `--no-doi`, or never answered —
      `crossref_asked` tells the two apart), and `title` the work Crossref names for it
      (`@existence-not-identity`). No citing table carries a stated title to compare it with, so it
      is recorded and reported, never compared. `agency` is who registered the DOI when Crossref did
      not (`CrossrefWork.agency`).
    * The quote half has `LiteratureRow`'s columns and meanings: `fulltext_status` is `retrieved`,
      `absent` or `unreachable` (`None` when no quote asked the question), `quote_source` says which
      text was searched, and `quotes_checked()` is the same rule (`settled_quotes`).
    """

    doi: str
    exists: bool | None = None
    crossref_asked: bool = False
    title: str | None = None
    agency: str | None = None
    quotes_authored: int = 0
    quotes_found: int | None = None
    quote_source: str | None = None
    fulltext_status: str | None = None
    europepmc_id: str | None = None
    license: str | None = None

    def quotes_checked(self) -> int:
        return settled_quotes(self.quotes_authored, self.quotes_found, self.quote_source)


@dataclass
class LiteratureResult:
    """What the pass found, and — through `subject_rows` — what it found it *about*.

    **One subject set, read by the report, by the `strict` gates and by the attestation.** The set is
    the citations the module makes *now*, answered by the rows `literature.csv` holds *now*, and it is
    the single rule the whole pass turns on. Three separate defects came from parts of this file
    reading three different sets:

    * the `strict` gates read lists appended inside the fetch loop, so a module enriched once with
      `--best-effort` and then with `--strict` was blessed on a citation PubMed has no record of —
      the refusal depended on the order the two runs happened in, and the attestation written by the
      same run said `findings=1` while the gate beside it said nothing was wrong;
    * the identifier cross-check ran inside that loop too, so an existing `literature.csv` hid every
      DOI/PMC id disagreement;
    * the counts read `rows`, which is everything the sidecar carries and never shrinks, so a
      citation deleted from `studies.csv` went on being counted and no authored edit could clear the
      finding it produced.

    Merge-not-clobber is what makes the distinction real: the sidecar keeps rows for citations the
    module has since dropped, and those rows are still written back (deleting a curator's row is not
    this pass's call) — they are simply not what any of this run's questions were about.
    """

    rows: list[LiteratureRow]
    missing: list[str] = field(default_factory=list)  # PMIDs PubMed has no record of
    #: Why Crossref never answered, when it did not: `retired` once it answered 410 (RM361).
    crossref_unanswered: str = UNREACHABLE
    doi_conflicts: list[DoiConflict] = field(default_factory=list)
    pmcid_conflicts: list[PmcidConflict] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)  # the PMIDs the module cites right now
    existence_checked: int = 0  # of those, the ones carrying a verdict
    unresolved_citations: int = 0  # of those, the ones resolving nowhere
    doi_verdicts_stale: int = 0  # pinned DOI answers about another DOI
    doi_never_checked: int = 0  # cited DOIs no run has resolved
    noncommercial_quoted: list[str] = field(default_factory=list)  # quoted under a no-sale licence
    titles_as_quotes: list[str] = field(default_factory=list)  # PMIDs whose quote IS the title (S54)
    fulltext_requested: bool = True  # --fulltext/--no-fulltext, as run
    quotes_authored: int = 0
    quotes_found: int = 0
    quotes_checked: int = 0  # quotes a retrieved text settled
    quotes_unchecked: int = 0  # unretrievable + never examined
    quotes_unexamined: int = 0  # authored after the sidecar pinned the row
    quotes_without_pmid: int = 0  # quotes on `pmid=NONE` study rows, which no PMID reaches (RM336)
    citations_without_pmid: int = 0  # `pmid=NONE` rows on any citing table: cited by DOI alone (RM336)
    doi_citations: list[DoiCitation] = field(default_factory=list)  # what this run asked about them (RM349)
    fulltext_checked: list[str] = field(default_factory=list)  # PMIDs whose fulltext was read
    abstract_checked: list[str] = field(default_factory=list)  # PMIDs matched against the abstract only
    doi_missing: list[str] = field(default_factory=list)  # DOIs Crossref has no record of
    identifiers_authored: int = 0  # citations carrying an authored doi/PMC id
    identifiers_compared: int = 0  # of those, the ones PubMed also named one for
    identifiers_conflicting: int = 0  # of those, the ones where the two disagree
    identifiers_unmatched: int = 0  # of those, the ones PubMed named none for
    identifiers_foreign: int = 0  # of those, the ones a curator wrote
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    skipped_offline: bool = False

    @property
    def subject_rows(self) -> list[LiteratureRow]:
        """The rows this run's questions were about: a row for a citation the module still makes.

        Not `rows`, which is the whole sidecar — see the class docstring. Not this run's fetch list
        either: `literature.csv` *is* the pin, so a row merged from an earlier run carries a verdict
        that still stands, and counting only what this run looked up would let a no-op re-run replace
        a true attestation with `subjects=0`, which reads as "the check ran and had nothing in scope".
        """
        cited = set(self.cited)
        return [r for r in self.rows if r.pmid in cited]

    @property
    def coverage(self) -> str:
        """The sentence this pass exists to be able to say honestly.

        The denominator is what had **something to check** — a citation with no authored quote was
        not skipped for lack of a fulltext, it simply asked no question. Counting it as unretrievable
        was a real bug found by running this against `reference_examples/pathogenic_clinvar/`, whose
        single citation is open access *and* carries no quote: the old wording claimed its fulltext
        could not be retrieved, which was the opposite of true.

        **Counted in quotes, off the tally, and not in citations off the run's own fetch lists.** The
        earlier wording read `fulltext_checked`, which only ever holds PMIDs *this run* retrieved, so
        a no-op re-run over a pinned open-access citation printed "0 of 1 … 1 with nothing
        retrievable" one line above "1/1 found" — the same false retrievability claim the paragraph
        above records as a bug, arrived at from the other direction. Quotes also partition cleanly
        where citations do not: one citation can carry a settled quote and a never-examined one at
        once, so a citation-granular sentence has to put it in one bucket and be wrong about the
        other.
        """
        if self.quotes_authored == 0 and self.quotes_without_pmid:
            return _doi_quote_coverage(self)
        if self.quotes_authored == 0:
            return (
                f"no provenance quotes authored across {len(self.cited)} citation(s) — nothing to "
                f"check against fulltext"
            )
        if self.quotes_without_pmid:
            # The quotes on `pmid=NONE` rows (RM349) are a second clause rather than a share of the
            # first: they reach their text by DOI, through Europe PMC, and a reader acts on the two
            # gaps differently.
            return f"{self._pmid_coverage()}; {_doi_quote_coverage(self)}"
        return self._pmid_coverage()

    def _pmid_coverage(self) -> str:
        """The coverage sentence for the quotes a PubMed id reaches, as it read before RM349."""
        if not self.fulltext_requested:
            # `--no-fulltext` leaves every quote unchecked, and the generic wording below would call
            # that "nothing retrievable" — a claim about articles nobody tried to fetch, and one the
            # verification record for the same run contradicts by saying `not_requested`.
            return f"{self.quotes_authored} authored quote(s) not matched against anything: --no-fulltext"
        parts = [
            f"checked {self.quotes_checked} of {self.quotes_authored} authored quote(s) against "
            f"retrieved text"
        ]
        unretrievable = self.quotes_unchecked - self.quotes_unexamined
        if unretrievable:
            # An abstract miss lives here rather than in the checked count, and the clause says so: a
            # hit in an abstract settles a quote, a miss does not, so the two searches are not the
            # same evidence.
            parts.append(
                f"{unretrievable} with nothing retrievable (or only an abstract, where a miss is not "
                f"a verdict)"
            )
        if self.quotes_unexamined:
            parts.append(
                f"{self.quotes_unexamined} not looked up, because literature.csv pins their citation "
                f"at another quote count — re-run the pass online to re-derive it"
            )
        return "; ".join(parts)


# ── Europe PMC ──────────────────────────────────────────────────────────────────────────────────


@dataclass
class EuropePmcClient:
    """Open-access lookup and fulltext retrieval. Paced like every other client in this tier."""

    base_url: str = DEFAULT_EUROPEPMC_BASE
    repo_url: str = DEFAULT_EUROPEPMC_REPO_URL
    batch_size: int = 25
    min_request_interval: float = 0.5
    timeout: float = 30.0
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "EuropePmcClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=1.0, max=10.0),
        retry=retry_if_transient(),
        reraise=True,
    )
    def _fetch(self, url: str, params: dict | None = None) -> httpx.Response:
        """One paced request to any Europe PMC host, retried on a transport failure, a 5xx or a 429."""
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(url, params=params)
        response.raise_for_status()
        return response

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        return self._fetch(f"{self.base_url.rstrip('/')}/{path}", params)

    def lookup(self, pmids: list[str]) -> dict[str, dict]:
        """`pmid -> {pmcid, doi, is_open_access, license, abstract}` for the ids Europe PMC knows.

        Ids it does not know are simply **absent from the result**, with no error marker — which is why
        this is not an existence check. A caller must read a miss here as "not retrievable", never as
        "does not exist".

        **The abstract comes back for paywalled records too**, in this same response, and that is worth
        more than it looks: probed across a mix of non-open-access papers, four of five carried one
        (only a 1994 non-research document did not). It is the difference between checking a quote for
        the open-access minority and checking it for nearly everything.

        **So does the article's `license`** (RM46), which is why per-article terms cost no extra
        request. Probed 2026-08-13 over 100 records: the values are lowercase CC spellings — `cc by`
        (64), `cc by-nc` (28), `cc by-nc-nd` (8). It is **independent of `isOpenAccess`** and must not
        be derived from it: PMID 28546431 comes back `isOpenAccess: N` with `license: cc by`, since
        the flag describes Europe PMC's OA subset while the licence describes the article. Stored
        verbatim; `licensing.article_terms` maps it to rights at read time.
        """
        out: dict[str, dict] = {}
        for batch in batched(dedupe(pmids), self.batch_size):
            query = " OR ".join(f"EXT_ID:{pmid}" for pmid in batch)
            # **Translate, do not leak** (`@client-exception-contract`, RM230). `_get` retries the
            # transport legs and re-raises what survives; this method used to call it bare and then
            # `.json()` the result, so all three failure legs escaped as their httpx/json types:
            # a persistent 503 as `httpx.HTTPStatusError`, a refused connection as
            # `httpx.ConnectError`, and a 200 that is not JSON as `json.JSONDecodeError`. The last is
            # the exact fourth leg `test_client_exception_contract.py` was written for, and every
            # sibling client in this tier closes it in its own module.
            #
            # It mattered where it landed: `enrich_literature` calls this inside a `try:` whose only
            # companion is `finally:` — no `except` — which is verbatim the shape
            # `test_pass_exception_contract.py` exists to refuse. The pass-level suite never drove
            # this leg because its stub raises earlier, on the eutils call.
            #
            # `fulltext` below is deliberately NOT changed: it catches httpx and returns `None`, the
            # tri-state withhold this tier uses for "could not be retrieved". The two methods answer
            # different questions, which is why the class's contract-suite exemption named `fulltext`
            # and silently covered `lookup` too.
            try:
                response = self._get("search", {"query": query, "resultType": "core", "format": "json"})
                payload = response.json()
            except httpx.HTTPError as exc:
                raise_if_retired(exc, LiteratureRetired, "Europe PMC")
                raise LiteratureUnavailable(f"Europe PMC could not be asked: {exc}") from exc
            except ValueError as exc:
                raise LiteratureUnavailable(
                    f"Europe PMC answered {response.status_code} with a body that is not JSON: {exc}"
                ) from exc
            for record in (payload.get("resultList") or {}).get("result") or []:
                pmid = str(record.get("pmid") or "")
                if not pmid:
                    continue
                out[pmid] = {
                    "pmcid": record.get("pmcid"),
                    "doi": record.get("doi"),
                    # The API answers with the strings 'Y'/'N', not booleans.
                    "is_open_access": _yes_no(record.get("isOpenAccess")),
                    # `inEPMC` is NOT a fulltext signal: a record can be in Europe PMC with
                    # `isOpenAccess=N`, and `fullTextXML` then answers 404. Probed on PMID 23788249.
                    "in_epmc": _yes_no(record.get("inEPMC")),
                    # Verbatim, and `None` when the field is absent — an article whose terms Europe
                    # PMC does not state is unknown, not unlicensed.
                    "license": (record.get("license") or None),
                    "abstract": record.get("abstractText"),
                }
        return out

    def pmids_for_doi(self, doi: str) -> list[str]:
        """The PubMed ids Europe PMC holds for one DOI, sorted, from its MEDLINE source (RM263).

        Europe PMC's search covers all of PubMed, where NCBI's id converter answers only for articles
        in PMC, so this reaches the paywalled case the converter misses (`10.1038/ng826` is
        `11788828`, Enattah 2002, not in PMC). An empty list is **Europe PMC's** answer that it holds
        no MEDLINE record for the DOI, never a statement about PubMed. More than one id is returned as
        it came, so a caller can report the multiplicity rather than pick. Failures translate to
        `LiteratureUnavailable` on every leg, as `lookup` does (`@client-exception-contract`).
        """
        try:
            response = self._get(
                "search", {"query": f'DOI:"{doi}" AND SRC:MED', "resultType": "lite", "format": "json"}
            )
            payload = response.json()
        except httpx.HTTPError as exc:
            raise LiteratureUnavailable(f"Europe PMC could not be asked about DOI {doi}: {exc}") from exc
        except ValueError as exc:
            raise LiteratureUnavailable(
                f"Europe PMC answered {response.status_code} with a body that is not JSON: {exc}"
            ) from exc
        records = (payload.get("resultList") or {}).get("result") or []
        return sorted({str(r["pmid"]) for r in records if r.get("pmid")}, key=int)

    def fetch_fulltext(self, pmcid: str) -> str | None:
        """Whitespace-normalized article text; `None` when Europe PMC holds no copy; raises
        `FulltextUnavailable` when the request never got an answer (RM258, RM361).

        A 404 is an answer: an embargoed or author-manuscript-only record answers it, which is
        *absent*. A 410 raises `FulltextRetired`. A 429, any other 4xx, a 5xx, a transport failure
        and a 200 whose body does not parse as XML are *unreachable*, and the caller asks again on a
        later run.
        """
        try:
            response = self._get(f"{pmcid}/fullTextXML")
        except httpx.HTTPStatusError as exc:
            _fulltext_absent_or_raise(exc, "Europe PMC", pmcid)
            return None
        except httpx.HTTPError as exc:
            raise FulltextUnavailable(
                f"Europe PMC could not be reached for {pmcid}'s fulltext: {exc}"
            ) from exc
        text = extract_text(response.text)
        if text is None:
            # A 200 that is not JATS (a maintenance page) is the fourth leg: withheld, never `absent`.
            raise FulltextUnavailable(
                f"Europe PMC answered 200 for {pmcid}'s fulltext with a body that does not parse"
            )
        return text

    def fulltext(self, pmcid: str) -> str | None:
        """`fetch_fulltext` with its two negative answers folded into one `None`, as before 0.8.

        Kept for callers that already treat `None` as "no text either way" (the authoring plugin's
        `fetch_fulltext` tool relies on it for Europe PMC's 500s). A caller that needs to tell an
        outage from an absent copy uses `fetch_fulltext`.
        """
        try:
            return self.fetch_fulltext(pmcid)
        except FulltextUnavailable as exc:
            logger.warning("Fulltext fetch failed for %s (%s)", pmcid, exc)
            return None

    def record_for_doi(self, doi: str) -> dict | None:
        """Europe PMC's record for one DOI, from any of its sources, or `None` when it holds none (RM349).

        The route to a `pmid=NONE` citation's text. Europe PMC indexes bioRxiv and medRxiv preprints
        (source `PPR`) by DOI, so the same `search` that `pmids_for_doi` restricts to MEDLINE reaches
        them here unrestricted. Only a record whose own `doi` is the one asked about is taken: the
        search is a query, and a query's first hit need not be the work (`@existence-not-identity`).

        Returns `{id, source, pmcid, is_open_access, license, abstract, title, preprint_id}`.
        `preprint_id` is the `PPR` id when the record says Europe PMC holds the preprint's full text
        (its `fullTextIdList`), and `None` otherwise, so a caller asks the repository only where there
        is something to fetch: probed 2026-11-04, the repository's answer for a preprint with no text
        (`PPR1146237`) is a 500, the same status as an outage. Failures translate to
        `LiteratureUnavailable` on every leg, as `pmids_for_doi` does (`@client-exception-contract`).
        """
        try:
            response = self._get("search", {"query": f'DOI:"{doi}"', "resultType": "core", "format": "json"})
            payload = response.json()
        except httpx.HTTPError as exc:
            raise LiteratureUnavailable(f"Europe PMC could not be asked about DOI {doi}: {exc}") from exc
        except ValueError as exc:
            raise LiteratureUnavailable(
                f"Europe PMC answered {response.status_code} with a body that is not JSON: {exc}"
            ) from exc
        wanted = doi_key(doi)
        matching: list[dict] = []
        for record in (payload.get("resultList") or {}).get("result") or []:
            if not record.get("doi") or doi_key(str(record["doi"])) != wanted:
                continue
            record_id = str(record.get("id") or "")
            fulltext_ids = (record.get("fullTextIdList") or {}).get("fullTextId") or []
            preprint = record.get("source") == "PPR" and record_id in fulltext_ids
            matching.append(
                {
                    "id": record_id or None,
                    "source": record.get("source"),
                    "pmcid": record.get("pmcid"),
                    "is_open_access": _yes_no(record.get("isOpenAccess")),
                    # Verbatim, and `None` when absent: unknown terms are unknown, never unlicensed.
                    "license": record.get("license") or None,
                    "abstract": record.get("abstractText"),
                    "title": record.get("title"),
                    "preprint_id": record_id if preprint else None,
                }
            )
        # One DOI can have several records (a MEDLINE or AGRICOLA one beside the preprint's), and only
        # some carry a route to the text: the first one that does wins, else the first match, so an
        # earlier text-less hit never makes the answer `absent` while a later one holds the text.
        return next(
            (r for r in matching if r["pmcid"] or r["preprint_id"]), matching[0] if matching else None
        )

    def fetch_preprint_fulltext(self, preprint_id: str) -> str | None:
        """A preprint's JATS body as normalized text; `None` when the repository lists no XML file for
        it; raises `FulltextUnavailable` when a request never got an answer (RM349, the RM258 shape).

        Two requests: the record's file list (`type=METADATA`), then the JATS file it names
        (`type=FILE`). The file name (`EMS…nxml`) is never guessed, and the PDF the list also names is
        never used: its link is session-bound (it answered 403 "expired" on 2026-11-04). Ask only for a
        preprint whose search record lists a full text (`record_for_doi`'s `preprint_id`), because a
        5xx here then means an outage rather than the repository's "no such copy", which shares it.
        A 200 that is not the list is the fourth leg and withholds too (`@client-exception-contract`).
        """
        try:
            listing = self._fetch(self.repo_url, {"pprId": preprint_id, "type": "METADATA"})
            files = listing.json().get("files") or []
            xml = next(
                (f for f in files if isinstance(f, dict) and f.get("type") == "xml" and f.get("filename")),
                None,
            )
            if xml is None:
                logger.info("Europe PMC lists no XML full text for %s", preprint_id)
                return None
            response = self._fetch(
                self.repo_url,
                {
                    "pprId": preprint_id,
                    "type": "FILE",
                    "fileName": xml["filename"],
                    "mimeType": xml.get("mimeType") or "application/xml",
                },
            )
        except httpx.HTTPStatusError as exc:
            _fulltext_absent_or_raise(exc, "Europe PMC's preprint repository", preprint_id)
            return None
        except httpx.HTTPError as exc:
            raise FulltextUnavailable(
                f"Europe PMC's preprint repository could not be reached for {preprint_id}: {exc}"
            ) from exc
        except (ValueError, AttributeError) as exc:
            raise FulltextUnavailable(
                f"Europe PMC's preprint repository answered for {preprint_id} with no readable file list: {exc}"
            ) from exc
        text = extract_text(response.text)
        if text is None:
            # A 200 that is not JATS (a maintenance page) is the fourth leg: withheld, never `absent`.
            raise FulltextUnavailable(
                f"Europe PMC's preprint repository answered 200 for {preprint_id}'s JATS with a body that "
                f"does not parse"
            )
        return text


@dataclass(frozen=True)
class CrossrefWork:
    """What Crossref said about one DOI: whether it exists, and *which work* it names (RM262, S113).

    `exists` is the tri-state `CrossrefClient.exists` has always answered. The four bibliographic
    fields are the same four `bibliographic` pulls out of a PubMed record, so a DOI-only citation can
    be checked for identity and not merely existence. Each is `None` when the record does not carry
    it, never `""`, and all four are `None` whenever `exists` is not `True`.
    """

    exists: bool | None
    title: str | None = None
    journal: str | None = None
    year: str | None = None
    first_author: str | None = None
    #: The registration agency (`crossref`, `datacite`, …) when one answered (RM349). A DOI another
    #: agency minted exists with no Crossref record, so it has no title here: `exists=True`, the four
    #: fields `None`, and this field says why.
    agency: str | None = None


def crossref_bibliographic(message: dict) -> dict[str, str | None]:
    """The four identity fields out of a Crossref `/works/{doi}` `message`, shaped like `bibliographic`.

    The shapes differ from PubMed's and each difference is a place to go wrong. `title` and
    `container-title` are **lists**, empty for much `posted-content`. The year is the leading int of
    `issued.date-parts[0]`, Crossref's earliest-publication date. The first author is the entry marked
    `sequence: "first"`, which need not be at index 0, and is rendered `Family GI` so it reads the same
    as PubMed's `sortfirstauthor`; an organisational author has only a `name`. Title markup (Crossref
    passes JATS tags such as `<i>` through) is kept verbatim: the field is for a person to compare
    against the paper they meant, and rewriting it would be a second opinion about the title.
    """
    out: dict[str, str | None] = {"title": None, "journal": None, "year": None, "first_author": None}
    for key, target in (("title", "title"), ("container-title", "journal")):
        values = message.get(key)
        if isinstance(values, list) and values and isinstance(values[0], str) and values[0].strip():
            out[target] = " ".join(values[0].split())
    parts = (message.get("issued") or {}).get("date-parts")
    if (
        isinstance(parts, list)
        and parts
        and isinstance(parts[0], list)
        and parts[0]
        and isinstance(parts[0][0], int)
    ):
        out["year"] = str(parts[0][0])
    authors = [a for a in message.get("author") or [] if isinstance(a, dict)]
    first = next((a for a in authors if a.get("sequence") == "first"), authors[0] if authors else None)
    if first is not None:
        family = first.get("family")
        if isinstance(family, str) and family.strip():
            given = first.get("given") if isinstance(first.get("given"), str) else ""
            initials = "".join(part[0] for part in given.replace("-", " ").split() if part[:1].isalpha())
            out["first_author"] = f"{family.strip()} {initials}".strip()
        elif isinstance(first.get("name"), str) and first["name"].strip():
            out["first_author"] = first["name"].strip()
    return out


@dataclass
class CrossrefClient(Withholding):
    """DOI existence, for the citations PubMed does not index.

    PubMed answers "does this article exist" for anything it indexes — **including paywalled work**;
    a paywall governs the *fulltext*, not the record. What it cannot answer for is everything outside
    its scope: preprints, books, theses, datasets, standards. Those have DOIs and no PMID, and Crossref
    is the registry that mints and resolves them (a probed bioRxiv preprint, `10.1101/2024.06.17.599351`,
    returns `type: posted-content`; a fabricated DOI returns a clean 404).

    This is also what makes the 1.0 **doi-first** flip low-risk: once `pmid` becomes optional and a
    citation may carry only a DOI, existence checking has to work without PubMed, and it already does.

    Crossref asks callers to identify themselves in the User-Agent and gives the "polite pool" in
    return; the contact address is sent only when one is configured, for the same reason `eutils` omits
    it rather than inventing one.
    """

    base_url: str = DEFAULT_CROSSREF_BASE
    min_request_interval: float = 0.1
    timeout: float = 30.0
    contact_email: str | None = None
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        # Same rule as `EutilsSettings` and `PharmVarClient` (RM100, `@credential-where-read`): the
        # contact address lives in `.env`, and reading `os.environ` without loading it meant the
        # `mailto:` in the User-Agent appeared or not depending on whether some unrelated call had
        # resolved a cache path first. Both polite-identification services ask for it by name. Read
        # without exporting the rest of the `.env` (RM301).
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)
        if self.contact_email is None:
            self.contact_email = env_value("JUST_DNA_CONTACT_EMAIL") or None

    def _http(self) -> httpx.Client:
        if self._client is None:
            agent = "just-dna-enricher"
            if self.contact_email:
                agent += f" (mailto:{self.contact_email})"
            self._client = httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers={"User-Agent": agent}
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "CrossrefClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=1.0, max=10.0),
        retry=retry_if_transient(),
        reraise=True,
    )
    def _request(self, doi: str) -> httpx.Response:
        """The retrying half, kept separate so the translation sits **outside** the retry (RM208).

        Same split as `eutils._request`, `cpic._request` and `gnomad._request`, and it was the one
        client in this package that never got it. The decorator asked for three attempts and got
        **one**: the body caught `httpx.HTTPError`, which is the *superclass* of both retried types,
        so a `ConnectError` was turned into `None` before tenacity could see it and
        `attempt_floor(3)` — the knob a deployment is meant to raise — did nothing at all. Measured,
        not argued: one upstream request against a transport that raises every time.

        The gate is waited **inside** here, so each attempt is paced and `PacingGate.spent` counts
        one per upstream attempt, which is the definition RM203 published.
        """
        assert self.gate is not None
        self.gate.wait()
        return self._http().get(f"{self.base_url.rstrip('/')}/works/{doi}")

    def exists(self, doi: str) -> bool | None:
        """`True`/`False`, or `None` when Crossref could not be asked. `work(doi).exists`."""
        return self.work(doi).exists

    def work(self, doi: str) -> CrossrefWork:
        """Existence **and** identity, from the one request `exists` always made (RM262, S113).

        `exists` used to read the status and throw the body away, so a DOI got an existence answer and
        never the title that says which paper it is — the answer `existence is not identity` exists to
        refuse. The body was already in hand; parsing it costs no request.

        `exists=None` rather than `False` on a transport failure or an unexpected status: "we could not
        check" and "this DOI does not exist" are different claims, and only the second is a finding
        against the module. The translation stays here and the retrying stays in `_request` above —
        `reraise=True` means the last failure arrives back at this `except` after the attempts are
        spent. **A 200 whose body is not a Crossref record withholds too** (`@client-exception-contract`,
        the fourth leg): a maintenance page or a CDN interstitial is not Crossref saying the DOI exists,
        and `exists` used to answer `True` for one because it read only the status.
        """
        try:
            response = self._request(doi)
        except httpx.HTTPError as exc:
            logger.warning("Crossref lookup failed for %s (%s); not checked", doi, exc)
            return CrossrefWork(exists=None)
        if response.status_code == 404:
            return self._registered_elsewhere(doi)
        if response.status_code != 200:
            self.note_retired("Crossref", response)
            logger.warning("Crossref answered HTTP %s for %s; not checked", response.status_code, doi)
            return CrossrefWork(exists=None)
        try:
            message = response.json().get("message")
        except (ValueError, AttributeError):
            message = None
        if not isinstance(message, dict):
            logger.warning("Crossref answered 200 for %s with no readable record; not checked", doi)
            return CrossrefWork(exists=None)
        return CrossrefWork(exists=True, agency="crossref", **crossref_bibliographic(message))

    def _registered_elsewhere(self, doi: str) -> CrossrefWork:
        """After a `/works` 404: whether **any** agency registered the DOI (RM349).

        `/works` answers 404 for every DOI Crossref did not mint, and a `pmid=NONE` row cites exactly
        the works that are often minted elsewhere: a Zenodo dataset (`10.5281/zenodo.3360392`, DataCite)
        404s there and is real. Reading that 404 as "does not exist" made a real dataset a finding.
        Crossref's own `/works/{doi}/agency` route answers for every agency's DOIs (probed 2026-11-04:
        `datacite` for the Zenodo DOI, 404 for a fabricated one and for an unregistered Zenodo number),
        so the negative is now the registries' and not one registry's. An agency other than Crossref
        means the DOI exists and Crossref names no work for it. Any other answer withholds.
        """
        try:
            response = self._request(f"{doi}/agency")
        except httpx.HTTPError as exc:
            logger.warning("Crossref agency lookup failed for %s (%s); not checked", doi, exc)
            return CrossrefWork(exists=None)
        if response.status_code == 404:
            return CrossrefWork(exists=False)
        self.note_retired("Crossref", response)
        try:
            agency = response.json()["message"]["agency"]["id"] if response.status_code == 200 else None
        except (ValueError, KeyError, TypeError):
            agency = None
        if not isinstance(agency, str) or not agency or agency == "crossref":
            # `crossref` here contradicts the `/works` 404 one request earlier: withhold, never pick.
            logger.warning("Crossref answered %s on %s's agency; not checked", response.status_code, doi)
            return CrossrefWork(exists=None)
        return CrossrefWork(exists=True, agency=agency)


@dataclass(frozen=True)
class PmcIdRecord:
    """One answer from the PMC id converter. `in_pmc=False` is PMC saying it has no such record;
    an id the request never reached is absent from the result entirely, never one of these."""

    pmcid: str
    pmid: str | None = None
    in_pmc: bool = True
    error: str | None = None


@dataclass
class PmcIdConverterClient(Withholding):
    """PMCID → PMID, for a curator holding the wrong half of the pair (RM50).

    **It reports; it never fills.** The PMID it returns is handed back as an advisory the author types
    themselves, because filling `StudyRow.pmid` from NCBI would make `literature.exists` compare NCBI
    against NCBI — the `hints.REDUNDANCY_BEARING` rule, already argued for `doi` (Crossref is asked
    about the *authored* DOI, since a derived one exists by construction).

    **Why this exists although the pass docstring says the converter is unused.** That statement is
    true of the direction the pass needs — PMID → PMCID arrives free in the `esummary` `articleids`
    block, so calling the converter for it would be a third request for data already in hand, and it
    answers a *different* question (asked about a paywalled PMID it replies "Identifier not found in
    PMC", which is about PMC membership rather than existence). None of that says anything about
    **PMCID → PMID**, which is the direction the converter is actually for and the one a curator has
    no other route to.

    Probed 2026-08-13: the `www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` path 301-redirects to the
    address below, an absent id comes back as a record with `status: "error"` and
    `errmsg: "Identifier not found in PMC"`, and `pmid` arrives as a JSON **number**.
    """

    base_url: str = DEFAULT_PMC_IDCONV_URL
    batch_size: int = 200
    min_request_interval: float = 0.5
    timeout: float = 30.0
    contact_email: str | None = None
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        # Same rule as `EutilsSettings` and `PharmVarClient` (RM100, `@credential-where-read`): the
        # contact address lives in `.env`, and reading `os.environ` without loading it meant the
        # `mailto:` in the User-Agent appeared or not depending on whether some unrelated call had
        # resolved a cache path first. Both polite-identification services ask for it by name. Read
        # without exporting the rest of the `.env` (RM301).
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)
        if self.contact_email is None:
            self.contact_email = env_value("JUST_DNA_CONTACT_EMAIL") or None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PmcIdConverterClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=1.0, max=10.0),
        retry=retry_if_transient(),
        reraise=True,
    )
    def _get(self, params: dict) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(self.base_url, params=params)
        response.raise_for_status()
        return response

    def resolve(self, pmcids: list[str]) -> dict[str, PmcIdRecord]:
        """`PMCID -> PmcIdRecord` for every id the converter answered about.

        **Four outcomes, and none of them is spelled the same way as another.** An id it resolved
        carries a `pmid`; an id it knows with no PubMed id carries `in_pmc=True, pmid=None` (a real
        answer — some PMC records genuinely have none); an id it has no record of carries
        `in_pmc=False` with the service's own `errmsg`; and an id the request never reached is simply
        **absent from the result**. A caller must not read a missing key as "does not exist" — that
        conflation is exactly what S20 was about, one service over.
        """
        out: dict[str, PmcIdRecord] = {}
        for batch in batched(dedupe(pmcids), self.batch_size):
            params = {"ids": ",".join(batch), "format": "json", "tool": "just-dna-enricher"}
            if self.contact_email:
                params["email"] = self.contact_email
            try:
                payload = self._get(params).json()
            except httpx.HTTPError as exc:
                self.note_retired("The PMC id converter", exc)
                logger.warning("PMC id converter could not be asked for %s (%s)", batch, exc)
                continue
            for record in payload.get("records") or []:
                requested = str(record.get("requested-id") or record.get("pmcid") or "")
                if not requested:
                    continue
                pmid = record.get("pmid")
                out[requested] = PmcIdRecord(
                    pmcid=requested,
                    pmid=str(pmid) if pmid is not None else None,
                    in_pmc=record.get("status") != "error",
                    error=record.get("errmsg"),
                )
        return out


@dataclass
class PmcBiocClient(Withholding):
    """PMC's BioC text-mining service: the body text of an article Europe PMC will not serve (RM257, S110).

    **The records this reaches are the ones the Europe PMC rung cannot.** An NIH author manuscript is
    `isOpenAccess: N` in Europe PMC, so the pass never asked it for fulltext, and asking anyway
    answered HTTP 500 for `PMC6463297` on 2026-09-24. PMC serves the same manuscript here for text
    mining — 294 passages, both body tables among them as tab-separated `table` passages, and for a
    GWAS paper the tables are where the per-locus rows live. Probed the same day: an article outside
    the service's set answers **200** with the body `[Error] : No result can be found.`, which is an
    answer (no copy) rather than an outage, so it reads as absent like a 404 does.

    **Retrieval here says nothing about the article's licence.** The service's own infon reads *"This
    file is available for text mining. It may also be used consistent with the principles of fair
    use"*, which names no licence, so the row keeps Europe PMC's `is_open_access` and `license`
    untouched (`@no-named-licence`). It changes how far the quote search reached, which is what
    `quote_source` records, and nothing else.

    `REF` passages are dropped: they are the reference list, most of the document by count (186 of
    294 on the probed article), and a quote located in someone else's title is not located in this
    paper. An NCBI host, so the pass hands it the E-utilities gate rather than giving it a budget of
    its own (`@shared-pacing-gate`).
    """

    base_url: str = DEFAULT_PMC_BIOC_URL
    min_request_interval: float = 0.5
    timeout: float = 60.0
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PmcBiocClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=1.0, max=10.0),
        retry=retry_if_transient(),
        reraise=True,
    )
    def _get(self, pmcid: str) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(f"{self.base_url.rstrip('/')}/{pmcid}/unicode")
        response.raise_for_status()
        return response

    def fetch_fulltext(self, pmcid: str) -> str | None:
        """Body text with the reference list removed; `None` when the service holds no copy; raises
        `FulltextUnavailable` when the request never got an answer (RM258).

        **Only the recorded "no copy" 200 is an answer** (RM361). The service's reply for an article
        outside its set is a 200 with a plain-text body opening `BIOC_NO_RESULT_PREFIX`
        (`assets/pmc_bioc_no_result.txt`), so it reads as *absent*, as a 404 does. Any other 200 that
        is not JSON (a maintenance page) is the fourth leg and *unreachable*; a 410 raises
        `FulltextRetired`; a 429, any other 4xx, a 5xx or a transport failure, after the retries, is
        *unreachable*.
        """
        try:
            response = self._get(pmcid)
        except httpx.HTTPStatusError as exc:
            _fulltext_absent_or_raise(exc, "PMC BioC", pmcid)
            return None
        except httpx.HTTPError as exc:
            raise FulltextUnavailable(f"PMC BioC could not be reached for {pmcid}: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            if response.text.lstrip().startswith(BIOC_NO_RESULT_PREFIX):
                logger.info("No BioC text for %s (the service's 'no result' answer)", pmcid)
                return None
            raise FulltextUnavailable(
                f"PMC BioC answered 200 for {pmcid} with a body that is neither JSON nor its 'no result' "
                f"answer: {' '.join(response.text.split())[:80]!r}"
            ) from exc
        return extract_bioc_text(payload)

    def fulltext(self, pmcid: str) -> str | None:
        """`fetch_fulltext` with its two negative answers folded into one `None`, as before 0.8."""
        try:
            return self.fetch_fulltext(pmcid)
        except FulltextUnavailable as exc:
            if isinstance(exc, FulltextRetired) and isinstance(exc.__cause__, httpx.HTTPStatusError):
                self.note_retired("PMC BioC", exc.__cause__)
            logger.warning("BioC fetch failed for %s (%s)", pmcid, exc)
            return None


def extract_bioc_text(payload: object) -> str | None:
    """BioC JSON → one normalized string of every non-reference passage, or `None` if it holds none.

    The service wraps its collection in a one-element list; a bare collection is accepted too, since
    the BioC format itself does not require the wrapper.
    """
    collections = payload if isinstance(payload, list) else [payload]
    texts: list[str] = []
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        for document in collection.get("documents") or []:
            for passage in document.get("passages") or []:
                if (passage.get("infons") or {}).get("section_type") == "REF":
                    continue
                if passage.get("text"):
                    texts.append(passage["text"])
    joined = _WHITESPACE.sub(" ", " ".join(texts)).strip()
    return joined or None


def extract_text(xml: str) -> str | None:
    """JATS XML → one normalized string, or `None` if it is not a JATS article.

    `itertext()` rather than a tag-stripping regex: real JATS carries nested inline markup inside
    sentences (`<italic>`, `<xref>`, `<sup>`), and a regex that removes tags without joining their
    text would silently glue words together and break matches that should succeed.

    **A document that parses is not yet an article** (RM361): a maintenance page served as XHTML is
    well-formed XML, and reading its text as the article's would make every quote a miss against a
    fulltext, which settles it. Only a root element named `article` is JATS.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        logger.warning("Fulltext did not parse as XML (%s)", exc)
        return None
    if root.tag.rsplit("}", 1)[-1] != "article":
        logger.warning("Fulltext parsed as XML with a <%s> root, not a JATS <article>", root.tag)
        return None
    return _WHITESPACE.sub(" ", " ".join(root.itertext())).strip()


# ── quote / regex matching ──────────────────────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def quote_matches(quote: str, fulltext: str) -> bool:
    """Literal, whitespace- and case-insensitive containment. No engine, so nothing to bound."""
    return _normalize(quote) in _normalize(fulltext)


def _regex_worker(pattern: str, text: str, sink) -> None:
    """Run one match and post the verdict. Module-level so it survives a `spawn` start method."""
    sink.put(re.compile(pattern, re.IGNORECASE).search(text) is not None)


def regex_matches(pattern: str, fulltext: str, *, timeout: float = DEFAULT_REGEX_TIMEOUT) -> bool | None:
    """`True`/`False`, or **`None` when the match could not be completed in time**.

    The three-way return is the point: a pattern that runs long has not failed to match, it has failed
    to be *checked*, and reporting it as "not found" would send an author to fix a quote that is
    probably there.

    **Why a subprocess and not a thread.** The obvious implementation — submit to a
    `ThreadPoolExecutor` and take `future.result(timeout=...)` — does not work, and fails in a way that
    looks like it works: `re` never releases the GIL to a cancellation, threads cannot be killed, and
    the interpreter joins non-daemon pool threads at exit. So a runaway pattern returns `None` on time
    and then hangs the process on the way out. Verified by writing it that way first and watching the
    test suite stop. A child process is the only bound in the standard library that can actually be
    enforced, and it is cheap here: it runs only for a row that has a `provenance_regex` *and* a
    retrievable fulltext, which is a small subset of a small subset.
    """
    try:
        re.compile(pattern)
    except re.error as exc:
        # The compiler already grammar-checks `provenance_regex`, so this is a corrupt sidecar rather
        # than an authoring slip; abstain rather than claiming the quote is absent.
        logger.warning("provenance_regex %r did not compile (%s); not checked", pattern, exc)
        return None

    sink: multiprocessing.Queue = multiprocessing.Queue()
    worker = multiprocessing.Process(target=_regex_worker, args=(pattern, fulltext, sink))
    worker.daemon = True
    worker.start()
    try:
        worker.join(timeout)
        if worker.is_alive():
            worker.terminate()
            worker.join(1.0)
            logger.warning(
                "provenance_regex %r exceeded %.1fs against a %d-character fulltext; recorded as "
                "NOT CHECKED (never as not-found)",
                pattern,
                timeout,
                len(fulltext),
            )
            return None
        return sink.get_nowait() if not sink.empty() else None
    except Exception as exc:
        logger.warning("provenance_regex %r could not be evaluated (%s); not checked", pattern, exc)
        return None
    finally:
        sink.close()
        if worker.is_alive():
            worker.kill()


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def _citations(studies: list[StudyRow], table_pmids: list[str] | None = None) -> dict[str, list[StudyRow]]:
    """`pmid -> [study rows citing it]`, in first-occurrence order (deterministic emission, P7).

    One study row can carry several PMIDs (`pmid` is free-form and may hold a `;`-joined list), so this
    is a genuine fan-out rather than a re-keying.

    **`studies.csv` is one citation site of several** (RM47, RM132): a `pmid` on a binning row grounds
    the *boundary* it sits on, and one on a `pharm_variants.csv` row grounds that row's own drug and
    genotype claim. A citation reaching us only from such a row maps to an **empty** study list — it is
    a real citation to check for existence and identifiers, and it carries no quote or authored DOI
    because neither row has those columns (`provenance_quote` deliberately did not follow the `pmid`
    to either site), so every per-study loop downstream simply finds nothing to do. Studies go in
    first so a paper cited both ways keeps its study rows.
    """
    out: dict[str, list[StudyRow]] = {}
    for study in studies:
        for pmid in extract_pmids(study.pmid):
            out.setdefault(pmid, []).append(study)
    for pmid in table_pmids or []:
        out.setdefault(pmid, [])
    return out


def _ask_fulltext(
    epmc: "EuropePmcClient", bioc: "PmcBiocClient", pmcid: str | None, is_open: bool | None
) -> tuple[str | None, str]:
    """The fulltext question for one article, and how it ended: `(text, fulltext_status)` (RM258).

    Europe PMC first when it calls the article open, then PMC's BioC service, which serves author
    manuscripts Europe PMC calls closed (RM257). `retrieved` when either answered with text;
    `retired` or `unreachable` when neither did and at least one request never got an answer
    (`aggregate_reason`: a 410 leads), because that one may answer next time; `absent` otherwise,
    including an article with no PMCID, which neither service can hold.
    """
    if not pmcid:
        return None, "absent"
    unanswered: list[str] = []
    if is_open:
        try:
            text = epmc.fetch_fulltext(pmcid)
        except FulltextUnavailable as exc:
            logger.warning("Europe PMC fulltext for %s was not answered (%s)", pmcid, exc)
            unanswered.append(could_not_ask_reason(exc))
        else:
            if text is not None:
                return text, "retrieved"
    try:
        text = bioc.fetch_fulltext(pmcid)
    except FulltextUnavailable as exc:
        logger.warning("BioC text for %s was not answered (%s)", pmcid, exc)
        unanswered.append(could_not_ask_reason(exc))
    else:
        if text is not None:
            return text, "retrieved"
    return None, aggregate_reason(unanswered) if unanswered else "absent"


def _needs_reask(row: LiteratureRow) -> bool:
    """A pinned row whose fulltext question is still open (RM258).

    `unreachable` and `retired` were asked and never answered (RM361). A null status on a row that did
    not match against a fulltext was written before the column existed, and is asked once; a null row
    whose quotes were matched against a fulltext already has its answer. `absent` and `retrieved` are
    settled.
    """
    if row.fulltext_status in (UNREACHABLE, RETIRED):
        return True
    return row.fulltext_status is None and row.quote_source != "fulltext"


def enrich_literature(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    check_fulltext: bool = True,
    check_doi: bool = True,
    regex_timeout: float = DEFAULT_REGEX_TIMEOUT,
    write: bool = True,
    eutils: EutilsClient | None = None,
    europepmc: EuropePmcClient | None = None,
    crossref: CrossrefClient | None = None,
    bioc: PmcBiocClient | None = None,
) -> LiteratureResult:
    """Fill `literature.csv` from the citations a module makes.

    **`studies.csv` is one citation site of several** (RM47, RM132): `MeasureBinRow.pmid` grounds the
    threshold its row states, and `PharmVariantRow.pmid` grounds the drug/genotype claim its row
    makes — a claim `studies.csv` cannot ground, because a study row attaches to the whole variant. A
    module whose only citations come from those tables is enriched exactly like one with a
    `studies.csv`; reading fewer than all the sites would leave the rest unchecked, which is worse
    than the honest gap the columns replaced. The kinds come from the compiler's own derived registry
    through `load_citing_rows`/`table_citations`, so a kind that gains the column is read here with no
    edit to this tier.

    Existing rows are authoritative and merged, never clobbered — the same rule `enrich()` applies to
    `resolution.csv`, with the same consequence: to regenerate after a machinery change you must delete
    the file first. **That includes the licence columns** (RM46): rows written before 0.6 carry no
    `license`, and re-running will not back-fill them, because merge-not-clobber cannot tell an
    absent value from a curator's deliberate blank. Delete the sidecar to re-derive.

    `--offline` makes this a no-op with a warning. There is no offline literature snapshot and there
    will not be one; once `literature.csv` is written it *is* the pin, and later compiles read it
    offline and deterministically.

    **Three checks are attested on the way out** (`_attest`), the offline return included: a run that
    did not put a question has to say so, or the manifest cannot tell it from a run that put one and
    found nothing.
    """
    spec_dir = Path(spec_dir)
    # `studies.csv` stays a plain join: it is an AUTHORED table and lives in the spec root, and
    # `sidecar_path` is for the machine-written files RM49 allowed under `derived/`.
    studies_path = spec_dir / "studies.csv"
    # Through the resolver, never joined by hand (RM99): a module keeping its sidecars under
    # `derived/` (RM49) has this file there, and a pass with its own literal would read the split copy
    # and write a flat one, leaving the module with both -- the collision RM49 made an error rather
    # than a preference. `@sidecar-name-and-place`: write to the file you read.
    output_path = sidecar_path(spec_dir, "literature.csv", error=LiteratureEnrichmentError)

    studies: list[StudyRow] = []
    if studies_path.exists():
        studies, errors, _ = load_csv_rows(studies_path, StudyRow, "studies.csv")
        if errors:
            raise LiteratureEnrichmentError(f"studies.csv is invalid: {errors[0]}")
    # The table pointers, through the compiler's own loader: importing its private citing-kind tuple
    # or keeping a second list of the kinds here is the RM41 shape, and the copy goes stale the next
    # time a model declares a `pmid`. Its `ValueError` is re-raised as this pass's own error so a bad
    # citing row is diagnosed the way a bad `studies.csv` two lines above already is, rather than
    # tracebacking out of the CLI.
    try:
        citing_rows = load_citing_rows(spec_dir)
    except ValueError as exc:
        raise LiteratureEnrichmentError(f"a citing table is invalid: {exc}") from exc
    table_pmids = table_citations(citing_rows)
    # A `pmid=NONE` row cites by DOI alone (RM336): a citation, so the module is not citation-free, and
    # one no PubMed lookup below can reach, so it is counted apart and said in the records.
    cited_by_doi_only = sum(
        1
        for row in [*studies, *(r for rows in citing_rows.values() for r in rows)]
        if row.pmid and not extract_pmids(row.pmid)
    )
    if not studies and not table_pmids and not cited_by_doi_only:
        raise LiteratureEnrichmentError(
            f"no citations in {spec_dir} — the literature pass checks the citations a module makes, "
            f"and this one has neither studies.csv rows nor a `pmid` on any binning or "
            f"pharm_variants row."
        )

    existing: dict[tuple, LiteratureRow] = {}
    if output_path.exists():
        rows, errors, _ = load_csv_rows(output_path, LiteratureRow, "literature.csv")
        if errors:
            raise LiteratureEnrichmentError(f"existing literature.csv is invalid: {errors[0]}")
        for row in rows:
            existing[merge_key(row)] = row

    citations = _citations(studies, table_pmids)
    authored_total = sum(
        1 for rows in citations.values() for s in rows if s.provenance_quote or s.provenance_regex
    )
    # A `pmid=NONE` row cites by DOI alone (RM336), so `_citations` has no key for it and its quote is
    # in none of the counts above. Counted apart so the record never says "no quote on any citation"
    # about a module carrying one. Online, the DOI is the key it is asked about instead (RM349).
    without_pmid = sum(
        1 for s in studies if not extract_pmids(s.pmid) and (s.provenance_quote or s.provenance_regex)
    )
    doi_cited = _doi_only_citations(studies, citing_rows)

    if offline:
        logger.warning(
            "Literature enrichment skipped: --offline and there is no offline PubMed/Europe PMC "
            "snapshot. Any existing literature.csv is kept as the pin; compiles stay reproducible."
        )
        out = sorted(existing.values(), key=lambda r: int(r.pmid))
        if write and existing:
            _write_literature_csv(out, output_path)
        return _attest(
            LiteratureResult(
                rows=out,
                mode=mode,
                skipped_offline=True,
                sources=sorted({r.source for r in out if r.source}),
                cited=sorted(citations, key=int),
                quotes_authored=authored_total,
                quotes_without_pmid=without_pmid,
                citations_without_pmid=cited_by_doi_only,
                fulltext_requested=check_fulltext,
            ),
            spec_dir,
            write=write,
            check_fulltext=check_fulltext,
            check_doi=check_doi,
        )

    # **A pin whose quote count no longer matches `studies.csv` is re-fetched (RM277).** The row's own
    # input changed, so it describes a different set of quotes: its `quotes_found` cannot be paired
    # with the new count (`_tally_quotes` reads exactly that mismatch as "unexamined"), and rewriting
    # the count alone would attach the old verdict to the new quotes. Re-deriving the row is the
    # corrected derivation, and it is what makes the compiler's `quote_counter_stale` remedy, "re-run
    # the literature pass", true. Offline has returned above and keeps the pin.
    stale_pins = {
        row.pmid
        for row in existing.values()
        if row.pmid in citations
        and (row.quotes_authored or 0)
        != sum(1 for s in citations[row.pmid] if s.provenance_quote or s.provenance_regex)
    }
    if stale_pins:
        logger.info(
            "Literature: re-fetching %d pinned citation(s) whose quote count changed in studies.csv: %s",
            len(stale_pins),
            ", ".join(sorted(stale_pins, key=int)),
        )
    # Against the rows rather than the dict's keys, which are merge-key tuples and not bare PMIDs.
    have = {row.pmid for row in existing.values()} - stale_pins
    wanted = [pmid for pmid in citations if pmid not in have]
    # **Pinned rows whose fulltext question never got an answer are asked that one question again
    # (RM258).** Everything else on the row stays merged, since answered is per field
    # (`@answered-is-not-absent`): existence, identifiers and the licence were answered, and dropping
    # them to get a retry is the refused repair. Only rows with a quote to check, and only when this run
    # checks fulltext at all.
    reask = (
        [
            row
            for row in sorted(existing.values(), key=lambda r: int(r.pmid))
            if row.pmid in have
            and row.pmid in citations
            and _has_quote(citations[row.pmid])
            and _needs_reask(row)
        ]
        if check_fulltext
        else []
    )
    fetched_at = now_utc_iso()
    result = LiteratureResult(
        rows=[row for row in existing.values() if row.pmid not in stale_pins],
        mode=mode,
        cited=sorted(citations, key=int),
        quotes_authored=authored_total,
        # Set here, before the coverage line is logged, so the log carries the DOI-only clause (RM349).
        quotes_without_pmid=without_pmid,
        citations_without_pmid=cited_by_doi_only,
        fulltext_requested=check_fulltext,
    )

    # **Titles are needed for MERGED rows too, which is the correction S54's reporter filed against
    # their own report.** A pinned row is not in `wanted`, so the fetch loop never sees it — and on
    # the four modules that motivated the title check, every row is pinned, so the check would not
    # have fired on a single one of the 3,668 quotes it was written for. `esummary` batches, so
    # adding the already-pinned PMIDs that carry a quote costs no extra round trip in the common
    # case and nothing at all when there are none.
    titled = [pmid for pmid in citations if pmid not in wanted and _has_quote(citations[pmid])]
    # The citations by DOI alone (RM349): Crossref for existence, Europe PMC for the text. Nothing about
    # them is pinned (see `DoiCitation`), so an online run asks again whenever it has a question.
    ask_dois = bool(doi_cited) and (
        check_doi or (check_fulltext and any(_has_quote(rows) for rows in doi_cited.values()))
    )
    result.doi_citations = [
        DoiCitation(doi=key, quotes_authored=_quote_count(doi_cited[key])) for key in sorted(doi_cited)
    ]
    if wanted or titled or reask or ask_dois:
        owned_eutils = eutils is None
        client = eutils or EutilsClient()
        summaries: dict = {}
        try:
            if wanted or titled or reask:
                summaries = client.esummary("pubmed", wanted + titled)
        except EutilsError as exc:
            raise LiteratureUnavailable(f"PubMed could not be reached: {exc}") from exc
        finally:
            if owned_eutils:
                client.close()

        owned_epmc = europepmc is None
        epmc = europepmc or EuropePmcClient()
        owned_crossref = crossref is None
        crossref = crossref or CrossrefClient()
        # On the E-utilities gate, which outlives the esummary client above: one NCBI budget.
        owned_bioc = bioc is None
        bioc = bioc or PmcBiocClient(gate=client.gate)
        try:
            # Guarded: a run whose only questions are about DOI-only citations has no PMID to look up.
            indexed = epmc.lookup(wanted) if wanted else {}
            for pmid in wanted:
                summary = summaries.get(pmid, {})
                exists = not is_missing(summary)
                ids = _identifiers(summary)
                epmc_record = indexed.get(pmid, {})
                doi = ids.get("doi") or epmc_record.get("doi")
                pmcid = ids.get("pmcid") or epmc_record.get("pmcid")
                is_open = epmc_record.get("is_open_access") if epmc_record else None
                # Verbatim from Europe PMC; rights derived at read time so a mapping correction
                # reaches rows already written (`licensing.article_terms`).
                license_name = epmc_record.get("license") if epmc_record else None
                terms = article_terms(license_name)

                # Nothing is tallied in this loop, and that is the rule rather than a preference:
                # every count this pass reports is taken afterwards over `subject_rows`, so the
                # `strict` gates, the CLI report and the attestation cannot end up reading three
                # different sets. A citation already pinned in `literature.csv` is not fetched here,
                # so a count made in this loop is a count of *this run's requests* — which made the
                # existence gate, the identifier cross-check and the record disagree with each other
                # depending on the order two runs happened in.

                # Crossref checks the **authored** DOI in preference to the derived one. Checking the
                # registry's own DOI would be circular — it exists by construction, since the registry
                # just handed it over. The authored cell is the one nobody has verified, and it is the
                # only one that exists at all for a citation PubMed does not index (a preprint, book or
                # dataset), which is the case this whole client is here for.
                target_doi = _doi_to_check(citations[pmid], doi)
                doi_exists: bool | None = None
                if check_doi and target_doi:
                    doi_exists = crossref.exists(target_doi)

                quotes = [s for s in citations[pmid] if s.provenance_quote or s.provenance_regex]
                found: int | None = None
                quote_source: str | None = None
                fulltext_status: str | None = None
                if check_fulltext and quotes:
                    # PMC serves an author manuscript for text mining where Europe PMC calls it
                    # closed or fails on it (RM257, S110). Any PMCID qualifies: an article outside
                    # the service's set costs one paced request answering "no copy". How the question
                    # ended is recorded, so an outage is asked again rather than pinned (RM258).
                    text, fulltext_status = _ask_fulltext(epmc, bioc, pmcid, is_open)
                    if text is not None:
                        result.fulltext_checked.append(pmid)
                        quote_source = "fulltext"
                    else:
                        # Fall back to the abstract, which Europe PMC serves for paywalled records
                        # too. A HIT here is as conclusive as one in the body; a MISS is not, because
                        # the body was never searched — which is what `quote_source` records, and why
                        # this row still counts as unchecked below.
                        text = epmc_record.get("abstract")
                        if text:
                            result.abstract_checked.append(pmid)
                            quote_source = "abstract"
                    if text:
                        found = _quotes_found(quotes, text, regex_timeout=regex_timeout)
                # Costs no request: the title arrived in the same `esummary` response that answered
                # existence. Outside the `check_fulltext` guard deliberately — this compares the quote
                # against metadata already held, so it answers even for a paywalled article whose
                # fulltext was never retrievable, which is where the defect hides.
                if quotes and _quote_is_the_title(quotes, summary):
                    result.titles_as_quotes.append(pmid)
                # What the retrieved text settled is tallied once, after the loop, over every row —
                # see `_tally_quotes`. The per-row facts it reads (`quotes_authored`, `quotes_found`,
                # `quote_source`) are written right here, so the tally is the same arithmetic applied
                # to merged rows as well as fresh ones.
                result.rows.append(
                    LiteratureRow(
                        pmid=pmid,
                        doi=doi,
                        pmcid=pmcid,
                        exists=exists,
                        is_open_access=is_open,
                        license=license_name,
                        share_alike=terms.share_alike,
                        commercial_use=terms.commercial_use,
                        redistribution=terms.redistribution,
                        quotes_authored=len(quotes),
                        quotes_found=found,
                        quote_source=quote_source,
                        fulltext_status=fulltext_status,
                        doi_exists=doi_exists,
                        # Which DOI that verdict is about. Without it the pin cannot say, and a
                        # re-run pairs the stored answer with whatever the author writes next.
                        doi_checked=target_doi if doi_exists is not None else None,
                        # PubMed is the row's source: it decides existence and supplies the
                        # identifiers. Europe PMC contributes `is_open_access` and the fulltext, but
                        # it cannot originate a row (it silently omits ids it does not know), so it
                        # is not a `source` in the sense the other sidecars use the word.
                        source="pubmed",
                        status="resolved" if exists else "not_found",
                        fetched_at=fetched_at,
                    )
                )
            # The pinned rows whose fulltext question is still open (RM258): that one question, and a
            # row rewritten only where the answer changed it. An answer overwrites the quote counts,
            # `quote_source` and the status; a request that fails again leaves the row as it was,
            # marked `unreachable`, so the next run asks again.
            for row in reask:
                text, status = _ask_fulltext(epmc, bioc, row.pmcid, row.is_open_access)
                update: dict[str, object] = {"fulltext_status": status}
                if text is not None:
                    quotes = [s for s in citations[row.pmid] if s.provenance_quote or s.provenance_regex]
                    update |= {
                        "quote_source": "fulltext",
                        "quotes_found": _quotes_found(quotes, text, regex_timeout=regex_timeout),
                    }
                    result.fulltext_checked.append(row.pmid)
                if all(getattr(row, name) == value for name, value in update.items()):
                    continue
                healed = row.model_copy(update={**update, "fetched_at": fetched_at})
                result.rows = [healed if r.pmid == row.pmid else r for r in result.rows]
            # The pinned rows: no row is written for them (the sidecar is authoritative) and the
            # fulltext is never fetched, but the title comparison needs only the summary — so it
            # answers here where `quotes_found` cannot.
            for pmid in titled:
                if _quote_is_the_title(
                    [s for s in citations[pmid] if s.provenance_quote or s.provenance_regex],
                    summaries.get(pmid, {}),
                ):
                    result.titles_as_quotes.append(pmid)
            if ask_dois:
                result.doi_citations = [
                    _check_doi_citation(
                        key,
                        doi_cited[key],
                        crossref=crossref,
                        epmc=epmc,
                        bioc=bioc,
                        check_doi=check_doi,
                        check_fulltext=check_fulltext,
                        regex_timeout=regex_timeout,
                    )
                    for key in sorted(doi_cited)
                ]
            result.crossref_unanswered = withheld_reason(crossref)
        finally:
            if owned_epmc:
                epmc.close()
            if owned_crossref:
                crossref.close()
            if owned_bioc:
                bioc.close()

    result.titles_as_quotes = sorted(set(result.titles_as_quotes), key=int)
    result.rows.sort(key=lambda r: int(r.pmid))
    result.fulltext_checked = sorted(set(result.fulltext_checked), key=int)
    result.sources = sorted({r.source for r in result.rows if r.source})
    # Every tally runs here, once, over the sorted subject rows — so each list is ordered by PMID
    # rather than by whatever order the fetch took, and the gates below refuse on exactly what the
    # attestation records.
    _tally_existence(result, citations)
    # A DOI no registration agency knows is a cited DOI that does not resolve, whichever kind of row
    # cites it (RM349), so the `strict` gate and the report below name it with the others.
    # Both sides by `doi_key` (RM363): the PubMed path records the registry's DOI as the registry spells it.
    missing = {doi_key(doi) for doi in result.doi_missing}
    result.doi_missing += [
        c.doi for c in result.doi_citations if c.exists is False and doi_key(c.doi) not in missing
    ]
    _tally_quotes(result, citations)
    _compare_identifiers(result, citations)
    logger.info("Literature: %s", result.coverage)

    if mode == "strict" and result.missing:
        raise LiteratureEnrichmentError(
            f"strict literature enrichment: PubMed has no record of {len(result.missing)} cited "
            f"PMID(s): {result.missing}. Either the identifier is a typo or the article was pulled "
            f"from the index; both mean the row's grounding evidence does not resolve. Fix the "
            f"citation, or enrich with mode='best_effort' to record it as a warning."
        )
    if mode == "strict" and result.doi_missing:
        raise LiteratureEnrichmentError(
            f"strict literature enrichment: Crossref has no record of {len(result.doi_missing)} "
            f"cited DOI(s): {result.doi_missing}. A DOI that does not resolve is a citation that "
            f"cannot be followed."
        )
    if mode == "strict" and result.doi_conflicts:
        raise LiteratureEnrichmentError(
            f"strict literature enrichment: {len(result.doi_conflicts)} authored DOI(s) disagree with "
            f"the registry: {[str(c) for c in result.doi_conflicts]}. One of the two identifiers "
            f"points at the wrong paper."
        )
    if mode == "strict" and result.pmcid_conflicts:
        raise LiteratureEnrichmentError(
            f"strict literature enrichment: {len(result.pmcid_conflicts)} authored PMC id(s) disagree "
            f"with PubMed's for the same record: {[str(c) for c in result.pmcid_conflicts]}. One of "
            f"the two identifiers points at the wrong paper."
        )
    if write:
        _write_literature_csv(result.rows, output_path)
    return _attest(result, spec_dir, write=write, check_fulltext=check_fulltext, check_doi=check_doi)


def _doi_only_citations(studies: list[StudyRow], citing_rows: dict[str, list]) -> dict[str, list[StudyRow]]:
    """`doi_key -> [study rows citing it]` for the rows citing by DOI alone (`pmid=NONE`, RM336, RM349).

    `_citations`' shape, keyed on the DOI because that is the only identifier such a row carries: two
    spellings of one DOI (bare, or a doi.org URL in another case) are one citation (`spelling.doi_key`,
    RM336's duplicate key). A citing-table row maps to an empty list, as there: it is a citation to
    check for existence, with no quote. The predicate is the one `cited_by_doi_only` counts with.
    """
    out: dict[str, list[StudyRow]] = {}
    for study in studies:
        if study.pmid and not extract_pmids(study.pmid) and study.doi:
            out.setdefault(doi_key(study.doi), []).append(study)
    for rows in citing_rows.values():
        for row in rows:
            doi = getattr(row, "doi", None)
            if row.pmid and not extract_pmids(row.pmid) and doi:
                out.setdefault(doi_key(doi), [])
    return out


def _quote_count(studies: list[StudyRow]) -> int:
    return sum(1 for s in studies if s.provenance_quote or s.provenance_regex)


def _check_doi_citation(
    doi: str,
    studies: list[StudyRow],
    *,
    crossref: "CrossrefClient",
    epmc: "EuropePmcClient",
    bioc: "PmcBiocClient",
    check_doi: bool,
    check_fulltext: bool,
    regex_timeout: float,
) -> DoiCitation:
    """The two questions for one DOI-only citation (RM349): does the DOI exist, and is the quote there.

    Existence is Crossref's `work`, so the answer names the work it found (`@existence-not-identity`).
    The quote is matched as a PMID's is: against the full text when one is retrieved, else against the
    abstract, where a hit settles and a miss does not. Never writes a PubMed id anywhere, even where
    Europe PMC's record carries one (RM263 reports; it never fills).
    """
    work = crossref.work(doi) if check_doi else CrossrefWork(exists=None)
    quotes = [s for s in studies if s.provenance_quote or s.provenance_regex]
    found: int | None = None
    quote_source: str | None = None
    status: str | None = None
    record: dict | None = None
    if check_fulltext and quotes:
        text, status, record = _ask_doi_fulltext(epmc, bioc, doi)
        if text:
            quote_source = "fulltext"
        elif record and record.get("abstract"):
            text = record["abstract"]
            quote_source = "abstract"
        if text:
            found = _quotes_found(quotes, text, regex_timeout=regex_timeout)
    return DoiCitation(
        doi=doi,
        exists=work.exists,
        crossref_asked=check_doi,
        title=work.title,
        agency=work.agency,
        quotes_authored=len(quotes),
        quotes_found=found,
        quote_source=quote_source,
        fulltext_status=status,
        europepmc_id=record.get("id") if record else None,
        license=record.get("license") if record else None,
    )


def _ask_doi_fulltext(
    epmc: "EuropePmcClient", bioc: "PmcBiocClient", doi: str
) -> tuple[str | None, str, dict | None]:
    """The fulltext question for a DOI-only citation: `(text, fulltext_status, Europe PMC record)`.

    `fulltext_status` means what it means on a `LiteratureRow` (RM258): `retrieved`, `absent` (Europe
    PMC holds no record, or a record with no text) or `unreachable` (a request never got an answer).
    A record carrying a PMC id goes the PMID route (`_ask_fulltext`: Europe PMC, then BioC); a
    preprint goes to Europe PMC's preprint repository, and only when its record lists a full text.
    """
    try:
        record = epmc.record_for_doi(doi)
    except LiteratureUnavailable as exc:
        logger.warning("Europe PMC could not be asked for DOI %s (%s)", doi, exc)
        return None, could_not_ask_reason(exc), None
    if record is None:
        return None, "absent", None
    if record.get("pmcid"):
        text, status = _ask_fulltext(epmc, bioc, record["pmcid"], record.get("is_open_access"))
        return text, status, record
    if not record.get("preprint_id"):
        return None, "absent", record
    try:
        text = epmc.fetch_preprint_fulltext(record["preprint_id"])
    except FulltextUnavailable as exc:
        logger.warning("Preprint text for %s was not answered (%s)", doi, exc)
        return None, could_not_ask_reason(exc), record
    return text, "retrieved" if text is not None else "absent", record


def _doi_to_check(studies: list[StudyRow], registry_doi: str | None) -> str | None:
    """The DOI Crossref is asked about: the **authored** one, else the registry's.

    Shared by the fetch loop and `_tally_existence` so the run and the tally cannot end up naming
    different identifiers for the same citation. Checking the registry's own DOI is circular — it
    exists by construction, since the registry just handed it over — but it is the only one a
    citation without an authored cell has, and a citation PubMed does not index (a preprint, book or
    dataset) has only the authored one, which is the case the Crossref client is here for.
    """
    authored = next((s.doi for s in studies if s.doi), None)
    return doi_token(authored) if authored else (registry_doi or None)


def _tally_existence(result: LiteratureResult, citations: dict[str, list[StudyRow]]) -> None:
    """Which cited citations resolve nowhere — the `strict` gates' subject, and the record's.

    Taken over `subject_rows` rather than accumulated in the fetch loop. The loop only visits
    citations this run looked up, so on a module already carrying a `literature.csv` both lists came
    out empty and `strict` refused nothing — while the same run's attestation, reading the rows,
    reported the finding. A gate and a record disagreeing about one run is the RM44 class: the module
    would ship a manifest naming a defect its own `--strict` compile had just blessed.

    **A pinned DOI verdict only counts while it is about the DOI the module cites now**
    (`doi_checked`). The PMID half needs no such guard — the row is keyed by the PMID, so a stored
    `exists` cannot be about another one — but the DOI half is a verdict about a cell the author can
    edit, and a re-run does not refetch a pinned row. Without the guard, correcting a bad DOI to a
    good one left `--strict` refusing and the attestation publishing a finding, both now naming the
    *corrected* DOI: a finding no authored edit could clear, which is the class this pass treats as
    a defect wherever else it appears. Same reasoning as `_tally_quotes`' `pinned != authored_now`.
    A row written before the column existed carries no `doi_checked`, so its verdict is unattributable
    and is left out rather than guessed at — re-run after deleting the sidecar to re-derive it.

    **A DOI nothing ever resolved is counted too** (`doi_never_checked`), and it is a different
    absence from a stale verdict. Run the pass once with `--no-doi` and again without: the rows exist
    by then, so Crossref is never asked, and the record would otherwise report a full denominator for
    a check the vocabulary defines over PubMed *and* Crossref with the Crossref half never put for any
    row. Both counts ride in `detail` rather than shrinking the denominator, because the PMID half of
    each of those citations really was answered.
    """
    stale_doi = never_checked = 0
    missing: list[str] = []
    doi_missing: list[str] = []
    checked = unresolved = 0
    for row in result.subject_rows:
        target = _doi_to_check(citations.get(row.pmid) or [], row.doi)
        doi_stands = row.doi_exists is not None and row.doi_checked == target and target is not None
        if row.doi_exists is not None and not doi_stands:
            stale_doi += 1
        elif row.doi_exists is None and target is not None:
            never_checked += 1
        if row.exists is not None or doi_stands:
            checked += 1
        if row.exists is False:
            missing.append(row.pmid)
        if row.exists is False or (doi_stands and row.doi_exists is False):
            unresolved += 1
        if doi_stands and row.doi_exists is False and target is not None:
            doi_missing.append(target)
    result.missing = sorted(missing, key=int)
    result.doi_missing = doi_missing
    result.existence_checked = checked
    result.unresolved_citations = unresolved
    result.doi_verdicts_stale = stale_doi
    result.doi_never_checked = never_checked


def _tally_quotes(result: LiteratureResult, citations: dict[str, list[StudyRow]]) -> None:
    """Count what a retrieved text actually SETTLED, over the cited rows.

    Four numbers, and the split between the last two is the whole reason this is a function rather
    than a sum: `quotes_found` is the numerator, `quotes_checked` is the denominator a verdict was
    reached over, and the rest is unchecked — for one of **two** reasons that must not be rendered as
    one sentence, since only the second is about the article being unreadable.

    * `quotes_unexamined` — the pinned row does not describe the quotes the module carries now.
      Since RM277 an online run re-fetches such a row before this tally, so the arm is a guard: it
      fires only if a stale pin reaches the tally anyway. Calling that "no fulltext could be
      retrieved" would state a retrievability failure that never happened, and for an open-access
      article it is flatly false.
    * the remainder — the article's text could not be read, or only its abstract could, where a
      **hit** settles a quote and a miss does not (`quote_source` records which text was searched).
      A row carrying a count with no `quote_source` is read the same conservative way, since the
      column is null exactly when neither text could be retrieved.

    Running it over the merged rows rather than inside the fetch loop is the same fix as everywhere
    else in this file: the loop's version reported `quotes_unchecked = 0` on a re-run for citations
    whose fulltext had never been retrievable.

    **The pinned count has to MATCH, not merely be non-zero.** A row pinned at `quotes_authored=2,
    quotes_found=1` whose failing quote the author then deletes would otherwise keep publishing
    `subjects=2, findings=1` — a finding about a quote the module no longer makes, clearable by no
    authored edit — which is the defect this same round fixed one level up for whole citations. When
    the counts differ the pin is describing a different set of quotes, so none of its verdicts is
    attributable to these and the whole row goes to `unexamined`: understating rather than
    misattributing, the rule RM4's audit fallback already follows. A count is not a fingerprint, so
    an *edited* quote at the same count still inherits the old verdict here; what catches that is the
    attestation's own binding, which perishes the moment `studies.csv` changes.
    """
    found = checked = unchecked = unexamined = 0
    noncommercial: list[str] = []
    for row in result.subject_rows:
        authored_now = sum(
            1 for s in (citations.get(row.pmid) or []) if s.provenance_quote or s.provenance_regex
        )
        if not authored_now:
            continue
        # The licence notice belongs to the same subject set and the same "now": it is about
        # publisher text sitting in *this* module's annotation layer, so a citation the author has
        # since dropped is not carrying any. Reading the row's pinned `quotes_authored` here would
        # have gone on naming it every run, clearable only by deleting the sidecar.
        if row.commercial_use is False:
            noncommercial.append(row.pmid)
        pinned = row.quotes_authored or 0
        if pinned != authored_now:
            unexamined += authored_now
            continue
        # The per-row arithmetic is `LiteratureRow.quotes_checked`, shared with the manifest block so
        # the pass report and the published counters cannot disagree about what an abstract settled.
        settled = row.quotes_checked()
        found += row.quotes_found or 0
        checked += settled
        unchecked += pinned - settled
    result.noncommercial_quoted = sorted(noncommercial, key=int)
    result.quotes_found = found
    result.quotes_checked = checked
    result.quotes_unexamined = unexamined
    result.quotes_unchecked = unchecked + unexamined


def _compare_identifiers(result: LiteratureResult, citations: dict[str, list[StudyRow]]) -> None:
    """Authored DOIs and PMC ids against the registry's own, for every row — merged ones included.

    This used to happen inside the fetch loop, which meant it happened only for citations this run
    looked up. A module enriched twice therefore reported no identifier conflicts the second time,
    and since the conflict lists are what `strict` refuses on, running `--best-effort` first and
    `--strict` second blessed a module that the same two commands in the other order refuse. The
    comparison needs no request — both halves are already in hand — so there is no reason to make it
    depend on which rows were fetched.

    **Only a row this pass wrote is compared** (`_REGISTRY_SOURCE`). A curator who hand-corrects a
    row spells `source` something else, and their `doi` is their own claim, not PubMed's; reporting a
    disagreement with it as "the registry's" would put a false attribution in front of an author.

    The counts are collected here, beside the comparison, because they are the denominator of the
    `citation_identifier` attestation: citations that authored an identifier at all, of those the
    ones the registry also named one for, and of those the ones that disagree. A citation counts once
    however many identifiers it carries, which is what keeps findings a subset of subjects. The two
    ways a citation can drop out are counted **apart** — the registry named no identifier, or the row
    is a curator's — because a single "not compared" number reported a hand-corrected row as one
    PubMed reports nothing for, which is a claim about PubMed that the run never established.
    """
    doi_conflicts: list[DoiConflict] = []
    pmcid_conflicts: list[PmcidConflict] = []
    authored = compared = conflicting = unmatched = foreign = 0
    for row in result.subject_rows:
        studies = citations.get(row.pmid) or []
        authored_dois = [s.doi for s in studies if s.doi]
        authored_pmcids = [p for s in studies for p in extract_pmcids(s.pmid)]
        if not authored_dois and not authored_pmcids:
            continue
        authored += 1
        if row.source != _REGISTRY_SOURCE:
            foreign += 1
            continue
        # "Comparable" means both halves exist. PubMed reports no PMC id for a paywalled article and
        # sometimes no DOI at all, and an absent registry value is not a contradiction — the same
        # tri-state `_doi_conflicts` and `_pmcid_conflicts` already apply row by row.
        if not ((authored_dois and row.doi) or (authored_pmcids and row.pmcid)):
            unmatched += 1
            continue
        compared += 1
        found_doi = _doi_conflicts(row.pmid, studies, row.doi)
        found_pmcid = _pmcid_conflicts(row.pmid, studies, row.pmcid)
        doi_conflicts.extend(found_doi)
        pmcid_conflicts.extend(found_pmcid)
        if found_doi or found_pmcid:
            conflicting += 1
    result.doi_conflicts = doi_conflicts
    result.pmcid_conflicts = pmcid_conflicts
    result.identifiers_authored = authored
    result.identifiers_compared = compared
    result.identifiers_conflicting = conflicting
    result.identifiers_unmatched = unmatched
    result.identifiers_foreign = foreign


def _attest(
    result: LiteratureResult,
    spec_dir: Path,
    *,
    write: bool,
    check_fulltext: bool,
    check_doi: bool,
) -> LiteratureResult:
    """Record what this pass checked into `verification.json`, then hand the result back (RM45).

    Called on the offline return as well as the ordinary one, for the reason `clinpgx._attest` gives:
    a pass that records its findings and stays silent about not having run leaves the manifest unable
    to tell "asked and found nothing" from "never asked", which is the collapse the whole item exists
    to undo. Not called on a `strict` refusal — that path raises, so there is no run to attest.
    """
    if write:
        record_verification(
            _verification_records(result, check_fulltext=check_fulltext, check_doi=check_doi),
            spec_dir,
            error=LiteratureEnrichmentError,
        )
    return result


def _verification_records(
    result: LiteratureResult, *, check_fulltext: bool, check_doi: bool
) -> list[VerificationRecord]:
    """The three checks this pass puts, as records `verification.json` can carry.

    Three records rather than one, because they are three questions with three different
    denominators: every citation carries an existence verdict, only some carry an authored identifier
    to compare, and fewer still carry a quote whose article could be read. One record averaging them
    would be a number nothing could act on.

    Every count is read off `result`, over the one subject set the `strict` gates refuse on — see
    `LiteratureResult`. Nothing is recounted here, for the reason `enrich`'s own record builder
    states: a denominator recomputed beside a check is one that can disagree with it.

    **An offline run that has a pin records nothing at all**, and that is the point rather than an
    omission. `--offline` is a documented no-op: it fetches nothing and re-examines nothing, so it
    has put no question and has nothing to say, and a record of having said nothing is worse than
    silence. With no pin at all there is no earlier answer to protect and nothing this run could
    learn, so the three skips are written and say why.

    This paragraph used to carry a second reason — that the skip would *overwrite* a true
    `subjects=5, findings=1` from an earlier online run, because `merge_records` replaced per check.
    RM72 narrowed that: a skip no longer displaces a real answer **while the authored bytes stand
    still**. It still does when they have moved, which is the only way this branch is reached with an
    earlier record in the file at all — the skips here are written when no pinned row covers the
    citations the module makes *now*, and after an online run that is true only because the citations
    changed. So the displacement is deliberate here rather than a defect: the earlier answer is about
    a citation this module no longer makes, and a finding no authored edit could clear is what the
    round before RM72 removed. What is left of the paragraph is the half that never depended on
    either: a no-op has nothing to say.

    `release` is null on all three. PubMed and Europe PMC are continuously updated and publish no
    release a run could pin, and inventing a date here would make a re-run look like a different
    edition of the same source.
    """
    offline = result.skipped_offline
    if offline and result.subject_rows:
        return []

    records: list[VerificationRecord] = []
    unanswered = len(result.cited) - result.existence_checked
    # The DOI-only citations' existence verdicts (RM349), one per distinct DOI: what Crossref answered.
    doi_checked = [c for c in result.doi_citations if c.exists is not None]
    doi_absent = [c for c in doi_checked if c.exists is False]

    # ── does the citation exist ─────────────────────────────────────────────────────────────────
    if offline:
        records.append(
            skipped(
                "citation_existence",
                "offline",
                detail=(
                    # Says what was established, not that the file is absent: `literature.csv` may
                    # be sitting right there and simply pin none of the citations the module makes
                    # now, which is the same "nothing to protect" state and a different sentence.
                    "PubMed and Crossref have no offline snapshot, and no citation this module "
                    "makes carries a pinned answer in literature.csv"
                    + (f"; {_doi_only_clause(result)}" if result.citations_without_pmid else "")
                ),
                source="pubmed",
            )
        )
    elif not result.cited and result.citations_without_pmid:
        # Every citation is DOI-only (RM349): Crossref is the registry that answered, so the record is
        # its, and never `ran(0, 0)`, for the reason the identifier branch below gives. Which way no
        # answer came is the skip: the caller's `--no-doi`, or Crossref never answering. `unsupported`
        # is left for a row whose `doi` carries no DOI token, which no route can ask about (a loaded
        # `NONE` row cannot be one, since `check_citation_pair` requires the token).
        doi_parts = _doi_existence_parts(result)
        if doi_checked:
            if result.doi_missing:
                doi_parts.append(f"{len(result.doi_missing)} cited DOI(s) do not resolve in Crossref")
            records.append(
                ran(
                    "citation_existence",
                    subjects=len(doi_checked),
                    findings=len(doi_absent),
                    source="crossref",
                    detail="; ".join(doi_parts),
                )
            )
        elif result.doi_citations and not any(c.crossref_asked for c in result.doi_citations):
            records.append(
                skipped("citation_existence", "not_requested", detail="; ".join(doi_parts), source="crossref")
            )
        elif result.doi_citations:
            records.append(
                skipped(
                    "citation_existence",
                    result.crossref_unanswered,
                    detail="; ".join(doi_parts),
                    source="crossref",
                )
            )
        else:
            records.append(
                skipped(
                    "citation_existence", "unsupported", detail=_doi_only_clause(result), source="crossref"
                )
            )
    else:
        parts = _doi_existence_parts(result)
        if result.missing:
            parts.append(f"{len(result.missing)} cited PMID(s) have no PubMed record")
        if result.doi_missing:
            parts.append(f"{len(result.doi_missing)} cited DOI(s) do not resolve in Crossref")
        if result.doi_verdicts_stale:
            parts.append(
                f"{result.doi_verdicts_stale} pinned DOI verdict(s) are about a DOI the module no "
                f"longer cites and were not counted — delete literature.csv to re-derive them"
            )
        if result.doi_never_checked:
            parts.append(
                f"{result.doi_never_checked} cited DOI(s) have never been resolved in Crossref — "
                f"their row was pinned by a run that did not ask, and a re-run does not refetch a "
                f"row it already has, so delete literature.csv to put the question"
            )
        if unanswered:
            parts.append(
                f"{unanswered} of {len(result.cited)} citation(s) carry no verdict at all and are "
                f"outside this denominator"
            )
        if not check_doi:
            # Worded for the pin, not for the run. `doi_exists` is a persisted verdict, so a module
            # whose sidecar already carries a failed DOI still counts it here — and saying "only
            # PubMed was asked" beside that count made one published `detail` string contradict its
            # own numbers, on a field RM44 established consumers parse.
            parts.append(
                "--no-doi: no DOI was looked up this run, so any DOI verdict above comes from the "
                "pinned literature.csv and a citation with no pinned verdict went unchecked"
            )
        records.append(
            ran(
                "citation_existence",
                subjects=result.existence_checked + len(doi_checked),
                findings=result.unresolved_citations + len(doi_absent),
                source="pubmed",
                detail="; ".join(parts) or None,
                # RM292: Crossref is a witness only when a DOI verdict it gave is among the subjects;
                # a PMID-only module was put to PubMed alone, and the record says so.
                witness_source=(
                    "crossref+pubmed"
                    if any(row.doi_exists is not None for row in result.subject_rows)
                    else "pubmed"
                ),
            )
        )

    # ── do the authored identifiers agree with the registry's ───────────────────────────────────
    if offline:
        records.append(
            skipped(
                "citation_identifier",
                "offline",
                detail="the registry's own DOI and PMC id arrive with the existence lookup, which "
                "did not run",
                source="pubmed",
            )
        )
    elif result.identifiers_authored == 0:
        records.append(
            skipped(
                "citation_identifier",
                "nothing_to_check",
                detail=(
                    f"none of {len(result.cited)} citation(s) carries an authored DOI or PMC id, so "
                    f"there was nothing to compare against PubMed's own"
                ),
                source="pubmed",
            )
        )
    elif result.identifiers_compared == 0:
        # Authored identifiers, and not one of them had a registry value to sit beside. `ran(0, 0)`
        # would read as "the check ran and had nothing in scope", which is the clean-looking pass
        # this whole item exists to stop — so the two reasons are named instead, and named APART,
        # because "PubMed reports none of its own" is a claim about PubMed that a curator-written
        # row does not license anyone to make.
        reasons = []
        if result.identifiers_unmatched:
            reasons.append(
                f"{result.identifiers_unmatched} citation(s) PubMed reports no identifier of its own for"
            )
        if result.identifiers_foreign:
            reasons.append(
                f"{result.identifiers_foreign} citation(s) whose literature.csv row a curator "
                f"wrote, so its identifiers are that curator's claim rather than the registry's"
            )
        records.append(
            skipped(
                "citation_identifier",
                "no_reference",
                detail=(
                    f"{result.identifiers_authored} authored identifier(s), none with a registry "
                    f"value to compare against: " + "; ".join(reasons)
                ),
                source="pubmed",
            )
        )
    else:
        parts = []
        if result.identifiers_conflicting:
            parts.append(
                f"{len(result.doi_conflicts)} DOI and {len(result.pmcid_conflicts)} PMC id disagreement(s)"
            )
        if result.identifiers_unmatched:
            parts.append(
                f"{result.identifiers_unmatched} citation(s) authored an identifier PubMed reports "
                f"none of its own for"
            )
        if result.identifiers_foreign:
            parts.append(
                f"{result.identifiers_foreign} citation(s) whose row a curator wrote, so the "
                f"registry's own identifier is not in hand for them"
            )
        records.append(
            ran(
                "citation_identifier",
                subjects=result.identifiers_compared,
                findings=result.identifiers_conflicting,
                source="pubmed",
                detail="; ".join(parts) or None,
            )
        )

    # ── does the quoted passage appear in the article ───────────────────────────────────────────
    # Four reasons this can be absent, and the order is not arbitrary: the two that no amount of
    # egress would clear come first. `not_requested` is the caller's own switch (the ordering
    # `enrich._verification_records` uses), and a module with no authored quote asks this question in
    # no mode at all — reporting either as `offline` would send an author looking for a network they
    # are not in fact missing. Only then does connectivity decide, and last comes having looked and
    # got no text back.
    if not check_fulltext and result.quotes_checked:
        # A switched-off check that the pin already answers is the offline case again: this run put
        # no question, so writing `not_requested` would replace a true `subjects=1, findings=0` with
        # "the caller declined to ask" on a run that changed nothing — and the sentence would be
        # false by this run's own tally, since `_tally_quotes` just read those verdicts off the pin.
        pass
    elif not check_fulltext:
        records.append(
            skipped(
                "provenance_quote",
                "not_requested",
                detail="--no-fulltext: no authored quote was matched against any retrieved text",
                source="europepmc",
            )
        )
    elif result.quotes_authored == 0 and result.quotes_without_pmid == 0:
        records.append(
            skipped(
                "provenance_quote",
                "nothing_to_check",
                detail=("no provenance quote or regex on any citation, so none of them asked this question"),
                source="europepmc",
            )
        )
    elif offline:
        # A quote on a `pmid=NONE` row is matched by DOI on an online run (RM349), so offline is the
        # honest reason for it too, never `unsupported`, which would say no run could ask.
        records.append(
            skipped(
                "provenance_quote",
                "offline",
                detail=_with_without_pmid(
                    f"{result.quotes_authored} authored quote(s); an article's text can only come "
                    f"over the network, and there is no offline fulltext archive"
                    if result.quotes_authored
                    else None,
                    result,
                ),
                source="europepmc",
            )
        )
    elif result.quotes_authored == 0 and not result.doi_citations:
        # The residual `unsupported`: quotes on rows whose `doi` carries no DOI token, which no route
        # reaches. A loaded `NONE` row cannot be one (`check_citation_pair`).
        records.append(
            skipped(
                "provenance_quote",
                "unsupported",
                detail=_without_pmid_clause(result),
                source="europepmc",
            )
        )
    elif result.quotes_checked + _doi_quotes_checked(result) == 0:
        # Not `ran(subjects=0)`: with quotes authored and no verdict on any of them, "the check ran
        # and had nothing in scope" would be the false half of the answered-absence/unasked-question
        # collapse. Which of the two ways of having read nothing applies is spelled out rather than
        # smoothed over — saying "could not be retrieved" about a quote nobody went looking for is
        # flatly false when the article is open access and was read on an earlier run.
        records.append(
            skipped(
                "provenance_quote",
                "no_reference",
                detail=(
                    f"{result.quotes_authored + result.quotes_without_pmid} authored quote(s), none of "
                    f"them settled: " + _all_quote_gaps(result)
                ),
                source="europepmc",
            )
        )
    else:
        # The DOI-only quotes join the denominator (RM349): each was put to a text found by its DOI,
        # under the same rule a PMID's is (`settled_quotes`).
        checked = result.quotes_checked + _doi_quotes_checked(result)
        found = result.quotes_found + sum(c.quotes_found or 0 for c in result.doi_citations)
        unchecked = result.quotes_unchecked + _doi_quotes_unsettled(result)
        records.append(
            ran(
                "provenance_quote",
                subjects=checked,
                findings=checked - found,
                source="europepmc",
                detail=(
                    f"{unchecked} further authored quote(s) outside this denominator: "
                    + _all_quote_gaps(result)
                    if unchecked
                    else None
                ),
            )
        )
    return records


def _doi_quotes_checked(result: LiteratureResult) -> int:
    """Quotes on DOI-only citations that a retrieved text settled, found or missed (RM349)."""
    return sum(c.quotes_checked() for c in result.doi_citations)


def _doi_quotes_unsettled(result: LiteratureResult) -> int:
    """Quotes on DOI-only citations no retrieved text settled (RM349)."""
    return sum(c.quotes_authored - c.quotes_checked() for c in result.doi_citations)


def _all_quote_gaps(result: LiteratureResult) -> str:
    """The PMID quotes' gaps and the DOI-only quotes' gaps, each named in its own clause."""
    parts = [_quote_gap_detail(result) if result.quotes_unchecked else "", _doi_quote_gap(result)]
    return "; ".join(part for part in parts if part)


def _doi_quote_gap(result: LiteratureResult) -> str:
    """How the unsettled quotes on DOI-only citations ended, by `fulltext_status` (RM349).

    The three ways are named apart, for the reason `_quote_gap_detail` gives: an outage is cleared by
    running again, an absent copy is not, and an abstract miss is no verdict at all.
    """
    unreachable = absent = abstract = 0
    for c in result.doi_citations:
        unsettled = c.quotes_authored - c.quotes_checked()
        if not unsettled:
            continue
        # Unreachable first, whatever the abstract said: it is the one a re-run clears. A retired
        # route is asked again too (RM361), so it is counted with it rather than as absent.
        if c.fulltext_status in (UNREACHABLE, RETIRED):
            unreachable += unsettled
        elif c.quote_source == "abstract":
            abstract += unsettled
        else:
            absent += unsettled
    parts = []
    if unreachable:
        parts.append(
            f"{unreachable} on pmid NONE citation(s) whose text Europe PMC never answered for "
            f"(unreachable, so only an abstract could be searched, if any; asked again on the next "
            f"online run)"
        )
    if abstract:
        parts.append(
            f"{abstract} on pmid NONE citation(s) searched in the abstract only, where a miss is not "
            f"a verdict"
        )
    if absent:
        parts.append(f"{absent} on pmid NONE citation(s) whose DOI Europe PMC holds no text for")
    return "; ".join(parts)


def _doi_only_clause(result: LiteratureResult) -> str:
    """The citations no PMID reaches, when no DOI was asked about either (RM336, RM349)."""
    return (
        f"{result.citations_without_pmid} citation(s) have pmid NONE and cite by DOI alone; they are "
        f"asked of Crossref by DOI on an online run, and none was asked this run"
    )


def _doi_existence_parts(result: LiteratureResult) -> list[str]:
    """What this run learned about the DOI-only citations' existence, clause by clause (RM349).

    The titles are named (`@existence-not-identity`: a DOI that resolves may still be the wrong work,
    and only the title says which), a bounded few with a count (`verification.examples`). A DOI that
    resolves with no title in hand is said apart, and so is each way of not having an answer, since
    neither is in the denominator.
    """
    if not result.doi_citations:
        return [_doi_only_clause(result)] if result.citations_without_pmid else []
    cites = result.doi_citations
    asked = any(c.crossref_asked for c in cites)
    parts = [
        f"{result.citations_without_pmid} citation(s) have pmid NONE and cite {len(cites)} DOI(s) "
        f"alone" + (", asked of Crossref by DOI" if asked else "")
    ]
    named = [f"{c.doi} as {c.title!r}" for c in cites if c.exists and c.title]
    if named:
        parts.append(f"Crossref names {examples(named)}")
    untitled = [f"{c.doi} ({c.agency or 'no agency'})" for c in cites if c.exists and not c.title]
    if untitled:
        parts.append(
            f"{len(untitled)} DOI(s) resolve with no title in hand (registered with another agency, "
            f"or a record naming none), so which work they name is unconfirmed: {examples(untitled)}"
        )
    unanswered = [c.doi for c in cites if c.crossref_asked and c.exists is None]
    if unanswered:
        parts.append(
            f"Crossref did not answer for {len(unanswered)} DOI(s), outside this denominator: "
            f"{examples(unanswered)}"
        )
    not_asked = [c.doi for c in cites if not c.crossref_asked]
    if not_asked:
        parts.append(f"{len(not_asked)} DOI(s) were not looked up: --no-doi")
    return parts


def _without_pmid_clause(result: LiteratureResult) -> str:
    """The quotes on `pmid=NONE` rows when none was matched this run (RM336, RM349)."""
    return (
        f"{result.quotes_without_pmid} authored quote(s) sit on citation(s) whose pmid is NONE; they "
        f"are matched against the text Europe PMC holds for their DOI on an online run, and none was "
        f"matched this run"
    )


def _doi_quote_coverage(result: LiteratureResult) -> str:
    """The coverage clause for quotes on `pmid=NONE` rows (RM349)."""
    if not any(c.fulltext_status is not None for c in result.doi_citations):
        return _without_pmid_clause(result)
    return (
        f"checked {_doi_quotes_checked(result)} of {result.quotes_without_pmid} quote(s) on pmid NONE "
        f"citation(s) against text Europe PMC holds for their DOI"
    )


def _with_without_pmid(detail: str | None, result: LiteratureResult) -> str | None:
    """`detail`, with the quotes no PMID reaches appended when there are any."""
    if not result.quotes_without_pmid:
        return detail
    return "; ".join(part for part in (detail, _without_pmid_clause(result)) if part)


def _quote_gap_detail(result: LiteratureResult) -> str:
    """The two ways a quote goes unchecked, named apart — never rendered as one sentence.

    An article whose text could not be read and a quote nobody went looking for are different facts
    with different remedies: the first is this pass's honest reach, the second is merge-not-clobber
    declining to refetch a pinned citation, and only the second is cleared by deleting the sidecar.
    """
    parts = []
    unretrievable = result.quotes_unchecked - result.quotes_unexamined
    if unretrievable:
        parts.append(
            f"{unretrievable} in articles whose fulltext could not be read (or only an abstract "
            f"could, where a miss is not a verdict, or a provenance_regex could not be evaluated)"
        )
    if result.quotes_unexamined:
        parts.append(
            f"{result.quotes_unexamined} never looked up, because literature.csv pinned their "
            f"citation at another quote count — re-run the pass online to re-derive it"
        )
    return "; ".join(parts)


def _identifiers(summary: dict) -> dict[str, str | None]:
    """Pull `doi`/`pmcid` out of an esummary record's `articleids` block.

    Both arrive free with the existence check, which is what makes the PMC ID converter unnecessary.
    Note `pmcid` appears twice in `articleids` under different `idtype`s — as a bare `PMC…` under
    `pmc`, and wrapped as `pmc-id: PMC…;` under `pmcid`. The bare one is the usable form.
    """
    out: dict[str, str | None] = {"doi": None, "pmcid": None}
    for entry in summary.get("articleids") or []:
        idtype, value = entry.get("idtype"), entry.get("value")
        if not value:
            continue
        if idtype == "doi" and out["doi"] is None:
            out["doi"] = str(value).strip()
        elif idtype == "pmc" and out["pmcid"] is None:
            out["pmcid"] = str(value).strip()
    return out


def bibliographic(summary: dict) -> dict[str, str | None]:
    """Pull the fields that say *which paper this is* out of an esummary record.

    Public, unlike `_identifiers`, because two tiers need it and the alternative is a consumer
    re-implementing a parse of a payload we already hold — the RM41 lesson. `lookup.CitationHint`
    reads it so "does this PMID exist" can become "does this PMID name the paper you meant":
    existence alone cannot catch a fabricated citation, because PMIDs are densely allocated and an
    invented number is usually a real record for a different article.

    Every value is `None` when the field is absent rather than empty-string, so a caller can tell
    "PubMed did not say" from "PubMed said nothing is there" — the house tri-state, applied to
    metadata. `year` is the leading four digits of `pubdate` (which is free-form: `2017 Nov 20`,
    `2017`, `2017 Nov-Dec`), and nothing is invented when it does not start with a year.
    """
    out: dict[str, str | None] = {"title": None, "journal": None, "year": None, "first_author": None}
    for key, target in (
        ("title", "title"),
        ("fulljournalname", "journal"),
        ("sortfirstauthor", "first_author"),
    ):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            out[target] = value.strip()
    pubdate = summary.get("pubdate")
    if isinstance(pubdate, str):
        leading = pubdate.strip()[:4]
        if leading.isdigit():
            out["year"] = leading
    return out


def _doi_conflicts(pmid: str, studies: list[StudyRow], registry_doi: str | None) -> list[DoiConflict]:
    """Authored DOIs that disagree with the registry's, de-duplicated and order-stable.

    `StudyRow.doi` is free-form and may be wrapped in a URL, so both sides are reduced to the DOI token
    before comparison — otherwise `https://doi.org/10.1/x` and `10.1/x` would read as a conflict.
    """
    if not registry_doi:
        return []
    expected = doi_token(registry_doi)
    if expected is None:
        return []
    conflicts: list[DoiConflict] = []
    for authored in dedupe(s.doi for s in studies if s.doi):
        token = doi_token(authored)
        if token is not None and token != expected:
            conflicts.append(DoiConflict(pmid=pmid, authored=authored, registry=registry_doi))
    return conflicts


def _pmcid_conflicts(pmid: str, studies: list[StudyRow], registry_pmcid: str | None) -> list[PmcidConflict]:
    """Authored PMC ids that disagree with PubMed's for the same record (RM50).

    Read out of the **authored `pmid` cell**, which is free-form: a curator who writes
    `21551363 (PMC3110566)` has recorded two identifiers, and `extract_pmcids` is the same normalizer
    the schema's refusal uses, so the two cannot drift into different ideas of what spells a PMC id.
    De-duplicated and order-stable, like `_doi_conflicts`.

    Nothing is claimed when PubMed reports no PMC id: a paywalled article legitimately has none, and
    "the registry did not say" is not a contradiction (the same tri-state `_doi_conflicts` applies to
    an absent registry DOI).
    """
    if not registry_pmcid:
        return []
    expected = registry_pmcid.strip().upper()
    conflicts: list[PmcidConflict] = []
    for authored in dedupe(
        authored_pmcid for study in studies for authored_pmcid in extract_pmcids(study.pmid)
    ):
        if authored != expected:
            conflicts.append(PmcidConflict(pmid=pmid, authored=authored, registry=expected))
    return conflicts


def _normalized_title(text: str) -> str:
    """A title reduced to what a comparison should ignore: case, whitespace and a trailing period.

    Nothing more. A quote *containing* the title is a real quote of a paper that names itself, and a
    normalizer aggressive enough to catch that would start rejecting located passages.
    """
    return " ".join(text.split()).rstrip(".").casefold()


def _has_quote(studies: list[StudyRow]) -> bool:
    """Whether any of these citing rows carries a locator at all."""
    return any(s.provenance_quote or s.provenance_regex for s in studies)


def _quote_is_the_title(quotes: list[StudyRow], summary: dict) -> bool:
    """Whether every `provenance_quote` for this citation is just the article's own title (S54).

    **A title always appears in its own fulltext, so this check cannot fail on one** — `quotes_found`
    equals `quotes_authored`, and the module reports full quote coverage while establishing nothing
    about whether any claim is in any paper. Measured on four published modules: 3,668 rows, one
    distinct quote per PMID, each verbatim the title including the trailing period. That is worse than
    the failure the machine-located-passage refusal was written to prevent, because the check agrees.

    **The discriminator is the metadata, not the shape of the string.** A minimum length does not
    separate a title from a passage — seventeen words is an ordinary title and an ordinary sentence —
    and requiring a regex instead is no help, since a regex is as copyable as a quote. The comparison
    is against the title we already hold for that article, and it costs no request.

    `every`, not `any`: a module that quotes the title on one row and a located passage on another has
    an author who is doing the work, and flagging the citation would be noise. A citation where the
    title is the only thing on offer is the reported case.
    """
    title = bibliographic(summary).get("title")
    if not title:
        return False
    target = _normalized_title(title)
    located = [s.provenance_quote for s in quotes if s.provenance_quote]
    if not located or len(located) != len(quotes):
        # Some row uses a regex, which this cannot judge — withhold rather than report (the house
        # rule: unknown is not false).
        return False
    return all(_normalized_title(q) == target for q in located)


def _study_quote_found(study: StudyRow, fulltext: str, *, regex_timeout: float) -> bool | None:
    """Whether this study's locator appears in the article: `True`, `False`, or `None` when the regex
    could not be evaluated (a timeout, or a pattern that does not compile). A quote and a regex both
    count, and a literal hit settles it without the regex.

    `None` is never folded into `False` (RM361). It used to be, with a docstring promising that the
    run-level unchecked count would record the gap; it did not, because a quote matched against a
    fulltext counts as settled, so an undecided regex was published as a quote absent from the paper.
    """
    if study.provenance_quote and quote_matches(study.provenance_quote, fulltext):
        return True
    if study.provenance_regex:
        return regex_matches(study.provenance_regex, fulltext, timeout=regex_timeout)
    return False


def _quotes_found(quotes: list[StudyRow], text: str, *, regex_timeout: float) -> int | None:
    """How many of `quotes` the text contains, or `None` when any one of them could not be decided.

    The one count every quote tally writes (`quotes_found` on a row, a re-ask's heal, a DOI-only
    citation's). `None` withholds the whole count rather than one member of it: `quotes_found` is one
    cell, and a count missing one undecided quote would be read against fulltext as that quote
    checked and missed (`settled_quotes`). With the count withheld nothing on the row is settled, and
    every quote on it is reported unchecked, which is what an undecided regex is (RM361).
    """
    verdicts = [_study_quote_found(s, text, regex_timeout=regex_timeout) for s in quotes]
    if any(verdict is None for verdict in verdicts):
        return None
    return sum(1 for verdict in verdicts if verdict)


def _write_literature_csv(rows: list[LiteratureRow], output_path: Path) -> None:
    """Model column order, canonical cells, byte-stable across runs.

    Generic over the fields rather than a per-column dict literal, for the reason `_FIELDNAMES` gives:
    a hand-kept renderer is the same thing as a hand-kept column list, one edit later.

    **This file is a pure build product since 0.7 (RM124).** Hand-editing it is not expected and
    nothing preserves such an edit — a correction to a derived row belongs in `overrides.csv` beside
    the spec, where the compiler applies it on every build and it travels with the reason it was
    made. That is what makes deleting this file and re-running cost nothing: the author's judgements
    are not in here to lose, including the deliberate blank a merge could never tell from an absent
    value. The re-run itself is unchanged, and still gap-fills rather than re-asking every subject;
    what changed is that leaving a recorded row alone now risks nothing.
    """
    if nothing_to_write(output_path, rows):
        return  # RM370: a pass that answered nothing leaves no table
    with atomic_writer(output_path, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _cell(getattr(row, name)) for name in _FIELDNAMES})


def _cell(value: object) -> str:
    """`true`/`false`/empty for a tri-state, the value otherwise — matching the compiler's
    `_scalar_cell`, so reverse and this agree."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

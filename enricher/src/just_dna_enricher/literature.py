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
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import binning_citations, load_binning_rows, load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.layout import atomic_writer
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import VerificationRecord
from just_dna_format.normalize import now_utc_iso
from just_dna_format.spec import DOI_PATTERN, StudyRow, extract_pmcids, extract_pmids
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.eutils import EutilsClient, EutilsError, is_missing
from just_dna_enricher.licensing import article_terms, sidecar_path
from just_dna_enricher.locations import load_env
from just_dna_enricher.net import PacingGate, attempt_floor, batched, dedupe
from just_dna_enricher.verification import ran, record_verification, skipped

logger = logging.getLogger(__name__)

DEFAULT_EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DEFAULT_CROSSREF_BASE = "https://api.crossref.org"
#: The current address of NCBI's PMC ID converter. The long-published
#: `www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` 301-redirects here (probed 2026-08-13); named rather
#: than relied on as a redirect so a client that follows none still lands in the right place.
DEFAULT_PMC_IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"

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
    missing: list[str] = field(default_factory=list)          # PMIDs PubMed has no record of
    doi_conflicts: list[DoiConflict] = field(default_factory=list)
    pmcid_conflicts: list[PmcidConflict] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)             # the PMIDs the module cites right now
    existence_checked: int = 0                                 # of those, the ones carrying a verdict
    unresolved_citations: int = 0                              # of those, the ones resolving nowhere
    doi_verdicts_stale: int = 0                                # pinned DOI answers about another DOI
    doi_never_checked: int = 0                                 # cited DOIs no run has resolved
    noncommercial_quoted: list[str] = field(default_factory=list)   # quoted under a no-sale licence
    titles_as_quotes: list[str] = field(default_factory=list)      # PMIDs whose quote IS the title (S54)
    fulltext_requested: bool = True                            # --fulltext/--no-fulltext, as run
    quotes_authored: int = 0
    quotes_found: int = 0
    quotes_checked: int = 0                                    # quotes a retrieved text settled
    quotes_unchecked: int = 0                                  # unretrievable + never examined
    quotes_unexamined: int = 0                                 # authored after the sidecar pinned the row
    fulltext_checked: list[str] = field(default_factory=list)  # PMIDs whose fulltext was read
    abstract_checked: list[str] = field(default_factory=list)  # PMIDs matched against the abstract only
    doi_missing: list[str] = field(default_factory=list)       # DOIs Crossref has no record of
    identifiers_authored: int = 0                              # citations carrying an authored doi/PMC id
    identifiers_compared: int = 0                              # of those, the ones PubMed also named one for
    identifiers_conflicting: int = 0                           # of those, the ones where the two disagree
    identifiers_unmatched: int = 0                             # of those, the ones PubMed named none for
    identifiers_foreign: int = 0                               # of those, the ones a curator wrote
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
        if self.quotes_authored == 0:
            return (
                f"no provenance quotes authored across {len(self.cited)} citation(s) — nothing to "
                f"check against fulltext"
            )
        if not self.fulltext_requested:
            # `--no-fulltext` leaves every quote unchecked, and the generic wording below would call
            # that "nothing retrievable" — a claim about articles nobody tried to fetch, and one the
            # verification record for the same run contradicts by saying `not_requested`.
            return (
                f"{self.quotes_authored} authored quote(s) not matched against anything: "
                f"--no-fulltext"
            )
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
                f"{self.quotes_unexamined} not looked up, because literature.csv already pins their "
                f"citation — delete it to re-derive"
            )
        return "; ".join(parts)


# ── Europe PMC ──────────────────────────────────────────────────────────────────────────────────


@dataclass
class EuropePmcClient:
    """Open-access lookup and fulltext retrieval. Paced like every other client in this tier."""

    base_url: str = DEFAULT_EUROPEPMC_BASE
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
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(f"{self.base_url.rstrip('/')}/{path}", params=params)
        response.raise_for_status()
        return response

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
            payload = self._get(
                "search", {"query": query, "resultType": "core", "format": "json"}
            ).json()
            for record in (payload.get("resultList") or {}).get("result") or []:
                pmid = str(record.get("pmid") or "")
                if not pmid:
                    continue
                out[pmid] = {
                    "pmcid": record.get("pmcid"),
                    "doi": record.get("doi"),
                    # The API answers with the strings 'Y'/'N', not booleans.
                    "is_open_access": str(record.get("isOpenAccess") or "").upper() == "Y",
                    # `inEPMC` is NOT a fulltext signal: a record can be in Europe PMC with
                    # `isOpenAccess=N`, and `fullTextXML` then answers 404. Probed on PMID 23788249.
                    "in_epmc": str(record.get("inEPMC") or "").upper() == "Y",
                    # Verbatim, and `None` when the field is absent — an article whose terms Europe
                    # PMC does not state is unknown, not unlicensed.
                    "license": (record.get("license") or None),
                    "abstract": record.get("abstractText"),
                }
        return out

    def fulltext(self, pmcid: str) -> str | None:
        """Whitespace-normalized article text, or `None` when it cannot be retrieved.

        `None` is a normal outcome, not an error: an embargoed or author-manuscript-only record answers
        404, and the caller must record that as *unchecked* rather than as a failed match.
        """
        try:
            response = self._get(f"{pmcid}/fullTextXML")
        except httpx.HTTPStatusError as exc:
            logger.info("No retrievable fulltext for %s (HTTP %s)", pmcid, exc.response.status_code)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Fulltext fetch failed for %s (%s)", pmcid, exc)
            return None
        return extract_text(response.text)


@dataclass
class CrossrefClient:
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
        # resolved a cache path first. Both polite-identification services ask for it by name.
        load_env()
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)
        if self.contact_email is None:
            self.contact_email = os.environ.get("JUST_DNA_CONTACT_EMAIL") or None

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
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def exists(self, doi: str) -> bool | None:
        """`True`/`False`, or `None` when Crossref could not be asked.

        `None` rather than `False` on a transport failure or an unexpected status: "we could not
        check" and "this DOI does not exist" are different claims, and only the second is a finding
        against the module.
        """
        assert self.gate is not None
        self.gate.wait()
        try:
            response = self._http().get(f"{self.base_url.rstrip('/')}/works/{doi}")
        except httpx.HTTPError as exc:
            logger.warning("Crossref lookup failed for %s (%s); not checked", doi, exc)
            return None
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            logger.warning(
                "Crossref answered HTTP %s for %s; not checked", response.status_code, doi
            )
            return None
        return True


@dataclass(frozen=True)
class PmcIdRecord:
    """One answer from the PMC id converter. `in_pmc=False` is PMC saying it has no such record;
    an id the request never reached is absent from the result entirely, never one of these."""

    pmcid: str
    pmid: str | None = None
    in_pmc: bool = True
    error: str | None = None


@dataclass
class PmcIdConverterClient:
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
        # resolved a cache path first. Both polite-identification services ask for it by name.
        load_env()
        if self.gate is None:
            self.gate = PacingGate(self.min_request_interval)
        if self.contact_email is None:
            self.contact_email = os.environ.get("JUST_DNA_CONTACT_EMAIL") or None

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
        wait=wait_exponential_jitter(initial=1.0, max=10.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
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


def extract_text(xml: str) -> str | None:
    """JATS XML → one normalized string, or `None` if it does not parse.

    `itertext()` rather than a tag-stripping regex: real JATS carries nested inline markup inside
    sentences (`<italic>`, `<xref>`, `<sup>`), and a regex that removes tags without joining their
    text would silently glue words together and break matches that should succeed.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        logger.warning("Fulltext did not parse as XML (%s)", exc)
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


def regex_matches(
    pattern: str, fulltext: str, *, timeout: float = DEFAULT_REGEX_TIMEOUT
) -> bool | None:
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
                "NOT CHECKED (never as not-found)", pattern, timeout, len(fulltext),
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


def _citations(
    studies: list[StudyRow], bin_pmids: list[str] | None = None
) -> dict[str, list[StudyRow]]:
    """`pmid -> [study rows citing it]`, in first-occurrence order (deterministic emission, P7).

    One study row can carry several PMIDs (`pmid` is free-form and may hold a `;`-joined list), so this
    is a genuine fan-out rather than a re-keying.

    **There are two citation sites since 0.6** (RM47): `studies.csv`, and a `pmid` on a binning row,
    which grounds the *boundary* it sits on. A bin-only citation maps to an **empty** study list — it
    is a real citation to check for existence and identifiers, and it carries no quote or authored DOI
    because a bin row has neither column, so every per-study loop downstream simply finds nothing to
    do. Studies go in first so a paper cited both ways keeps its study rows.
    """
    out: dict[str, list[StudyRow]] = {}
    for study in studies:
        for pmid in extract_pmids(study.pmid):
            out.setdefault(pmid, []).append(study)
    for pmid in bin_pmids or []:
        out.setdefault(pmid, [])
    return out


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
) -> LiteratureResult:
    """Fill `literature.csv` from the citations a module makes.

    **Two citation sites since 0.6** (RM47): `studies.csv`, and `MeasureBinRow.pmid` on a binning
    table, which grounds the threshold it sits on. A module whose only citations are bin pointers is
    enriched exactly like one with a `studies.csv` — reading only the first would leave every
    threshold-grounding citation unchecked, which is worse than the honest gap the column replaced.

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
    # The bin pointers, through the compiler's own loader: importing its private binning-kind tuple or
    # keeping a second list of the four kinds here is the RM41 shape, and the copy goes stale on the
    # fifth kind. Its `ValueError` is re-raised as this pass's own error so a bad binning row is
    # diagnosed the way a bad `studies.csv` two lines above already is, rather than tracebacking out
    # of the CLI.
    try:
        bin_rows = load_binning_rows(spec_dir)
    except ValueError as exc:
        raise LiteratureEnrichmentError(f"a binning table is invalid: {exc}") from exc
    bin_pmids = binning_citations(bin_rows)
    if not studies and not bin_pmids:
        raise LiteratureEnrichmentError(
            f"no citations in {spec_dir} — the literature pass checks the citations a module makes, "
            f"and this one has neither studies.csv rows nor a `pmid` on any binning row."
        )

    existing: dict[tuple, LiteratureRow] = {}
    if output_path.exists():
        rows, errors, _ = load_csv_rows(output_path, LiteratureRow, "literature.csv")
        if errors:
            raise LiteratureEnrichmentError(f"existing literature.csv is invalid: {errors[0]}")
        for row in rows:
            existing[merge_key(row)] = row

    citations = _citations(studies, bin_pmids)
    authored_total = sum(
        1 for rows in citations.values() for s in rows if s.provenance_quote or s.provenance_regex
    )

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
                rows=out, mode=mode, skipped_offline=True,
                sources=sorted({r.source for r in out if r.source}),
                cited=sorted(citations, key=int),
                quotes_authored=authored_total,
                fulltext_requested=check_fulltext,
            ),
            spec_dir, write=write, check_fulltext=check_fulltext, check_doi=check_doi,
        )

    # Against the rows rather than the dict's keys, which are merge-key tuples and not bare PMIDs.
    have = {row.pmid for row in existing.values()}
    wanted = [pmid for pmid in citations if pmid not in have]
    fetched_at = now_utc_iso()
    result = LiteratureResult(rows=list(existing.values()), mode=mode,
                              cited=sorted(citations, key=int),
                              quotes_authored=authored_total,
                              fulltext_requested=check_fulltext)

    # **Titles are needed for MERGED rows too, which is the correction S54's reporter filed against
    # their own report.** A pinned row is not in `wanted`, so the fetch loop never sees it — and on
    # the four modules that motivated the title check, every row is pinned, so the check would not
    # have fired on a single one of the 3,668 quotes it was written for. `esummary` batches, so
    # adding the already-pinned PMIDs that carry a quote costs no extra round trip in the common
    # case and nothing at all when there are none.
    titled = [pmid for pmid in citations if pmid not in wanted and _has_quote(citations[pmid])]
    if wanted or titled:
        owned_eutils = eutils is None
        client = eutils or EutilsClient()
        try:
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
        try:
            indexed = epmc.lookup(wanted)
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

                quotes = [
                    s for s in citations[pmid] if s.provenance_quote or s.provenance_regex
                ]
                found: int | None = None
                quote_source: str | None = None
                if check_fulltext and quotes:
                    text = epmc.fulltext(pmcid) if (is_open and pmcid) else None
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
                        found = sum(
                            1 for s in quotes
                            if _study_quote_found(s, text, regex_timeout=regex_timeout)
                        )
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
                        pmid=pmid, doi=doi, pmcid=pmcid, exists=exists,
                        is_open_access=is_open,
                        license=license_name,
                        share_alike=terms.share_alike,
                        commercial_use=terms.commercial_use,
                        redistribution=terms.redistribution,
                        quotes_authored=len(quotes),
                        quotes_found=found,
                        quote_source=quote_source,
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
            # The pinned rows: no row is written for them (the sidecar is authoritative) and the
            # fulltext is never fetched, but the title comparison needs only the summary — so it
            # answers here where `quotes_found` cannot.
            for pmid in titled:
                if _quote_is_the_title(
                    [s for s in citations[pmid] if s.provenance_quote or s.provenance_regex],
                    summaries.get(pmid, {}),
                ):
                    result.titles_as_quotes.append(pmid)
        finally:
            if owned_epmc:
                epmc.close()
            if owned_crossref:
                crossref.close()

    result.titles_as_quotes = sorted(set(result.titles_as_quotes), key=int)
    result.rows.sort(key=lambda r: int(r.pmid))
    result.fulltext_checked = sorted(set(result.fulltext_checked), key=int)
    result.sources = sorted({r.source for r in result.rows if r.source})
    # Every tally runs here, once, over the sorted subject rows — so each list is ordered by PMID
    # rather than by whatever order the fetch took, and the gates below refuse on exactly what the
    # attestation records.
    _tally_existence(result, citations)
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
    return _attest(
        result, spec_dir, write=write, check_fulltext=check_fulltext, check_doi=check_doi
    )


def _doi_to_check(studies: list[StudyRow], registry_doi: str | None) -> str | None:
    """The DOI Crossref is asked about: the **authored** one, else the registry's.

    Shared by the fetch loop and `_tally_existence` so the run and the tally cannot end up naming
    different identifiers for the same citation. Checking the registry's own DOI is circular — it
    exists by construction, since the registry just handed it over — but it is the only one a
    citation without an authored cell has, and a citation PubMed does not index (a preprint, book or
    dataset) has only the authored one, which is the case the Crossref client is here for.
    """
    authored = next((s.doi for s in studies if s.doi), None)
    return _doi_token(authored) if authored else (registry_doi or None)


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
      Merge-not-clobber never refetches a pinned row, so a quote authored since is one nothing ever
      looked for. Calling that "no fulltext could be retrieved" states a retrievability failure that
      never happened, and for an open-access article it is flatly false; the remedy is also
      different, since deleting the sidecar re-derives it.
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
        if row.quotes_found is None:
            unchecked += pinned
            continue
        found += row.quotes_found
        if row.quote_source == "fulltext":
            checked += pinned
        else:
            checked += row.quotes_found
            unchecked += pinned - row.quotes_found
    result.noncommercial_quoted = sorted(noncommercial, key=int)
    result.quotes_found = found
    result.quotes_checked = checked
    result.quotes_unexamined = unexamined
    result.quotes_unchecked = unchecked + unexamined


def _compare_identifiers(
    result: LiteratureResult, citations: dict[str, list[StudyRow]]
) -> None:
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
                ),
                source="pubmed",
            )
        )
    else:
        parts = []
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
                subjects=result.existence_checked,
                findings=result.unresolved_citations,
                source="pubmed",
                detail="; ".join(parts) or None,
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
                f"{result.identifiers_unmatched} citation(s) PubMed reports no identifier of its "
                f"own for"
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
                f"{len(result.doi_conflicts)} DOI and {len(result.pmcid_conflicts)} PMC id "
                f"disagreement(s)"
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
    elif result.quotes_authored == 0:
        records.append(
            skipped(
                "provenance_quote",
                "nothing_to_check",
                detail=(
                    "no provenance quote or regex on any citation, so none of them asked this "
                    "question"
                ),
                source="europepmc",
            )
        )
    elif offline:
        records.append(
            skipped(
                "provenance_quote",
                "offline",
                detail=(
                    f"{result.quotes_authored} authored quote(s); an article's text can only come "
                    f"over the network, and there is no offline fulltext archive"
                ),
                source="europepmc",
            )
        )
    elif result.quotes_checked == 0:
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
                    f"{result.quotes_authored} authored quote(s), none of them settled: "
                    + _quote_gap_detail(result)
                ),
                source="europepmc",
            )
        )
    else:
        records.append(
            ran(
                "provenance_quote",
                subjects=result.quotes_checked,
                findings=result.quotes_checked - result.quotes_found,
                source="europepmc",
                detail=(
                    f"{result.quotes_unchecked} further authored quote(s) outside this denominator: "
                    + _quote_gap_detail(result)
                    if result.quotes_unchecked
                    else None
                ),
            )
        )
    return records


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
            f"could, where a miss is not a verdict)"
        )
    if result.quotes_unexamined:
        parts.append(
            f"{result.quotes_unexamined} never looked up, because literature.csv already pinned "
            f"their citation and a merge never refetches one — delete the sidecar to re-derive"
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


def _doi_conflicts(
    pmid: str, studies: list[StudyRow], registry_doi: str | None
) -> list[DoiConflict]:
    """Authored DOIs that disagree with the registry's, de-duplicated and order-stable.

    `StudyRow.doi` is free-form and may be wrapped in a URL, so both sides are reduced to the DOI token
    before comparison — otherwise `https://doi.org/10.1/x` and `10.1/x` would read as a conflict.
    """
    if not registry_doi:
        return []
    expected = _doi_token(registry_doi)
    if expected is None:
        return []
    conflicts: list[DoiConflict] = []
    for authored in dedupe(s.doi for s in studies if s.doi):
        token = _doi_token(authored)
        if token is not None and token != expected:
            conflicts.append(DoiConflict(pmid=pmid, authored=authored, registry=registry_doi))
    return conflicts


def _pmcid_conflicts(
    pmid: str, studies: list[StudyRow], registry_pmcid: str | None
) -> list[PmcidConflict]:
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
            conflicts.append(
                PmcidConflict(pmid=pmid, authored=authored, registry=expected)
            )
    return conflicts


def _doi_token(raw: str) -> str | None:
    """The bare `10.x/y` token inside a free-form DOI cell, lowercased (DOIs are case-insensitive)."""
    match = DOI_PATTERN.search(raw)
    return match.group(0).rstrip(".,;").casefold() if match else None


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


def _study_quote_found(study: StudyRow, fulltext: str, *, regex_timeout: float) -> bool:
    """Whether this study's locator appears in the article. A quote and a regex both count.

    An unbounded/uncheckable regex returns `None` from `regex_matches` and is treated here as
    not-found *for this row's tally only* when a literal quote also failed — the row-level count stays
    conservative, while the run-level `quotes_unchecked` records the coverage gap.
    """
    if study.provenance_quote and quote_matches(study.provenance_quote, fulltext):
        return True
    if study.provenance_regex:
        return regex_matches(study.provenance_regex, fulltext, timeout=regex_timeout) is True
    return False


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

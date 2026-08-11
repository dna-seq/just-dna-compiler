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
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.literature import LiteratureRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.spec import DOI_PATTERN, StudyRow, extract_pmids
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.eutils import EutilsClient, is_missing
from just_dna_enricher.net import PacingGate, attempt_floor, batched, dedupe

logger = logging.getLogger(__name__)

DEFAULT_EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DEFAULT_CROSSREF_BASE = "https://api.crossref.org"

_FIELDNAMES = [
    "pmid", "doi", "pmcid", "exists", "doi_exists", "is_open_access",
    "quotes_authored", "quotes_found", "quote_source", "source", "status", "fetched_at",
]

#: Seconds a single `provenance_regex` match may run before it is recorded as unchecked.
DEFAULT_REGEX_TIMEOUT = 5.0

_WHITESPACE = re.compile(r"\s+")


class LiteratureEnrichmentError(RuntimeError):
    """Raised in strict mode when a citation does not resolve, or contradicts its own identifiers."""


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
class LiteratureResult:
    rows: list[LiteratureRow]
    missing: list[str] = field(default_factory=list)          # PMIDs PubMed has no record of
    doi_conflicts: list[DoiConflict] = field(default_factory=list)
    quotes_authored: int = 0
    quotes_found: int = 0
    quotes_unchecked: int = 0                                  # no retrievable fulltext
    fulltext_checked: list[str] = field(default_factory=list)  # PMIDs whose fulltext was read
    abstract_checked: list[str] = field(default_factory=list)  # PMIDs matched against the abstract only
    doi_missing: list[str] = field(default_factory=list)       # DOIs Crossref has no record of
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    skipped_offline: bool = False

    @property
    def coverage(self) -> str:
        """The sentence this pass exists to be able to say honestly.

        The denominator is citations that had **something to check** — one with no authored quote was
        not skipped for lack of a fulltext, it simply asked no question. Counting it as unretrievable
        was a real bug found by running this against `reference_examples/pathogenic_clinvar/`, whose
        single citation is open access *and* carries no quote: the old wording claimed its fulltext
        could not be retrieved, which was the opposite of true.
        """
        checkable = [r for r in self.rows if (r.quotes_authored or 0) > 0]
        if not checkable:
            return (
                f"no provenance quotes authored across {len(self.rows)} citation(s) — nothing to "
                f"check against fulltext"
            )
        unread = len(checkable) - len(self.fulltext_checked) - len(self.abstract_checked)
        parts = [
            f"checked fulltext for {len(self.fulltext_checked)} of {len(checkable)} citation(s) with "
            f"an authored quote"
        ]
        if self.abstract_checked:
            # Reported separately, never folded into the fulltext count: a hit in an abstract settles
            # a quote, a miss does not, so the two searches are not the same evidence.
            parts.append(f"{len(self.abstract_checked)} abstract-only (a miss there is not a verdict)")
        parts.append(f"{unread} with nothing retrievable")
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
        """`pmid -> {pmcid, doi, is_open_access, abstract}` for the ids Europe PMC knows.

        Ids it does not know are simply **absent from the result**, with no error marker — which is why
        this is not an existence check. A caller must read a miss here as "not retrievable", never as
        "does not exist".

        **The abstract comes back for paywalled records too**, in this same response, and that is worth
        more than it looks: probed across a mix of non-open-access papers, four of five carried one
        (only a 1994 non-research document did not). It is the difference between checking a quote for
        the open-access minority and checking it for nearly everything.
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


def _citations(studies: list[StudyRow]) -> dict[str, list[StudyRow]]:
    """`pmid -> [study rows citing it]`, in first-occurrence order (deterministic emission, P7).

    One study row can carry several PMIDs (`pmid` is free-form and may hold a `;`-joined list), so this
    is a genuine fan-out rather than a re-keying.
    """
    out: dict[str, list[StudyRow]] = {}
    for study in studies:
        for pmid in extract_pmids(study.pmid):
            out.setdefault(pmid, []).append(study)
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
    """Fill `literature.csv` from the citations in `studies.csv`.

    Existing rows are authoritative and merged, never clobbered — the same rule `enrich()` applies to
    `resolution.csv`, with the same consequence: to regenerate after a machinery change you must delete
    the file first.

    `--offline` makes this a no-op with a warning. There is no offline literature snapshot and there
    will not be one; once `literature.csv` is written it *is* the pin, and later compiles read it
    offline and deterministically.
    """
    spec_dir = Path(spec_dir)
    studies_path = spec_dir / "studies.csv"
    output_path = spec_dir / "literature.csv"

    if not studies_path.exists():
        raise LiteratureEnrichmentError(
            f"no studies.csv in {spec_dir} — the literature pass checks the citations a module makes, "
            f"so there is nothing to do without one."
        )
    studies, errors, _ = load_csv_rows(studies_path, StudyRow, "studies.csv")
    if errors:
        raise LiteratureEnrichmentError(f"studies.csv is invalid: {errors[0]}")

    existing: dict[str, LiteratureRow] = {}
    if output_path.exists():
        rows, errors, _ = load_csv_rows(output_path, LiteratureRow, "literature.csv")
        if errors:
            raise LiteratureEnrichmentError(f"existing literature.csv is invalid: {errors[0]}")
        for row in rows:
            existing[row.pmid] = row

    citations = _citations(studies)
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
        return LiteratureResult(
            rows=out, mode=mode, skipped_offline=True,
            sources=sorted({r.source for r in out if r.source}),
            quotes_authored=authored_total,
        )

    wanted = [pmid for pmid in citations if pmid not in existing]
    fetched_at = now_utc_iso()
    result = LiteratureResult(rows=list(existing.values()), mode=mode,
                              quotes_authored=authored_total)

    if wanted:
        owned_eutils = eutils is None
        client = eutils or EutilsClient()
        try:
            summaries = client.esummary("pubmed", wanted)
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

                if not exists:
                    result.missing.append(pmid)

                for conflict in _doi_conflicts(pmid, citations[pmid], doi):
                    result.doi_conflicts.append(conflict)

                # Crossref checks the **authored** DOI in preference to the derived one. Checking the
                # registry's own DOI would be circular — it exists by construction, since the registry
                # just handed it over. The authored cell is the one nobody has verified, and it is the
                # only one that exists at all for a citation PubMed does not index (a preprint, book or
                # dataset), which is the case this whole client is here for.
                authored_doi = next((s.doi for s in citations[pmid] if s.doi), None)
                target_doi = _doi_token(authored_doi) if authored_doi else (doi or None)
                doi_exists: bool | None = None
                if check_doi and target_doi:
                    doi_exists = crossref.exists(target_doi)
                    if doi_exists is False:
                        result.doi_missing.append(target_doi)

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
                if quotes and (found is None or (quote_source == "abstract" and found < len(quotes))):
                    # Unchecked = the body was never read. An abstract hit settles a quote; an abstract
                    # miss leaves it open, so only the shortfall counts as unchecked.
                    result.quotes_unchecked += len(quotes) - (found or 0)
                result.rows.append(
                    LiteratureRow(
                        pmid=pmid, doi=doi, pmcid=pmcid, exists=exists,
                        is_open_access=is_open,
                        quotes_authored=len(quotes),
                        quotes_found=found,
                        quote_source=quote_source,
                        doi_exists=doi_exists,
                        # PubMed is the row's source: it decides existence and supplies the
                        # identifiers. Europe PMC contributes `is_open_access` and the fulltext, but
                        # it cannot originate a row (it silently omits ids it does not know), so it
                        # is not a `source` in the sense the other sidecars use the word.
                        source="pubmed",
                        status="resolved" if exists else "not_found",
                        fetched_at=fetched_at,
                    )
                )
        finally:
            if owned_epmc:
                epmc.close()
            if owned_crossref:
                crossref.close()

    result.rows.sort(key=lambda r: int(r.pmid))
    result.missing = sorted(set(result.missing), key=int)
    result.fulltext_checked = sorted(set(result.fulltext_checked), key=int)
    result.sources = sorted({r.source for r in result.rows if r.source})
    result.quotes_found = sum(r.quotes_found for r in result.rows if r.quotes_found is not None)
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
    if write:
        _write_literature_csv(result.rows, output_path)
    return result


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


def _doi_token(raw: str) -> str | None:
    """The bare `10.x/y` token inside a free-form DOI cell, lowercased (DOIs are case-insensitive)."""
    match = DOI_PATTERN.search(raw)
    return match.group(0).rstrip(".,;").casefold() if match else None


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
    """Fixed column order, canonical cells, byte-stable across runs."""
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "pmid": row.pmid,
                    "doi": row.doi or "",
                    "pmcid": row.pmcid or "",
                    "exists": _bool_cell(row.exists),
                    "doi_exists": _bool_cell(row.doi_exists),
                    "is_open_access": _bool_cell(row.is_open_access),
                    "quotes_authored": row.quotes_authored if row.quotes_authored is not None else "",
                    "quotes_found": row.quotes_found if row.quotes_found is not None else "",
                    "quote_source": row.quote_source or "",
                    "source": row.source or "",
                    "status": row.status or "",
                    "fetched_at": row.fetched_at or "",
                }
            )


def _bool_cell(value: bool | None) -> str:
    """`true`/`false`/empty — matching the compiler's `_scalar_cell`, so reverse and this agree."""
    if value is None:
        return ""
    return "true" if value else "false"

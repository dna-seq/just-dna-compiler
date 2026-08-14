"""The literature pass — existence, identifier agreement, and honestly-partial fulltext coverage.

Every payload here is **recorded from the live services**, not written by hand, and the recordings
carry three quirks a fabricated fixture would have smoothed over:

* PMID 99999999 comes back from PubMed as a normal-looking record with an `error` key — the basis of
  the existence check. It is eight digits rather than a rounder nine because `spec.PMID_PATTERN` caps
  a PMID at eight, so a nine-digit id cannot even be authored; and it was *checked* against the live
  service rather than assumed absent, per the `rs999999999` sampling trap in CLAUDE.md;
* PMID 12345678 is a **real, indexed** PubMed record that is *not in PMC*, so it is retrievable-no /
  exists-yes. Conflating those two is the mistake this pass is built to avoid;
* Europe PMC, asked about all three, returns **two results and silently omits the third** — no error,
  no marker. That is why PubMed decides existence and Europe PMC only decides retrievability.
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.literature import (
    CrossrefClient,
    EuropePmcClient,
    LiteratureEnrichmentError,
    enrich_literature,
    extract_text,
    quote_matches,
    regex_matches,
)
from just_dna_enricher.net import PacingGate
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.verification import read_verification


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    """8 bits instead of 20: the pass attests on its way out and these cases are not about the work."""
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_ESUMMARY = json.loads((_ASSETS / "pubmed_esummary_payload.json").read_text())
_EPMC_SEARCH = json.loads((_ASSETS / "europepmc_search_payload.json").read_text())
_FULLTEXT_XML = (_ASSETS / "europepmc_fulltext_PMC5753237.xml").read_text()
_CROSSREF = json.loads((_ASSETS / "crossref_works_payload.json").read_text())

_REAL = "29165669"        # ClinVar paper: exists, open access, in PMC
_PAYWALLED = "12345678"   # real PubMed record, NOT in PMC
_ABSENT = "99999999"      # no PubMed record at all (checked, not assumed)

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


# ── fixtures / doubles ──────────────────────────────────────────────────────────────────────────


def _eutils() -> EutilsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ESUMMARY)

    client = EutilsClient(settings=EutilsSettings(email=None))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _epmc(fulltext: str | None = _FULLTEXT_XML, fulltext_status: int = 200) -> EuropePmcClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fullTextXML"):
            if fulltext is None:
                return httpx.Response(fulltext_status)
            return httpx.Response(fulltext_status, text=fulltext)
        return httpx.Response(200, json=_EPMC_SEARCH)

    client = EuropePmcClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _crossref() -> CrossrefClient:
    def handler(request: httpx.Request) -> httpx.Response:
        doi = str(request.url).split("/works/", 1)[1]
        record = _CROSSREF.get(doi)
        if record is None or record["status"] == 404:
            return httpx.Response(404)
        return httpx.Response(200, json={"message": record["message"]})

    client = CrossrefClient(contact_email=None)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _spec(d: Path, studies: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n", encoding="utf-8"
    )
    (d / "studies.csv").write_text(studies, encoding="utf-8")
    return d


def _run(spec: Path, **kw):
    return enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(), crossref=_crossref(), **kw
    )


# ── existence ───────────────────────────────────────────────────────────────────────────────────


def test_a_nonexistent_pmid_is_detected_and_a_paywalled_one_is_not(tmp_path: Path) -> None:
    """The distinction the whole pass turns on: *not indexed* is not *not retrievable*."""
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\nrs334,{_PAYWALLED}\nrs334,{_ABSENT}\n")
    result = _run(spec)

    assert result.missing == [_ABSENT]
    by_pmid = {r.pmid: r for r in result.rows}
    assert by_pmid[_ABSENT].exists is False
    assert by_pmid[_ABSENT].status == "not_found"
    # ...while the paywalled record exists perfectly well; it is only unreadable.
    assert by_pmid[_PAYWALLED].exists is True
    assert by_pmid[_PAYWALLED].is_open_access is False
    assert by_pmid[_PAYWALLED].pmcid is None


def test_strict_refuses_a_citation_that_does_not_resolve(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_ABSENT}\n")
    with pytest.raises(LiteratureEnrichmentError, match="no record of"):
        _run(spec, mode="strict")


# ── identifiers come free with the existence check ──────────────────────────────────────────────


def test_doi_and_pmcid_are_filled_from_the_same_response(tmp_path: Path) -> None:
    """Both arrive in esummary's `articleids`, which is why the PMC ID converter is not called.

    Expected values are read out of the recorded payload at runtime rather than pasted in, so a
    refreshed recording cannot leave a stale assertion passing.
    """
    record = _ESUMMARY["result"][_REAL]
    expected = {e["idtype"]: e["value"] for e in record["articleids"]}

    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    row = _run(spec).rows[0]

    assert row.doi == expected["doi"]
    assert row.pmcid == expected["pmc"]
    assert row.pmcid.startswith("PMC")           # the bare form, not the `pmc-id: …;` wrapper


def test_an_absent_authored_doi_is_filled_in_the_sidecar_not_in_studies_csv(tmp_path: Path) -> None:
    """Enrichment, not co-authoring: `content_signature` is defined as reference-independent."""
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    before = (spec / "studies.csv").read_text()
    result = _run(spec)

    assert result.rows[0].doi
    assert (spec / "studies.csv").read_text() == before
    assert (spec / "literature.csv").is_file()


def test_a_contradicting_authored_doi_is_reported_never_repaired(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/definitely-not-this-paper\n"
    )
    result = _run(spec)

    assert len(result.doi_conflicts) == 1
    assert result.doi_conflicts[0].authored == "10.9999/definitely-not-this-paper"
    assert "reported, never rewritten" in str(result.doi_conflicts[0])
    # The row still records the REGISTRY's doi; the authored cell is untouched.
    assert result.rows[0].doi == "10.1093/nar/gkx1153"
    assert "10.9999" in (spec / "studies.csv").read_text()


def test_a_url_wrapped_doi_is_not_a_conflict(tmp_path: Path) -> None:
    """`https://doi.org/10.1/x` and `10.1/x` are the same identifier written two ways."""
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},https://doi.org/10.1093/nar/gkx1153\n"
    )
    assert _run(spec).doi_conflicts == []


def test_strict_refuses_a_contradicting_doi(tmp_path: Path) -> None:
    """The authored DOI is a **real** paper, just not this one — which isolates the conflict from the
    separate "this DOI does not resolve" finding, so the test pins the diagnosis it means to."""
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.1101/2024.06.17.599351\n")
    with pytest.raises(LiteratureEnrichmentError, match="disagree with the registry"):
        _run(spec, mode="strict")


# ── fulltext: partial coverage, reported as partial ─────────────────────────────────────────────


def test_a_quote_present_in_the_real_article_is_found(tmp_path: Path) -> None:
    """Matched against the recorded JATS fulltext, with the phrase taken FROM that fulltext."""
    text = extract_text(_FULLTEXT_XML)
    assert text and len(text) > 10_000
    phrase = "variant interpretations"
    assert phrase in text.casefold()

    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},{phrase}\n"
    )
    result = _run(spec)

    assert result.fulltext_checked == [_REAL]
    assert result.rows[0].quotes_authored == 1
    assert result.rows[0].quotes_found == 1
    assert result.quotes_unchecked == 0


def test_a_quote_absent_from_the_article_is_reported_as_checked_and_not_found(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},this sentence is certainly not in the paper\n",
    )
    result = _run(spec)

    assert result.rows[0].quotes_found == 0        # zero: checked, not found
    assert result.quotes_unchecked == 0


def test_a_paywalled_article_is_never_checked_rather_than_failed(tmp_path: Path) -> None:
    """The single most important honesty property: null ≠ zero.

    A quote in an article we could not read has not failed to match. Recording it as 0-found would
    describe the pass's own reach as a defect in the module.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_PAYWALLED},anything at all\n"
    )
    result = _run(spec)

    assert result.rows[0].quotes_found is None     # null: not checked
    assert result.rows[0].quotes_authored == 1
    assert result.quotes_unchecked == 1
    assert result.fulltext_checked == []
    assert result.abstract_checked == []      # this one has no abstract either
    assert result.rows[0].quote_source is None
    assert "1 with nothing retrievable" in result.coverage


def test_coverage_is_stated_as_a_fraction(tmp_path: Path) -> None:
    """Counted in quotes, not citations: one citation can carry a settled quote and an unread one."""
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
        f"rs334,{_PAYWALLED},something\n",
    )
    result = _run(spec)
    assert result.coverage == (
        "checked 1 of 2 authored quote(s) against retrieved text; 1 with nothing retrievable "
        "(or only an abstract, where a miss is not a verdict)"
    )


def test_a_citation_with_no_quote_is_not_counted_as_unretrievable(tmp_path: Path) -> None:
    """Found by dogfooding `reference_examples/pathogenic_clinvar/`, whose one citation is open access
    and carries no quote — the old wording said its fulltext could not be retrieved, the opposite of
    the truth. A citation that asked no question was not skipped for lack of an answer.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    result = _run(spec)

    assert result.rows[0].is_open_access is True          # it IS retrievable
    assert "nothing to check against fulltext" in result.coverage
    assert "no retrievable fulltext" not in result.coverage


def test_a_404_fulltext_falls_back_to_the_abstract(tmp_path: Path) -> None:
    """Embargoed records answer 404 even when Europe PMC flags them open access — so the abstract,
    which arrived in the same search response, is searched instead.

    The miss is still counted as unchecked: the body was never read, so `quote_source="abstract"` is
    what tells a reader that this 0 is not a verdict."""
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},anything\n")
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(fulltext=None, fulltext_status=404),
        crossref=_crossref(),
    )
    assert result.rows[0].quote_source == "abstract"
    assert result.rows[0].quotes_found == 0
    assert result.quotes_unchecked == 1
    assert result.fulltext_checked == [] and result.abstract_checked == [_REAL]


# ── the regex bound ─────────────────────────────────────────────────────────────────────────────


def test_a_regex_locator_matches_the_fulltext() -> None:
    text = extract_text(_FULLTEXT_XML)
    assert regex_matches(r"variant\s+interpretations", text) is True
    assert regex_matches(r"zzz-not-here-zzz", text) is False


def test_a_catastrophic_regex_is_recorded_as_unchecked_not_as_absent() -> None:
    """The three-way return is the point: a pattern that ran too long has not disproved the quote.

    Uses a genuinely catastrophic pattern against a long non-matching subject, with a short timeout so
    the test is quick. Demonstrated, not asserted from theory: it must return `None`, never `False`.
    """
    evil = r"(a+)+$"
    subject = "a" * 40 + "!"
    assert regex_matches(evil, subject, timeout=0.25) is None


def test_an_uncompilable_regex_abstains() -> None:
    assert regex_matches(r"(unclosed", "anything") is None


def test_quote_matching_ignores_case_and_whitespace_shape() -> None:
    """JATS text is re-flowed on extraction, so a quote copied from a PDF must still match."""
    assert quote_matches("Variant   Interpretations", "the variant interpretations we support")
    assert not quote_matches("variant interpretations", "unrelated text")


# ── merge semantics and offline ─────────────────────────────────────────────────────────────────


def test_existing_rows_are_authoritative_and_not_refetched(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
        f"{_REAL},10.0000/hand-corrected,,true,,,,manual,resolved,\n",
        encoding="utf-8",
    )
    result = _run(spec)
    assert [r.doi for r in result.rows] == ["10.0000/hand-corrected"]
    assert [r.source for r in result.rows] == ["manual"]


def test_offline_is_a_no_op_with_a_warning(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    result = enrich_literature(spec, offline=True)
    assert result.skipped_offline is True
    assert result.rows == []
    assert not (spec / "literature.csv").exists()


def test_rows_are_emitted_in_a_deterministic_order(tmp_path: Path) -> None:
    """Emission order feeds parquet bytes, so it is pinned rather than left to dict iteration."""
    spec = _spec(
        tmp_path / "s", f"rsid,pmid\nrs334,{_ABSENT}\nrs334,{_REAL}\nrs334,{_PAYWALLED}\n"
    )
    result = _run(spec)
    assert [r.pmid for r in result.rows] == sorted([_REAL, _PAYWALLED, _ABSENT], key=int)


def test_one_study_row_citing_several_pmids_fans_out(tmp_path: Path) -> None:
    """`StudyRow.pmid` is free-form and may hold a `;`-joined list — each id is its own citation."""
    spec = _spec(tmp_path / "s", f'rsid,pmid\nrs334,"PMID: {_REAL}; PMID: {_PAYWALLED}"\n')
    result = _run(spec)
    assert {r.pmid for r in result.rows} == {_REAL, _PAYWALLED}


# ── live probes (opt-in) ────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not __import__("os").environ.get("JUST_DNA_NETWORK_TESTS"),
    reason="set JUST_DNA_NETWORK_TESTS=1 to run live literature probes",
)
def test_live_services_still_behave_as_recorded() -> None:
    """Guards the recordings: if PubMed or Europe PMC change shape, this fails before the unit tests
    start passing against a fiction."""
    with EutilsClient() as client:
        records = client.esummary("pubmed", [_REAL, _ABSENT])
    from just_dna_enricher.eutils import is_missing

    assert not is_missing(records[_REAL])
    assert is_missing(records[_ABSENT])

    with EuropePmcClient() as epmc:
        found = epmc.lookup([_REAL, _PAYWALLED, _ABSENT, "31182865"])
    assert found[_REAL]["is_open_access"] is True
    assert found[_PAYWALLED]["is_open_access"] is False
    assert _ABSENT not in found, "Europe PMC omits unknown ids silently — it is not an existence oracle"
    # The abstract fallback's premise: a paywalled record still carries an abstract.
    paywalled_with_abstract = found["31182865"]
    assert paywalled_with_abstract["is_open_access"] is False
    assert paywalled_with_abstract["abstract"], "abstracts for non-OA records are the coverage gain"

    with CrossrefClient() as crossref:
        assert crossref.exists("10.1093/nar/gkx1153") is True
        assert crossref.exists("10.1101/2024.06.17.599351") is True   # preprint, no PMID
        assert crossref.exists("10.9999/definitely-not-a-real-doi") is False


# ── the abstract fallback: coverage for paywalled articles ──────────────────────────────────────


def test_a_paywalled_article_with_an_abstract_is_still_searched(tmp_path: Path) -> None:
    """The coverage gain that answers "how do we check a paywalled item".

    Existence was never the problem — PubMed indexes paywalled work, so `exists` is already True for
    them. What was missing was the *quote* check, and Europe PMC serves the abstract for non-open-access
    records in the very response the pass already makes. Probed across a mix of non-OA papers, four of
    five carried one.

    The phrase is read out of the recorded abstract at runtime, so a refreshed recording cannot leave a
    stale assertion passing.
    """
    record = next(
        r for r in _EPMC_SEARCH["resultList"]["result"] if r.get("abstractText")
        and r.get("isOpenAccess") == "N"
    )
    pmid, abstract = record["pmid"], record["abstractText"]
    phrase = " ".join(abstract.split()[3:8]).replace('"', "")

    spec = _spec(tmp_path / "s", f'rsid,pmid,provenance_quote\nrs334,{pmid},"{phrase}"\n')
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(), crossref=_crossref(),
    )
    row = next(r for r in result.rows if r.pmid == pmid)
    assert row.is_open_access is False        # genuinely paywalled...
    assert row.quote_source == "abstract"     # ...and still checked
    assert row.quotes_found == 1
    assert pmid in result.abstract_checked


def test_an_abstract_hit_settles_a_quote_but_a_miss_does_not(tmp_path: Path) -> None:
    """The asymmetry `quote_source` exists to record.

    A phrase found in the abstract is in the paper — conclusive. A phrase absent from a 200-word
    abstract says nothing about the body, so it stays counted as unchecked rather than as a failure.
    """
    record = next(
        r for r in _EPMC_SEARCH["resultList"]["result"] if r.get("abstractText")
        and r.get("isOpenAccess") == "N"
    )
    pmid = record["pmid"]
    spec = _spec(
        tmp_path / "s",
        f'rsid,pmid,provenance_quote\nrs334,{pmid},"certainly not in this abstract at all"\n',
    )
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(), crossref=_crossref(),
    )
    row = next(r for r in result.rows if r.pmid == pmid)
    assert (row.quote_source, row.quotes_found) == ("abstract", 0)
    assert result.quotes_unchecked == 1       # a miss in an abstract is not a verdict
    assert "not a verdict" in result.coverage


# ── Crossref: the citations PubMed structurally cannot cover ────────────────────────────────────


def test_crossref_confirms_a_real_doi_and_rejects_a_fabricated_one() -> None:
    """Crossref answers for preprints, books and datasets — things PubMed does not index at all.

    Asserted straight off the recording: a journal article and a bioRxiv preprint both resolve, and a
    fabricated DOI 404s. The preprint is the case that matters, because it has no PMID and is exactly
    what the 1.0 doi-first flip will make authorable.
    """
    client = _crossref()
    assert client.exists("10.1093/nar/gkx1153") is True
    assert client.exists("10.1101/2024.06.17.599351") is True    # bioRxiv preprint, no PMID
    assert client.exists("10.9999/definitely-not-a-real-doi") is False
    assert _CROSSREF["10.1101/2024.06.17.599351"]["message"]["type"] == "posted-content"


def test_a_doi_crossref_cannot_resolve_is_reported(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/definitely-not-a-real-doi\n"
    )
    result = _run(spec)
    # The AUTHORED doi is what gets checked — the registry's own would exist by construction.
    assert result.doi_missing == ["10.9999/definitely-not-a-real-doi"]
    assert result.rows[0].doi_exists is False


def test_an_unreachable_crossref_records_not_checked_never_absent(tmp_path: Path) -> None:
    """A transport failure must not be reported as "this DOI does not exist"."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    client = CrossrefClient(contact_email=None)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    assert client.exists("10.1093/nar/gkx1153") is None


# ── what the pass records about itself (RM45) ───────────────────────────────────────────────────


def _records(spec: Path) -> dict:
    return {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}


def test_the_three_checks_are_recorded_with_their_own_denominators(tmp_path: Path) -> None:
    """Three questions, three denominators — every citation exists, only some carry a quote.

    Before this the pass answered all three to a log line and let the record die with the process, so
    a module whose citations had been checked and one where the command was never run shipped
    identical manifests. Run this file against the pass as it stood and no `verification.json` is
    written at all.
    """
    phrase = "variant interpretations"
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},{phrase}\nrs334,{_PAYWALLED},\n",
    )
    result = _run(spec, check_doi=False)
    records = _records(spec)

    assert set(records) == {"citation_existence", "citation_identifier", "provenance_quote"}
    assert all(r.release is None for r in records.values())      # neither service publishes one

    existence = records["citation_existence"]
    assert existence.skipped is None
    assert existence.subjects == result.existence_checked == len(result.rows) == 2
    assert existence.findings == 0 and existence.source == "pubmed"
    # Half a check is reported as half a check: `--no-doi` leaves a DOI-only citation unasked, and a
    # record that did not say so would let a reader read the zero as covering both registries.
    assert "--no-doi" in (existence.detail or "")

    # No authored doi or PMC id anywhere: nothing to compare, and that is not a clean pass.
    assert records["citation_identifier"].skipped == "nothing_to_check"

    quote = records["provenance_quote"]
    assert quote.skipped is None and quote.source == "europepmc"
    assert quote.subjects == result.quotes_checked == 1     # only the open-access one was read
    assert quote.findings == 0                              # and the quote is in it


def test_a_quote_the_article_does_not_carry_is_a_finding(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},this sentence is certainly not in the paper\n",
    )
    result = _run(spec)

    quote = _records(spec)["provenance_quote"]
    assert (quote.subjects, quote.findings) == (1, 1)
    assert result.quotes_found == 0


def test_an_article_nobody_could_read_is_a_skip_never_a_clean_run(tmp_path: Path) -> None:
    """The F4 trap: `subjects 0, findings 0` on a check that could not run reads as a pass.

    A quote in an article with neither fulltext nor abstract has not failed to match and has not been
    confirmed either. `no_reference` says which, and the authored count rides in `detail` so the
    reader can see the size of what went unread.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_PAYWALLED},anything at all\n"
    )
    result = _run(spec)

    quote = _records(spec)["provenance_quote"]
    assert quote.skipped == "no_reference"
    assert (quote.subjects, quote.findings) == (0, 0)
    assert "1 authored quote(s)" in (quote.detail or "")
    assert result.quotes_checked == 0 and result.quotes_unchecked == 1


def test_a_citation_that_resolves_in_neither_registry_is_one_finding(tmp_path: Path) -> None:
    """PubMed's `exists` and Crossref's `doi_exists` answer the same question for one citation, so a
    row failing both is one unresolved citation rather than two — which is also what keeps findings a
    subset of subjects."""
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_ABSENT},10.9999/definitely-not-a-real-doi\n"
    )
    result = _run(spec)

    assert result.missing == [_ABSENT] and result.doi_missing == ["10.9999/definitely-not-a-real-doi"]
    existence = _records(spec)["citation_existence"]
    assert (existence.subjects, existence.findings) == (1, 1)
    assert "no PubMed record" in (existence.detail or "")
    assert "do not resolve in Crossref" in (existence.detail or "")


def test_an_authored_identifier_is_compared_and_the_disagreement_recorded(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/definitely-not-this-paper\n"
    )
    result = _run(spec)

    record = _records(spec)["citation_identifier"]
    assert (record.subjects, record.findings) == (1, 1)
    assert record.subjects == result.identifiers_compared
    assert "1 DOI and 0 PMC id disagreement(s)" in (record.detail or "")


def test_offline_records_three_skips_and_claims_no_check_ran(tmp_path: Path) -> None:
    """With no `literature.csv` there is no earlier answer to protect, so the skips are written."""
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},anything\n")
    enrich_literature(spec, offline=True)

    records = _records(spec)
    assert {name: r.skipped for name, r in records.items()} == {
        "citation_existence": "offline",
        "citation_identifier": "offline",
        "provenance_quote": "offline",
    }
    assert all(r.subjects == 0 and r.findings == 0 for r in records.values())


def test_a_check_the_caller_switched_off_is_not_requested_not_offline(tmp_path: Path) -> None:
    """The two are different facts about the same absence, and only one is cleared by egress."""
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},anything\n")
    _run(spec, check_fulltext=False)
    assert _records(spec)["provenance_quote"].skipped == "not_requested"

    other = _spec(tmp_path / "t", f"rsid,pmid,provenance_quote\nrs334,{_REAL},anything\n")
    enrich_literature(other, offline=True, check_fulltext=False)
    assert _records(other)["provenance_quote"].skipped == "not_requested"


def test_re_running_the_pass_does_not_downgrade_what_it_recorded(tmp_path: Path) -> None:
    """`literature.csv` is the pin, so the second run's record must not read `nothing in scope`.

    `record_verification` replaces per check, so a denominator counted over *this run's fetches*
    would let a no-op re-run overwrite a true attestation with `subjects=0` — which the model's own
    field description reads as "the check ran and had nothing in scope".
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\nrs334,{_ABSENT}\n")
    _run(spec)
    first = _records(spec)["citation_existence"]
    _run(spec)
    second = _records(spec)["citation_existence"]

    assert (first.subjects, first.findings) == (2, 1)
    assert (second.subjects, second.findings) == (first.subjects, first.findings)


def test_an_identifier_conflict_is_still_found_on_a_second_run(tmp_path: Path) -> None:
    """The comparison used to run only over rows this run fetched, so an existing `literature.csv`
    hid every identifier conflict — and since the conflict lists are what `strict` refuses on,
    `--best-effort` then `--strict` blessed a module the same two commands in the other order refuse.
    Both halves are in hand without a request, so nothing about the comparison needs the fetch.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.1101/2024.06.17.599351\n")
    assert len(_run(spec).doi_conflicts) == 1
    assert (spec / "literature.csv").is_file()

    assert len(_run(spec).doi_conflicts) == 1
    with pytest.raises(LiteratureEnrichmentError, match="disagree with the registry"):
        _run(spec, mode="strict")


def test_a_curators_own_identifier_is_never_called_the_registrys(tmp_path: Path) -> None:
    """A hand-corrected row spells its own `source`, and its doi is that curator's claim.

    Comparing against it and reporting "disagrees with the registry" would put a false attribution in
    front of an author — the same rule that keeps the gene/locus check coarse. And the *record* must
    not launder that into a different false attribution: `ran(0, 0)` reads as a clean pass, and
    "PubMed reports no identifier of its own" is a claim about PubMed that this run never put.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/authored\n")
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
        f"{_REAL},10.0000/hand-corrected,,true,,,,manual,resolved,\n",
        encoding="utf-8",
    )
    result = _run(spec)

    assert result.doi_conflicts == []
    assert (result.identifiers_authored, result.identifiers_foreign) == (1, 1)
    assert result.identifiers_unmatched == 0     # PubMed was not the reason, and must not be blamed
    record = _records(spec)["citation_identifier"]
    assert record.skipped == "no_reference"
    assert "a curator wrote" in (record.detail or "")
    assert "PubMed reports no identifier" not in (record.detail or "")


def test_strict_refuses_the_same_citation_however_many_runs_precede_it(tmp_path: Path) -> None:
    """The gate and the record must read one set, or a module ships a manifest naming a defect its
    own `--strict` compile just blessed.

    `result.missing` used to be appended inside the fetch loop, so a second run over an existing
    `literature.csv` left it empty and `strict` refused nothing — while the attestation the same run
    wrote, reading the rows, said `findings=1`. Whether `--strict` refuses became a function of how
    many times the author had run `--best-effort` first.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\nrs334,{_ABSENT}\n")
    assert _run(spec).missing == [_ABSENT]

    second = _run(spec)
    assert second.missing == [_ABSENT], "the pin still says PubMed has no record of it"
    record = _records(spec)["citation_existence"]
    assert (record.subjects, record.findings) == (2, 1)
    with pytest.raises(LiteratureEnrichmentError, match="PubMed has no record"):
        _run(spec, mode="strict")


def test_an_offline_re_run_leaves_an_earlier_answer_alone(tmp_path: Path) -> None:
    """`--offline` is a documented no-op, so it must not rewrite a verdict into "never asked".

    `merge_records` replaces per check, so a skip written here would overwrite the real record — and
    the sidecar it is a summary of is still sitting there unchanged.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\nrs334,{_ABSENT}\n")
    _run(spec)
    before = _records(spec)["citation_existence"]
    assert (before.subjects, before.findings, before.skipped) == (2, 1, None)

    enrich_literature(spec, offline=True)
    after = _records(spec)["citation_existence"]
    assert (after.subjects, after.findings, after.skipped) == (2, 1, None)
    assert after.checked_at == before.checked_at, "an untouched record keeps its own timestamp"


def test_offline_with_no_pin_still_says_why_it_could_not_ask(tmp_path: Path) -> None:
    """The other half of the rule: silence is only right when it protects an answer."""
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    enrich_literature(spec, offline=True)
    assert _records(spec)["citation_existence"].skipped == "offline"


def test_a_quote_authored_after_the_pin_was_never_looked_up_not_unretrievable(tmp_path: Path) -> None:
    """Two ways of having read nothing, and this one is not the article's fault.

    Merge-not-clobber never refetches a pinned citation, so a quote added after `literature.csv` was
    written is simply never examined — the row still says `quotes_authored=0`. Reporting that as "no
    fulltext could be retrieved" states a retrievability failure that never happened, and for this
    PMID it is flatly false: its fulltext is open access and was read on the first run.
    """
    studies = f"rsid,pmid,provenance_quote\nrs334,{_REAL},\n"
    spec = _spec(tmp_path / "s", studies)
    _run(spec)
    assert _records(spec)["provenance_quote"].skipped == "nothing_to_check"

    (spec / "studies.csv").write_text(
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n", encoding="utf-8"
    )
    result = _run(spec)

    assert (result.quotes_authored, result.quotes_checked) == (1, 0)
    assert result.quotes_unexamined == 1
    record = _records(spec)["provenance_quote"]
    assert record.skipped == "no_reference"
    assert "never looked up" in (record.detail or "")
    assert "could not be read" not in (record.detail or "")


def test_a_citation_removed_from_studies_stops_being_counted(tmp_path: Path) -> None:
    """A finding no authored edit could clear is the defect, not the finding.

    `literature.csv` never drops a row — deleting a curator's row is not this pass's call — so a
    subject set read off the whole sidecar goes on reporting a citation the module no longer makes,
    and the only remedy is deleting the file by hand.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\nrs334,{_ABSENT}\n")
    _run(spec)
    assert _records(spec)["citation_existence"].findings == 1

    (spec / "studies.csv").write_text(f"rsid,pmid\nrs334,{_REAL}\n", encoding="utf-8")
    result = _run(spec)

    assert result.missing == [] and result.cited == [_REAL]
    assert [r.pmid for r in result.rows] == sorted([_REAL, _ABSENT], key=int)  # the row is kept
    record = _records(spec)["citation_existence"]
    assert (record.subjects, record.findings) == (1, 0)
    _run(spec, mode="strict")       # and the module is compilable again without deleting anything


def test_a_quote_removed_since_the_pin_is_not_a_finding_about_the_module(tmp_path: Path) -> None:
    """The same rule one level down: a pin that counts two quotes describes neither of one.

    The row's `quotes_found` says which of *its* quotes matched, not which of these, and nothing can
    say which one the author deleted. Keeping the verdict published a finding about a quote the
    module no longer makes — clearable only by deleting the sidecar, which is the defect class this
    round fixed for whole citations. Understating is the fallback, never misattributing.
    """
    both = (
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
        f"rs334,{_REAL},this sentence is certainly not in the paper\n"
    )
    spec = _spec(tmp_path / "s", both)
    first = _run(spec)
    assert (first.quotes_checked, first.quotes_found) == (2, 1)
    assert _records(spec)["provenance_quote"].findings == 1

    (spec / "studies.csv").write_text(
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n", encoding="utf-8"
    )
    result = _run(spec)

    assert (result.quotes_authored, result.quotes_checked) == (1, 0)
    assert result.quotes_unexamined == 1 and result.quotes_found == 0
    record = _records(spec)["provenance_quote"]
    assert record.skipped == "no_reference" and "never looked up" in (record.detail or "")


def test_coverage_never_calls_a_pinned_verdict_unretrievable(tmp_path: Path) -> None:
    """The printed sentence reads the tally, not this run's fetch list.

    A no-op re-run retrieves nothing, so a coverage line counting `fulltext_checked` said "0 of 1 …
    1 with nothing retrievable" for an open-access article it had read minutes earlier — one line
    above `quotes: 1/1 found`.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
    )
    first = _run(spec)
    second = _run(spec)

    assert second.coverage == first.coverage
    assert "nothing retrievable" not in second.coverage
    assert (second.quotes_found, second.quotes_checked) == (1, 1)


def test_the_no_doi_note_does_not_contradict_its_own_counts(tmp_path: Path) -> None:
    """`doi_exists` is a persisted verdict, so `--no-doi` does not erase it — and must not deny it.

    `manifest.compilation.warnings` established that a published string is a consumer surface (RM44);
    the same holds of a record's `detail`, and "only PubMed was asked" printed beside "1 cited DOI(s)
    do not resolve in Crossref" is one sentence disagreeing with itself.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/definitely-not-a-real-doi\n"
    )
    _run(spec)
    _run(spec, check_doi=False)

    detail = _records(spec)["citation_existence"].detail or ""
    assert "do not resolve in Crossref" in detail
    assert "only PubMed was asked" not in detail
    assert "comes from the pinned literature.csv" in detail


def test_correcting_a_doi_clears_the_finding_it_caused(tmp_path: Path) -> None:
    """A pinned verdict is about the DOI it was put to, and `doi_checked` is what says which.

    `literature.csv` is the pin and a re-run does not refetch a row it already has, so pairing the
    stored "does not resolve" with whatever the author writes next made the correction *inherit* the
    finding: `--strict` went on refusing, naming the corrected DOI, and the attestation published it.
    Cleared only by deleting the sidecar, which is the class this pass treats as a defect everywhere
    else. The row is still kept — deleting a row is not this pass's call — its verdict simply stops
    being attributed to a DOI it was never about.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.9999/definitely-not-a-real-doi\n"
    )
    first = _run(spec)
    assert first.doi_missing == ["10.9999/definitely-not-a-real-doi"]
    assert first.rows[0].doi_checked == "10.9999/definitely-not-a-real-doi"

    (spec / "studies.csv").write_text(
        f"rsid,pmid,doi\nrs334,{_REAL},10.1093/nar/gkx1153\n", encoding="utf-8"
    )
    result = _run(spec)

    assert result.doi_missing == [] and result.doi_verdicts_stale == 1
    record = _records(spec)["citation_existence"]
    assert record.findings == 0
    assert "no longer cites" in (record.detail or "")
    _run(spec, mode="strict")       # and strict stops refusing, without deleting the sidecar


def test_no_fulltext_does_not_erase_an_answer_the_pin_already_holds(tmp_path: Path) -> None:
    """`--no-fulltext` puts no question, so it must not overwrite one that was answered.

    The same rule the offline branch states for itself. Writing `not_requested` here also made the
    record contradict the run that wrote it: `_tally_quotes` had just read a settled verdict off the
    pin, so "no authored quote was matched against any retrieved text" was false by its own tally.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
    )
    _run(spec)
    before = _records(spec)["provenance_quote"]
    assert (before.subjects, before.findings, before.skipped) == (1, 0, None)

    result = _run(spec, check_fulltext=False)
    after = _records(spec)["provenance_quote"]

    assert result.quotes_checked == 1                    # the pin still answers it
    assert (after.subjects, after.findings, after.skipped) == (1, 0, None)
    assert after.checked_at == before.checked_at


def test_no_fulltext_on_a_module_with_no_answer_still_says_the_caller_declined(tmp_path: Path) -> None:
    """The other half: silence is only right when it protects an answer."""
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
    )
    _run(spec, check_fulltext=False)
    assert _records(spec)["provenance_quote"].skipped == "not_requested"


def test_a_doi_no_run_ever_resolved_is_counted_apart_from_a_stale_one(tmp_path: Path) -> None:
    """Two absences with the same shape and different remedies, and one had no counter at all.

    Run once with `--no-doi` and again without: the rows exist by the second run, so Crossref is
    never asked, and the record would otherwise report a full denominator for a check the vocabulary
    defines over PubMed *and* Crossref with the Crossref half never put for any row.
    """
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{_REAL},10.1093/nar/gkx1153\n")
    _run(spec, check_doi=False)
    result = _run(spec)

    assert result.rows[0].doi_exists is None and result.doi_never_checked == 1
    assert result.doi_verdicts_stale == 0            # nothing stale: nothing was ever answered
    detail = _records(spec)["citation_existence"].detail or ""
    assert "never been resolved in Crossref" in detail


def test_no_fulltext_coverage_does_not_call_an_unfetched_article_unretrievable(tmp_path: Path) -> None:
    """The CLI line and the record are two published sentences from one run, and they must agree.

    `--no-fulltext` leaves every quote unchecked, and the generic wording called that "nothing
    retrievable" — about articles nobody tried to fetch — while the record for the same run said
    `not_requested`.
    """
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
    )
    result = _run(spec, check_fulltext=False)

    assert "nothing retrievable" not in result.coverage
    assert result.coverage == "1 authored quote(s) not matched against anything: --no-fulltext"
    assert _records(spec)["provenance_quote"].skipped == "not_requested"


def test_an_offline_skip_never_asserts_the_sidecar_is_absent(tmp_path: Path) -> None:
    """A `literature.csv` can be present and pin none of the citations the module makes now."""
    spec = _spec(tmp_path / "s", f"rsid,pmid\nrs334,{_REAL}\n")
    _run(spec)
    (spec / "studies.csv").write_text(f"rsid,pmid\nrs334,{_PAYWALLED}\n", encoding="utf-8")

    enrich_literature(spec, offline=True)
    record = _records(spec)["citation_existence"]

    assert (spec / "literature.csv").is_file()
    assert record.skipped == "offline"
    assert "carries no literature.csv" not in (record.detail or "")
    assert "no citation this module makes carries a pinned answer" in (record.detail or "")

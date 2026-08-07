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
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,provenance_quote\nrs334,{_REAL},variant interpretations\n"
        f"rs334,{_PAYWALLED},something\n",
    )
    result = _run(spec)
    assert result.coverage == (
        "checked fulltext for 1 of 2 citation(s) with an authored quote; 1 with nothing retrievable"
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

"""A `pmid=NONE` row's DOI is checked to exist, and its quote matched where the text is reachable (RM349).

RM336 made `pmid=NONE` + `doi` legal and left the literature pass with nothing to look up: a fabricated
DOI and a real one read the same, as an `unsupported` skip. The DOI is the only identifier such a row
carries, so it is the one the pass now asks about: Crossref for existence (and the title it names,
`@existence-not-identity`), Europe PMC for the text, matched as RM257/RM258 match a PMID's.

Every response here is **recorded from the live services** on 2026-11-04, never hand-written:

* `crossref_works_payload.json` gained `10.1101/2025.11.27.690701`, a CC BY bioRxiv preprint;
* `europepmc_doi_search_payload.json` is Europe PMC's `search` for three DOIs — that preprint (record
  `PPR1129025`, with a `fullTextIdList`), the older preprint the suite already uses (`PPR1146237`,
  abstract only, no full text) and the fabricated DOI (no record);
* `europepmc_preprint_repo_metadata_PPR1129025.json` and `europepmc_preprint_PPR1129025.nxml` are the
  two `fulltextRepo` answers that carry the preprint's JATS, the nxml trimmed to its front matter and
  first two body paragraphs. The documented `/{id}/fullTextXML` answers 500 for every `PPR` id probed
  (four of four, with and without full text), so it is not the route.
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.literature import (
    CrossrefClient,
    EuropePmcClient,
    FulltextUnavailable,
    LiteratureEnrichmentError,
    LiteratureUnavailable,
    enrich_literature,
)
from just_dna_enricher.lookup import LookupClients, lookup_citation
from just_dna_enricher.net import PacingGate
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.spec import PMID_NONE
from just_dna_format.verification import read_verification

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_CROSSREF = json.loads((_ASSETS / "crossref_works_payload.json").read_text())
_EPMC_SEARCH = json.loads((_ASSETS / "europepmc_search_payload.json").read_text())
_DOI_SEARCH = json.loads((_ASSETS / "europepmc_doi_search_payload.json").read_text())
_REPO_METADATA = json.loads((_ASSETS / "europepmc_preprint_repo_metadata_PPR1129025.json").read_text())
_PREPRINT_NXML = (_ASSETS / "europepmc_preprint_PPR1129025.nxml").read_text()
_FULLTEXT_XML = (_ASSETS / "europepmc_fulltext_PMC5753237.xml").read_text()

_PREPRINT = "10.1101/2025.11.27.690701"  # bioRxiv, CC BY, full text in Europe PMC
_ABSTRACT_ONLY = "10.1101/2024.06.17.599351"  # bioRxiv, Europe PMC holds the abstract and no text
_FABRICATED = "10.9999/definitely-not-a-real-doi"
_REAL_PMID = "29165669"

# A sentence of the preprint's introduction, which its abstract does not carry: found only in the body.
_BODY_QUOTE = "single-molecule experiments typically study one sequence at a time"
_NOT_IN_TEXT = "APOE e4 carriers show a threefold risk of late-onset disease"

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


def _gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _crossref(*, down: bool = False) -> CrossrefClient:
    """Crossref off the recording; `down` raises on every request, the transport failing outright."""

    def handler(request: httpx.Request) -> httpx.Response:
        client.requested.append(str(request.url))
        if down:
            raise httpx.ConnectError("no route to host")
        tail = str(request.url).split("/works/", 1)[1]
        if tail.endswith("/agency"):
            record = _CROSSREF.get(tail.removesuffix("/agency"))
            if record is None or record["status"] == 404:
                return httpx.Response(404, text="Resource not found.")
            agency = {"id": "crossref", "label": "Crossref"}
            return httpx.Response(200, json={"message": {"DOI": tail, "agency": agency}})
        record = _CROSSREF.get(tail)
        if record is None or record["status"] == 404:
            return httpx.Response(404)
        return httpx.Response(200, json={"message": record["message"]})

    client = CrossrefClient(contact_email=None)
    client.requested = []  # type: ignore[attr-defined]
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = _gate()
    return client


def _epmc(*, repo_status: int = 200) -> EuropePmcClient:
    """Europe PMC off the recordings: `search` by DOI or by PMID, and the preprint repository.

    `requested` records every URL, so a test can assert the repository was or was not reached.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        client.requested.append(str(request.url))
        if request.url.host == "europepmc.org":
            if repo_status != 200:
                return httpx.Response(repo_status, json={"error": "Impossible to retrieve metadata"})
            if request.url.params.get("type") == "METADATA":
                return httpx.Response(200, json=_REPO_METADATA)
            return httpx.Response(200, text=_PREPRINT_NXML)
        if request.url.path.endswith("/fullTextXML"):
            return httpx.Response(200, text=_FULLTEXT_XML)
        query = request.url.params.get("query", "")
        if query.startswith('DOI:"'):
            return httpx.Response(200, json=_DOI_SEARCH[query.removeprefix('DOI:"').removesuffix('"')])
        return httpx.Response(200, json=_EPMC_SEARCH)

    client = EuropePmcClient()
    client.requested = []  # type: ignore[attr-defined]
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = _gate()
    return client


class _NeverAsked:
    """A client the pass must not touch."""

    def __getattr__(self, name: str):
        raise AssertionError(f"the pass asked a registry ({name}) it had no question for")


def _spec(d: Path, studies: str) -> Path:
    d.mkdir(parents=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n", encoding="utf-8")
    (d / "studies.csv").write_text(studies, encoding="utf-8")
    return d


def _records(spec: Path) -> dict:
    return {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}


def _run(
    spec: Path, *, crossref: CrossrefClient | None = None, europepmc: EuropePmcClient | None = None, **kw
):
    """A run whose every citation is DOI-only: PubMed and BioC have no question, so they are never asked."""
    never = _NeverAsked()
    return enrich_literature(
        spec,
        eutils=never,
        bioc=never,
        crossref=crossref or _crossref(),
        europepmc=europepmc or _epmc(),
        **kw,
    )


# ── existence, and the title that says which work it is ─────────────────────────────────────────


def test_an_existing_preprint_doi_is_checked_and_names_its_title(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{PMID_NONE},{_PREPRINT}\n")
    result = _run(spec)
    title = _CROSSREF[_PREPRINT]["message"]["title"][0]
    [checked] = result.doi_citations
    assert (checked.doi, checked.exists, checked.title) == (_PREPRINT, True, title)
    assert result.doi_missing == []
    record = _records(spec)["citation_existence"]
    assert (record.skipped, record.subjects, record.findings, record.source) == (None, 1, 0, "crossref")
    # `@existence-not-identity`: the record names the work Crossref found, not only that it found one.
    assert title in (record.detail or "")


def test_a_fabricated_doi_is_a_finding_naming_it(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,doi\nrs334,{PMID_NONE},{_PREPRINT}\nrs334,{PMID_NONE},{_FABRICATED}\n",
    )
    result = _run(spec)
    assert result.doi_missing == [_FABRICATED]
    record = _records(spec)["citation_existence"]
    assert (record.subjects, record.findings) == (2, 1)
    assert "1 cited DOI(s) do not resolve in Crossref" in (record.detail or "")


def test_strict_refuses_a_fabricated_doi(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{PMID_NONE},{_FABRICATED}\n")
    with pytest.raises(LiteratureEnrichmentError, match=_FABRICATED.replace(".", r"\.")):
        _run(spec, mode="strict")


def test_an_unreachable_crossref_is_unreachable_never_absent(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{PMID_NONE},{_PREPRINT}\n")
    result = _run(spec, crossref=_crossref(down=True))
    [checked] = result.doi_citations
    assert checked.exists is None
    assert result.doi_missing == []
    record = _records(spec)["citation_existence"]
    assert record.skipped == "unreachable"
    assert "Crossref did not answer" in (record.detail or "")


def test_no_doi_puts_no_question_to_crossref(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,doi\nrs334,{PMID_NONE},{_PREPRINT}\n")
    crossref = _crossref()
    _run(spec, crossref=crossref, check_doi=False)
    assert crossref.requested == []  # type: ignore[attr-defined]
    assert _records(spec)["citation_existence"].skipped == "not_requested"


def test_a_doi_another_agency_registered_is_not_reported_as_absent() -> None:
    """Crossref's `/works` answers 404 for a DataCite DOI (a Zenodo dataset), which is what a
    `pmid=NONE` row often cites. Its `/agency` route says who registered it, so a real dataset DOI is
    never a finding; a DOI no agency knows is."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/agency"):
            if "zenodo.3360392" in url:
                return httpx.Response(
                    200, json={"message": {"agency": {"id": "datacite", "label": "DataCite"}}}
                )
            return httpx.Response(404, text="Resource not found.")
        return httpx.Response(404)

    client = CrossrefClient(contact_email=None)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = _gate()
    dataset = client.work("10.5281/zenodo.3360392")
    assert (dataset.exists, dataset.agency, dataset.title) == (True, "datacite", None)
    assert client.work(_FABRICATED).exists is False


def _failing(leg: str):
    """A handler failing one way: a 5xx, a transport error, or a 200 whose body is not the record."""

    def handler(request: httpx.Request) -> httpx.Response:
        if leg == "transport":
            raise httpx.ConnectError("no route to host")
        if leg == "5xx":
            return httpx.Response(503)
        return httpx.Response(200, text="<html>maintenance</html>")

    return handler


@pytest.mark.parametrize("leg", ["5xx", "transport", "html"])
def test_the_agency_leg_withholds_on_every_failure(leg: str) -> None:
    """After a `/works` 404, an agency lookup that never answered is not an absent DOI."""
    fail = _failing(leg)

    def handler(request: httpx.Request) -> httpx.Response:
        return fail(request) if str(request.url).endswith("/agency") else httpx.Response(404)

    client = CrossrefClient(contact_email=None)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = _gate()
    assert client.work(_PREPRINT).exists is None


@pytest.mark.parametrize("leg", ["5xx", "transport", "html"])
def test_the_doi_search_translates_every_failure(leg: str) -> None:
    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(_failing(leg)))
    with pytest.raises(LiteratureUnavailable):
        client.record_for_doi(_PREPRINT)


@pytest.mark.parametrize("leg", ["5xx", "transport", "html"])
def test_the_preprint_repository_raises_unreachable_on_every_unanswered_leg(leg: str) -> None:
    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(_failing(leg)))
    with pytest.raises(FulltextUnavailable):
        client.fetch_preprint_fulltext("PPR1129025")


def test_a_4xx_from_the_preprint_repository_is_absent() -> None:
    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    assert client.fetch_preprint_fulltext("PPR1129025") is None


def test_a_hint_names_the_agency_rather_than_a_crossref_record_it_does_not_have() -> None:
    """`hint citation --doi` on a DataCite DOI: it exists, and the finding says who registered it."""

    def crossref_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/agency"):
            return httpx.Response(200, json={"message": {"agency": {"id": "datacite", "label": "DataCite"}}})
        return httpx.Response(404)

    crossref = CrossrefClient(contact_email=None)
    crossref._client = httpx.Client(transport=httpx.MockTransport(crossref_handler))
    crossref.gate = _gate()
    europepmc = EuropePmcClient(gate=_gate())
    europepmc._client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"resultList": {"result": []}})
        )
    )
    hint = lookup_citation(
        doi="10.5281/zenodo.3360392", clients=LookupClients(crossref=crossref, europepmc=europepmc)
    )
    assert hint.doi_exists is True
    messages = [f.message for f in hint.findings if f.column == "doi"]
    assert any("registered with datacite, not Crossref" in m for m in messages)
    assert not any("Crossref has a record" in m for m in messages)


def test_a_jats_answer_that_does_not_parse_is_unreachable_not_absent() -> None:
    """The file list answered and the JATS leg came back as a maintenance page: withheld."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("type") == "METADATA":
            return httpx.Response(200, json=_REPO_METADATA)
        return httpx.Response(200, text="<html>maintenance")

    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FulltextUnavailable):
        client.fetch_preprint_fulltext("PPR1129025")


def test_the_record_with_a_route_to_the_text_wins_over_an_earlier_one_without() -> None:
    """One DOI, two records: a text-less one first must not make the answer `absent`."""
    preprint = _DOI_SEARCH[_PREPRINT]["resultList"]["result"][0]
    textless = {**preprint, "id": "AGR0000001", "source": "AGR", "fullTextIdList": None}
    payload = {"hitCount": 2, "resultList": {"result": [textless, preprint]}}
    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    record = client.record_for_doi(_PREPRINT)
    assert record is not None and record["preprint_id"] == preprint["id"]


# ── the quote, against the preprint's own text ──────────────────────────────────────────────────


def test_a_quote_in_the_preprint_body_is_found(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
    )
    result = _run(spec)
    [checked] = result.doi_citations
    assert (checked.quotes_authored, checked.quotes_found) == (1, 1)
    assert (checked.quote_source, checked.fulltext_status) == ("fulltext", "retrieved")
    record = _records(spec)["provenance_quote"]
    assert (record.skipped, record.subjects, record.findings) == (None, 1, 0)
    # The coverage sentence the run logs says the same, rather than "no provenance quotes authored".
    assert result.coverage.startswith("checked 1 of 1 quote(s) on pmid NONE")


def test_a_quote_the_preprint_does_not_carry_is_a_finding(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_NOT_IN_TEXT}\n"
    )
    result = _run(spec)
    [checked] = result.doi_citations
    assert (checked.quotes_found, checked.fulltext_status) == (0, "retrieved")
    record = _records(spec)["provenance_quote"]
    assert (record.skipped, record.subjects, record.findings) == (None, 1, 1)


def test_a_preprint_with_no_text_asks_no_repository_and_falls_back_to_the_abstract(tmp_path: Path) -> None:
    """`PPR1146237` carries no `fullTextIdList`, so the repository is not asked (its "no copy" answer
    is a 500, which would read as an outage); the abstract is searched, where a hit settles a quote."""
    abstract = _DOI_SEARCH[_ABSTRACT_ONLY]["resultList"]["result"][0]["abstractText"]
    hit = " ".join(abstract.split()[:12])
    spec = _spec(
        tmp_path / "s",
        "rsid,pmid,doi,provenance_quote\n"
        f"rs334,{PMID_NONE},{_ABSTRACT_ONLY},{hit}\n"
        f"rs334,{PMID_NONE},{_ABSTRACT_ONLY},{_NOT_IN_TEXT}\n",
    )
    europepmc = _epmc()
    result = _run(spec, europepmc=europepmc)
    assert not [u for u in europepmc.requested if "fulltextRepo" in u]  # type: ignore[attr-defined]
    [checked] = result.doi_citations
    assert (checked.fulltext_status, checked.quote_source, checked.quotes_found) == ("absent", "abstract", 1)
    record = _records(spec)["provenance_quote"]
    # The hit settles; the miss does not, since the body was never searched.
    assert (record.subjects, record.findings) == (1, 0)
    assert "1 further authored quote(s)" in (record.detail or "")


def test_an_unanswered_repository_is_unreachable_not_absent(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
    )
    result = _run(spec, europepmc=_epmc(repo_status=503))
    [checked] = result.doi_citations
    # The body was unreachable, so the abstract was searched; it does not carry this quote, so no verdict.
    assert (checked.fulltext_status, checked.quote_source, checked.quotes_found) == (
        "unreachable",
        "abstract",
        0,
    )
    record = _records(spec)["provenance_quote"]
    assert record.skipped == "no_reference"
    assert "unreachable" in (record.detail or "")


def test_a_doi_europe_pmc_holds_no_record_of_is_absent(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_FABRICATED},{_BODY_QUOTE}\n"
    )
    result = _run(spec)
    [checked] = result.doi_citations
    assert (checked.exists, checked.fulltext_status, checked.quotes_found) == (False, "absent", None)
    assert _records(spec)["provenance_quote"].skipped == "no_reference"


def test_no_fulltext_puts_no_question_to_europe_pmc(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
    )
    result = _run(spec, europepmc=_NeverAsked(), check_fulltext=False)  # type: ignore[arg-type]
    assert result.doi_citations[0].fulltext_status is None
    assert _records(spec)["provenance_quote"].skipped == "not_requested"


def test_one_preprint_cited_twice_in_two_spellings_is_asked_once(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s",
        "rsid,pmid,doi,provenance_quote\n"
        f"rs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
        f"rs334,{PMID_NONE},https://doi.org/{_PREPRINT.upper()},{_NOT_IN_TEXT}\n",
    )
    crossref = _crossref()
    result = _run(spec, crossref=crossref)
    assert [c.doi for c in result.doi_citations] == [_PREPRINT]
    assert len(crossref.requested) == 1  # type: ignore[attr-defined]
    assert (result.doi_citations[0].quotes_authored, result.doi_citations[0].quotes_found) == (2, 1)


# ── beside a PMID citation, and offline ─────────────────────────────────────────────────────────


def test_a_preprint_beside_a_pmid_adds_to_both_denominators(tmp_path: Path) -> None:
    esummary = json.loads((_ASSETS / "pubmed_esummary_payload.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=esummary)

    eutils = EutilsClient(settings=EutilsSettings(email=None))
    eutils._client = httpx.Client(transport=httpx.MockTransport(handler))
    eutils.gate = _gate()
    spec = _spec(
        tmp_path / "s",
        "rsid,pmid,doi,provenance_quote\n"
        f"rs334,{_REAL_PMID},,{_NOT_IN_TEXT}\n"
        f"rs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n",
    )
    result = enrich_literature(
        spec, eutils=eutils, europepmc=_epmc(), crossref=_crossref(), bioc=_NeverAsked()
    )
    records = _records(spec)
    existence = records["citation_existence"]
    assert (existence.subjects, existence.findings) == (
        result.existence_checked + 1,
        result.unresolved_citations,
    )
    quote = records["provenance_quote"]
    assert quote.subjects == result.quotes_checked + 1
    assert quote.findings == (result.quotes_checked - result.quotes_found) + 0


def test_offline_asks_nothing_and_says_offline(tmp_path: Path) -> None:
    """Nothing is asked offline (`@unreachable-not-absent`): no verdict, and the reason is egress now
    that a route exists — never `unsupported`, which would say the tier cannot ask."""
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
    )
    never = _NeverAsked()
    result = enrich_literature(spec, offline=True, eutils=never, europepmc=never, crossref=never, bioc=never)
    assert result.doi_citations == []
    records = _records(spec)
    assert records["citation_existence"].skipped == "offline"
    assert records["provenance_quote"].skipped == "offline"
    assert "whose pmid is NONE" in (records["provenance_quote"].detail or "")


# ── live (opt-in) ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_live_a_biorxiv_preprint_is_checked_and_its_quote_found(tmp_path: Path) -> None:
    """The recordings above against the live services, including the undocumented `fulltextRepo`
    route, which is the one most likely to drift."""
    with CrossrefClient() as crossref:
        work = crossref.work(_PREPRINT)
        assert (work.exists, work.title) == (True, _CROSSREF[_PREPRINT]["message"]["title"][0])
        assert crossref.work(_FABRICATED).exists is False
    with EuropePmcClient() as europepmc:
        record = europepmc.record_for_doi(_PREPRINT)
        assert record is not None and record["preprint_id"] == "PPR1129025"
        text = europepmc.fetch_preprint_fulltext("PPR1129025")
        assert text is not None and _BODY_QUOTE in text
        assert europepmc.record_for_doi(_FABRICATED) is None
    spec = _spec(
        tmp_path / "s", f"rsid,pmid,doi,provenance_quote\nrs334,{PMID_NONE},{_PREPRINT},{_BODY_QUOTE}\n"
    )
    result = enrich_literature(spec, eutils=_NeverAsked(), bioc=_NeverAsked())
    [checked] = result.doi_citations
    assert (checked.exists, checked.fulltext_status, checked.quotes_found) == (True, "retrieved", 1)

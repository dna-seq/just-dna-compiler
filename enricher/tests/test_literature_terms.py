"""Per-article licences, the second citation site, and PMCID → PMID (RM46 + RM47 + RM50).

Both payloads here are **recorded from the live services**, not hand-written.
`europepmc_licensed_payload.json` was recorded on 2026-08-13 and carries the two facts the licence
half rests on, neither of which a fabricated fixture would have produced:

* PMID 41585745 is `cc by-nc` — a real non-commercial article with a PubMed id, which is what the
  quoting notice is about; and
* PMID 28546431 comes back `isOpenAccess: N` **with** `license: cc by`. The licence is therefore
  independent of the open-access flag and must not be derived from it: one describes Europe PMC's OA
  subset, the other describes the article.

The already-recorded `europepmc_search_payload.json` carries the complementary case — three records
that state no licence at all — which is what the withhold path is tested against.
"""

import json
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.licensing import ARTICLE_TERMS_BY_LICENSE, ArticleTerms, article_terms
from just_dna_enricher.literature import (
    EuropePmcClient,
    LiteratureEnrichmentError,
    PmcIdConverterClient,
    _pmcid_conflicts,
    enrich_literature,
)
from just_dna_enricher.lookup import LookupClients, lookup_citation
from just_dna_enricher.net import PacingGate
from just_dna_format.literature import LiteratureRow
from just_dna_format.spec import StudyRow

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_ESUMMARY = json.loads((_ASSETS / "pubmed_esummary_payload.json").read_text())
_EPMC_SEARCH = json.loads((_ASSETS / "europepmc_search_payload.json").read_text())
_EPMC_LICENSED = json.loads((_ASSETS / "europepmc_licensed_payload.json").read_text())

_REAL = "29165669"        # in the esummary + unlicensed epmc recordings
#: The two licensed records, read out of the recording rather than pasted in.
_LICENSED = {r["pmid"]: r for r in _EPMC_LICENSED["resultList"]["result"]}
_NC_PMID = "41585745"
_CC_BY_PMID = "28546431"

#: The real converter pair, probed 2026-08-13: PMC3110566 is PMID 21551363. They share no digits.
_PMC = "PMC3110566"
_PMC_PMID = "21551363"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    "genome_build: GRCh38\n"
)


@pytest.fixture(autouse=True)
def _no_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests must not depend on a configured NCBI key, and `.env` leaks into `os.environ` from
    any earlier test that resolved a cache path. `setenv(VAR, "")`, never `delenv`: `load_dotenv`
    skips a key that is merely present, and every reader treats empty as absent."""
    monkeypatch.setenv("NCBI_API_KEY", "")
    monkeypatch.setenv("JUST_DNA_CONTACT_EMAIL", "")


# ── doubles ─────────────────────────────────────────────────────────────────────────────────────


def _eutils(payload: dict | None = None) -> EutilsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload or _ESUMMARY)

    client = EutilsClient(settings=EutilsSettings(email=None))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _epmc(payload: dict) -> EuropePmcClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fullTextXML"):
            return httpx.Response(404)
        return httpx.Response(200, json=payload)

    client = EuropePmcClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _idconv(records: list[dict]) -> PmcIdConverterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "records": records})

    client = PmcIdConverterClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _spec(d: Path, *, studies: str | None = None, bins: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    if studies is not None:
        (d / "variants.csv").write_text(
            "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n", encoding="utf-8"
        )
        (d / "studies.csv").write_text(studies, encoding="utf-8")
    if bins is not None:
        (d / "repeat_alleles.csv").write_text(bins, encoding="utf-8")
    return d


# ── RM46: the licence is per article ────────────────────────────────────────────────────────────


def test_the_licence_map_is_total_over_the_spellings_europe_pmc_publishes() -> None:
    """Probed over 100 open-access records on 2026-08-13: the values are lowercase CC spellings."""
    recorded = {r["license"] for r in _LICENSED.values() if r.get("license")}
    assert recorded, "the recording must carry licences for this test to mean anything"
    assert recorded <= set(ARTICLE_TERMS_BY_LICENSE)


def test_an_unknown_licence_withholds_every_axis() -> None:
    """`None` is never `False`: a licence this tier has not read is undetermined, not permissive and
    not forbidding. Nothing is inferred from a substring."""
    for value in ("bronze", "publisher-specific", "", None, "cc by-nc-nd-sa-xx"):
        assert article_terms(value) == ArticleTerms()


def test_the_three_rights_are_orthogonal() -> None:
    """CC BY-NC forbids sale and expressly allows sharing — which is why `redistribution` is its own
    axis rather than a reading of `commercial_use`."""
    nc = article_terms("cc by-nc")
    assert (nc.commercial_use, nc.redistribution, nc.share_alike) == (False, True, False)
    sa = article_terms("cc by-nc-sa")
    assert (sa.commercial_use, sa.redistribution, sa.share_alike) == (False, True, True)


def test_the_pass_records_the_article_licence_and_its_rights(tmp_path: Path) -> None:
    """Read out of the recording at runtime, so a refreshed payload cannot leave a stale assertion."""
    spec = _spec(tmp_path / "s", studies=f"rsid,pmid\nrs334,{_NC_PMID}\nrs334,{_CC_BY_PMID}\n")
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_LICENSED), check_doi=False
    )
    rows = {r.pmid: r for r in result.rows}
    for pmid, record in _LICENSED.items():
        assert rows[pmid].license == record["license"]
        expected = article_terms(record["license"])
        assert rows[pmid].commercial_use is expected.commercial_use
        assert rows[pmid].share_alike is expected.share_alike
        assert rows[pmid].redistribution is expected.redistribution
    assert rows[_NC_PMID].commercial_use is False


def test_the_licence_is_not_derived_from_the_open_access_flag(tmp_path: Path) -> None:
    """PMID 28546431 is `isOpenAccess: N` with `license: cc by` — the two answer different questions,
    and collapsing them would mislabel every such article."""
    record = _LICENSED[_CC_BY_PMID]
    assert record["isOpenAccess"] == "N" and record["license"] == "cc by", "the recorded case"

    spec = _spec(tmp_path / "s", studies=f"rsid,pmid\nrs334,{_CC_BY_PMID}\n")
    row = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_LICENSED), check_doi=False
    ).rows[0]
    assert row.is_open_access is False
    assert row.license == "cc by"
    assert row.commercial_use is True


def test_a_record_stating_no_licence_leaves_every_axis_null(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", studies=f"rsid,pmid\nrs334,{_REAL}\n")
    row = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_SEARCH), check_doi=False
    ).rows[0]
    assert row.license is None
    assert (row.commercial_use, row.share_alike, row.redistribution) == (None, None, None)


def test_the_written_columns_are_derived_from_the_model(tmp_path: Path) -> None:
    """A hand-kept column list loses a column — `SOURCES_FIELDNAMES` lost `redistribution` exactly
    this way, and this file would have lost the same one."""
    spec = _spec(tmp_path / "s", studies=f"rsid,pmid\nrs334,{_NC_PMID}\n")
    enrich_literature(spec, eutils=_eutils(), europepmc=_epmc(_EPMC_LICENSED), check_doi=False)
    header = (spec / "literature.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == list(LiteratureRow.model_fields)
    # And the file it just wrote reloads through the model it was written from.
    reloaded = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_LICENSED), check_doi=False
    )
    assert reloaded.rows[0].license == _LICENSED[_NC_PMID]["license"]


# ── RM47: a bin pointer is a citation site the pass must read ───────────────────────────────────


def test_a_module_whose_only_citations_are_bin_pointers_is_enriched(tmp_path: Path) -> None:
    """Reading only `studies.csv` would leave every threshold-grounding citation unchecked."""
    spec = _spec(
        tmp_path / "s",
        bins=(
            "gene,repeat_unit,measure_kind,measure_min,measure_max,conclusion,unresolved,pmid\n"
            f"HTT,CAG,repeat_count,40,,fully penetrant,false,{_REAL}\n"
            "HTT,CAG,repeat_count,,,not measured,true,\n"
        ),
    )
    assert not (spec / "studies.csv").exists()
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_SEARCH), check_doi=False
    )
    assert [r.pmid for r in result.rows] == [_REAL]
    assert result.rows[0].exists is True


def test_a_module_citing_nothing_at_all_still_refuses(tmp_path: Path) -> None:
    """The relaxation is about *where* a citation may live, not about whether one is needed."""
    spec = _spec(
        tmp_path / "s",
        bins=(
            "gene,repeat_unit,measure_kind,measure_min,measure_max,conclusion,unresolved\n"
            "HTT,CAG,repeat_count,40,,fully penetrant,false\n"
        ),
    )
    with pytest.raises(LiteratureEnrichmentError, match="neither studies.csv rows nor"):
        enrich_literature(spec, eutils=_eutils(), europepmc=_epmc(_EPMC_SEARCH))


def test_a_bin_only_citation_asks_no_quote_question(tmp_path: Path) -> None:
    """A binning row has no `provenance_quote` column, so it contributes a citation with nothing to
    check — which must read as *nothing to check*, never as an unretrievable fulltext."""
    spec = _spec(
        tmp_path / "s",
        bins=(
            "gene,repeat_unit,measure_kind,measure_min,measure_max,conclusion,unresolved,pmid\n"
            f"HTT,CAG,repeat_count,40,,fully penetrant,false,{_REAL}\n"
        ),
    )
    result = enrich_literature(
        spec, eutils=_eutils(), europepmc=_epmc(_EPMC_SEARCH), check_doi=False
    )
    assert result.rows[0].quotes_authored == 0
    assert result.rows[0].quotes_found is None
    assert "nothing to check against fulltext" in result.coverage


# ── RM50: the PMC id, both directions ───────────────────────────────────────────────────────────


def test_an_authored_pmc_id_that_contradicts_pubmeds_is_reported() -> None:
    """The case the schema guard cannot see: the cell carries a real PubMed id, so nothing refuses
    it, while the two halves name different articles."""
    studies = [StudyRow(rsid="rs334", pmid=f"{_PMC_PMID} ({_PMC})")]
    assert _pmcid_conflicts(_PMC_PMID, studies, _PMC) == []

    conflicts = _pmcid_conflicts(_PMC_PMID, studies, "PMC9999999")
    assert len(conflicts) == 1
    assert conflicts[0].authored == _PMC and conflicts[0].registry == "PMC9999999"


def test_nothing_is_claimed_when_pubmed_reports_no_pmc_id() -> None:
    """A paywalled article legitimately has none, and "the registry did not say" is not a
    contradiction."""
    studies = [StudyRow(rsid="rs334", pmid=f"{_PMC_PMID} ({_PMC})")]
    assert _pmcid_conflicts(_PMC_PMID, studies, None) == []


def test_the_converter_reports_the_pmid_and_never_fills_it() -> None:
    """Filling `pmid` from NCBI would make the existence check compare NCBI with itself — the
    `REDUNDANCY_BEARING` rule already argued for `doi`."""
    clients = LookupClients(
        pmc_idconv=_idconv([{"pmcid": _PMC, "requested-id": _PMC, "pmid": int(_PMC_PMID)}]),
        eutils=_eutils(),
        europepmc=_epmc(_EPMC_SEARCH),
    )
    hint = lookup_citation(pmcid=_PMC, clients=clients)
    advisories = [a for a in hint.alterations if a.column == "pmid"]
    assert len(advisories) == 1
    assert advisories[0].after == _PMC_PMID
    assert advisories[0].applied is False
    assert advisories[0].refusal == "redundancy_bearing"


def test_the_four_converter_outcomes_are_spelled_four_different_ways() -> None:
    """Resolved, in-PMC-with-no-pmid, not-in-PMC, and never-answered. Collapsing the last two would
    render a failed request as a definite negative, which is S20 one service over."""
    absent = _idconv(
        [{"pmcid": _PMC, "requested-id": _PMC, "status": "error",
          "errmsg": "Identifier not found in PMC"}]
    )
    hint = lookup_citation(pmcid=_PMC, clients=LookupClients(pmc_idconv=absent))
    assert any(f.level == "warning" and "PMC has no record of" in f.message for f in hint.findings)
    assert not hint.alterations

    no_pmid = _idconv([{"pmcid": _PMC, "requested-id": _PMC}])
    hint = lookup_citation(pmcid=_PMC, clients=LookupClients(pmc_idconv=no_pmid))
    assert any("carries no PubMed id" in f.message for f in hint.findings)
    assert not hint.alterations

    silent = _idconv([])
    hint = lookup_citation(pmcid=_PMC, clients=LookupClients(pmc_idconv=silent))
    assert any(f.level == "info" and "did not answer" in f.message for f in hint.findings)
    assert not any("no record of" in f.message for f in hint.findings)
    assert not hint.alterations


def test_a_pmcid_and_a_pmid_that_disagree_are_compared_not_merged() -> None:
    """A caller supplying both has two identifiers in mind; silently replacing one hides the finding."""
    clients = LookupClients(
        pmc_idconv=_idconv([{"pmcid": _PMC, "requested-id": _PMC, "pmid": int(_PMC_PMID)}]),
    )
    hint = lookup_citation(pmid="9545397", pmcid=_PMC, clients=clients)
    assert any("name different articles" in f.message for f in hint.findings)
    assert not [a for a in hint.alterations if a.column == "pmid"]


def test_the_converter_batches_and_answers_by_requested_id() -> None:
    """`resolve` is keyed on what was asked, so a caller can tell an unanswered id from a resolved
    one — probed shape: `pmid` arrives as a JSON number and absences carry `status: error`."""
    client = _idconv(
        [
            {"pmcid": _PMC, "requested-id": _PMC, "pmid": int(_PMC_PMID)},
            {"pmcid": "PMC9999999999", "requested-id": "PMC9999999999", "status": "error",
             "errmsg": "Identifier not found in PMC"},
        ]
    )
    resolved = client.resolve([_PMC, "PMC9999999999", _PMC])
    assert set(resolved) == {_PMC, "PMC9999999999"}
    assert resolved[_PMC].pmid == _PMC_PMID and resolved[_PMC].in_pmc is True
    assert resolved["PMC9999999999"].in_pmc is False
    assert resolved["PMC9999999999"].pmid is None
    assert resolved["PMC9999999999"].error == "Identifier not found in PMC"

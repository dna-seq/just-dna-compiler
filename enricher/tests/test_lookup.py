"""Authoring lookups — questions about a value, answered without writing one (0.5).

Offline by default. What is pinned: nothing reaches the filesystem, every answer that a later check
cross-examines comes back `applied=False` with a reason, and a check that could not run reports
`unchecked` rather than `absent` (`None` is not `False`).
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.hints import REDUNDANCY_BEARING
from just_dna_enricher.eutils import NO_SUMMARY
from just_dna_enricher.lookup import (
    LookupClients,
    as_report_rows,
    lookup_citation,
    lookup_variant,
)


class _FakeEutils:
    """An `EutilsClient` stand-in. Records what it was asked, so client reuse can be asserted."""

    def __init__(self, records: dict) -> None:
        self.records = records
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def esummary(self, db: str, ids: list[str]) -> dict:
        self.calls.append((db, tuple(ids)))
        return {uid: self.records[uid] for uid in ids if uid in self.records}

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass


class _FakeEuropePmc:
    def __init__(self, records: dict | None = None) -> None:
        self.records = records or {}

    def lookup(self, pmids: list[str]) -> dict:
        return {p: self.records[p] for p in pmids if p in self.records}

    def close(self) -> None:  # pragma: no cover
        pass


class _FakeCrossref:
    def __init__(self, answer: bool | None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def exists(self, doi: str) -> bool | None:
        self.asked.append(doi)
        return self.answer

    def close(self) -> None:  # pragma: no cover
        pass


def test_offline_says_unchecked_rather_than_absent(tmp_path: Path) -> None:
    """A check that could not run is not a check that failed."""
    hint = lookup_variant(rsid="rs1801133", offline=True, ensembl_cache=tmp_path,
                          clinvar_cache=tmp_path)
    assert hint.rsid_status is None  # not "absent"
    assert any("offline" in f.message for f in hint.findings)


def test_a_lookup_writes_nothing(tmp_path: Path) -> None:
    """The primary MUST-NOT, asserted by bytes."""
    (tmp_path / "sentinel.txt").write_text("untouched")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    lookup_variant(rsid="rs1801133", offline=True, ensembl_cache=tmp_path, clinvar_cache=tmp_path)
    lookup_citation(pmid="12345678", offline=True)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_a_missing_snapshot_is_reported_not_raised(tmp_path: Path) -> None:
    hint = lookup_variant(rsid="rs1801133", offline=True, ensembl_cache=tmp_path,
                          clinvar_cache=tmp_path)
    assert hint.loci == []
    assert isinstance(hint.rsid_candidates, list)


class _FakeEnsembl:
    """An `EnsemblResolver` stand-in. `resolve_rsid` returns the same `(loci, source)` shape."""

    def __init__(
        self, loci: list[dict], source: str = "ensembl-rest", *, unreachable: bool = False
    ) -> None:
        self.loci = loci
        self.source = source
        self.unreachable = unreachable
        self.asked: list[str] = []

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        self.asked.append(rsid)
        if self.unreachable:
            return None, None          # could not ask — distinct from the empty answer below (S20)
        return list(self.loci), self.source

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass


_H63D = {"chrom": "6", "start": 26090951, "ref": "C", "alts": "G,T"}


def test_a_cache_miss_falls_through_to_live_ensembl(tmp_path: Path) -> None:
    """Found by dogfooding: `hint` searched only the local snapshot and then said "not found in
    Ensembl". rs1799945 (HFE H63D) is served by Ensembl at 6:26090951 and was absent from the
    snapshot, so an advisory tool answered "no locus" where the pass it advises on answers a
    coordinate."""
    ensembl = _FakeEnsembl([_H63D])
    hint = lookup_variant(
        rsid="rs1799945", ensembl_cache=tmp_path, clinvar_cache=tmp_path,
        clients=LookupClients(ensembl=ensembl, eutils=_FakeEutils({})),
    )
    assert ensembl.asked == ["rs1799945"]
    assert hint.loci == [_H63D]


def test_the_live_locus_is_labelled_live_and_not_as_a_snapshot(tmp_path: Path) -> None:
    """The provenance field is what an author reads to judge reproducibility, and it was hard-coded
    to `snapshot` — so a network answer claimed to come from a pinned file."""
    hint = lookup_variant(
        rsid="rs1799945", ensembl_cache=tmp_path, clinvar_cache=tmp_path,
        clients=LookupClients(ensembl=_FakeEnsembl([_H63D]), eutils=_FakeEutils({})),
    )
    offered = {row["column"]: row for row in as_report_rows(hint)}
    assert {"chrom", "start", "ref", "alts"} <= set(offered)
    assert {row["source"] for row in offered.values()} == {"ensembl-rest"}
    # Still advisory: a live answer is not a licence to fill a redundancy-bearing cell.
    assert all(row["applied"] is False for row in offered.values())


def test_a_snapshot_hit_does_not_reach_the_network(tmp_path: Path) -> None:
    """Cache first, live only for a miss — `enrich()`'s order, so a provisioned snapshot costs
    nothing and the two surfaces cannot disagree about where an answer came from."""
    ensembl = _FakeEnsembl([_H63D])
    hint = lookup_variant(
        rsid="rs1799945", offline=True, ensembl_cache=tmp_path, clinvar_cache=tmp_path,
        clients=LookupClients(ensembl=ensembl),
    )
    assert ensembl.asked == [] and hint.loci == []


def test_live_ensembl_not_knowing_it_either_is_said_plainly(tmp_path: Path) -> None:
    ensembl = _FakeEnsembl([])
    hint = lookup_variant(
        rsid="rs2000000000", ensembl_cache=tmp_path, clinvar_cache=tmp_path,
        clients=LookupClients(ensembl=ensembl, eutils=_FakeEutils({})),
    )
    assert hint.loci == []
    assert any("live Ensembl has no GRCh38 locus" in f.message for f in hint.findings)
    # And the snapshot finding no longer claims to speak for Ensembl.
    assert not any("not found in Ensembl" in f.message for f in hint.findings)
    # An answered-empty records which link answered — the missing element that used to be the only
    # trace of a failure is now a present one stating the opposite (S20).
    assert "ensembl-rest" in hint.checked


def test_an_unreachable_ensembl_reports_unchecked_rather_than_absent(tmp_path: Path) -> None:
    """S20. Same call, same rsID, only the transport differs — and the two runs must not produce
    the same finding. `rs6567160` is a real MC4R BMI locus, so the old prose ("has no GRCh38 locus")
    was a false negative about a published variant, at `info`, where nothing draws the eye."""
    ensembl = _FakeEnsembl([], unreachable=True)
    hint = lookup_variant(
        rsid="rs6567160", ensembl_cache=tmp_path, clinvar_cache=tmp_path,
        clients=LookupClients(ensembl=ensembl, eutils=_FakeEutils({})),
    )
    assert ensembl.asked == ["rs6567160"] and hint.loci == []
    unchecked = [f for f in hint.findings if "could not be reached" in f.message]
    assert len(unchecked) == 1
    assert unchecked[0].level == "warning"             # the caller has to decide whether to re-run
    # The claim that inverted the judgment is gone, and so is the inference-from-absence.
    assert not any("has no GRCh38 locus" in f.message for f in hint.findings)
    assert "ensembl-rest" not in hint.checked


def _snapshot(tmp_path: Path, name: str, rows: dict) -> Path:
    """A **populated** reference that simply lacks the rsID under test.

    Every test above hands `lookup_variant` an empty directory, so `resolve_*_reference` finds no
    snapshot and the per-rsID miss warning is never emitted at all. That is why S61's defect sat in a
    green suite: the only line that could produce it was unreachable from the fixtures.
    """
    data = tmp_path / name / "data"
    data.mkdir(parents=True)
    pl.DataFrame(rows).write_parquet(data / "chr.parquet")
    return tmp_path / name


def _ensembl_snapshot(tmp_path: Path) -> Path:
    return _snapshot(tmp_path, "ens", {"id": ["rs1801133"], "chrom": ["1"], "start": [11856377],
                                       "ref": ["G"], "alt": ["A"]})


def _clinvar_snapshot(tmp_path: Path) -> Path:
    return _snapshot(tmp_path, "cv", {"rsid": ["rs334"], "chrom": ["11"], "start": [5227002],
                                      "ref": ["T"], "alt": ["A"]})


_LCT = {"chrom": "2", "start": 135851076, "ref": "G", "alts": "A"}


def test_a_snapshot_miss_does_not_call_the_position_unset_once_live_fills_it(tmp_path: Path) -> None:
    """S61. The cache link answered a question it could not yet know the answer to.

    `lookup_variant` returned rs4988235 at 2:135851076 *and* a finding saying the position remained
    unset, in one payload — the live leg that filled it runs after the link that spoke. A consumer
    whose reader is an agent is told everywhere to trust findings over bare values, so the two halves
    of one response disagree about whether the lookup succeeded.
    """
    hint = lookup_variant(
        rsid="rs4988235",
        ensembl_cache=_ensembl_snapshot(tmp_path), clinvar_cache=_clinvar_snapshot(tmp_path),
        clients=LookupClients(ensembl=_FakeEnsembl([_LCT]), eutils=_FakeEutils({})),
    )
    assert hint.loci == [_LCT]
    assert not any("remains unset" in f.message for f in hint.findings)
    # The miss itself is still on the record: knowing the local snapshot is incomplete is what tells
    # an author whether to warm it, and dropping that was the repair the reporter argued against.
    assert any("not in the injected Ensembl snapshot" in f.message for f in hint.findings)


def test_the_clinvar_link_names_the_snapshot_it_searched_rather_than_clinvar(tmp_path: Path) -> None:
    """The twin of the Ensembl link, and it kept the wording that link was fixed out of.

    `clinvar.lookup_loci` is documented as signature-identical to `resolver.lookup_loci` — "one
    implementation, no drift" — but only the Ensembl half was reworded when it stopped speaking for
    its source. A snapshot that does not carry an rsID is not ClinVar declining to know it.
    """
    hint = lookup_variant(
        rsid="rs4988235",
        ensembl_cache=_ensembl_snapshot(tmp_path), clinvar_cache=_clinvar_snapshot(tmp_path),
        clients=LookupClients(ensembl=_FakeEnsembl([_LCT]), eutils=_FakeEutils({})),
    )
    assert any("not in the injected ClinVar snapshot" in f.message for f in hint.findings)
    assert not any("not found in ClinVar" in f.message for f in hint.findings)


@pytest.mark.parametrize(
    "kwargs, clients",
    [
        (
            {"offline": True},
            lambda: LookupClients(ensembl=_FakeEnsembl([])),
        ),
        (
            {},
            lambda: LookupClients(ensembl=_FakeEnsembl([]), eutils=_FakeEutils({})),
        ),
        (
            {},
            lambda: LookupClients(ensembl=_FakeEnsembl([], unreachable=True), eutils=_FakeEutils({})),
        ),
    ],
    ids=["offline", "live-answered-empty", "live-unreachable"],
)
def test_an_rsid_no_link_placed_still_ends_with_the_position_stated_unset(
    tmp_path: Path, kwargs: dict, clients
) -> None:
    """Moving the sentence must not lose it. Each way a run can end unresolved still says so.

    The clause was load-bearing offline, where a snapshot miss really is the end of the road, and the
    reporter's ask was that it stop being asserted early — not that it stop being said.
    """
    hint = lookup_variant(
        rsid="rs4988235",
        ensembl_cache=_ensembl_snapshot(tmp_path), clinvar_cache=_clinvar_snapshot(tmp_path),
        clients=clients(), **kwargs,
    )
    assert hint.loci == []
    unset = [f for f in hint.findings if f.message == "rs4988235: position remains unset"]
    assert len(unset) == 1 and unset[0].level == "info"


def test_a_position_only_lookup_is_never_told_its_position_is_unset(tmp_path: Path) -> None:
    """The guard on the closing finding. A position-only question fills `rsid_candidates`, never
    `loci`, so an unguarded "position remains unset" would replace one false sentence with another —
    addressed this time to the caller who supplied the position."""
    hint = lookup_variant(
        chrom="1", start=11856377, ref="G", offline=True,
        ensembl_cache=_ensembl_snapshot(tmp_path), clinvar_cache=_clinvar_snapshot(tmp_path),
        clients=LookupClients(),
    )
    assert not any("remains unset" in f.message for f in hint.findings)


def test_a_known_pmid_offers_its_doi_but_never_applies_it() -> None:
    """The DOI arrives free with the existence check — and is exactly what
    `literature._doi_conflicts` compares the authored one against, so it stays advisory."""
    eutils = _FakeEutils({"12345678": {"uid": "12345678", "articleids": [
        {"idtype": "doi", "value": "10.1234/abc"},
        {"idtype": "pmcid", "value": "PMC123"},
    ]}})
    clients = LookupClients(eutils=eutils, europepmc=_FakeEuropePmc())
    hint = lookup_citation(pmid="12345678", clients=clients)
    assert hint.pmid_exists is True
    assert hint.registry_doi == "10.1234/abc"
    offered = as_report_rows(hint)
    assert [row["column"] for row in offered] == ["doi"]
    assert offered[0]["applied"] is False
    assert offered[0]["refusal"] == "redundancy_bearing"


def test_a_real_pmid_for_the_wrong_paper_is_catchable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existence cannot detect fabrication; identity can (S12).

    The failure is demonstrated rather than described: a caller who meant one paper and recalled a
    PMID belonging to another gets `pmid_exists=True` from both, so the *only* thing that separates
    them is what the record says it is — which is why the hint has to carry it. The payload uses the
    real esummary field names (`fulljournalname`, `pubdate`, `sortfirstauthor`), since a parse against
    invented keys would pass this test and fail against PubMed.
    """
    meant, recalled = "29165669", "29165670"
    eutils = _FakeEutils({
        meant: {
            "uid": meant, "articleids": [],
            "title": "MTHFR C677T and homocysteine in coronary disease.",
            "fulljournalname": "The New England Journal of Medicine",
            "pubdate": "2017 Nov 20", "sortfirstauthor": "Smith J",
        },
        recalled: {
            "uid": recalled, "articleids": [],
            "title": "Chloroplast biogenesis in Arabidopsis.",
            "fulljournalname": "Plant Cell", "pubdate": "2003", "sortfirstauthor": "Okuda T",
        },
    })
    clients = LookupClients(eutils=eutils, europepmc=_FakeEuropePmc())

    both = [lookup_citation(pmid=p, clients=clients) for p in (meant, recalled)]
    assert [h.pmid_exists for h in both] == [True, True], "existence cannot tell these apart"
    assert both[0].title != both[1].title, "identity can"

    hint = both[1]
    assert hint.journal == "Plant Cell"
    assert hint.year == "2003"                       # leading four digits of a free-form pubdate
    assert hint.first_author == "Okuda T"
    assert both[0].year == "2017"                    # '2017 Nov 20' -> '2017', nothing invented
    named = [f for f in hint.findings if "existence is not identity" in f.message]
    assert len(named) == 1 and named[0].level == "info"
    assert "Chloroplast biogenesis" in named[0].message


def test_metadata_absent_from_the_record_stays_none() -> None:
    """`None` means PubMed did not say — never an empty string, and never an invented year."""
    eutils = _FakeEutils({"1": {"uid": "1", "articleids": [], "title": "  ", "pubdate": "n.d."}})
    hint = lookup_citation(pmid="1", clients=LookupClients(eutils=eutils, europepmc=_FakeEuropePmc()))
    assert hint.pmid_exists is True
    assert (hint.title, hint.journal, hint.year, hint.first_author) == (None, None, None, None)
    assert not [f for f in hint.findings if "existence is not identity" in f.message]


def test_a_pmid_pubmed_does_not_know_is_reported_false_not_none() -> None:
    """Existence was answered — negatively. Distinct from 'could not ask'."""
    eutils = _FakeEutils({"999999999": {"uid": "999999999", "error": NO_SUMMARY}})
    hint = lookup_citation(pmid="999999999", clients=LookupClients(eutils=eutils))
    assert hint.pmid_exists is False
    assert any(f.level == "warning" for f in hint.findings)


def test_a_pmid_that_could_not_be_asked_stays_none() -> None:
    hint = lookup_citation(pmid="12345678", clients=LookupClients(eutils=_FakeEutils({})))
    assert hint.pmid_exists is None


def test_crossref_tri_state_is_carried_through() -> None:
    for answer in (True, False, None):
        crossref = _FakeCrossref(answer)
        hint = lookup_citation(doi="10.1234/abc", clients=LookupClients(crossref=crossref))
        assert hint.doi_exists is answer
        # the AUTHORED doi is what gets checked — a derived one exists by construction
        assert crossref.asked == ["10.1234/abc"]


def test_the_injected_client_is_reused_rather_than_rebuilt() -> None:
    """Each client owns a PacingGate; a fresh one per question would discard the rate-limit state."""
    eutils = _FakeEutils({"1": {"uid": "1", "articleids": []}, "2": {"uid": "2", "articleids": []}})
    clients = LookupClients(eutils=eutils, europepmc=_FakeEuropePmc())
    lookup_citation(pmid="1", clients=clients)
    lookup_citation(pmid="2", clients=clients)
    assert [call[1] for call in eutils.calls] == [("1",), ("2",)]


def test_open_access_and_abstract_reach_is_reported() -> None:
    """How far a quote check could reach — a miss in an abstract is not a verdict."""
    eutils = _FakeEutils({"7": {"uid": "7", "articleids": []}})
    europepmc = _FakeEuropePmc({"7": {"is_open_access": False, "abstract": "some text"}})
    hint = lookup_citation(pmid="7", clients=LookupClients(eutils=eutils, europepmc=europepmc))
    assert hint.open_access is False
    assert hint.abstract_available is True
    assert any("not a verdict" in f.message for f in hint.findings)


def test_every_offered_column_is_one_the_compiler_calls_redundancy_bearing() -> None:
    """The two tiers must agree on which cells are the author's; a column offered here that the
    compiler does not protect would be a hole in the partition."""
    eutils = _FakeEutils({"12345678": {"uid": "12345678", "articleids": [
        {"idtype": "doi", "value": "10.1234/abc"}
    ]}})
    hint = lookup_citation(
        pmid="12345678", clients=LookupClients(eutils=eutils, europepmc=_FakeEuropePmc())
    )
    for row in as_report_rows(hint):
        assert row["column"] in REDUNDANCY_BEARING, row["column"]


@pytest.mark.parametrize("kwargs", [{"rsid": "rs1801133"}, {"chrom": "1", "start": 11796321}])
def test_either_identifier_shape_is_accepted(kwargs: dict, tmp_path: Path) -> None:
    hint = lookup_variant(offline=True, ensembl_cache=tmp_path, clinvar_cache=tmp_path, **kwargs)
    assert hint.ambiguous is False  # nothing found, so nothing ambiguous

"""Authoring lookups — questions about a value, answered without writing one (0.5).

Offline by default. What is pinned: nothing reaches the filesystem, every answer that a later check
cross-examines comes back `applied=False` with a reason, and a check that could not run reports
`unchecked` rather than `absent` (`None` is not `False`).
"""

from pathlib import Path
from typing import Optional

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
    def __init__(self, records: Optional[dict] = None) -> None:
        self.records = records or {}

    def lookup(self, pmids: list[str]) -> dict:
        return {p: self.records[p] for p in pmids if p in self.records}

    def close(self) -> None:  # pragma: no cover
        pass


class _FakeCrossref:
    def __init__(self, answer: Optional[bool]) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def exists(self, doi: str) -> Optional[bool]:
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

    def __init__(self, loci: list[dict], source: str = "ensembl-rest") -> None:
        self.loci = loci
        self.source = source
        self.asked: list[str] = []

    def resolve_rsid(self, rsid: str) -> tuple[list[dict], Optional[str]]:
        self.asked.append(rsid)
        return (list(self.loci), self.source) if self.loci else ([], None)

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

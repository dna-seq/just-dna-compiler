"""The literature pass never looks up a DOI's digits as PubMed ids (RM336).

Before the fix, `10.1101/2025.03.01.640000` in a `pmid` cell came back from `extract_pmids` as six
PubMed ids, and `_citations` — the map the pass iterates to ask PubMed — put PMIDs 10, 1101, 2025, 03,
01 and 640000 in its lookup list as that row's citations. A DOI-only cell is refused at load now, so
what reaches the pass is a cell carrying a PMID beside a DOI, or the `NONE` sentinel with its `doi`.
"""

from pathlib import Path

from just_dna_enricher.literature import _citations, enrich_literature
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.spec import PMID_NONE, StudyRow
from just_dna_format.verification import read_verification

_DOI = "10.1101/2025.03.01.640000"
_PMID = "11788828"
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def test_a_pmid_beside_a_doi_is_the_only_lookup() -> None:
    study = StudyRow(rsid="rs4988235", pmid=f"{_PMID}; {_DOI}")
    assert list(_citations([study])) == [_PMID]


def test_a_preprint_row_puts_nothing_in_the_lookup_list() -> None:
    study = StudyRow(rsid="rs4988235", pmid=PMID_NONE, doi=_DOI)
    assert _citations([study]) == {}


def test_a_doi_only_cell_from_an_older_writer_puts_nothing_in_the_lookup_list() -> None:
    """A row that skipped validation (an older writer's table, `model_construct`) is still not looked
    up digit by digit: the normalizer is what the pass reads, not the validator."""
    study = StudyRow.model_construct(rsid="rs429358", pmid=_DOI)
    assert _citations([study]) == {}


def _spec(d: Path, studies: str) -> Path:
    d.mkdir(parents=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs4988235,A/A,alt,c\n", encoding="utf-8")
    (d / "studies.csv").write_text(studies, encoding="utf-8")
    return d


def _quote_record(spec: Path):
    return {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}["provenance_quote"]


def test_a_quote_on_a_preprint_row_is_never_reported_as_no_quote(tmp_path: Path) -> None:
    """`_citations` has no key for a `NONE` row, so its quote sat in none of the pass's counts and the
    record said "no provenance quote or regex on any citation" about a module carrying one. It is a
    question this pass cannot put (it reads text by PubMed id), so `unsupported`, said with the count."""
    spec = _spec(
        tmp_path / "s",
        f"rsid,pmid,doi,provenance_quote\nrs4988235,{PMID_NONE},{_DOI},lactase persistence\n",
    )
    result = enrich_literature(spec, offline=True)
    assert result.quotes_authored == 0
    assert result.quotes_without_pmid == 1
    record = _quote_record(spec)
    assert record.skipped == "unsupported"
    assert "1 authored quote(s) sit on citation(s) whose pmid is NONE" in (record.detail or "")


def test_a_preprint_quote_beside_a_pmid_quote_is_named_outside_the_denominator(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path / "s",
        "rsid,pmid,doi,provenance_quote\n"
        f"rs4988235,{_PMID},,lactase persistence\n"
        f"rs4988235,{PMID_NONE},{_DOI},lactase persistence\n",
    )
    enrich_literature(spec, offline=True)
    record = _quote_record(spec)
    assert record.skipped == "offline"
    assert record.detail is not None
    assert record.detail.startswith("1 authored quote(s);")
    assert "whose pmid is NONE" in record.detail

"""The literature pass never looks up a DOI's digits as PubMed ids (RM336).

Before the fix, `10.1101/2025.03.01.640000` in a `pmid` cell came back from `extract_pmids` as six
PubMed ids, and `_citations` — the map the pass iterates to ask PubMed — put PMIDs 10, 1101, 2025, 03,
01 and 640000 in its lookup list as that row's citations. A DOI-only cell is refused at load now, so
what reaches the pass is a cell carrying a PMID beside a DOI, or the `NONE` sentinel with its `doi`.
"""

import csv
import io
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


_SLCO1B1 = Path(__file__).resolve().parents[2] / "reference_examples" / "pgx_slco1b1_simvastatin"


class _NeverAsked:
    """A client the pass must not touch: every citation here is DOI-only, so there is nothing to ask."""

    def __getattr__(self, name: str):
        raise AssertionError(f"the pass asked a registry ({name}) about a module citing by DOI alone")


def _pharm_spec_citing_by_doi(d: Path) -> Path:
    """The SLCO1B1 example with no studies.csv and its Toxicity rows citing a preprint by DOI."""
    d.mkdir(parents=True)
    for source in _SLCO1B1.iterdir():
        if source.suffix in {".csv", ".yaml"} and source.name != "pharm_variants.csv":
            (d / source.name).write_bytes(source.read_bytes())
    rows = list(csv.DictReader(io.StringIO((_SLCO1B1 / "pharm_variants.csv").read_text(encoding="utf-8"))))
    toxicity = [r["phenotype_category"] == "Toxicity" for r in rows]
    assert any(toxicity), "the example must carry a Toxicity row"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[*rows[0], "pmid", "doi"], lineterminator="\n")
    writer.writeheader()
    for row, cites in zip(rows, toxicity, strict=True):
        writer.writerow({**row, "pmid": PMID_NONE if cites else "", "doi": _DOI if cites else ""})
    (d / "pharm_variants.csv").write_text(buffer.getvalue(), encoding="utf-8")
    return d


def _existence_record(spec: Path):
    return {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}["citation_existence"]


def test_a_module_citing_only_by_doi_is_not_a_module_citing_nothing(tmp_path: Path) -> None:
    """The pass used to refuse with "no citations in …", false for a module whose every citation is a
    `NONE`+`doi` pharm row, and past that would record `ran(0, 0)`, the clean-looking pass the
    identifier check already refuses to emit. The question was never put, so: `unsupported`, counted."""
    spec = _pharm_spec_citing_by_doi(tmp_path / "s")
    expected = sum(
        1 for r in csv.DictReader(io.StringIO((spec / "pharm_variants.csv").read_text())) if r["doi"]
    )
    never = _NeverAsked()
    result = enrich_literature(spec, eutils=never, europepmc=never, crossref=never)
    assert result.cited == []
    assert result.citations_without_pmid == expected
    record = _existence_record(spec)
    assert record.skipped == "unsupported"
    assert f"{expected} citation(s) have pmid NONE" in (record.detail or "")


def test_offline_it_says_the_same_count(tmp_path: Path) -> None:
    spec = _pharm_spec_citing_by_doi(tmp_path / "s")
    enrich_literature(spec, offline=True)
    record = _existence_record(spec)
    assert record.skipped == "offline"
    assert "have pmid NONE and cite by DOI alone" in (record.detail or "")

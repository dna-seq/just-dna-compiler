"""The literature pass never looks up a DOI's digits as PubMed ids (RM336).

Before the fix, `10.1101/2025.03.01.640000` in a `pmid` cell came back from `extract_pmids` as six
PubMed ids, and `_citations` — the map the pass iterates to ask PubMed — put PMIDs 10, 1101, 2025, 03,
01 and 640000 in its lookup list as that row's citations. A DOI-only cell is refused at load now, so
what reaches the pass is a cell carrying a PMID beside a DOI, or the `NONE` sentinel with its `doi`.
"""

from just_dna_enricher.literature import _citations
from just_dna_format.spec import PMID_NONE, StudyRow

_DOI = "10.1101/2025.03.01.640000"
_PMID = "11788828"


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

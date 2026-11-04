"""The enricher compares an authored value with a source's by the one key (RM363).

`schema/tests/test_one_normalizer_per_kind.py` walks every comparison site; these pin the two that
answer a question about a source: an authored gene in another case is checked against PharmVar's
spelling, and a DOI-only study written with trailing punctuation is one citation, the token the
PubMed path already compared.
"""

from just_dna_enricher.literature import _doi_only_citations
from just_dna_enricher.pgx import _compare
from just_dna_format.pgx import AlleleFunctionRow
from just_dna_format.spec import StudyRow


def test_an_authored_gene_in_another_case_is_compared_with_the_sources() -> None:
    authored = [AlleleFunctionRow(gene="Cyp2c19", allele="*2", function_status="no_function")]
    same = {("CYP2C19", "*2"): "no_function"}
    differs = {("CYP2C19", "*2"): "normal_function"}
    conflicts, compared = _compare(authored, same, "pharmvar")
    assert (conflicts, len(compared)) == ([], 1)
    conflicts, compared = _compare(authored, differs, "pharmvar")
    assert len(conflicts) == 1 and len(compared) == 1


def test_a_doi_with_trailing_punctuation_is_one_doi_only_citation() -> None:
    studies = [
        StudyRow(rsid="rs429358", pmid="NONE", doi="10.1101/2024.01.01.123456"),
        StudyRow(rsid="rs429358", pmid="NONE", doi="https://doi.org/10.1101/2024.01.01.123456."),
    ]
    citations = _doi_only_citations(studies, {})
    assert list(citations) == ["10.1101/2024.01.01.123456"]
    assert len(citations["10.1101/2024.01.01.123456"]) == 2

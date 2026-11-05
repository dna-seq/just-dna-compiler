"""A DOI is never written into `pmid`, and `pmid=NONE` makes `doi` the citation (RM336).

The reproduction is the RM336 one, run on the shipped extractor before the fix: a preprint's DOI in
`pmid` validated, and `extract_pmids("10.1101/2025.03.01.640000")` came back
`['10', '1101', '2025', '03', '01', '640000']` — six PubMed ids the literature pass then looked up as
the row's citations. A preprint-only row is exactly where an author writes it, because `pmid` is
required and the paper has no PubMed record.

The decided shape (ROADMAP_0_8 § RM336, the latest line): a DOI-only `pmid` is refused and named, as
RM50's PMCID arm refuses a PMC id; `pmid` accepts the exact sentinel `NONE`, which makes `doi` the
mandatory substitute, checked against `spec.DOI_PATTERN`. One rule on every citing model.
"""

import pytest
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.pgx import PharmVariantRow
from just_dna_format.spec import (
    PMID_NONE,
    CitationPair,
    StudyRow,
    check_citation_pair,
    extract_pmids,
    validate_pmid_cell,
)

#: The RM336 reproduction: a bioRxiv preprint DOI, written where the PMID goes.
_PREPRINT_DOI = "10.1101/2025.03.01.640000"
#: A real PMID (Enattah 2002, the LCT paper) — the digits that must survive beside a DOI.
_PMID = "11788828"


def _bin(**cells: object) -> RepeatAlleleRow:
    return RepeatAlleleRow(
        gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant", **cells
    )


def _pharm(**cells: object) -> PharmVariantRow:
    return PharmVariantRow(
        rsid="rs4149056", drug="simvastatin", genotype="C/C", conclusion="increased myopathy risk", **cells
    )


def _gwas(**cells: object) -> GwasEffectRow:
    return GwasEffectRow(
        association_id="1",
        variant_key="rs4149056",
        dataset="gwas_catalog_test",
        source="gwas_catalog",
        **cells,
    )


class TestADoiIsNotAPmid:
    @pytest.mark.parametrize(
        "cell",
        [
            _PREPRINT_DOI,
            f"doi:{_PREPRINT_DOI}",
            f"https://doi.org/{_PREPRINT_DOI}",
            "10.1038/s41586-019-1234-5",
        ],
    )
    def test_no_spelling_of_a_doi_yields_a_pmid(self, cell: str) -> None:
        assert extract_pmids(cell) == []

    def test_a_cell_carrying_both_keeps_the_real_pmid(self) -> None:
        """The arm stays narrow the way RM50's does: only a cell whose sole content is a DOI is refused."""
        cell = f"{_PMID}; {_PREPRINT_DOI}"
        assert extract_pmids(cell) == [_PMID]
        assert StudyRow(rsid="rs4988235", pmid=cell).pmid == cell

    def test_the_rm336_reproduction_is_refused_naming_the_doi(self) -> None:
        with pytest.raises(Exception) as exc:
            StudyRow(rsid="rs429358", pmid=_PREPRINT_DOI)
        message = str(exc.value)
        assert _PREPRINT_DOI in message, "the refusal must name the DOI that was written"
        assert "doi" in message and PMID_NONE in message, "and say where it goes instead"

    @pytest.mark.parametrize("build", [_bin, _pharm, _gwas])
    def test_every_citing_model_refuses_it(self, build) -> None:
        with pytest.raises(Exception) as exc:
            build(pmid=_PREPRINT_DOI)
        assert _PREPRINT_DOI in str(exc.value)


class TestTheNoneSentinel:
    def test_none_yields_no_pmid(self) -> None:
        assert extract_pmids(PMID_NONE) == []

    def test_the_sentinel_is_exactly_none(self) -> None:
        assert PMID_NONE == "NONE"
        assert validate_pmid_cell(PMID_NONE, "pmid", required=True) == PMID_NONE

    @pytest.mark.parametrize("cell", ["none", "None", "NA", "n/a", "-"])
    def test_other_spellings_are_refused_with_a_pointer_to_none(self, cell: str) -> None:
        with pytest.raises(ValueError) as exc:
            validate_pmid_cell(cell, "pmid", required=True)
        message = str(exc.value)
        assert "at least one PubMed ID" in message, "the generic message's leading phrase is unchanged"
        assert f"'{PMID_NONE}'" in message

    def test_none_without_doi_is_refused(self) -> None:
        with pytest.raises(Exception, match="doi"):
            StudyRow(rsid="rs429358", pmid=PMID_NONE)

    def test_none_with_a_doi_is_accepted_and_kept_verbatim(self) -> None:
        row = StudyRow(rsid="rs429358", pmid=PMID_NONE, doi=f"https://doi.org/{_PREPRINT_DOI}")
        assert row.pmid == PMID_NONE
        assert row.doi == f"https://doi.org/{_PREPRINT_DOI}"

    def test_none_with_a_doi_that_is_not_one_is_refused(self) -> None:
        with pytest.raises(Exception, match="DOI token"):
            StudyRow(rsid="rs429358", pmid=PMID_NONE, doi="bioRxiv preprint, March 2025")

    @pytest.mark.parametrize("build", [_bin, _pharm, _gwas])
    def test_every_citing_model_runs_the_pair_rule(self, build) -> None:
        with pytest.raises(Exception, match="doi"):
            build(pmid=PMID_NONE)
        row = build(pmid=PMID_NONE, doi=_PREPRINT_DOI)
        assert (row.pmid, row.doi) == (PMID_NONE, _PREPRINT_DOI)

    @pytest.mark.parametrize("build", [_bin, _pharm, _gwas])
    def test_a_doi_beside_a_pmid_is_optional_and_validated(self, build) -> None:
        assert build(pmid=_PMID).doi is None
        assert build(pmid=_PMID, doi=_PREPRINT_DOI).doi == _PREPRINT_DOI
        with pytest.raises(Exception, match="DOI token"):
            build(pmid=_PMID, doi="not a doi")


class TestTheSharedRule:
    def test_the_function_and_the_mixin_are_one_rule(self) -> None:
        check_citation_pair(_PMID, None)
        check_citation_pair(None, None)
        check_citation_pair(PMID_NONE, _PREPRINT_DOI)
        with pytest.raises(ValueError, match="doi"):
            check_citation_pair(PMID_NONE, None)
        for model in (StudyRow, RepeatAlleleRow, PharmVariantRow, GwasEffectRow):
            assert issubclass(model, CitationPair)

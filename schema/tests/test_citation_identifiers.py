"""PubMed and PubMed Central ids are one letter apart, and the outcome used to turn on a space (RM50).

Every spelling exercised here was **probed against the shipped extractor** before the guard was
written, not imagined: `PMC3110566` came back `[]` (there is no word boundary between `C` and a
digit) and `pmcid: PMC3110566` came back `[]`, but `PMC 3110566` came back `['3110566']` — and
3110566 is a real PMID for an unrelated article, because PubMed ids are densely allocated. So one
spelling of one mistake was refused with a message that never said "PMCID", and another was accepted
as a confident citation of the wrong paper.

The pair used throughout is real and checked: PMC3110566 is PMID 21551363 (NCBI's id converter,
probed 2026-08-13). They share no digits, which is the whole point.
"""

import pytest
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.spec import StudyRow, extract_pmcids, extract_pmids, validate_pmid_cell

#: The real pair. `_PMC` is *not* `_PMID`, and reading one as the other cites a different article.
_PMC = "PMC3110566"
_PMID = "21551363"
#: The digits inside `_PMC`, which the old extractor handed back as a PubMed id for the spaced form.
_PMC_DIGITS = "3110566"


class TestPmcIsNotAPmid:
    @pytest.mark.parametrize(
        "cell",
        ["PMC3110566", "PMC 3110566", "pmcid: PMC3110566", "pmcid: 3110566", "PMC-3110566",
         "PMCID 3110566", "pmc3110566"],
    )
    def test_no_spacing_of_a_pmc_id_yields_a_pmid(self, cell: str) -> None:
        """The spaced form is the one that used to slip through, so parametrizing is the test."""
        assert extract_pmids(cell) == []
        assert extract_pmcids(cell) == [_PMC]

    def test_the_digits_alone_are_still_a_pmid(self) -> None:
        """Nothing is inferred from the number: without the PMC context this is an ordinary cell, and
        refusing it would bar a real PubMed id that happens to share digits with some PMC record."""
        assert extract_pmids(_PMC_DIGITS) == [_PMC_DIGITS]

    def test_a_cell_carrying_both_keeps_the_real_pmid(self) -> None:
        """This is what keeps the guard narrow: only a cell whose *sole* numeric content is a PMC id
        is refused, and that cell previously resolved to another article entirely."""
        cell = f"{_PMID}; {_PMC}"
        assert extract_pmids(cell) == [_PMID]
        assert extract_pmcids(cell) == [_PMC]
        assert StudyRow(rsid="rs1800562", pmid=cell).pmid == cell

    def test_the_existing_authored_forms_are_untouched(self) -> None:
        for cell, expected in (
            ("9545397", ["9545397"]),
            ("[PMID: 9545397]", ["9545397"]),
            ("PMID 17478681; PMID: 30278588", ["17478681", "30278588"]),
        ):
            assert extract_pmids(cell) == expected
            assert extract_pmcids(cell) == []

    def test_a_journal_name_containing_pmc_is_not_a_pmc_id(self) -> None:
        """`PMC` followed by a word is not an identifier — the digits must be adjacent."""
        assert extract_pmcids("PMC Journal 2011") == []
        assert extract_pmids(f"PMC Journal, {_PMID}") == [_PMID]


class TestTheRefusalNamesWhatItSaw:
    def test_it_names_the_pmcid_rather_than_the_missing_pmid(self) -> None:
        with pytest.raises(Exception) as exc:
            StudyRow(rsid="rs1800562", pmid=_PMC)
        message = str(exc.value)
        assert _PMC in message, "the refusal must name the id that was written"
        assert "PubMed Central" in message
        # And it must point somewhere: a generic refusal is a dead end where a specific one is a fix.
        assert "hint citation --pmcid" in message

    def test_a_cell_with_no_identifier_at_all_gets_the_generic_message(self) -> None:
        """A misplaced diagnosis is worse than none: only a PMC-shaped cell earns the PMC message."""
        with pytest.raises(Exception) as exc:
            StudyRow(rsid="rs1800562", pmid="https://www.ncbi.nlm.nih.gov/snp/rs1800562")
        assert "PubMed Central" not in str(exc.value)
        assert "at least one PubMed ID" in str(exc.value)

    def test_an_empty_cell_still_refuses_where_the_pointer_is_required(self) -> None:
        with pytest.raises(Exception, match="must not be empty"):
            StudyRow(rsid="rs1800562", pmid="")


class TestTheSharedGrammar:
    """One rule, two models — `required` is the only thing that differs between them."""

    def test_required_and_optional_differ_only_on_emptiness(self) -> None:
        assert validate_pmid_cell(None, "pmid", required=False) is None
        assert validate_pmid_cell("  ", "pmid", required=False) is None
        with pytest.raises(ValueError, match="must not be empty"):
            validate_pmid_cell(None, "pmid", required=True)

    def test_a_binning_row_runs_the_same_refusal(self) -> None:
        """The bin pointer is a different column on a different model and must not drift."""
        with pytest.raises(Exception) as exc:
            RepeatAlleleRow(
                gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant",
                pmid=_PMC,
            )
        assert _PMC in str(exc.value)

    def test_a_bin_pointer_is_optional_and_kept_verbatim(self) -> None:
        bare = RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant"
        )
        assert bare.pmid is None
        cited = RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant",
            pmid="[PMID: 8458085]",
        )
        assert cited.pmid == "[PMID: 8458085]"
        assert extract_pmids(cited.pmid) == ["8458085"]


class TestASubjectlessCitationRow:
    """RM47: a citation may ground the module or a bin boundary rather than a variant."""

    def test_it_validates_and_has_no_variant_key(self) -> None:
        row = StudyRow(pmid="8458085", conclusion="defines the CAG thresholds")
        assert row.variant_key is None
        assert row.rsid is None and row.chrom is None

    def test_the_key_is_never_the_string_none(self) -> None:
        """`derive_variant_key(None, None, None, None)` returns `"None:None:None"`, which looks like
        an identity and names nothing — the reason the property short-circuits instead."""
        assert StudyRow(pmid="8458085").variant_key is None

    def test_naming_a_variant_still_works_unchanged(self) -> None:
        assert StudyRow(rsid="rs1800562", pmid="8458085").variant_key == "rs1800562"
        assert StudyRow(chrom="4", pmid="8458085").variant_key == "4:None:None"

    @pytest.mark.parametrize(
        "partial", [{"start": 94781859}, {"ref": "G"}, {"start": 94781859, "ref": "G"}]
    )
    def test_half_a_coordinate_is_still_refused(self, partial: dict) -> None:
        """The relaxation legalises an *empty* subject, never a partial one.

        A blank `chrom` cell in the middle of a coordinate is the commonest CSV slip, and it is not a
        subject-less citation: `variant_key` would answer `None` while `studies.parquet` still carried
        the orphaned position, so the row would read as grounding the module while holding a
        coordinate nothing can join."""
        with pytest.raises(Exception, match="half-written coordinate"):
            StudyRow(pmid="8458085", **partial)

    def test_the_same_columns_beside_a_chrom_are_fine(self) -> None:
        row = StudyRow(chrom="4", start=3074877, ref="C", pmid="8458085")
        assert row.variant_key == "4:3074877:C"

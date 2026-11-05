"""`resolution.csv` `source_loci` (RM387): one spelling, written and read through one pair of helpers."""

import pytest
from just_dna_format.resolution import (
    RESOLUTION_FACT_FIELDS,
    ResolutionRow,
    source_loci_cell,
    split_source_loci,
)
from pydantic import ValidationError


def test_the_cell_is_one_string_per_set_of_places() -> None:
    """Folded contigs, sorted, duplicates once, so the order the links answered in never moves a byte."""
    one = source_loci_cell([("chr6", 600), ("5", 500), ("6", 600)])
    two = source_loci_cell([("5", 500), ("6", 600)])
    assert one == two == "5:500,6:600"
    assert split_source_loci(one) == {("5", 500), ("6", 600)}


def test_a_place_with_no_contig_or_start_is_left_out_and_nothing_is_none() -> None:
    assert source_loci_cell([(None, 5), ("1", None)]) is None
    assert split_source_loci(None) == frozenset() == split_source_loci("")


@pytest.mark.parametrize("cell", ["5", "5:", ":500", "5:-1", "5:500;6:600", "5:5x"])
def test_a_malformed_cell_is_refused_at_load(cell: str) -> None:
    with pytest.raises(ValidationError, match="source_loci"):
        ResolutionRow(variant_key="rs1", rsid="rs1", source_loci=cell)


def test_the_column_is_outside_the_fact_signature() -> None:
    """A record of what was offered beside the answer chosen, so it moves no `resolution_signature`."""
    assert "source_loci" not in RESOLUTION_FACT_FIELDS

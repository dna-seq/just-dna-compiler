"""`HeteroplasmyRow` variant identity (0.5.1) — and the continuous-tiling proof beside it.

Found by building `reference_examples/mt_heteroplasmy/`. A mitochondrial gene carries several
pathogenic variants with genuinely different heteroplasmy thresholds, and the table keyed on the gene
alone, so their bins landed in one group and `validate_bins` **errored**. The module could not compile
at all, and there was no honest workaround: `trait_efo_id` is in the group key and would have
separated them, but only by giving one disease two ontology ids.
"""

import pytest

from just_dna_format.binning import HeteroplasmyRow, validate_bins


def _bin(lo, hi, conclusion="c", **kwargs) -> HeteroplasmyRow:
    payload = {
        "gene": "MT-TL1",
        "reference_sequence": "NC_012920.1",
        "conclusion": conclusion,
        "measure_min": lo,
        "measure_max": hi,
        **kwargs,
    }
    return HeteroplasmyRow(**payload)


#: The two real MELAS-causing MT-TL1 variants, with their real (different) blood thresholds.
_M3243 = {"chrom": "MT", "start": 3243, "ref": "A", "alts": "G"}
_M3271 = {"chrom": "MT", "start": 3271, "ref": "T", "alts": "C"}


def test_two_variants_in_one_gene_no_longer_collide() -> None:
    """The blocking case. Both cause MELAS, so `trait_efo_id` cannot separate them."""
    rows = [
        _bin(0.0, 0.099, "m.3243A>G low", trait_efo_id="MONDO:0010789", **_M3243),
        _bin(0.3, 1.0, "m.3243A>G high", trait_efo_id="MONDO:0010789", **_M3243),
        _bin(0.0, 0.149, "m.3271T>C low", trait_efo_id="MONDO:0010789", **_M3271),
        _bin(0.15, 1.0, "m.3271T>C high", trait_efo_id="MONDO:0010789", **_M3271),
    ]
    # No exception: the overlapping [0, 0.099] and [0, 0.149] are now different groups.
    assert not [w for w in validate_bins(rows) if "overlap" in w]


def test_without_the_identity_the_same_rows_are_rejected() -> None:
    """Demonstrate the failure on the old shape rather than asserting it would have happened."""
    rows = [
        _bin(0.0, 0.099, "m.3243A>G low", trait_efo_id="MONDO:0010789"),
        _bin(0.0, 0.149, "m.3271T>C low", trait_efo_id="MONDO:0010789"),
    ]
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins(rows)


def test_two_variants_at_one_position_are_distinguished_by_their_alt() -> None:
    """MT-ATP6 m.8993T>G (NARP/Leigh) and m.8993T>C are the same base, different alleles — which is
    why the identity is derived with `alts` rather than position-only."""
    to_g = _bin(0.0, 0.6, "T>G low", chrom="MT", start=8993, ref="T", alts="G")
    to_c = _bin(0.0, 0.8, "T>C low", chrom="MT", start=8993, ref="T", alts="C")
    assert to_g.variant_key != to_c.variant_key
    assert not [w for w in validate_bins([to_g, to_c]) if "overlap" in w]


def test_a_gene_only_table_keeps_working_exactly_as_before() -> None:
    """P3/P8: the columns are optional, so an already-authored single-variant table is untouched."""
    bare = _bin(0.1, 0.8)
    assert bare.variant_key is None
    assert HeteroplasmyRow._KEY_FIELDS == ("gene", "reference_sequence", "tissue", "variant_key")
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins([_bin(0.0, 0.5), _bin(0.4, 1.0)])


def test_tissue_still_separates_bins_for_one_variant() -> None:
    """The pre-existing key component must survive: the same fraction means different things in
    blood and muscle, and that is the whole point of `tissue`."""
    rows = [
        _bin(0.0, 0.299, "blood low", tissue="blood", **_M3243),
        _bin(0.3, 1.0, "blood high", tissue="blood", **_M3243),
        _bin(0.0, 0.399, "muscle low", tissue="muscle", **_M3243),
        _bin(0.4, 1.0, "muscle high", tissue="muscle", **_M3243),
    ]
    assert not [w for w in validate_bins(rows) if "overlap" in w]


# ── the continuous-tiling problem (RM35, fixed: a shared endpoint is a boundary) ───────────────


def test_a_continuous_table_can_now_be_tiled_with_no_finding() -> None:
    """The whole point of the fix: touching bins on a dense measure are legal and complete.

    Three rules used to be jointly unsatisfiable — inclusive at both ends, overlap-is-an-error,
    any-positive-hole-is-a-warning — so adjacent continuous bins either shared an endpoint (error) or
    did not (warning). A shared endpoint is now a *boundary* owned by the higher bin, so a real
    heteroplasmy table tiles [0, 0.1], [0.1, 0.3], [0.3, 1.0] and reports nothing at all.
    """
    rows = [_bin(0.0, 0.1, "low"), _bin(0.1, 0.3, "MIDD"), _bin(0.3, 1.0, "MELAS")]
    assert validate_bins(rows) == []
    # …and the top of the domain stays reachable, which is why the bound was not made exclusive: a
    # heteroplasmy of 1.0 is homoplasmy, a real measurement, and it selects the top bin.
    assert rows[-1].measure_max == 1.0


def test_the_old_convention_could_not_be_satisfied_and_here_is_that_proof() -> None:
    """Demonstrated on the old rule rather than asserted, using the kind that still obeys it.

    The unsatisfiability argument was never about continuity as such — it was about
    `lo <= prev_hi` being the overlap test on a domain where the only alternative to touching is a
    gap. `copy_number` still uses that test (correctly: two integer bins sharing an endpoint really do
    both claim it), so running the same pair through a discrete kind reproduces the original bind
    exactly: touching errors, and any epsilon short of touching leaves a hole.
    """
    from just_dna_format.binning import CopyNumberRow

    def _cn(lo, hi):
        return CopyNumberRow(gene="SMN1", conclusion="c", measure_min=lo, measure_max=hi)

    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins([_cn(0.0, 1.0), _cn(1.0, 3.0)])
    assert [w for w in validate_bins([_cn(0.0, 1.0), _cn(2.5, 3.0)]) if "coverage gap" in w]


def test_a_real_overlap_on_a_continuous_measure_still_refuses() -> None:
    """The check keeps its teeth: touching is legal, crossing is not."""
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins([_bin(0.0, 0.3), _bin(0.2, 1.0)])


def test_a_gap_on_a_continuous_measure_still_warns() -> None:
    """The other half is unchanged — a hole is still a hole, at any epsilon."""
    for epsilon in (0.001, 0.0000001):
        gaps = validate_bins([_bin(0.0, 0.1 - epsilon), _bin(0.1, 1.0)])
        assert [w for w in gaps if "coverage gap" in w], epsilon


def test_two_bins_sharing_a_lower_bound_refuse_because_nothing_can_break_the_tie() -> None:
    """The boundary rule selects the greatest `measure_min` ≤ the measurement, and equals do not sort.

    Reachable only as a single point beside a wider bin — anything wider would already be a crossing
    overlap — and a measurement of exactly 0.1 would then have two answers.
    """
    with pytest.raises(ValueError, match="same lower bound"):
        validate_bins([_bin(0.1, 0.1, "sharp"), _bin(0.1, 0.3, "range")])


def test_a_point_bin_below_a_boundary_is_fine() -> None:
    """The mirror case, and it must stay legal: distinct minima are always separable."""
    assert validate_bins([_bin(0.0, 0.1, "below"), _bin(0.1, 0.1, "exactly 0.1")]) == []


def test_an_integer_kind_tiles_cleanly_which_is_why_this_was_missed() -> None:
    from just_dna_format.binning import RepeatAlleleRow

    rows = [
        RepeatAlleleRow(gene="HTT", repeat_unit="CAG", conclusion="normal",
                        measure_min=6, measure_max=35),
        RepeatAlleleRow(gene="HTT", repeat_unit="CAG", conclusion="intermediate",
                        measure_min=36, measure_max=39),
        RepeatAlleleRow(gene="HTT", repeat_unit="CAG", conclusion="pathogenic",
                        measure_min=40, measure_max=None),
    ]
    assert validate_bins(rows) == []

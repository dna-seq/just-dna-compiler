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


# ── the continuous-tiling problem (RM35, recorded not fixed) ───────────────────────────────────


def test_a_continuous_measure_cannot_be_tiled_without_a_finding() -> None:
    """Proof, not opinion: three rules that are jointly unsatisfiable on a continuous scale.

    Bounds are inclusive at both ends, overlaps are an **error**, and any positive hole is a
    **warning**. So adjacent bins either share an endpoint (overlap → error) or do not (hole →
    warning), and no epsilon escapes it. Every `allele_fraction` and `prs_percentile` table must
    therefore emit a finding forever. Integer kinds are fine — `[36,39]` and `[40,None]` are gapless
    because the domain is discrete — which is where the inclusive convention was generalized from.
    """
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins([_bin(0.0, 0.1), _bin(0.1, 1.0)])

    for epsilon in (0.001, 0.0000001):
        gaps = validate_bins([_bin(0.0, 0.1 - epsilon), _bin(0.1, 1.0)])
        assert [w for w in gaps if "coverage gap" in w], epsilon


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

"""The schema-tier half of the 0.6 VCF 4.4 conformance round: RM55, RM56, RM58 and RM60.

Each test states the finding it pins and, where the finding is that a check *cannot* see something,
demonstrates the blind spot by running the real lookup rule rather than asserting a message.
"""

import math

import pytest
from just_dna_format.alleles import (
    MISSING_ALLELE,
    non_nucleotide_alleles,
    non_nucleotide_reason,
)
from just_dna_format.base import derive_variant_key
from just_dna_format.binning import (
    _INTEGER_KINDS,
    _VCF_MEASURE_FIELDS,
    VALID_MEASURE_KINDS,
    CopyNumberRow,
    HeteroplasmyRow,
    RepeatAlleleRow,
    measurement_shape_warnings,
    validate_bins,
)
from just_dna_format.spec import VALID_CHROMOSOMES, VariantRow
from just_dna_format.vrs import normalize_chrom


def _htt_bins() -> list[RepeatAlleleRow]:
    """The real `reference_examples/htt_repeat_expansion` tiling, thresholds and all."""
    bounds = [(6, 26), (27, 35), (36, 39), (40, None)]
    return [
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi,
            conclusion=f"{lo}-{hi} CAG",
        )
        for lo, hi in bounds
    ]


def _smn_bins() -> list[CopyNumberRow]:
    """A sharp-integer SMN1 dosage tiling — the shape `CopyNumberRow`'s own docstring describes."""
    rows = [
        CopyNumberRow(gene="SMN1", measure_min=n, measure_max=n, conclusion=f"{n} copies")
        for n in (0, 1, 2)
    ]
    rows.append(CopyNumberRow(gene="SMN1", measure_min=3, conclusion="3+ copies"))
    return rows


def _selected(rows, x: float):
    """The bin the documented consumer rule selects for `x`, or None for 'no matching bin'.

    *The row with the greatest `measure_min` at or below the measurement*, then the inclusive
    `measure_max` decides whether it actually claims the value. Implemented here rather than imported
    because the point of these tests is that the schema has no such function — the rule lives in the
    consumer contract, and a fractional measurement falls out of it.
    """
    candidates = [r for r in rows if r.measure_min is not None and r.measure_min <= x]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: r.measure_min)
    if best.measure_max is not None and x > best.measure_max:
        return None
    return best


# ── RM55: the integer kinds are not integral ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rows, fractional",
    [
        (_htt_bins(), 39.5),
        (_smn_bins(), 2.4),
    ],
    ids=["repeat_count (RUC is a Float, VCF 4.4 §3)", "copy_number (CN, VCF 4.4 §7.2)"],
)
def test_an_integer_tiling_silently_answers_nothing_for_a_fractional_measurement(
    rows, fractional: float
) -> None:
    """The defect RM55 names, demonstrated rather than asserted.

    `validate_bins` is *content*: the tiling is legal, gapless by its own rule and warning-free — and a
    measurement the source is entitled to produce selects no bin at all. Neither half is visible to an
    author, which is why the warning had to be added somewhere: the table is green and unanswerable.

    The exposure is **at a boundary** (39.5 sits between the reduced-penetrance bin's inclusive 39 and
    the fully-penetrant bin's 40) and **on a sharp tiling** (SMN1's `[2,2]`), not everywhere — a
    fraction inside a wide range bin is answered fine. Writing this test is what found the first
    draft's warning overclaiming exactly that, so the assertion below is the corrected shape.
    """
    assert validate_bins(rows) == []
    assert _selected(rows, fractional) is None
    # …while the neighbouring whole numbers on both sides are answered perfectly well, so this is not
    # a table that simply fails to cover its domain.
    assert _selected(rows, math.floor(fractional)) is not None
    assert _selected(rows, math.ceil(fractional)) is not None


def test_the_gap_check_cannot_see_a_hole_of_one_on_an_integer_kind() -> None:
    """The second half of RM55: the hole a fractional measurement falls into is not reportable.

    An integer kind only warns about a hole wider than a whole number, because on a genuinely integral
    domain `[6,26]` beside `[27,35]` covers everything between them. Once the domain is fractional that
    reasoning is void, and the check has no way to say so — which is exactly why the finding is stated
    against the *kind* rather than derived from the bounds.
    """
    adjacent = _htt_bins()
    assert validate_bins(adjacent) == []
    assert _selected(adjacent, 26.5) is None


def test_both_integer_kinds_warn_and_nothing_else_does() -> None:
    """Fixing one kind and leaving the other is the thing this pins against.

    Both were placed in `_INTEGER_KINDS` on one premise — an integral domain — and VCF 4.4 withdrew it
    for both, so the warning set and the integer-kind set must be the same set.
    """
    assert set(_VCF_MEASURE_FIELDS) == _INTEGER_KINDS
    assert set(_VCF_MEASURE_FIELDS) <= VALID_MEASURE_KINDS

    warned = {
        kind
        for kind, rows in (("repeat_count", _htt_bins()), ("copy_number", _smn_bins()))
        if measurement_shape_warnings(rows)
    }
    assert warned == _INTEGER_KINDS

    fraction_bins = [
        HeteroplasmyRow(
            gene="MT-TL1", reference_sequence="NC_012920.1", measure_min=lo, measure_max=hi,
            conclusion=f"{lo}-{hi}",
        )
        for lo, hi in ((0.0, 0.1), (0.1, 0.6), (0.6, 1.0))
    ]
    assert measurement_shape_warnings(fraction_bins) == []


def test_the_warning_names_the_field_and_the_kind_it_is_about() -> None:
    """Aggregated to the kind, never one line per bin, and each kind names its own VCF field."""
    for kind, rows in (("repeat_count", _htt_bins()), ("copy_number", _smn_bins())):
        value_field, ci_field, _note = _VCF_MEASURE_FIELDS[kind]
        warnings = measurement_shape_warnings(rows)
        assert len(warnings) == 2, warnings  # one RM55 line, one RM56 line — not one per bin
        assert all(kind in w for w in warnings)
        assert value_field in warnings[0]
        assert ci_field in warnings[1]
        other_field = next(f for k, (f, _c, _n) in _VCF_MEASURE_FIELDS.items() if k != kind)
        assert not any(other_field in w for w in warnings)


# ── RM56: a measurement is an interval, and it can cross a threshold ───────────────────────────


def test_the_spanning_warning_needs_a_threshold_to_span() -> None:
    """One bin has no boundary an interval could cross, so saying otherwise would be a false finding.

    The HTT tiling is the opposite case and the reason the item exists: three thresholds inside a
    14-count window, so a real `RUC=38, CIRUC=-5,5` reaches [33, 43] and touches three different
    conclusions.
    """
    one_bin = [RepeatAlleleRow(gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="≥40")]
    assert len(measurement_shape_warnings(one_bin)) == 1  # RM55 only

    htt = _htt_bins()
    touched = {
        _selected(htt, x).conclusion for x in range(33, 44) if _selected(htt, x) is not None
    }
    assert len(touched) == 3, touched  # benign, uncertain and fully penetrant, from one call
    assert len(measurement_shape_warnings(htt)) == 2


def test_the_spanning_warning_states_the_withhold_placeholder() -> None:
    """The behaviour is *stated*, not left silent — that is the whole of what 0.6 ships for RM56.

    It must also say what withholding is not: falling back to the `unresolved` sentinel, which means
    no measurement was available and is a different claim about the sample.
    """
    spanning = [w for w in measurement_shape_warnings(_htt_bins()) if "span" in w]
    assert len(spanning) == 1
    assert "withholds" in spanning[0]
    assert "unresolved" in spanning[0]


def test_a_group_is_the_unit_a_measurement_could_span() -> None:
    """Two motifs at one gene are two groups, so neither one's bin count is the other's.

    `_KEY_FIELDS` makes `(gene, repeat_unit)` the group, and a measurement is of one motif — counting
    across both would report a span that no single measurement could make.
    """
    two_motifs = [
        RepeatAlleleRow(gene="HTT", repeat_unit=unit, measure_min=6, measure_max=26, conclusion="a")
        for unit in ("CAG", "CCG")
    ]
    assert len(measurement_shape_warnings(two_motifs)) == 1  # RM55 only: neither group has two bins


# ── RM58: `.` is VCF's MISSING marker, not an allele ───────────────────────────────────────────


def test_the_missing_marker_is_its_own_reason_and_not_a_notation() -> None:
    """It used to fall through to `"notation"` beside `<DEL>`, which is a false claim about the cell.

    A symbolic allele names a variant this grammar cannot spell — a gap a release may widen. `.` names
    no variant at all: the record is asserting that there is no alternate allele. Different claim,
    different consequence, so a different reason.
    """
    assert non_nucleotide_reason(MISSING_ALLELE) == "missing"
    assert non_nucleotide_reason("<DEL>") == "notation"
    assert non_nucleotide_reason("Y") == "ambiguity"
    assert non_nucleotide_reason("ACGT") is None
    # And the three stay three: a whitespace-padded cell is the same marker, not a fourth thing.
    assert non_nucleotide_reason(" . ") == "missing"


def test_the_missing_marker_is_reported_per_allele_with_its_own_reason() -> None:
    """A locus can carry the marker beside a real spelling problem; neither reason may absorb the other."""
    assert non_nucleotide_alleles("A", ".") == {".": "missing"}
    assert non_nucleotide_alleles("A", "<DEL>,.") == {"<DEL>": "notation", ".": "missing"}


def test_the_missing_marker_splits_the_variant_key_of_a_coordinate_row() -> None:
    """The identity consequence, which is what makes this the only VCF finding that reaches identity.

    Computed through the real `derive_variant_key` rather than asserted as a literal, and stated against
    an authored row, because the point is that a module writing the cell and a module leaving it empty
    describe one site and dedup against nothing.
    """
    with_marker = VariantRow(
        chrom="1", start=1, ref="A", alts=".", genotype="A/A", state="ref", conclusion="x"
    )
    without = VariantRow(
        chrom="1", start=1, ref="A", genotype="A/A", state="ref", conclusion="x"
    )
    assert with_marker.variant_key != without.variant_key
    assert without.variant_key == derive_variant_key(None, "1", 1, "A")
    # No `ga4gh:VA.…` is minted for it either — `is_substitution` refuses a non-nucleotide alt — so the
    # split is a key *string* problem and never a false content-addressed claim.
    assert not with_marker.variant_key.startswith("ga4gh:")


def test_an_rsid_row_carries_the_marker_without_the_identity_split() -> None:
    """An rsid short-circuits the key, so the cell is wrong and the identity is not — say only that."""
    row = HeteroplasmyRow(
        gene="MT-TL1", rsid="rs199474657", alts=".", reference_sequence="NC_012920.1",
        measure_min=0.1, measure_max=0.5, conclusion="x",
    )
    assert row.variant_key == "rs199474657"
    assert non_nucleotide_reason(row.alts) == "missing"


# ── RM60: `chrom` accepts the spelling most human pipelines write ──────────────────────────────


@pytest.mark.parametrize(
    "spelling, expected",
    [
        ("MT", "MT"), ("chrMT", "MT"), ("chrM", "MT"), ("M", "MT"),
        ("7", "7"), ("chr7", "7"), ("CHR7", "7"), ("x", "X"), ("chrY", "Y"),
    ],
)
def test_every_accepted_spelling_stores_the_declared_member(spelling: str, expected: str) -> None:
    """What is stored is the member, never the author's spelling — the `match_vocab` property.

    That is what makes the widening safe: nothing downstream ever sees two spellings of one contig, so
    no key, signature or join can split on it.
    """
    row = VariantRow(
        chrom=spelling, start=3243, ref="A", alts="G", genotype="A", state="risk", conclusion="x"
    )
    assert row.chrom == expected
    assert row.chrom in VALID_CHROMOSOMES


def test_the_gate_and_the_normalizer_now_agree() -> None:
    """The finding was that two normalizers in one package disagreed and the stricter one was the gate.

    Discovered by *behaviour* over the members rather than from a list, so a future contig cannot be
    added to one and missed by the other.
    """
    for member in sorted(VALID_CHROMOSOMES):
        for spelling in (member, f"chr{member}", member.lower()):
            row = VariantRow(
                chrom=spelling, start=1, ref="A", alts="G", genotype="A", state="risk",
                conclusion="x",
            )
            assert row.chrom == normalize_chrom(spelling) == member


@pytest.mark.parametrize(
    "rejected",
    ["GL000009.2", "chrUn_KI270302v1", "HLA-A*01:01:01:01", "23", "chrEBV", ""],
)
def test_an_off_assembly_contig_is_still_refused(rejected: str) -> None:
    """Widening only means widening *only*: scaffolds, patches, decoys and alt contigs stay out.

    `REFGET_GRCh38` is primary assembly only, so accepting one would let a module mint an identity
    against a sequence the format has no accession for.
    """
    with pytest.raises(ValueError):
        VariantRow(
            chrom=rejected, start=1, ref="A", alts="G", genotype="A", state="risk", conclusion="x"
        )

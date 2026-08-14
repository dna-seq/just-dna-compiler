"""Two rules that were true of the code and absent from the strings the code prints.

`describe`, `requirements` and `reference` render `Field(description=...)` verbatim, so a description
is the authoring contract rather than internal commentary — the lesson the 0-vs-1-based `start`
docstring cost 3,038 rows to learn, and pinned for that column in `test_coordinate_convention.py`.
Two 0.6 findings landed just short of it:

* **RM63** corrected what a pipe in a genotype means, in a comment above the shared validator. The
  validator accepts `A|G`, the compiler materializes and round-trips `phased`, and the printed
  description said only "Slash-separated sorted alleles, e.g. A/G" — so the pipe form, and the
  hemizygous single-allele form beside it, were supported and undescribed.
* **RM62** established that a VCF `Float` is 32-bit and an inclusive non-dyadic `measure_max` can be
  missed by a value that reads as equal in the source file. It reached `docs/SCHEMAS.md` and not the
  column the author fills in.

Both halves are pinned the same way round as the coordinate tests: the *behaviour* first — what the
validator accepts, what float32 does to a real authored bound — and only then the requirement that
the prose agree with it. Writing them down that way turned up two claims that were not quite true and
would have been printed: RM62's error runs in **both** directions (`float32(0.9)` is *below* `0.9`, so
`measure_min` is not the harmless half and narrowing only the upper bound has its own failure), and
RM63's "read a pipe as heterozygous" is false of `C|C`, an ordinary phased homozygous call the grammar
accepts. The printed strings state the narrower, true versions.
"""

from __future__ import annotations

import csv
import struct
from pathlib import Path

import pytest
from just_dna_format.binning import HeteroplasmyRow, MeasureBinRow
from just_dna_format.pgx import PharmVariantRow
from just_dna_format.reference import authoring_reference
from just_dna_format.spec import VariantRow
from pydantic import ValidationError

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _described(model_name: str, field: str) -> str:
    """The description as an author actually receives it, off the generated reference surface."""
    fields = authoring_reference()["models"][model_name]
    return next(f for f in fields if f["name"] == field)["description"]


# ── RM63: the genotype grammar has three shapes and the contract named one ──────────────────────


def _variant(genotype: str) -> VariantRow:
    return VariantRow(
        rsid="rs1799945",
        chrom="6",
        start=26091179,
        ref="C",
        alts="G",
        genotype=genotype,
        state="risk",
        conclusion="HFE H63D.",
    )


def test_the_genotype_grammar_accepts_three_shapes() -> None:
    """The ground truth: unphased pair, phased pair, and a lone allele all load."""
    assert _variant("C/G").genotype == "C/G"
    assert _variant("C|G").genotype == "C|G"
    assert _variant("G").genotype == "G"

    # The shared validator on `AuthoredModel`, so the PGx column has the same three shapes.
    for genotype in ("C/G", "C|G", "G"):
        pharm = PharmVariantRow(
            rsid="rs1799945",
            genotype=genotype,
            drug="warfarin",
            conclusion="Standard dosing.",
        )
        assert pharm.genotype == genotype


def test_the_phased_pair_is_the_one_shape_left_unsorted() -> None:
    """`G/C` is refused as unsorted while `G|C` is kept — the asymmetry an author meets first, and
    the reason the description has to say what the retained order does and does not assert."""
    assert _variant("G|C").genotype == "G|C"
    with pytest.raises(ValidationError, match="sorted"):
        _variant("G/C")


def test_every_accepted_genotype_shape_is_named_in_the_printed_description() -> None:
    """A shape the validator accepts and the contract omits is a shape no author writes."""
    for model, example in (("VariantRow", "A|G"), ("PharmVariantRow", "C|T")):
        described = _described(model, "genotype")
        assert example in described, f"{model} never shows the phased form"
        assert "hemizygous" in described, f"{model} never shows the single-allele form"
        assert "/" in described


def test_the_description_carries_RM63s_reading_rather_than_the_overclaim_it_replaced() -> None:
    """VCF orders alleles only *within* a phase set (§1.6.2 adds PSL for exactly that reason) and this
    format has no phase-set column, so a pipe records that the call was phased and names no homolog.
    The corrected wording lived only in a comment above the validator; it has to be where the author
    reads it, or the silence overclaims on the comment's behalf.
    """
    for model in ("VariantRow", "PharmVariantRow"):
        described = _described(model, "genotype")
        assert "phase recorded but unaddressable" in described, model
        assert "names no homolog" in described, model

    # The module-level answer for cis/trans is a different table, and the SNP core's description says
    # which one rather than leaving an author to infer that a pipe will do.
    assert "diplotypes.csv" in _described("VariantRow", "genotype")


def test_the_reading_is_about_the_homolog_and_not_about_zygosity() -> None:
    """`1|1` is an ordinary phased homozygous VCF call, and the grammar accepts its transcription.

    RM63's sentence in `base.py` reads "heterozygous, phase recorded but unaddressable", and the
    heterozygous half is incidental to the correction — what a pipe cannot do is name a homolog.
    Carried onto the printed contract verbatim it would instruct a consumer to call `C|C`
    heterozygous, which is a false claim on exactly the surface this file exists to keep true.
    """
    assert _variant("C|C").genotype == "C|C"
    for model in ("VariantRow", "PharmVariantRow"):
        assert "heterozygous, phase" not in _described(model, "genotype"), model


# ── RM62: a 32-bit measurement against a 64-bit inclusive bound ─────────────────────────────────


def _authored_bounds() -> list[tuple[float | None, float | None]]:
    """Every bin the heteroplasmy example actually authors, as `(measure_min, measure_max)`."""
    text = (_EXAMPLES / "mt_heteroplasmy" / "heteroplasmy.csv").read_text().splitlines()
    return [
        (
            float(r["measure_min"]) if r["measure_min"] else None,
            float(r["measure_max"]) if r["measure_max"] else None,
        )
        for r in csv.DictReader(text)
    ]


def _as_float32(value: float) -> float:
    """What a VCF `Float` cell carrying this decimal reads as once widened back to float64."""
    return struct.unpack("f", struct.pack("f", value))[0]


def test_a_float32_measurement_overshoots_a_real_authored_upper_bound() -> None:
    """The defect, on the corpus's own numbers rather than an invented one.

    A consumer reading `FORMAT/AF` gets a 32-bit float. Widening it to float64 is exact, but it is
    not value-preserving against the decimal the author typed: the nearest float32 to `0.3` is
    0.300000011920928955…, so a source file whose cell reads `0.3` compares as strictly greater than
    an inclusive bound of `0.3`, and the row a consumer should have matched is missed.
    """
    missed = [hi for _, hi in _authored_bounds() if hi is not None and _as_float32(hi) > hi]
    assert missed, "mt_heteroplasmy no longer carries a non-dyadic inclusive upper bound"

    for bound in missed:
        measured = _as_float32(bound)  # the source file's own cell, read as VCF says to read it
        assert not measured <= bound, "the naive comparison would have matched"
        assert measured <= _as_float32(bound), "comparing in float32 recovers the row"
        # An epsilon is the reflex and the rule refuses it: the gap is the representation error, not
        # a chosen tolerance, and it scales with the bound rather than being one constant.
        assert measured - bound < abs(bound) * 2**-23 + 2**-149


def test_the_error_runs_both_ways_so_neither_bound_is_the_safe_one() -> None:
    """`measure_min` is *not* the harmless half, and this is why the rule is "compare in float32"
    rather than "narrow the upper bound".

    `float32(0.3)` is above `0.3` and `float32(0.9)` is below `0.9` — both are ordinary
    allele-fraction thresholds. Upward, an inclusive `measure_max` misses the value; downward, a
    `measure_min` drops it into the bin beneath. Narrowing *one* side has its own failure: against a
    measurement that never went through float32, a narrowed downward-rounding bound rejects a value
    the naive comparison would have matched, which is RM62's own defect pointed the other way.
    """
    up, down = 0.3, 0.9
    assert _as_float32(up) > up and _as_float32(down) < down

    # Upward: the inclusive top of [0.1, 0.3] is missed.
    assert not _as_float32(up) <= up
    # Downward: the inclusive bottom of [0.9, 1.0] is missed, the same way.
    assert not _as_float32(down) >= down
    # Comparing in float32 — both sides narrowed — is exact in both directions, because float32
    # rounding is monotone: a measurement below the bound stays below it.
    assert _as_float32(up - 0.01) <= _as_float32(up)
    assert _as_float32(down + 0.01) >= _as_float32(down)
    # Narrowing only the bound is the rule that breaks: a float64-precise 0.9 — a consumer that
    # parsed the text cell straight to float64 — falls out of a bin whose inclusive upper bound is
    # 0.9, which the naive comparison would have matched.
    assert not down <= _as_float32(down)
    # And narrowing *both* sides is a narrowing rather than an identity, so it is stated as "compare
    # in float32" and not as an exact equivalence: a float64-precise value just above the bound is
    # admitted, which is the direction to err in for an inclusive bound.
    assert _as_float32(0.30000000000000004) == _as_float32(up)


def test_a_dyadic_bound_is_unaffected_in_either_direction() -> None:
    """`0.0`, `0.5`, `1.0` are exactly representable, so the rule is about which decimals an author
    writes rather than about every bound."""
    row = HeteroplasmyRow(
        chrom="MT", start=3243, ref="A", alts="G", gene="MT-TL1",
        reference_sequence="NC_012920.1", tissue="blood", measure_kind="allele_fraction",
        measure_min=0.5, measure_max=1.0, conclusion="MELAS spectrum.",
    )
    assert row.measure_min is not None and _as_float32(row.measure_min) == row.measure_min
    assert row.measure_max is not None and _as_float32(row.measure_max) == row.measure_max


def test_the_narrowing_rule_reaches_the_column_an_author_fills_in() -> None:
    """RM62 is a rule about authoring and comparing a bound, and it reached only `docs/SCHEMAS.md`.

    It belongs on `measure_max`, which is where it bites, and it must say *narrow* rather than leave
    the reader to reach for an epsilon — an epsilon is a guess about magnitude where the
    representation is exactly known.
    """
    described = MeasureBinRow.model_fields["measure_max"].description or ""
    assert "float32" in described
    assert "narrow" in described
    assert "epsilon" in described

    # It reaches every kind, because the column is declared once on the base and no subclass
    # redeclares it — the four binning tables an author picks between must all say the same thing.
    for kind in ("HeteroplasmyRow", "RepeatAlleleRow", "CopyNumberRow", "ActivityPhenotypeRow"):
        assert _described(kind, "measure_max") == described

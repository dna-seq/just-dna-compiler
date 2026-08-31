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
import re
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


def test_every_authored_field_carries_a_description() -> None:
    """A field an author must fill and cannot read about is undocumented, not self-evident (S63).

    `describe`, `requirements` and `reference` render `Field(description=...)` verbatim, so a blank
    one is not "no comment needed" — it is the authoring surface saying nothing at the moment the
    author is filling that cell. The three found by the report were `ModuleInfo.title`,
    `.description` and `.report_title`: the only undescribed fields in the block, and the three an
    author *must* replace before a spec validates, so the surface explained `icon_set`'s vocabulary
    and was silent about the line a browsing consumer reads first.

    Walked over `_ALL_MODELS` and asserted as an **equality**, the way the vocabulary guards above
    it are. A count or a floor would be satisfied by the state the report found, and a name list
    would not cover the next model somebody adds.
    """
    from just_dna_format.base import authored_field_names
    from just_dna_format.reference import _ALL_MODELS

    undescribed = [
        f"{name}.{field}"
        for name, model in _ALL_MODELS.items()
        for field in authored_field_names(model)
        if not (model.model_fields[field].description or "").strip()
    ]
    assert undescribed == []


def test_the_description_field_states_where_methodology_goes_instead() -> None:
    """The report's sharper half was repetition, not length, and the fix has to reach it.

    Four specs in the reporter's corpus ended with the byte-identical fifteen-word methodology
    sentence, so the field whose job is telling a module apart from its neighbours was doing the
    opposite on four cards at once. Naming the homes that *are* meant for methodology is what makes
    that actionable; saying only "keep it short" would not have.

    Deliberately **not** paired with a `max_length`: a ceiling refuses a merely verbose spec, refuses
    it after the prose is written, and would retroactively invalidate published modules that met
    every requirement that existed.
    """
    from just_dna_format.spec import ModuleInfo

    text = ModuleInfo.model_fields["description"].description
    assert "weighting:" in text and "authorship:" in text and "README.md" in text
    assert ModuleInfo.model_fields["description"].metadata == [], (
        "description must carry no length constraint — see the docstring above"
    )


# ── `state`'s members have standing, and the printed list gave them none (S80) ──────────────────


def test_the_state_description_separates_current_members_from_superseded_ones() -> None:
    """The description read as six peers, so an agent picked `alt` for a heterozygote (S80).

    `derive.py` calls `alt`/`ref` **the retired descriptors** and maps both to `direction=unknown`;
    nothing in the printed string carried that, and a consumer whose authoring surface passes our
    descriptions through verbatim — which is the contract we want it to keep — therefore offered six
    equal choices. The reporter had to read `derive.py` inside their own `.venv` to author one cell
    honestly.

    Asserted over the vocabulary rather than against a fixed sentence: every member must appear, and
    the three still-current ones must be named as such. A test keyed on the exact prose would pass for
    a description that lists all six under one heading again.
    """
    from just_dna_format.spec import VALID_STATES, VariantRow

    printed = VariantRow.model_fields["state"].description or ""

    assert set(VALID_STATES) == {"risk", "protective", "neutral", "significant", "alt", "ref"}
    for member in VALID_STATES:
        assert member in printed, member
    current, superseded = printed.split("Superseded", 1)
    # Word-boundary membership, not `split()`: the printed list is comma-separated prose, so a bare
    # `.split()` leaves `risk,` and `neutral.` and the assertion silently tests nothing.
    assert {"risk", "protective", "neutral"} <= set(re.findall(r"[a-z_]+", current))
    for retired in ("significant", "alt", "ref"):
        assert retired in superseded, retired
    assert "neutral" not in re.findall(r"[a-z_]+", superseded.split(";")[0])


def test_the_three_groups_are_the_three_axes_state_conflates() -> None:
    """Not the two-way split the report asked for, and the difference is load-bearing.

    `state` is the Principle 5 anti-pattern the charter names by hand: one field carrying statistical
    significance, effect direction and a genotype descriptor. `significant` is not retired the way
    `alt`/`ref` are — it makes a real claim that `direction` cannot express and `stat_significance`
    owns — so grouping it with them would tell an author it means nothing, when it means something
    this column is the wrong place for. `derive.py` is the evidence: `alt`/`ref` carry no direction
    at all, while `significant` is refined from the weight sign before falling back.
    """
    from just_dna_format.derive import _STATE_TO_DIRECTION, _STATE_TO_STAT_SIGNIFICANCE
    from just_dna_format.spec import VariantRow

    # The behaviour first: what each group actually derives to.
    assert _STATE_TO_DIRECTION["alt"] == _STATE_TO_DIRECTION["ref"] == "unknown"
    assert _STATE_TO_STAT_SIGNIFICANCE["alt"] == _STATE_TO_STAT_SIGNIFICANCE["ref"] == "unknown"
    assert _STATE_TO_STAT_SIGNIFICANCE["significant"] == "significant"
    assert _STATE_TO_DIRECTION["significant"] == "unknown"

    # Then that the printed string names each group's successor, since a standing with no destination
    # is a warning nobody can clear — P3's own test for whether a deprecation belongs in a minor.
    printed = VariantRow.model_fields["state"].description or ""
    assert "stat_significance" in printed
    assert "direction" in printed


def test_no_shipped_example_uses_a_superseded_member() -> None:
    """The usage evidence the report measured, recomputed here rather than copied from it.

    377 `risk` and 4 `neutral` across the sixteen reference examples; `significant`, `alt` and `ref`
    appear zero times. That is what made the flat list actively misleading — it gave equal standing to
    values no shipped example uses. Recomputed at runtime, so the assertion is the *relationship*
    (nothing superseded is in the corpus) rather than the counts, which are free to move.
    """
    from just_dna_format.spec import VariantRow

    root = Path(__file__).resolve().parents[2] / "reference_examples"
    used: set[str] = set()
    for path in sorted(root.glob("*/variants.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if (value := (row.get("state") or "").strip()):
                    used.add(value)

    assert used, "no reference example authored a `state` cell — the corpus moved"
    assert not used & {"significant", "alt", "ref"}
    printed = VariantRow.model_fields["state"].description or ""
    # And every value the corpus does use is on the current side of the printed split.
    assert used <= set(re.findall(r"[a-z_]+", printed.split("Superseded", 1)[0]))


# ── `direction` and `stat_significance` are one pair, and the description says so (S83) ─────────


def test_the_direction_description_says_a_weak_trend_still_has_a_sign() -> None:
    """Two runs of one prompt split `risk`/`unknown` on a concordant non-significant trend (S83).

    The old text named the four members and said only *orthogonal to `state`*. Both readings were
    defensible against it, which is the definition of a description that does not settle the question
    an author is actually asking: is a sign you cannot lean on still a sign?

    Asserted as *the pair is named together*, not as an exact sentence — a test keyed on the prose
    passes for a rewrite that drops the half doing the work.
    """
    from just_dna_format.spec import VariantRow

    printed = VariantRow.model_fields["direction"].description or ""

    # The reading: the sign is recorded regardless, and the other column carries the confidence.
    assert "stat_significance" in printed
    assert "established" in printed
    # And `unknown` is bounded, since absorbing "not established" is what made the two runs equal.
    assert "unknown" in printed


def test_the_two_columns_stay_independent_vocabularies() -> None:
    """The behaviour behind the prose: neither vocabulary borrows a member from the other.

    If `direction` ever gained a member meaning *looked, no sign established*, it would be a second
    spelling of `stat_significance`'s job — P5's overloading arriving as a synonym. Asserted as
    disjointness over the walked sets rather than by naming members, so a future addition to either
    side has to face the question deliberately.
    """
    from just_dna_format.vocab import VALID_DIRECTIONS, VALID_SIGNIFICANCE

    assert {"protective", "risk", "neutral", "unknown"} == VALID_DIRECTIONS
    assert {"significant", "suggestive", "not_significant", "unknown"} == VALID_SIGNIFICANCE
    # `unknown` is the one shared member, and it means the same thing on both: nothing to record.
    assert {"unknown"} == VALID_DIRECTIONS & VALID_SIGNIFICANCE


def test_the_reported_pair_is_expressible_without_a_new_member() -> None:
    """The reporter's case, authored: a real sign the evidence does not establish.

    `direction=risk` with `stat_significance=not_significant` is the state they wanted a member for,
    and it already validates — which is the answer to the ask. Round-tripped through the model rather
    than asserted about it, so the claim is that the pair is *authorable*, not merely that both
    vocabularies contain the words.
    """
    from just_dna_format.spec import VariantRow

    row = VariantRow(
        rsid="rs117385980",
        genotype="C/T",
        state="risk",
        conclusion="T allele depleted among the longest-lived; interval contains the null",
        direction="risk",
        stat_significance="not_significant",
        effect_size=3.58,
        effect_measure="OR",
    )
    assert (row.direction, row.stat_significance) == ("risk", "not_significant")
    # And the counter-direction has its own home, which is why the row is not self-contradictory.
    assert "negatives" in VariantRow.model_fields

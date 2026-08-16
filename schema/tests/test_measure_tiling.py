"""RM55's fix: tiling is its own axis, and a fractional measurement finally lands in a bin.

The finding these pin is in `test_vcf_measure_shape.py`, which demonstrates that a whole-number
tiling answers nothing for a 2.4 and that the schema *also refused the tiling that would fix it*.
This file is the other side: the effective tiling every rule now reads, the two notices the
resolution emits, and the companion float column for the one genuine `int`.

Expected values are computed from the models and the published default table rather than restated,
so a sixth measure kind or a changed default fails here instead of quietly passing.
"""

import pytest
from just_dna_format.binning import (
    DEFAULT_MEASURE_TILING,
    DEPRECATED_MODIFIER_PHRASE,
    FRACTIONAL_MEASURE_PHRASE,
    VALID_MEASURE_KINDS,
    VALID_MEASURE_TILINGS,
    ActivityPhenotypeRow,
    CopyNumberRow,
    HeteroplasmyRow,
    MeasureBinRow,
    RepeatAlleleRow,
    deprecation_warnings,
    measurement_shape_warnings,
    resolve_tiling,
    validate_bins,
)


def _selected(rows, x: float):
    """The bin the documented consumer rule selects for `x`, or None for 'no matching bin'.

    The same helper `test_vcf_measure_shape.py` carries, and for the same reason: the lookup rule
    lives in the consumer contract, so the only honest way to show a value is answered is to run it.
    """
    candidates = [r for r in rows if r.measure_min is not None and r.measure_min <= x]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: r.measure_min)
    if best.measure_max is not None and x > best.measure_max:
        return None
    return best


def _one_row_of(kind: str, **over) -> MeasureBinRow:
    """A single legal bin of each kind, so the resolution table can be exercised per kind."""
    common = {"measure_min": 0.0, "measure_max": 1.0, "conclusion": "x", **over}
    if kind == "activity_score":
        return ActivityPhenotypeRow(gene="CYP2D6", **common)
    if kind == "copy_number":
        return CopyNumberRow(gene="SMN1", **common)
    if kind == "repeat_count":
        return RepeatAlleleRow(gene="HTT", repeat_unit="CAG", **common)
    if kind == "allele_fraction":
        return HeteroplasmyRow(gene="MT-TL1", reference_sequence="NC_012920.1", **common)
    if kind == "prs_percentile":
        # The one member of the vocabulary with no subclass and so no table kind of its own — it is
        # reachable only on the base. Built here rather than skipped, because the default table must
        # answer for every *kind*, not only for every table.
        return MeasureBinRow(measure_kind=kind, **common)
    raise AssertionError(f"no fixture for measure_kind {kind!r} — add one when the kind is added")


# ── The resolution table ───────────────────────────────────────────────────────────────────────


def test_every_measure_kind_has_a_default_tiling_and_it_is_a_legal_answer() -> None:
    """The registry-completeness shape, and the key check alone would not be it.

    `DEFAULT_MEASURE_TILING` is a comprehension over `VALID_MEASURE_KINDS`, so its *keys* match by
    construction and asserting only that proves nothing. What can go wrong is the **value**: a sixth
    kind added to the vocabulary and to none of the three sets that build the table falls through to
    `None`, i.e. is silently read the way `activity_score` is — no gap warning, a shared endpoint an
    error — which is a decision nobody made. So the set that resolves to *neither* is pinned to the
    one kind that means it, and a new kind has to be placed deliberately or fail here.
    """
    assert set(DEFAULT_MEASURE_TILING) == VALID_MEASURE_KINDS
    for kind, tiling in DEFAULT_MEASURE_TILING.items():
        assert tiling is None or tiling in VALID_MEASURE_TILINGS, kind
    assert {k for k, v in DEFAULT_MEASURE_TILING.items() if v is None} == {"activity_score"}


@pytest.mark.parametrize("kind", sorted(VALID_MEASURE_KINDS))
def test_an_undeclared_group_resolves_to_its_kinds_default(kind: str) -> None:
    """Absence means the kind's default, never a value — the clause that keeps the column additive.

    `activity_score` is the one that resolves to **neither**, which is not an oversight: it is the
    third behaviour (no gap warning, a shared endpoint is an overlap) preserved exactly.
    """
    resolution = resolve_tiling([_one_row_of(kind)])
    assert resolution.declared is None
    assert resolution.value == DEFAULT_MEASURE_TILING[kind] == resolution.default
    assert not resolution.inferred and not resolution.contradicted
    if kind == "activity_score":
        assert resolution.value is None


@pytest.mark.parametrize("declared", sorted(VALID_MEASURE_TILINGS))
@pytest.mark.parametrize("kind", sorted(VALID_MEASURE_KINDS))
def test_a_declaration_wins_over_the_default_on_every_kind(kind: str, declared: str) -> None:
    """Including against `activity_score`'s `None`, which is a default like any other."""
    resolution = resolve_tiling([_one_row_of(kind, measure_tiling=declared)])
    assert resolution.value == resolution.declared == declared


def test_a_fractional_value_moves_a_quantised_group_and_leaves_the_others_alone() -> None:
    """The inference fires against the reading a fraction **contradicts**, and only that one.

    `quantised` asserts a step — that assertion is what lets the gap rule tolerate a hole of one —
    and a fractional bound falsifies it. `continuous` is already what the evidence would say, and
    `activity_score`'s `None` asserts nothing about the grid at all: the score is summed onto a grid
    whose step this schema does not know, which is exactly why it reports no interior hole. Reading
    a fractional activity score as continuous invents findings — `cyp2d6_structural`'s real bins at
    0.25/0.5/1.25/2.25 produce three "coverage gap" lines for intervals no score can land in — so
    the rule is *the data contradicts the reading*, not *the data is fractional*.
    """
    for kind in sorted(VALID_MEASURE_KINDS):
        fractional = resolve_tiling([_one_row_of(kind, measure_max=0.5)])
        if DEFAULT_MEASURE_TILING[kind] == "quantised":
            assert fractional.value == "continuous"
            assert fractional.inferred
        else:
            assert fractional.value == DEFAULT_MEASURE_TILING[kind]
            assert not fractional.inferred


def test_a_fractional_modifier_dosage_is_not_evidence_about_the_tiled_axis() -> None:
    """The modifier is a *group-key* column: it says which table you are in, not where a point sits.

    On `copynumbers.csv` the tiled axis is the SMN1 copy number and the SMN2 dosage is the condition
    the bins are read under, so a fractional SMN2 value contradicts nothing about how the SMN1 axis
    is divided — which is the rule the inference actually runs on. "It is a copy number too, so
    surely it counts" is the obvious wrong repair, and it was in the first cut of this lane; the two
    behaviours below are why it came out.
    """
    def bins(dosage: float, spans):
        return [
            CopyNumberRow(
                gene="SMN1", modifier_gene="SMN2", modifier_copy_number=dosage,
                measure_min=lo, measure_max=hi, conclusion="x",
            )
            for lo, hi in spans
        ]

    assert resolve_tiling(bins(2.5, [(0, 0)])).value == "quantised"
    assert resolve_tiling(bins(2.5, [(0, 0)])).fractional is None

    # **No legality flip.** One identical pair of bins must get one verdict, whatever an unrelated
    # key column happens to hold — letting the dosage vote made 2.0 refuse and 2.5 accept.
    for dosage in (2.0, 2.5):
        with pytest.raises(ValueError, match="overlapping bins"):
            validate_bins(bins(dosage, [(1, 2), (2, 3)]))

    # **No invented gaps.** Genuinely integral bounds under a fractional dosage tile exactly; read
    # as continuous they reported three holes no copy number can land in — the same false-positive
    # class `activity_score` is protected from, arriving through a different door.
    sharp = bins(2.5, [(0, 0), (1, 1), (2, 2), (3, None)])
    assert [w for w in validate_bins(sharp) if "coverage gap" in w] == []


def test_a_whole_number_says_nothing_about_the_tiling() -> None:
    """The asymmetry the whole design rests on: fractional-ness is evidence, integer-ness is not.

    `[0,1] [2,3]` is exactly what a genuinely continuous measure looks like when its author has only
    ever seen whole-number data, so a derivation-only mechanism would read it the wrong way with no
    way for the curator to object. Hence the column for the claim and the inference for the case the
    data has already settled.
    """
    rows = [
        HeteroplasmyRow(
            gene="MT-TL1", reference_sequence="NC_012920.1", measure_min=lo, measure_max=hi,
            conclusion="x", measure_tiling="quantised",
        )
        for lo, hi in ((0, 0), (1, 1))
    ]
    assert resolve_tiling(rows).value == "quantised"


# ── Group agreement ────────────────────────────────────────────────────────────────────────────


def test_two_rows_of_one_group_may_not_declare_different_tilings() -> None:
    """The rules run per group, so a group has one tiling or it has none it can run under."""
    rows = [
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi, conclusion="x",
            measure_tiling=tiling,
        )
        for (lo, hi), tiling in (((6, 26), "quantised"), ((27, 35), "continuous"))
    ]
    with pytest.raises(ValueError, match="conflicting measure_tiling"):
        validate_bins(rows)


def test_an_empty_cell_beside_a_declaration_is_absence_and_not_disagreement() -> None:
    """`None` is never a value — the house algebra, applied to the one place it would bite here.

    An author declaring the tiling once and leaving the column blank on the rest of the group has
    stated one tiling, not two.
    """
    rows = [
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi, conclusion="x",
            measure_tiling=tiling,
        )
        for (lo, hi), tiling in (((6, 26), "continuous"), ((26, 35), None))
    ]
    assert resolve_tiling(rows).declared == "continuous"
    # …and the shared endpoint at 26 is a boundary rather than an overlap, which is the point of
    # having declared it: on the kind's own default this pair refuses.
    assert validate_bins(rows) == []
    assert resolve_tiling([r.model_copy(update={"measure_tiling": None}) for r in rows]).value == (
        "quantised"
    )


def test_two_groups_may_disagree_with_each_other() -> None:
    """The constraint is *within* a group. A module carrying a quantised catalog count and a
    continuous segment mean for two different genes is not hypothetical."""
    rows = [
        CopyNumberRow(
            gene=gene, measure_min=0, measure_max=1, conclusion="x", measure_tiling=tiling,
        )
        for gene, tiling in (("SMN1", "quantised"), ("CYP2D6", "continuous"))
    ]
    assert validate_bins(rows) == []


# ── The two notices ────────────────────────────────────────────────────────────────────────────


def test_the_inference_announces_itself_and_names_the_value_that_triggered_it() -> None:
    """An inference a reader cannot see is what this repo distrusts about inference."""
    rows = [
        CopyNumberRow(gene="SMN1", measure_min=0, measure_max=2.5, conclusion="low"),
        CopyNumberRow(gene="SMN1", measure_min=2.5, conclusion="high"),
    ]
    notices = [w for w in validate_bins(rows) if "tiling inferred" in w]
    assert len(notices) == 1
    assert "2.5" in notices[0]
    assert "continuous" in notices[0]
    # And it names the rules it applied, because that is what changed about the reading.
    assert "share an endpoint" in notices[0] and "hole" in notices[0]


def test_a_declared_quantised_beside_a_fractional_value_warns_and_still_stands() -> None:
    """Neither side silently overrides the other — the three-valued algebra's whole point here.

    The declaration wins (a shared endpoint is still an overlap, and it is refused below), and the
    contradiction is *said*.
    """
    rows = [
        CopyNumberRow(
            gene="SMN1", measure_min=0, measure_max=2.5, conclusion="low",
            measure_tiling="quantised",
        )
    ]
    resolution = resolve_tiling(rows)
    assert resolution.value == "quantised"
    assert resolution.contradicted
    contradictions = [w for w in validate_bins(rows) if "contradicts it" in w]
    assert len(contradictions) == 1
    assert "2.5" in contradictions[0]

    # The declaration standing is observable and not just recorded: a shared endpoint still refuses.
    touching = rows + [
        CopyNumberRow(
            gene="SMN1", measure_min=2.5, conclusion="high", measure_tiling="quantised",
        )
    ]
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins(touching)


# ── The rules the tiling drives ────────────────────────────────────────────────────────────────


def test_a_fractional_bound_gets_its_boundaries_answered_and_gains_no_spurious_gap() -> None:
    """The widening, demonstrated end to end on the shape RM55 says is unworkaroundable today.

    A `measure_min=2.5` copy-number row already loads (the bounds have been floats since 0.4 and
    nothing checks integrality), so nothing that validated stops validating. What changes is that
    the tiling it forces is the one that can answer it: the two bins may share 2.5, the consumer rule
    selects the higher one there, and no coverage gap is reported between them.
    """
    rows = [
        CopyNumberRow(gene="SMN1", measure_min=0, measure_max=2.5, conclusion="low"),
        CopyNumberRow(gene="SMN1", measure_min=2.5, measure_max=4, conclusion="high"),
    ]
    assert resolve_tiling(rows).value == "continuous"
    assert [w for w in validate_bins(rows) if "coverage gap" in w] == []
    for probe in (0.0, 1.4, 2.4, 2.5, 2.6, 4.0):
        assert _selected(rows, probe) is not None, probe
    assert _selected(rows, 2.5).conclusion == "high"

    # …where the same pair, declared quantised, is exactly the refusal RM55 names as the half that
    # makes the defect unworkaroundable.
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins([r.model_copy(update={"measure_tiling": "quantised"}) for r in rows])


def test_a_declared_continuous_repeat_table_reports_the_hole_a_grid_hides() -> None:
    """The gap rule follows the tiling too, which is the half the roadmap entry named.

    HTT's `[6,26] [27,35]` is gapless on a grid of whole numbers and strands every count in `(26,27)`
    once `RUC` is a Float. Declaring the tiling is what makes the check able to say so.
    """
    def bins(tiling):
        return [
            RepeatAlleleRow(
                gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi, conclusion="x",
                measure_tiling=tiling,
            )
            for lo, hi in ((6, 26), (27, 35))
        ]

    assert [w for w in validate_bins(bins("quantised")) if "coverage gap" in w] == []
    holes = [w for w in validate_bins(bins("continuous")) if "coverage gap" in w]
    assert len(holes) == 1 and "(26.0, 27.0)" in holes[0]


def test_activity_score_keeps_its_third_behaviour() -> None:
    """Neither dense nor gap-checked, and both halves are asserted so neither can drift alone."""
    assert DEFAULT_MEASURE_TILING["activity_score"] is None
    gapped = [
        ActivityPhenotypeRow(gene="CYP2D6", measure_min=lo, measure_max=hi, conclusion="x")
        for lo, hi in ((0.0, 0.25), (1.25, 2.0))
    ]
    assert [w for w in validate_bins(gapped) if "coverage gap" in w] == []
    touching = [
        ActivityPhenotypeRow(gene="CYP2D6", measure_min=lo, measure_max=hi, conclusion="x")
        for lo, hi in ((0.0, 1.0), (1.0, 2.0))
    ]
    with pytest.raises(ValueError, match="overlapping bins"):
        validate_bins(touching)


# ── The RM55 warning, now conditional ──────────────────────────────────────────────────────────


def test_the_rm55_warning_is_silent_on_a_continuous_table_and_fires_on_a_quantised_one() -> None:
    """Its central claim — green and silently unanswerable at every boundary — stops being true
    of a table whose effective tiling is continuous, so the sentence must stop being said there."""
    def bins(tiling):
        return [
            RepeatAlleleRow(
                gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi, conclusion="x",
                measure_tiling=tiling,
            )
            for lo, hi in ((6, 26), (27, 35))
        ]

    assert [w for w in measurement_shape_warnings(bins(None)) if FRACTIONAL_MEASURE_PHRASE in w]
    assert not [
        w for w in measurement_shape_warnings(bins("continuous")) if FRACTIONAL_MEASURE_PHRASE in w
    ]
    # An inferred continuous reading silences it for the same reason a declared one does.
    inferred = [
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_min=lo, measure_max=hi, conclusion="x",
        )
        for lo, hi in ((6.0, 26.5), (26.5, 35.0))
    ]
    assert resolve_tiling(inferred).value == "continuous"
    assert not [
        w for w in measurement_shape_warnings(inferred) if FRACTIONAL_MEASURE_PHRASE in w
    ]


def test_a_declared_quantised_group_keeps_the_warning_even_beside_a_fraction() -> None:
    """Because the declaration stands, and under it the value really does sit between two bins.

    This is the branch someone will "fix" later: the contradiction warning is not a substitute for
    the RM55 line, it is a second thing to say about the same rows.
    """
    rows = [
        CopyNumberRow(
            gene="SMN1", measure_min=0, measure_max=2.5, conclusion="x",
            measure_tiling="quantised",
        )
    ]
    assert [w for w in measurement_shape_warnings(rows) if FRACTIONAL_MEASURE_PHRASE in w]


def test_the_warning_is_still_per_kind_and_not_per_group() -> None:
    """Conditional does not mean per-group: one quantised group is enough, and two are not two
    lines. The finding is about how the kind's axis is divided, and the sentence is the same."""
    rows = [
        CopyNumberRow(gene=gene, measure_min=0, measure_max=1, conclusion="x")
        for gene in ("SMN1", "SMN2", "CYP2D6")
    ]
    assert len([w for w in measurement_shape_warnings(rows) if FRACTIONAL_MEASURE_PHRASE in w]) == 1


# ── The companion float column ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cn, copy_number, expected",
    [
        (None, None, None),
        (2, None, 2.0),
        (None, 2.5, 2.5),
        # The one that catches an `or`-instead-of-`is not None` coalesce. SMN2 = 0 copies is a real
        # dosage, and a truthiness fallback reads it as unset.
        (0, None, 0.0),
        (None, 0.0, 0.0),
    ],
)
def test_the_effective_dosage_coalesces_including_at_zero(
    cn: int | None, copy_number: float | None, expected: float | None
) -> None:
    gene = "SMN2" if (cn is not None or copy_number is not None) else None
    row = CopyNumberRow(
        gene="SMN1", modifier_gene=gene, modifier_cn=cn, modifier_copy_number=copy_number,
        measure_min=0, measure_max=0, conclusion="x",
    )
    assert row.effective_modifier_copy_number == expected


def test_the_effective_dosage_is_a_fixed_point() -> None:
    """P7's idempotency clause: a read-time alias returns a set column unchanged.

    Free for a coalesce and still owed, because "free" is an argument and this is a check.
    """
    row = CopyNumberRow(
        gene="SMN1", modifier_gene="SMN2", modifier_cn=3,
        measure_min=0, measure_max=0, conclusion="x",
    )
    materialized = row.model_copy(
        update={"modifier_cn": None, "modifier_copy_number": row.effective_modifier_copy_number}
    )
    assert materialized.effective_modifier_copy_number == row.effective_modifier_copy_number


def test_setting_both_dosage_columns_is_an_error() -> None:
    """Two spellings that can disagree, with a rule for picking a winner, is the `vrs_id` desync
    shape. Refusing is the same move the half-filled modifier pair already gets."""
    with pytest.raises(ValueError, match="two spellings of one dosage"):
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_cn=2, modifier_copy_number=2.0,
            measure_min=0, measure_max=0, conclusion="x",
        )


@pytest.mark.parametrize("column", ["modifier_cn", "modifier_copy_number"])
def test_the_modifier_pair_rule_now_reads_the_effective_value(column: str) -> None:
    """Either spelling satisfies `modifier_gene`'s partner, and neither satisfies it alone."""
    CopyNumberRow(
        gene="SMN1", modifier_gene="SMN2", measure_min=0, measure_max=0, conclusion="x",
        **{column: 2},
    )
    with pytest.raises(ValueError, match="set together or both left null"):
        CopyNumberRow(
            gene="SMN1", measure_min=0, measure_max=0, conclusion="x", **{column: 2}
        )


def test_the_group_key_holds_one_spelling_of_one_dosage() -> None:
    """`_KEY_FIELDS` keys on the effective value, which is what answers the objection that a
    companion column would put two spellings of one number into a row's key.

    Two rows written the two ways are the *same* group, so their bins overlap and refuse — which is
    the correct answer and is exactly what a split key would have hidden.
    """
    assert "effective_modifier_copy_number" in CopyNumberRow._KEY_FIELDS
    assert "modifier_cn" not in CopyNumberRow._KEY_FIELDS
    rows = [
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_cn=3,
            measure_min=0, measure_max=1, conclusion="a",
        ),
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_copy_number=3.0,
            measure_min=0, measure_max=1, conclusion="b",
        ),
    ]
    with pytest.raises(ValueError, match="same lower bound|overlapping bins"):
        validate_bins(rows)


# ── The deprecation ────────────────────────────────────────────────────────────────────────────


def test_the_deprecation_is_one_line_per_table_however_many_rows_use_it() -> None:
    """A copy-number table states one dosage per modifier copy number, so a per-row line would be
    the same sentence as many times as the author wrote bins."""
    rows = [
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_cn=n,
            measure_min=0, measure_max=0, conclusion=f"SMA with SMN2={n}",
        )
        for n in (2, 3, 4)
    ]
    warnings = deprecation_warnings(rows)
    assert len(warnings) == 1
    assert DEPRECATED_MODIFIER_PHRASE in warnings[0]
    # Actionable, which is the 0.6 cadence amendment's own condition: it names the replacement, and
    # the replacement exists in this release.
    assert "modifier_copy_number" in warnings[0]
    assert "modifier_copy_number" in CopyNumberRow.model_fields
    # And it carries no count, so re-running the check on a different-sized row set cannot publish
    # two numbers for one finding. Asserted by comparing the sentences rather than by hunting digits
    # — the message legitimately names VCF 4.4 §7.2 and the 1.0 removal.
    assert deprecation_warnings(rows[:1]) == warnings


def test_nothing_is_deprecated_on_a_table_that_does_not_use_it() -> None:
    assert deprecation_warnings([_one_row_of(k) for k in sorted(VALID_MEASURE_KINDS)]) == []
    assert deprecation_warnings(
        [
            CopyNumberRow(
                gene="SMN1", modifier_gene="SMN2", modifier_copy_number=2.5,
                measure_min=0, measure_max=0, conclusion="x",
            )
        ]
    ) == []


def test_the_coalesce_does_not_move_a_published_warning_string() -> None:
    """A warning's text is an API, and re-keying onto a float would have moved it silently.

    `_KEY_FIELDS` now names `effective_modifier_copy_number`, which coalesces the deprecated `int`
    to a `float`, so every message naming the key would have turned `('SMN1', 'SMN2', 2, None)` into
    `2.0` on a module nobody edited — and `compile_module` copies its warnings into
    `manifest.compilation.warnings`. `format_group_key` normalizes the rendering, so the coalesce is
    invisible to a reader who never writes the new column and new text appears only where genuinely
    fractional data exists.
    """
    legacy = [
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_cn=2,
            measure_min=lo, measure_max=hi, conclusion="x",
        )
        for lo, hi in ((1, 1), (3, 3))
    ]
    gaps = [w for w in validate_bins(legacy) if "coverage gap" in w]
    assert len(gaps) == 1
    assert "'SMN2', 2, None)" in gaps[0], gaps[0]
    assert "2.0" not in gaps[0], gaps[0]

    # The same rows written the new way render identically — one dosage, one spelling downstream.
    modern = [r.model_copy(update={"modifier_cn": None, "modifier_copy_number": 2.0}) for r in legacy]
    assert validate_bins(modern) == gaps

    # …and a genuinely fractional dosage is still shown as one, because that is not a whole number.
    fractional = [r.model_copy(update={"modifier_copy_number": 2.5}) for r in modern]
    assert "'SMN2', 2.5, None)" in validate_bins(fractional)[0]


def test_the_deprecated_column_still_behaves_exactly_as_before() -> None:
    """Warn-only is the whole of what a deprecation in a minor may do (P3): it still reads, it still
    keys the group, and nothing about it refuses."""
    rows = [
        CopyNumberRow(
            gene="SMN1", modifier_gene="SMN2", modifier_cn=n,
            measure_min=0, measure_max=0, conclusion=f"SMA with SMN2={n}",
        )
        for n in (2, 3, 4)
    ]
    assert validate_bins(rows) == []
    assert len({tuple(getattr(r, f, None) for f in r._KEY_FIELDS) for r in rows}) == len(rows)


# ── The vocabulary itself ──────────────────────────────────────────────────────────────────────


def test_the_tiling_vocabulary_is_closed_and_reaches_every_binning_kind() -> None:
    """One optional column on the base, so all four kinds carry it — the `pmid` shape."""
    for kind in sorted(VALID_MEASURE_KINDS):
        row = _one_row_of(kind)
        assert "measure_tiling" in type(row).model_fields
    with pytest.raises(ValueError, match="measure_tiling must be one of"):
        _one_row_of("copy_number", measure_tiling="dense")


def test_the_separator_slip_stores_the_declared_member() -> None:
    """`check_vocab` canonicalizes `-`/`_`, and there is nothing to canonicalize here — asserted so
    that a future hyphenated member cannot be stored in the author's spelling."""
    assert all("_" not in m and "-" not in m for m in VALID_MEASURE_TILINGS)

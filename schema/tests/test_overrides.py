"""`overrides.csv` — the overlay's own rules, decision by decision (RM124).

Every derived sidecar was merge-not-clobber because a curator's edits lived inside it, and the price
was that re-deriving one meant deleting it and losing them. The overlay moves the edits beside the
table so the table becomes a pure build product. What that costs is a set of rules a single row has
to obey before anything is applied, and the rules are the interesting part rather than the mechanism:
which operations may go group-scoped, which column an override may not name, and what a no-op is.

**A test per decision, not per rule-line.** The two that carry the most weight are the refusals — an
empty `member` on a destructive operation, and a `field` naming the table's own key — because each of
them exists to stop a silent wrong answer rather than a crash.
"""

from __future__ import annotations

import pytest
from just_dna_format.base import field_category
from just_dna_format.overrides import (
    OVERRIDABLE_TABLES,
    VALID_OVERRIDE_OPERATIONS,
    OverrideRow,
    apply_overrides,
    overlay_coherence_errors,
)
from just_dna_format.resolution import ResolutionRow
from pydantic import ValidationError


def _row(**kwargs: object) -> OverrideRow:
    """An overlay row with the boilerplate filled, so a test names only what it is about."""
    data = {"reason": "checked against the source by hand"}
    data.update(kwargs)
    return OverrideRow.model_validate(data)


# ── the registry itself ─────────────────────────────────────────────────────────────────────────


def test_every_covered_table_names_columns_its_own_model_actually_has() -> None:
    """The registry is walked, never trusted (`@registry-completeness`).

    `subject_field` and `member_field` are column names on another model, so a rename one file over
    turns them into a lookup that silently matches nothing — an overlay that applies to no row and
    warns about it, which reads as an author's typo rather than as our bug.
    """
    for table, target in OVERRIDABLE_TABLES.items():
        assert target.subject_field in target.model.model_fields, (
            f"{table}: subject column {target.subject_field!r} is not on "
            f"{target.model.__name__}"
        )
        if target.member_field is not None:
            assert target.member_field in target.model.model_fields, (
                f"{table}: member column {target.member_field!r} is not on "
                f"{target.model.__name__}"
            )


def test_the_reason_column_is_required_and_the_rest_of_the_record_is_not() -> None:
    """`reason` is what makes the overlay a record rather than a knob, so its requiredness is the
    schema's claim and not a convention. `decided_by`/`decided_at` are deliberately optional — a
    correction with no attributable person is still a correction with a reason."""
    categories = {name: field_category(OverrideRow, name) for name in OverrideRow.model_fields}
    assert categories["reason"] == "required"
    assert categories["table"] == "required"
    assert categories["subject"] == "required"
    assert categories["operation"] == "required"
    assert {categories["decided_by"], categories["decided_at"]} == {"optional"}


def test_a_blank_reason_is_refused_by_name_rather_than_generically() -> None:
    """A present-but-empty `reason` is the authoring case: `load_csv_rows` keeps the key and maps the
    cell to `None`, so the row arrives carrying the column and nothing in it."""
    with pytest.raises(ValidationError) as exc:
        OverrideRow.model_validate(
            {
                "table": "literature.csv",
                "subject": "8696333",
                "field": "doi",
                "operation": "update",
                "value": "10.1/a",
                "reason": None,
            }
        )
    assert "needs a `reason`" in str(exc.value)


# ── the key, and the asymmetry between the operations ───────────────────────────────────────────


@pytest.mark.parametrize("operation", sorted(VALID_OVERRIDE_OPERATIONS - {"update"}))
def test_a_grouped_table_refuses_a_wildcard_member_for_everything_but_update(
    operation: str,
) -> None:
    """The decision the operations made sharp: `resolution.csv` keys a `variant_key` onto a *group*
    of loci ordered by `locus_index`, so an empty member means "all of them".

    A group-scoped *correction* is coherent and recoverable. A group-scoped *suppression* silently
    drops every locus for one key when the author almost certainly meant one, and is not recoverable
    by reading the result — the rows are simply absent. A group-scoped *insert* is worse than
    destructive, it is incoherent: the row it would create carries no member value, so nothing could
    ever match it again.
    """
    with pytest.raises(ValidationError) as exc:
        _row(
            table="resolution.csv",
            subject="rs1800562",
            operation=operation,
            **({"field": "chrom", "value": "6"} if operation == "insert" else {}),
        )
    assert "needs a member" in str(exc.value)


def test_a_wildcard_member_is_accepted_for_update_and_corrects_the_whole_group() -> None:
    """The other half of the asymmetry, and it has to be shown working rather than merely allowed."""
    override = _row(
        table="resolution.csv", subject="rs1800562", field="source", operation="update",
        value="manual",
    )
    rows = [
        ResolutionRow(variant_key="rs1800562", locus_index=0, chrom="6", start=1, source="cache"),
        ResolutionRow(variant_key="rs1800562", locus_index=1, chrom="6", start=2, source="cache"),
        ResolutionRow(variant_key="rs1799945", locus_index=0, chrom="6", start=3, source="cache"),
    ]
    after, errors, warnings = apply_overrides("resolution.csv", rows, [override])
    assert errors == [] and warnings == []
    assert [r.source for r in after] == ["manual", "manual", "cache"]


def test_a_table_whose_subject_identifies_one_row_refuses_a_member_at_all() -> None:
    """`literature.csv` keys on `pmid`, so there is no group to discriminate within and a member
    would be a value nothing could ever be compared against."""
    with pytest.raises(ValidationError) as exc:
        _row(
            table="literature.csv", subject="8696333", member="2", field="doi",
            operation="update", value="10.1/a",
        )
    assert "member is not used by literature.csv" in str(exc.value)


def test_an_override_may_not_write_the_column_it_keys_on() -> None:
    """Re-keying a derived row is a suppress plus an insert, not a correction.

    The failure this prevents is invisible on the first lap and appears only after a round trip: an
    update that moved `variant_key` would apply once, and then its own overlay row would match
    nothing on the recompile — a warning that shows up on a module's round trip and not on the
    module, which is precisely the disagreement `manifest.compilation.warnings` must never carry.
    """
    for field in ("variant_key", "locus_index"):
        with pytest.raises(ValidationError) as exc:
            _row(
                table="resolution.csv", subject="rs1800562", member="0", field=field,
                operation="update", value="whatever",
            )
        assert "keys ON" in str(exc.value)


def test_a_field_that_is_not_a_column_of_the_named_table_is_refused_with_the_column_list() -> None:
    """`@specific-rejection`: a typo'd column would otherwise apply to nothing, forever, silently."""
    with pytest.raises(ValidationError) as exc:
        _row(
            table="resolution.csv", subject="rs1800562", member="0", field="chromosome",
            operation="update", value="6",
        )
    message = str(exc.value)
    assert "'chromosome' is not a column of resolution.csv" in message
    assert "'chrom'" in message


def test_suppress_names_a_row_so_it_carries_neither_field_nor_value() -> None:
    for extra in ({"field": "chrom"}, {"value": "6"}):
        with pytest.raises(ValidationError):
            _row(
                table="resolution.csv", subject="rs1800562", member="0", operation="suppress",
                **extra,
            )


def test_one_key_group_carries_one_operation() -> None:
    """An insert is written as several rows sharing `(table, subject, member)`, one per field, so the
    key names one decision. Mixing operations under it has no defined order."""
    rows = [
        _row(table="literature.csv", subject="8696333", field="doi", operation="update",
             value="10.1/a"),
        _row(table="literature.csv", subject="8696333", operation="suppress"),
    ]
    errors = overlay_coherence_errors(rows)
    assert len(errors) == 1
    assert "more than one operation" in errors[0]


# ── applying it ─────────────────────────────────────────────────────────────────────────────────


def test_an_inserted_row_lands_at_the_end_of_its_subjects_group_in_overlay_order() -> None:
    """Row order is load-bearing — parquet bytes depend on it — so `insert` owes a placement rule,
    and the rule is a function of the overlay's own authored order rather than of a sort over values
    a later correction could move.

    Two inserts under one subject, and a third subject already present after it, so the assertion can
    tell "end of the group" from "end of the table"."""
    rows = [
        ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1),
        ResolutionRow(variant_key="rs2", locus_index=0, chrom="6", start=2),
    ]
    overlay = [
        _row(table="resolution.csv", subject="rs1", member="1", field="chrom", operation="insert",
             value="6"),
        _row(table="resolution.csv", subject="rs1", member="1", field="start", operation="insert",
             value="11"),
        _row(table="resolution.csv", subject="rs1", member="2", field="chrom", operation="insert",
             value="6"),
        _row(table="resolution.csv", subject="rs1", member="2", field="start", operation="insert",
             value="12"),
    ]
    after, errors, warnings = apply_overrides("resolution.csv", rows, overlay)
    assert errors == [] and warnings == []
    assert [(r.variant_key, r.locus_index, r.start) for r in after] == [
        ("rs1", 0, 1),
        ("rs1", 1, 11),
        ("rs1", 2, 12),
        ("rs2", 0, 2),
    ]


def test_a_subject_with_no_group_yet_is_appended_at_the_end_of_the_table() -> None:
    """The other half of the placement rule, which the group case cannot show."""
    rows = [ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1)]
    overlay = [
        _row(table="resolution.csv", subject="rs9", member="0", field="chrom", operation="insert",
             value="6"),
    ]
    after, errors, _ = apply_overrides("resolution.csv", rows, overlay)
    assert errors == []
    assert [r.variant_key for r in after] == ["rs1", "rs9"]


def test_all_three_operations_are_fixed_points_when_applied_to_their_own_result() -> None:
    """The property the round trip is bought with, asserted directly rather than only through a
    compile: `reverse_module` emits the post-overlay table plus the overlay, so the overlay applies
    twice and the second application must change nothing."""
    rows = [
        ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1, source="cache"),
        ResolutionRow(variant_key="rs2", locus_index=0, chrom="6", start=2, source="cache"),
    ]
    overlay = [
        _row(table="resolution.csv", subject="rs1", member="0", field="source", operation="update",
             value="manual"),
        _row(table="resolution.csv", subject="rs3", member="0", field="chrom", operation="insert",
             value="6"),
        _row(table="resolution.csv", subject="rs2", member="0", operation="suppress"),
    ]
    once, errors, _ = apply_overrides("resolution.csv", rows, overlay)
    assert errors == []
    twice, errors_again, warnings_again = apply_overrides("resolution.csv", once, overlay)
    assert errors_again == []
    assert [r.model_dump() for r in once] == [r.model_dump() for r in twice]
    assert warnings_again == [], "a second application must report nothing a first one did not"


def test_no_operation_reports_its_own_no_op() -> None:
    """The finding that must not exist, and the reason is structural rather than a matter of taste.

    After `reverse_module` the derived table is post-overlay, so update-already-equal,
    insert-already-present and suppress-already-absent are all three true of a perfectly healthy
    module. Any of them reported would make a module and its own round trip disagree on
    `manifest.compilation.warnings`, which is a published field.
    """
    rows = [ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1, source="manual")]
    overlay = [
        _row(table="resolution.csv", subject="rs1", member="0", field="source", operation="update",
             value="manual"),
        _row(table="resolution.csv", subject="rs1", member="0", field="chrom", operation="insert",
             value="6"),
        _row(table="resolution.csv", subject="rs4", member="0", operation="suppress"),
    ]
    # Split, because one key group carries one operation: the update and the insert share a key.
    for single in ([overlay[0]], [overlay[1]], [overlay[2]]):
        after, errors, warnings = apply_overrides("resolution.csv", rows, single)
        assert errors == [], single[0].operation
        assert warnings == [], f"{single[0].operation} reported its own no-op"


def test_an_update_that_reaches_no_row_warns_and_names_both_readings() -> None:
    """The one mismatch that is stable across both laps, because an update never creates a row.

    Both readings, because nothing here can separate them — a mistyped subject and a source that
    stopped publishing the row look identical from inside the compiler, and the house algebra
    withholds a verdict it cannot reach.
    """
    rows = [ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1)]
    overlay = [
        _row(table="resolution.csv", subject="rs_typo", member="0", field="chrom",
             operation="update", value="6"),
    ]
    after, errors, warnings = apply_overrides("resolution.csv", rows, overlay)
    assert errors == []
    assert [r.variant_key for r in after] == ["rs1"]
    assert len(warnings) == 1
    assert "may be mistyped, or the source may have stopped publishing" in warnings[0]


def test_an_update_producing_a_row_the_target_model_refuses_is_an_error() -> None:
    """The correction goes through the target model's own validators, which is the same net a hand
    edit went through — including the cross-field ones. `ResolutionRow` keeps `vrs_id` positionally
    aligned with `alts`, so correcting one without the other is refused here rather than reaching a
    parquet."""
    rows = [
        ResolutionRow(
            variant_key="rs1", locus_index=0, chrom="6", start=1, ref="G", alts="A",
            vrs_id="ga4gh:VA.__fXj0w0NCSkOLYF79GvSLtpDji99L42",
        )
    ]
    overlay = [
        _row(table="resolution.csv", subject="rs1", member="0", field="alts", operation="update",
             value="A,T"),
    ]
    after, errors, _ = apply_overrides("resolution.csv", rows, overlay)
    assert len(errors) == 1
    assert "produces a row the table refuses" in errors[0]
    assert after[0].alts == "A", "a refused correction leaves the derived row alone"


def test_an_insert_missing_a_required_column_is_an_error_rather_than_a_dropped_row() -> None:
    overlay = [
        _row(table="frequencies.csv", subject="rs1", member="global", field="allele_count",
             operation="insert", value="7"),
    ]
    after, errors, _ = apply_overrides("frequencies.csv", [], overlay)
    assert after == []
    assert len(errors) == 1 and "does not make a valid row" in errors[0]


def test_overrides_for_another_table_are_left_alone() -> None:
    """A caller hands the whole file to each table; each picks its own rows out."""
    overlay = [
        _row(table="literature.csv", subject="8696333", field="doi", operation="update",
             value="10.1/a"),
    ]
    rows = [ResolutionRow(variant_key="rs1", locus_index=0, chrom="6", start=1)]
    after, errors, warnings = apply_overrides("resolution.csv", rows, overlay)
    assert (after, errors, warnings) == (rows, [], [])


def test_a_decision_date_is_canonicalized_on_load() -> None:
    """It reaches `overrides.parquet` and so `artifact.digest`, where two spellings of one instant
    would be two identities for one overlay. A bare date is accepted and reads as midnight UTC."""
    assert _row(
        table="literature.csv", subject="8696333", field="doi", operation="update", value="10.1/a",
        decided_at="2026-08-28",
    ).decided_at == "2026-08-28T00:00:00Z"

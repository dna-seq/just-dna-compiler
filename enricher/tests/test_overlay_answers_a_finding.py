"""The enricher reads the author's overlay, so a correction stops coming back forever (RM136).

The compiler applies `overrides.csv` before any check reads a row — a check must report on what the
module *asserts*. The enricher did not: its passes re-read the raw derived file, so an author who
corrected a `resolution.csv` cell through the overlay went on being told the same finding on every
run, with no way to clear it and nothing saying the correction had been recorded and honoured one
tier over.

**Two halves, and they are deliberately different mechanisms.**

*Input reads* get the post-overlay rows, through the compiler's own `apply_overrides` — never a second
implementation, which is what the entry refuses on the grounds that the two would drift on the
normalization seam. *Merge baselines* stay raw: a pass that reads its own output file to merge against
it writes that file back, and feeding it post-overlay rows would bake the correction into the derived
table — the enricher writing *through* the overlay, which is RM83's standing refusal.

**Answered is per FIELD, and per row was refused.** Correcting a coordinate answers the coordinate
check and leaves an unrelated finding standing; the cheaper per-row rule would let one correction
silence findings the author never looked at, which is the silent-suppress hole the overlay's own
design calls its worst case.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from just_dna_enricher.licensing import overlaid_input_rows, overlay_answers
from just_dna_enricher.resolver import check_rsid_coordinates
from just_dna_format.resolution import ResolutionRow

_HEADER = [
    "table", "subject", "member", "field", "operation", "value", "reason", "decided_by",
    "decided_at",
]
_KEY = "rs1801133"
_LOCI = [{"chrom": "1", "start": 11856378, "ref": "G", "alts": "A"}]


def _spec(tmp_path: Path, overlay: list[list[str]] | None = None) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    if overlay is not None:
        with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(_HEADER)
            writer.writerows(overlay)
    return spec


def _row(**kwargs) -> ResolutionRow:
    base = {
        "variant_key": _KEY, "rsid": _KEY, "chrom": "1", "start": 11856378, "ref": "G", "alts": "A",
        "genome_build": "GRCh38", "locus_index": 0, "source": "ensembl", "status": "resolved",
    }
    return ResolutionRow(**{**base, **kwargs})


def _correction(field: str, value: str) -> list[str]:
    return [
        "resolution.csv", _KEY, "0", field, "update", value,
        "re-checked against dbSNP by hand", "curator", "2026-08-31",
    ]


# ── the answered set ────────────────────────────────────────────────────────────────────────────


def test_a_module_with_no_overlay_answers_nothing(tmp_path: Path) -> None:
    """Every module today, so the checks must behave exactly as they did before this shipped."""
    assert overlay_answers(_spec(tmp_path), "resolution.csv") == set()


def test_an_update_answers_the_cell_it_names_and_no_other(tmp_path: Path) -> None:
    """Per field, which is the decision. Per row would have been one line shorter and wrong."""
    spec = _spec(tmp_path, [_correction("start", "11856377")])

    answered = overlay_answers(spec, "resolution.csv")

    assert answered == {(_KEY, "start")}
    assert (_KEY, "ref") not in answered


def test_only_an_update_counts(tmp_path: Path) -> None:
    """An `insert` supplies a row the source had no answer for, so there was no finding to answer; a
    `suppress` removes the row, and its removal is already reported in its own right by RM131."""
    spec = _spec(
        tmp_path,
        [
            ["resolution.csv", "rs_new", "0", "chrom", "insert", "6", "r", "c", "2026-08-31"],
            ["resolution.csv", "rs_gone", "0", "", "suppress", "", "r", "c", "2026-08-31"],
        ],
    )

    assert overlay_answers(spec, "resolution.csv") == set()


def test_another_tables_overlay_does_not_answer_this_one(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path,
        [["frequencies.csv", _KEY, "nfe", "af", "update", "0.3", "r", "c", "2026-08-31"]],
    )

    assert overlay_answers(spec, "resolution.csv") == set()


# ── the check that consults it ──────────────────────────────────────────────────────────────────


def test_the_coordinate_disagreement_is_reported_when_nothing_answers_it() -> None:
    """The control. Without this the suppression below could pass on a check that never fired."""
    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI})

    assert check.disagreements
    assert check.answered == 0
    assert check.subjects == 1


def test_an_answered_disagreement_is_counted_rather_than_reported() -> None:
    """The finding the author has already answered stops being put to them a second time."""
    answered = {(_KEY, "start")}

    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI}, answered)

    assert check.disagreements == []
    assert check.answered == 1


def test_answered_is_not_agreed_and_the_denominator_says_so() -> None:
    """**The property that keeps this honest.** The comparison ran and found a difference, so the pair
    stays in `subjects`; dropping it would report a cleaner module than there is, which is the
    silent-success shape. What changes is only that it is not re-reported."""
    answered = {(_KEY, "start")}

    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI}, answered)

    assert check.subjects == 1, "the pair was compared, and it disagreed"
    assert check.answered == 1
    assert not check.disagreements


def test_an_overlay_on_a_different_column_does_not_silence_this_check() -> None:
    """The per-field rule doing its work: `source` is not a cell this comparison reads."""
    answered = {(_KEY, "source")}

    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI}, answered)

    assert check.disagreements, "an unrelated correction must not answer a coordinate finding"
    assert check.answered == 0


def test_an_overlay_on_a_different_row_does_not_silence_this_one() -> None:
    answered = {("rs9999999", "start")}

    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI}, answered)

    assert check.disagreements
    assert check.answered == 0


@pytest.mark.parametrize("column", ["chrom", "start", "ref", "alts"])
def test_every_coordinate_cell_this_check_reads_can_answer_it(column: str) -> None:
    """Parametrized over the columns rather than spot-checking one: the comparison reads a coordinate
    as a whole, so a correction to any part of it is an answer to the same finding."""
    check = check_rsid_coordinates([(_KEY, "1", 999999, "G")], {_KEY: _LOCI}, {(_KEY, column)})

    assert check.answered == 1
    assert not check.disagreements


# ── the input/baseline split ────────────────────────────────────────────────────────────────────


def test_an_input_read_sees_the_correction(tmp_path: Path) -> None:
    """What the whole item buys: the pass reads what the module asserts, like the compiler does."""
    spec = _spec(tmp_path, [_correction("start", "11856377")])

    applied = overlaid_input_rows(
        spec, "resolution.csv", [_row()], error=RuntimeError
    )

    assert applied[0].start == 11856377


def test_a_module_with_no_overlay_gets_its_rows_back_unchanged(tmp_path: Path) -> None:
    """A check that cannot fire must not change anything either (`@tautology-zero`'s neighbour)."""
    rows = [_row()]

    applied = overlaid_input_rows(_spec(tmp_path), "resolution.csv", rows, error=RuntimeError)

    assert [r.model_dump() for r in applied] == [r.model_dump() for r in rows]


def test_a_broken_overlay_raises_as_the_callers_own_error(tmp_path: Path) -> None:
    """A pass that quietly used the raw rows instead would be the silent-success shape.

    `error=` is the caller's exception class for the same reason `sidecar_path` takes one: a pass must
    fail as itself, not as the module it borrows a helper from.
    """
    class PassError(RuntimeError):
        pass

    spec = _spec(tmp_path, [["resolution.csv", _KEY, "0", "start", "update", "not-a-number",
                             "r", "c", "2026-08-31"]])

    with pytest.raises(PassError):
        overlaid_input_rows(spec, "resolution.csv", [_row()], error=PassError)


def test_the_overlay_is_read_through_the_compilers_own_apply(tmp_path: Path) -> None:
    """No second implementation — the entry's central refusal, asserted rather than trusted.

    Compared against `apply_overrides` directly on the same inputs: if the enricher ever grew its own
    copy, this is where the two would be seen to differ.
    """
    from just_dna_compiler.compiler import load_overlay
    from just_dna_format.overrides import apply_overrides

    spec = _spec(tmp_path, [_correction("start", "11856377")])
    overrides, errors, _ = load_overlay(spec)
    assert not errors, errors
    direct, _, _ = apply_overrides("resolution.csv", [_row()], overrides)

    through_helper = overlaid_input_rows(spec, "resolution.csv", [_row()], error=RuntimeError)

    assert [r.model_dump() for r in through_helper] == [r.model_dump() for r in direct]

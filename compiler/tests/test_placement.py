"""Delegated placement and partial rows (0.5.1).

Two mechanisms with one rule between them: the tool chooses **where** a row goes and **what cells it
can honestly state**, and never chooses what a human must decide. What is pinned here is that a
placed row moves only line numbers (never cells), that nothing is lost or duplicated, and that a
partial row stops being re-added the moment its stub is filled.
"""

import csv
import io
from pathlib import Path

from just_dna_compiler.compiler import _load_csv_rows, validate_spec
from just_dna_compiler.draft import (
    PartialRow,
    append_partial_rows,
    append_rows,
    group_of,
    place_rows,
)
from just_dna_format.pgx import AlleleFunctionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


# ── placement ───────────────────────────────────────────────────────────────────────────────────

def test_place_rows_joins_the_matching_block() -> None:
    existing = [{"gene": "A", "n": "1"}, {"gene": "B", "n": "2"}, {"gene": "B", "n": "3"}]
    incoming = [{"gene": "A", "n": "4"}]
    merged, shifted = place_rows(existing, incoming, ("gene",))
    assert [r["n"] for r in merged] == ["1", "4", "2", "3"]
    assert shifted == [1, 2]  # the two B rows moved down; their cells are untouched


def test_no_group_by_is_a_plain_append_and_shifts_nothing() -> None:
    existing = [{"gene": "A", "n": "1"}, {"gene": "B", "n": "2"}]
    merged, shifted = place_rows(existing, [{"gene": "A", "n": "3"}], ())
    assert [r["n"] for r in merged] == ["1", "2", "3"]
    assert shifted == []


def test_a_row_with_no_group_goes_to_the_end() -> None:
    merged, shifted = place_rows([{"gene": "A"}], [{"gene": ""}], ("gene",))
    assert merged[-1]["gene"] == ""
    assert shifted == []
    assert group_of({"gene": ""}, ("gene",)) is None


def test_incoming_rows_keep_their_relative_order_within_a_group() -> None:
    merged, _ = place_rows(
        [{"gene": "A", "n": "1"}], [{"gene": "A", "n": "2"}, {"gene": "A", "n": "3"}], ("gene",)
    )
    assert [r["n"] for r in merged] == ["1", "2", "3"]


def test_a_grouped_append_moves_lines_but_never_cells(tmp_path: Path) -> None:
    """The promise that makes placement safe: an existing row's bytes are identical afterwards."""
    append_rows(tmp_path, "allele_function.csv", [
        AlleleFunctionRow(gene="CYP2C19", allele="*2", function_status="no_function"),
        AlleleFunctionRow(gene="CYP2D6", allele="*4", function_status="no_function"),
    ])
    before = {tuple(r.items()) for r in _rows(tmp_path / "allele_function.csv")}

    report = append_rows(tmp_path, "allele_function.csv", [
        AlleleFunctionRow(gene="CYP2C19", allele="*17", function_status="increased_function"),
    ], group_by=("gene",))

    after = _rows(tmp_path / "allele_function.csv")
    assert [r["gene"] for r in after] == ["CYP2C19", "CYP2C19", "CYP2D6"]  # joined its block
    assert report.shifted == [1]                                          # the CYP2D6 row moved
    assert before <= {tuple(r.items()) for r in after}                    # cells untouched
    assert len(after) == 3                                                # nothing lost or doubled


def test_a_grouped_append_still_round_trips(tmp_path: Path) -> None:
    """Placement changes order, and order is digest-visible — but P7 is about reproducing the module
    you have, and a placed module still reproduces itself."""
    append_rows(tmp_path, "allele_function.csv", [
        AlleleFunctionRow(gene="A", allele="*1"), AlleleFunctionRow(gene="B", allele="*1"),
    ])
    append_rows(tmp_path, "allele_function.csv",
                [AlleleFunctionRow(gene="A", allele="*2")], group_by=("gene",))
    rows, errors, _ = _load_csv_rows(tmp_path / "allele_function.csv", AlleleFunctionRow,
                                     "allele_function.csv")
    assert errors == []
    assert [(r.gene, r.allele) for r in rows] == [("A", "*1"), ("A", "*2"), ("B", "*1")]


# ── partial rows ────────────────────────────────────────────────────────────────────────────────

def _partial(rsid: str, **extra) -> PartialRow:
    return PartialRow(
        model=VariantRow,
        cells={"rsid": rsid, "state": "risk", "conclusion": "c", **extra},
        stubbed=("genotype",),
        match_on=("rsid", "chrom", "start", "ref"),
    )


def test_a_partial_row_is_written_with_its_stub_and_cannot_load(tmp_path: Path) -> None:
    append_partial_rows(tmp_path, "variants.csv", [_partial("rs1801133")])
    cells = _rows(tmp_path / "variants.csv")[0]
    assert cells["genotype"] == TEMPLATE_PLACEHOLDER
    assert cells["rsid"] == "rs1801133"
    rows, errors, _ = _load_csv_rows(tmp_path / "variants.csv", VariantRow, "variants.csv")
    assert rows == [] and errors and TEMPLATE_PLACEHOLDER in errors[0]


def test_a_partial_row_is_not_re_added_once_the_human_fills_the_stub(tmp_path: Path) -> None:
    """The rule that makes a re-draft safe — and the one thing a natural key could not do here,
    because that key runs straight through the column still holding the placeholder."""
    append_partial_rows(tmp_path, "variants.csv", [_partial("rs1801133")])
    rows = _rows(tmp_path / "variants.csv")
    header = list(rows[0])
    rows[0]["genotype"] = "A/G"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    (tmp_path / "variants.csv").write_text(buf.getvalue())

    report = append_partial_rows(tmp_path, "variants.csv", [_partial("rs1801133")])
    assert report.added == []
    assert len(report.already_present) == 1
    assert not report.written
    filled = _rows(tmp_path / "variants.csv")
    assert len(filled) == 1 and filled[0]["genotype"] == "A/G"


def test_a_duplicate_inside_one_batch_is_caught(tmp_path: Path) -> None:
    report = append_partial_rows(
        tmp_path, "variants.csv", [_partial("rs1801133"), _partial("rs1801133")]
    )
    assert len(report.added) == 1 and len(report.already_present) == 1


def test_bad_published_cells_are_reported_not_written(tmp_path: Path) -> None:
    """The stubbed column is validated by omission; everything else still has to be real."""
    bad = _partial("rs1801133", clin_sig="not_a_clin_sig")
    report = append_partial_rows(tmp_path, "variants.csv", [bad])
    assert len(report.invalid) == 1
    assert "clin_sig" in report.invalid[0].differences["errors"][1]
    assert not (tmp_path / "variants.csv").exists()


def test_a_filled_partial_module_compiles(tmp_path: Path) -> None:
    """End to end: draft partial rows, fill the stubs, and the module is real."""
    (tmp_path / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: panel\n  title: P\n  description: d\n"
        "  report_title: P\n"
    )
    (tmp_path / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n")
    append_partial_rows(tmp_path, "variants.csv", [_partial("rs1801133", gene="MTHFR")],
                        group_by=("gene",))
    assert not validate_spec(tmp_path).valid

    rows = _rows(tmp_path / "variants.csv")
    header = list(rows[0])
    rows[0]["genotype"] = "A/G"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    (tmp_path / "variants.csv").write_text(buf.getvalue())
    result = validate_spec(tmp_path)
    assert result.valid, result.errors


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    report = append_partial_rows(tmp_path, "variants.csv", [_partial("rs1")], dry_run=True)
    assert len(report.added) == 1 and not report.written
    assert not (tmp_path / "variants.csv").exists()

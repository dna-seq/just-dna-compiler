"""RM294 keeps every STRchive claim beside the authored repeat bands."""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, load_csv_rows, reverse_module, validate_spec
from just_dna_compiler.hints import derived_model_for
from just_dna_format import integrity
from just_dna_format.base import field_first_seen

_HTT = Path(__file__).resolve().parents[2] / "reference_examples" / "htt_repeat_expansion"


def test_repeat_grade_signature_and_release() -> None:
    model = derived_model_for("repeat_grades.csv")
    assert field_first_seen(model) == dict.fromkeys(model.model_fields, "0.10.0")
    row = model(gene="HTT", repeat_unit="CAG", locus_id="HD_HTT")
    assert model._KEY_FIELDS == ("gene", "repeat_unit", "locus_id", "grade")
    signature = integrity.repeat_grade_signature
    original = signature([row])
    for field in (*model._KEY_FIELDS, "dataset"):
        assert signature([row.model_copy(update={field: "different"})]) != original
    for field in ("disease", "source", "status", "fetched_at"):
        assert signature([row.model_copy(update={field: "different"})]) == original


@pytest.mark.parametrize("strict", [False, True])
def test_orphan_checks_the_whole_repeat_key(tmp_path: Path, strict: bool) -> None:
    spec = shutil.copytree(_HTT, tmp_path / "spec")
    (spec / "repeat_grades.csv").write_text(
        "gene,repeat_unit,locus_id,grade\nHTT,CAG,HD_HTT,Refuted\nHTT,CAA,HD_HTT,Provisional\n"
    )
    checked = validate_spec(spec, strict=strict)
    compiled = compile_module(spec, tmp_path / "out", strict=strict)
    assert compiled.success, compiled.errors
    for result in (checked, compiled):
        warnings = result.warnings
        (warning,) = [w for w in warnings if "absent from repeat_alleles.csv" in w]
        assert result.warnings_summary["derived_row_orphan"] == 1
        assert "CAA" in warning and "CAG" not in warning


def test_repeat_grade_round_trip(tmp_path: Path) -> None:
    spec = shutil.copytree(_HTT, tmp_path / "spec")
    bare = compile_module(spec, tmp_path / "bare")
    assert bare.success, bare.errors
    grade_file = spec / "repeat_grades.csv"
    grade_file.write_text(
        "gene,repeat_unit,locus_id,grade,disease\nHTT,CAG,HD_HTT,,Huntington disease\n"
        "HTT,CAG,HD_HTT, Future wording ,Huntington disease\n"
    )
    before = compile_module(spec, tmp_path / "first")
    assert before.success, before.errors
    assert grade_file.name in {f.name for f in before.manifest.derived}
    rows, errors, _ = load_csv_rows(grade_file, derived_model_for(grade_file.name), grade_file.name)
    assert not errors
    assert before.manifest.repeat_grades.signature == integrity.repeat_grade_signature(rows)
    assert bare.manifest.content_signature == before.manifest.content_signature
    assert bare.manifest.artifact.digest != before.manifest.artifact.digest
    reverse_module(tmp_path / "first", tmp_path / "back")
    after = compile_module(tmp_path / "back", tmp_path / "second")
    assert after.success, after.errors
    table = "repeat_grades.parquet"
    a, b = (pl.read_parquet(tmp_path / out / table) for out in ("first", "second"))
    with grade_file.open(newline="") as handle:
        # The word is the source's; the cell padding is the CSV's, normalized like every other cell.
        expected_grades = [(row["grade"] or "").strip() or None for row in csv.DictReader(handle)]
    assert a.equals(b) and a["grade"].to_list() == expected_grades
    assert before.manifest.repeat_grades.signature == after.manifest.repeat_grades.signature
    assert before.manifest.artifact.digest == after.manifest.artifact.digest

"""Two fact-table rows under one merge key that state different values warn in both modes (RM275).

The reproduction is the entry's own: `hboc_palb2` with its first `gene_validity.csv` row duplicated and
the copy's `classification` changed from `definitive` to `refuted`. Before RM275 that compiled green
under `--strict` and `gene_validity.parquet` carried both rows, so a consumer read one or the other by
row order.
"""

import shutil
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_compiler.compiler.fact_checks import FACT_CONTRADICTION_FIELDS, _check_fact_rows_contradict
from just_dna_compiler.compiler.load import load_csv_rows
from just_dna_compiler.compiler.tables import _FACT_TABLES, _TABLE_DUPE_KEYS
from just_dna_format.frequency import FrequencyRow

_PALB2 = Path(__file__).resolve().parents[2] / "reference_examples" / "hboc_palb2"


def _with_duplicated_gene_validity_row(tmp_path: Path, edit) -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_PALB2, spec)
    path = spec / "gene_validity.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines.insert(2, edit(lines[1]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return spec


def _codes(warnings: list[str]) -> list[str]:
    return [w for w in warnings if getattr(w, "code", None) == "fact_rows_contradict"]


def test_a_contradicting_pair_warns_under_strict_and_the_compile_stays_green(tmp_path: Path) -> None:
    spec = _with_duplicated_gene_validity_row(
        tmp_path, lambda row: row.replace(",definitive,Definitive,", ",refuted,Refuted,")
    )
    checked = validate_spec(spec, strict=True)
    assert checked.valid, checked.errors
    compiled = compile_module(spec, tmp_path / "out", strict=True)
    assert compiled.success, compiled.errors

    # Parity by check: the pre-flight and the compile carry the same finding, once each.
    assert _codes(checked.warnings) == _codes(compiled.warnings)
    # The published list is plain strings (a pydantic field drops the code), so match the phrase there.
    [finding] = [w for w in compiled.manifest.compilation.warnings if "two rows state different values" in w]
    assert "gene_validity.csv carries 1 key(s) under which two rows state different values" in finding
    assert "classification" in finding
    assert compiled.manifest.compilation.warnings_summary["fact_rows_contradict"] == 1


def test_an_identical_duplicate_is_not_a_contradiction(tmp_path: Path) -> None:
    spec = _with_duplicated_gene_validity_row(tmp_path, lambda row: row)
    assert not _codes(compile_module(spec, tmp_path / "out").warnings)


def test_a_cell_one_row_leaves_empty_is_not_a_contradiction(tmp_path: Path) -> None:
    """`@absent-is-not-different`: an unstated cell beside a stated one is an absence."""
    spec = _with_duplicated_gene_validity_row(tmp_path, lambda row: row.replace(",Definitive,", ",,"))
    assert not _codes(compile_module(spec, tmp_path / "out").warnings)


def test_the_check_is_generic_over_the_registered_tables() -> None:
    """A second table, driven directly, so the rule is not only ever exercised on gene_validity."""
    rows, errors, _ = load_csv_rows(_PALB2 / "frequencies.csv", FrequencyRow, "frequencies.csv")
    assert not errors and rows
    first = rows[0]
    changed = first.model_copy(update={"allele_count": (first.allele_count or 0) + 1})
    assert _check_fact_rows_contradict("frequencies.csv", FrequencyRow, [first, first]) == []
    [finding] = _check_fact_rows_contradict("frequencies.csv", FrequencyRow, [first, changed])
    assert "allele_count" in finding


def test_every_fact_table_is_checked_here_or_refused_by_the_dupe_registry() -> None:
    fact_models = {model for _csv, _parquet, model in _FACT_TABLES}
    refused = fact_models & set(_TABLE_DUPE_KEYS)
    assert set(FACT_CONTRADICTION_FIELDS) | refused == fact_models
    assert not set(FACT_CONTRADICTION_FIELDS) & refused

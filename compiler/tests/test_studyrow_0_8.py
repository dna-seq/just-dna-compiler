"""The 0.8 `StudyRow` batch (PROPOSAL_0_8_PT2 §3 items 10–17, §5 A5).

longevitymap v2 sorts, weighs and tiers its evidence by facts a `studies.csv` row could not state
before 0.8: how many were analysed and in what unit (RM325), which outcome was measured (RM326), in
which ancestry (RM328), over which age band (RM329), inside which stratum (RM330), on which LD proxy
(RM331), and in what unit an effect is stated (RM332). Each is an optional authored column, so each
owes the same proof, and this file gives it once per column group:

* the column reaches `studies.parquet` with the authored value, row for row;
* `compile → reverse → compile` writes it back and lands on the same `artifact.digest` and
  `content_signature` (Principle 7);
* a stated cell is authored content and moves `content_signature`, while a module that never writes the
  column, or writes the header with every cell empty, keeps the signature it had (P3/P8);
* the new columns come after every 0.7 column, so no 0.7 parquet column changes position.

The fixture is a copy of `reference_examples/hfe_hemochromatosis`, which carries 33 real study rows over
eleven variants and a real `resolution.csv`. The cells are generated here and read back off the CSV the
test wrote, so every expectation is computed from what was authored rather than restated.
"""

import csv
import shutil
from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module, validate_spec
from just_dna_format.base import field_first_seen, field_vocabularies
from just_dna_format.pgs import VALID_TRAINING_ANCESTRY, PgsRow
from just_dna_format.spec import StudyRow
from just_dna_format.vocab import VALID_SUPERPOPULATIONS
from pydantic import ValidationError

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"

#: A fill writes the new cells of one study row in place, given the row's position in the file.
Fill = Callable[[int, dict[str, str]], None]


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _spec(tmp_path: Path, name: str, columns: tuple[str, ...], fill: Fill | None) -> Path:
    """A copy of the HFE example whose `studies.csv` carries `columns`, filled by `fill` (or empty)."""
    spec = tmp_path / name
    shutil.copytree(_EXAMPLE, spec)
    # The example is closed, and its attestation binds the bytes this edit changes; the attestation is
    # not what this file is about, so the copy carries none.
    (spec / "verification.json").unlink()
    header, rows = _read_rows(spec / "studies.csv")
    for i, row in enumerate(rows):
        for column in columns:
            row[column] = ""
        if fill is not None:
            fill(i, row)
    _write_rows(spec / "studies.csv", header + list(columns), rows)
    return spec


def _authored(spec: Path, columns: tuple[str, ...]) -> list[dict[str, str | None]]:
    """The authored cells, row by row; an empty cell is the unstated `None`."""
    _, rows = _read_rows(spec / "studies.csv")
    return [{c: row.get(c) or None for c in columns} for row in rows]


def _fill_sample_size(i: int, row: dict[str, str]) -> None:
    """Three shapes in turn: a case-control count in individuals, a parental count in lives, nothing."""
    if i % 3 == 0:
        row["sample_size"] = str(1000 + 7 * i)
        row["sample_unit"] = "individuals"
        row["n_cases"] = str(100 + i)
    elif i % 3 == 1:
        row["sample_size"] = str(1_012_240 + i)
        row["sample_unit"] = "lives"


#: v2's twelve classes as RM326 spells them; the test restates them so a drift in either is caught.
_V2_CLASSES: frozenset[str] = frozenset(
    {
        "EXTREME_SURVIVAL_CC",
        "PARENTAL_LIFESPAN",
        "OWN_SURVIVAL",
        "VIABILITY_AF",
        "HEALTHSPAN",
        "MULTIVARIATE_AGEING",
        "FAMILIAL",
        "DISEASE_DEPLETION",
        "RARE_BURDEN",
        "EVOLUTIONARY",
        "MR",
        "BIOMARKER",
    }
)


def _fill_phenotype_class(i: int, row: dict[str, str]) -> None:
    """Every recommended class in turn, with every fourth row left unstated."""
    if i % 4 != 3:
        row["phenotype_class"] = sorted(_V2_CLASSES)[i % len(_V2_CLASSES)]


def _fill_ancestry(i: int, row: dict[str, str]) -> None:
    """One code, two codes (a trans-ethnic study lists both, in the authored order), or nothing."""
    row["ancestry"] = ("EUR", "EAS|EUR", "AFR", "", "EUR|AMR|SAS")[i % 5]


#: Each column group this batch adds, with a fill that gives it distinct stated values and empty
#: cells, and how a parquet cell reads back as the CSV cell it came from.
_GROUPS: dict[str, tuple[tuple[str, ...], Fill]] = {
    "RM325": (("sample_size", "sample_unit", "n_cases"), _fill_sample_size),
    "RM326": (("phenotype_class",), _fill_phenotype_class),
    "RM328": (("ancestry",), _fill_ancestry),
}


def _as_cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "|".join(str(v) for v in value) or None
    return str(value)


# ── the generic proof, once per column group ────────────────────────────────────────────────────────


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_fixture_carries_distinct_values_and_empty_cells(tmp_path: Path, item: str) -> None:
    """The fixture earns its place, or the round trip below asserts over a uniform column."""
    columns, fill = _GROUPS[item]
    authored = _authored(_spec(tmp_path, "filled", columns, fill), columns)
    for column in columns:
        values = [cells[column] for cells in authored]
        assert None in values, column
        assert len({v for v in values if v is not None}) > 1, column


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_are_0_8_and_come_after_every_0_7_column(item: str) -> None:
    columns, _ = _GROUPS[item]
    first_seen = field_first_seen(StudyRow)
    fields = list(StudyRow.model_fields)
    assert {c: first_seen[c] for c in columns} == dict.fromkeys(columns, "0.8.0")
    last_old = max(i for i, name in enumerate(fields) if first_seen[name] != "0.8.0")
    assert all(fields.index(c) > last_old for c in columns)


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_reach_studies_parquet_row_for_row(tmp_path: Path, item: str) -> None:
    columns, fill = _GROUPS[item]
    spec = _spec(tmp_path, "filled", columns, fill)
    validation = validate_spec(spec, strict=True)
    assert validation.valid, validation.errors
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors

    df = pl.read_parquet(tmp_path / "out" / "studies.parquet")
    # `neg_log10_p` is the last 0.7 column; a reader by position sees every 0.7 column where it was.
    last_0_7 = df.columns.index("neg_log10_p")
    assert all(df.columns.index(c) > last_0_7 for c in columns)
    materialized = [{c: _as_cell(row[c]) for c in columns} for row in df.iter_rows(named=True)]
    authored = _authored(spec, columns)
    # Numbers come back as numbers: compare on the value, not the spelling.
    assert [{c: (float(v) if v and c in _NUMERIC else v) for c, v in r.items()} for r in materialized] == [
        {c: (float(v) if v and c in _NUMERIC else v) for c, v in r.items()} for r in authored
    ]


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_survive_reverse_and_recompile_to_a_fixed_point(tmp_path: Path, item: str) -> None:
    columns, fill = _GROUPS[item]
    spec = _spec(tmp_path, "filled", columns, fill)
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    header, _ = _read_rows(tmp_path / "rev" / "studies.csv")
    assert set(columns) <= set(header)
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "rev") == content_signature(spec)


@pytest.mark.parametrize("item", sorted(_GROUPS))
def test_the_columns_are_authored_content_and_an_unwritten_one_hashes_as_before(
    tmp_path: Path, item: str
) -> None:
    columns, fill = _GROUPS[item]
    baseline = content_signature(_EXAMPLE)
    assert content_signature(_spec(tmp_path, "empty", columns, None)) == baseline
    assert content_signature(_spec(tmp_path, "filled", columns, fill)) != baseline


#: Columns whose parquet type is a number, so the comparison above reads them as one.
_NUMERIC: frozenset[str] = frozenset({"sample_size", "n_cases"})


# ── RM325: sample size, its unit, and the case count ──────────────────────────────────────────────


def _study(**cells: object) -> StudyRow:
    return StudyRow(rsid="rs1800562", pmid="10381492", **cells)


def test_sample_unit_is_closed_over_individuals_and_lives() -> None:
    assert field_vocabularies(StudyRow)["sample_unit"] == {
        "name": "sample_unit",
        "options": ["individuals", "lives"],
        "closed": True,
    }
    for unit in ("individuals", "lives"):
        assert _study(sample_size=10, sample_unit=unit).sample_unit == unit
    with pytest.raises(ValidationError, match="sample_unit"):
        _study(sample_size=10, sample_unit="people")


def test_a_sample_size_with_no_unit_is_refused() -> None:
    """`@weight-has-no-unit`: parental-lifespan studies count lives, two per participant."""
    with pytest.raises(ValidationError, match="sample_unit"):
        _study(sample_size=389166)
    # A unit with no magnitude names an instrument nothing was measured on, and is harmless.
    assert _study(sample_unit="lives").sample_size is None


def test_more_cases_than_were_analysed_is_refused() -> None:
    with pytest.raises(ValidationError, match="n_cases"):
        _study(sample_size=100, sample_unit="individuals", n_cases=101)
    # Every analysed person a case is legal (a case-only design), and so is a case count alone.
    assert _study(sample_size=100, sample_unit="individuals", n_cases=100).n_cases == 100
    assert _study(n_cases=3484).sample_size is None


def test_a_negative_count_is_refused() -> None:
    for cells in ({"sample_size": -1, "sample_unit": "lives"}, {"n_cases": -1}):
        with pytest.raises(ValidationError):
            _study(**cells)


# ── RM326: the outcome a study measured ─────────────────────────────────────────────────────────


def _summary(tmp_path: Path, spec: Path, *, strict: bool) -> dict[str, int]:
    result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
    assert result.success, result.errors
    return dict(result.manifest.compilation.warnings_summary)


def test_phenotype_class_is_open_over_v2s_twelve() -> None:
    marker = field_vocabularies(StudyRow)["phenotype_class"]
    assert marker["closed"] is False
    assert set(marker["options"]) == _V2_CLASSES
    # Open: a class outside the twelve is a row, not a refusal (three real studies fit none of them).
    assert _study(phenotype_class="NOVEL_CLASS").phenotype_class == "NOVEL_CLASS"


@pytest.mark.parametrize("strict", [False, True])
def test_a_class_outside_the_recommended_set_warns_in_both_modes(tmp_path: Path, strict: bool) -> None:
    """v2 spells three classes two ways; the long form draws the warning, the recommended one does not."""

    def drift(i: int, row: dict[str, str]) -> None:
        row["phenotype_class"] = ("FAMILIAL_LONGEVITY", "MR_MEDIATOR", "FAMILIAL", "")[i % 4]

    spec = _spec(tmp_path, "drift", ("phenotype_class",), drift)
    summary = _summary(tmp_path, spec, strict=strict)
    assert summary.get("phenotype_class_unrecognized") == 1
    validation = validate_spec(spec, strict=strict)
    # `validate_spec` returns plain strings; the code is asserted on the manifest above, the text here.
    found = [w for w in validation.warnings if "phenotype_class outside the recommended set" in w]
    assert len(found) == 1
    # Each token is named once with its row count, and a recommended token is never named.
    _, rows = _read_rows(spec / "studies.csv")
    for token in ("FAMILIAL_LONGEVITY", "MR_MEDIATOR"):
        count = sum(1 for row in rows if row["phenotype_class"] == token)
        assert f"{token!r} ({count} rows)" in found[0]
    assert "'FAMILIAL'" not in found[0]


def test_only_recommended_classes_draw_no_warning(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM326"]
    spec = _spec(tmp_path, "clean", columns, fill)
    assert "phenotype_class_unrecognized" not in _summary(tmp_path, spec, strict=False)


# ── RM328: the ancestry a study was measured in ──────────────────────────────────────────────────


def test_ancestry_is_closed_over_the_1000g_superpopulations() -> None:
    assert VALID_SUPERPOPULATIONS == {"AFR", "AMR", "EAS", "EUR", "SAS"}
    marker = field_vocabularies(StudyRow)["ancestry"]
    assert marker["closed"] is True and set(marker["options"]) == VALID_SUPERPOPULATIONS
    assert _study(ancestry="EAS|EUR").ancestry == ["EAS", "EUR"]
    assert _study(ancestry="EUR").ancestry == ["EUR"]
    # Free text stays in `population`; a code list is not a description.
    for refused in ("European", "multi", "EUR|Ashkenazi"):
        with pytest.raises(ValidationError, match="ancestry"):
            _study(ancestry=refused)


def test_the_pgs_vocabulary_is_the_same_five_plus_multi() -> None:
    """One vocabulary, not two: `training_ancestry` is derived from the superpopulations."""
    assert VALID_TRAINING_ANCESTRY == VALID_SUPERPOPULATIONS | {"multi"}
    assert set(field_vocabularies(PgsRow)["training_ancestry"]["options"]) == VALID_TRAINING_ANCESTRY
    assert PgsRow(pgs_id="PGS000906", training_ancestry="multi").training_ancestry == ["multi"]


def test_ancestry_is_a_list_column_in_studies_parquet(tmp_path: Path) -> None:
    columns, fill = _GROUPS["RM328"]
    result = compile_module(_spec(tmp_path, "filled", columns, fill), tmp_path / "out")
    assert result.success, result.errors
    assert pl.read_parquet_schema(tmp_path / "out" / "studies.parquet")["ancestry"] == pl.List(pl.Utf8)

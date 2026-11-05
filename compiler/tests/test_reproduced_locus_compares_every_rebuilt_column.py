"""A locus is withheld as "reproduced by the row's cells" only when it is, on every carried column (RM389).

`withhold_reproduced_loci` nulls a key's `resolution_loci` wherever the row's own cells would rebuild the
table's rows exactly, and `reverse` then writes the table back from those cells. `_CELL_REBUILT` names the
carried columns the cell rebuild writes, `vrs_id`/`vrs_spec` among them, and a locus holding a value in
any other carried column is kept (RM380). But the comparison over the rebuilt columns was a hand-kept
tuple of six, without `vrs_id`/`vrs_spec`: a locus whose `vrs_spec` was `2.0` with no id (legal,
`ResolutionRow` does not pair them) matched on its coordinate, was withheld, and reverse wrote an empty
`vrs_spec`, because the cell lookup copies a version only beside an id. The same held for an id on a row
with no `ref`, which the lookup skips. A P7 loss, from 0.8 (RM364, widened by RM380).

The guard has two halves. The walk: perturb each carried column alone on a locus the cells reproduce,
and the set of columns that keep the locus must be every carried column, so a column the comparison
leaves out shows as a missing member. The round trip: every reference example with a `resolution.csv`,
its provenance stripped so the withhold is reachable, and a `vrs_spec` with no id on every positioned row,
must reverse to a table that still says `2.0`.
"""

import csv
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.parquets import (
    _CELL_REBUILT,
    CELL_FACT_FIELDS,
    RESOLUTION_LOCUS_DTYPE,
    RESOLUTION_LOCUS_FIELDS,
    cell_fact,
    withhold_reproduced_loci,
)
from just_dna_format.resolution import ResolutionRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

#: One row's cells, the way a `weights.parquet` record holds them (lists where the parquet has lists).
_CELLS: dict[str, Any] = {
    "rsid": "rs1",
    "chrom": "1",
    "start": 100,
    "ref": "A",
    "alts": ["G"],
    "locus_index": 0,
    "vrs_id": ["ga4gh:VA.__fXj0w0NCSkOLYF79GvSLtpDji99L42"],
    "vrs_spec": "2.0",
}


def _reproduced_locus() -> dict[str, Any]:
    """The locus the cells above rebuild, as `resolution_loci` holds it: every carried column, as stored."""
    locus: dict[str, Any] = dict.fromkeys(RESOLUTION_LOCUS_FIELDS)
    locus.update(
        {
            "rsid": "rs1",
            "chrom": "1",
            "start": 100,
            "ref": "A",
            "alts": "G",
            "locus_index": 0,
            "vrs_id": "ga4gh:VA.__fXj0w0NCSkOLYF79GvSLtpDji99L42",
            "vrs_spec": "2.0",
            "status": "resolved",
        }
    )
    return locus


def _other(value: Any, dtype: pl.DataType) -> Any:
    """A value of `dtype` different from `value`, non-empty."""
    if dtype == pl.Boolean:
        return value is not True
    if dtype.is_integer():
        return (value or 0) + 1
    return f"{value or ''}X"


def test_the_compared_columns_are_the_rebuilt_registry() -> None:
    """Every column `_CELL_REBUILT` names is compared, no exclusions, and each is a carried column."""
    assert set(CELL_FACT_FIELDS) == set(_CELL_REBUILT)
    assert set(_CELL_REBUILT) <= set(RESOLUTION_LOCUS_FIELDS), sorted(
        _CELL_REBUILT - set(RESOLUTION_LOCUS_FIELDS)
    )
    assert list(CELL_FACT_FIELDS) == [name for name in RESOLUTION_LOCUS_FIELDS if name in _CELL_REBUILT]


def test_a_locus_the_cells_rebuild_is_withheld() -> None:
    """The control: on a locus equal to the cells on every column, the column stays null."""
    assert withhold_reproduced_loci([[_reproduced_locus()]], ["rs1"], [cell_fact(_CELLS)]) == [None]


def test_every_carried_column_the_cells_would_not_write_back_keeps_the_locus() -> None:
    """Walk every carried column: a locus differing from the cells in that column alone is kept."""
    kept: set[str] = set()
    for field in RESOLUTION_LOCUS_DTYPE.fields:
        locus = _reproduced_locus()
        locus[field.name] = _other(locus[field.name], field.dtype)
        [cell] = withhold_reproduced_loci([[locus]], ["rs1"], [cell_fact(_CELLS)])
        if cell is not None:
            assert cell == [locus]
            kept.add(field.name)
    assert kept == set(RESOLUTION_LOCUS_FIELDS), (
        f"withheld although the cells would not write it back: {sorted(set(RESOLUTION_LOCUS_FIELDS) - kept)}"
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _examples_with_a_table() -> list[Path]:
    found = sorted(
        d
        for d in _EXAMPLES.iterdir()
        if (d / "module_spec.yaml").is_file() and (d / "resolution.csv").is_file()
    )
    assert found, f"no reference example under {_EXAMPLES} carries a resolution.csv"
    return found


def _stamp_a_version_with_no_id(spec: Path) -> None:
    """Strip every provenance column (so the withhold is reachable) and leave `vrs_spec=2.0`, no id."""
    rows = _rows(spec / "resolution.csv")
    provenance = set(RESOLUTION_LOCUS_FIELDS) - _CELL_REBUILT - {"status"}
    fieldnames = [*rows[0], *(name for name in ("vrs_id", "vrs_spec") if name not in rows[0])]
    with (spec / "resolution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            positioned = bool(row["chrom"] and row["start"])
            writer.writerow(
                {
                    **row,
                    **{name: "" for name in provenance if name in row},
                    "vrs_id": "",
                    "vrs_spec": "2.0" if positioned else "",
                }
            )


@pytest.mark.parametrize("example", _examples_with_a_table(), ids=lambda p: p.name)
def test_a_version_with_no_id_survives_the_round_trip(example: Path, tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(example, spec)
    _stamp_a_version_with_no_id(spec)
    lap1 = compile_module(spec, tmp_path / "o1")
    assert lap1.success, lap1.errors
    reverse_module(tmp_path / "o1", tmp_path / "back")
    build = lap1.manifest.genome_build
    returned = [
        ResolutionRow(**{k: v or None for k, v in row.items()})
        for row in _rows(tmp_path / "back" / "resolution.csv")
    ]
    positioned = [
        r for r in returned if r.genome_build == build and r.chrom is not None and r.start is not None
    ]
    assert positioned, f"{example.name}: the reversed table names no positioned row"
    lost = sorted({r.variant_key for r in positioned if r.vrs_spec != "2.0"})
    assert not lost, f"{example.name}: {len(lost)} key(s) came back without their vrs_spec, e.g. {lost[:3]}"
    lap2 = compile_module(tmp_path / "back", tmp_path / "o2")
    assert lap2.success, lap2.errors
    assert lap2.manifest.artifact.digest == lap1.manifest.artifact.digest
    assert lap2.manifest.content_signature == lap1.manifest.content_signature
    assert lap2.manifest.compilation.resolution_signature == lap1.manifest.compilation.resolution_signature


def test_an_id_on_a_row_with_no_ref_survives_the_round_trip(tmp_path: Path) -> None:
    """Grok's case: the cell lookup skips a table row with no `ref`, so the cells hold no id, while the
    locus does. Withheld, reverse wrote the id away."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / "hfe_hemochromatosis", spec)
    rows = _rows(spec / "resolution.csv")
    provenance = set(RESOLUTION_LOCUS_FIELDS) - _CELL_REBUILT - {"status"}
    with (spec / "resolution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, **{name: "" for name in provenance if name in row}, "ref": ""})
    stated = {row["variant_key"]: row["vrs_id"] for row in rows if row["vrs_id"]}
    assert stated, "the example must record an id for this to test anything"
    lap1 = compile_module(spec, tmp_path / "o1")
    assert lap1.success, lap1.errors
    reverse_module(tmp_path / "o1", tmp_path / "back")
    returned = {row["variant_key"]: row["vrs_id"] for row in _rows(tmp_path / "back" / "resolution.csv")}
    lost = sorted(key for key in returned.keys() & stated.keys() if returned[key] != stated[key])
    assert returned.keys() & stated.keys()
    assert not lost, f"{len(lost)} key(s) came back without their vrs_id, e.g. {lost[:3]}"

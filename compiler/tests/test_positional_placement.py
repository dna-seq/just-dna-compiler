"""How much of the 0.4 families joins by position, as counts rather than as a sentence (S31).

`resolution_subjects` (RM44) is the denominator for `variants.csv`; the positional tables had none,
so the only published record of whether a PGx module joins to a VCF was `UNJOINABLE_PHRASE` inside
`manifest.compilation.warnings` — and a downstream registry read it by substring. The consumer who
reported that had a 1,482-row `pharm_variants` module with a null coordinate on every row and found
out by opening the parquet.

Two things are pinned here and they are different claims: the counts agree with the artifact the
compile actually wrote, and `None` (this compiler did not count) stays distinguishable from `0` (the
module carries no positional table). Every expectation is computed at runtime — off the authored CSVs
or off the emitted parquet — so nothing here is a number transcribed from a dump.
"""

import csv
import io
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import _POSITIONAL_TABLE_KINDS, compile_module
from just_dna_format.manifest import Compilation

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _example_dirs() -> list[Path]:
    return sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())


def _authored_positional_rows(spec_dir: Path) -> int:
    """Rows across the three positional tables, counted off the files the author wrote."""
    total = 0
    for csv_name, _model in _POSITIONAL_TABLE_KINDS:
        for candidate in (spec_dir / csv_name, spec_dir / "derived" / csv_name):
            if candidate.is_file():
                total += len(list(csv.DictReader(io.StringIO(candidate.read_text()))))
    return total


@pytest.mark.parametrize("spec_dir", _example_dirs(), ids=lambda d: d.name)
def test_the_counts_describe_the_artifact_that_was_written(spec_dir: Path, tmp_path: Path) -> None:
    """`positional_rows` is what the author wrote; `positional_rows_placed` is what the parquet holds.

    The placed half is read back out of the emitted parquets rather than recomputed from the rows in
    memory, because the claim a consumer acts on is about the artifact: a coordinate that reached the
    manifest count but not the file would be exactly the gap this field exists to close.
    """
    out = tmp_path / spec_dir.name
    compile_module(spec_dir, out)
    compilation = json.loads((out / "manifest.json").read_text())["compilation"]

    assert compilation["positional_rows"] == _authored_positional_rows(spec_dir)

    placed = 0
    for csv_name, _model in _POSITIONAL_TABLE_KINDS:
        parquet = out / f"{Path(csv_name).stem}.parquet"
        if not parquet.is_file():
            continue
        frame = pl.read_parquet(parquet)
        placed += frame.filter(
            pl.col("chrom").is_not_null() & pl.col("start").is_not_null()
        ).height
    assert compilation["positional_rows_placed"] == placed
    assert compilation["positional_rows_placed"] <= compilation["positional_rows"]


def test_the_pgx_module_that_motivated_rm43_now_publishes_its_own_completeness(tmp_path: Path) -> None:
    """`pgx_slco1b1_simvastatin` is the reported case: table-only, so `fully_resolved` is vacuous.

    `fully_resolved=true` over `resolution_subjects=0` says nothing about a module whose every row
    lives in `pharm_variants.csv`. The positional pair is what carries the answer there, and post-RM43
    it is complete — which is the state a catalog could previously only infer from the *absence* of a
    warning sentence.
    """
    out = tmp_path / "slco1b1"
    compile_module(_EXAMPLES / "pgx_slco1b1_simvastatin", out)
    compilation = json.loads((out / "manifest.json").read_text())["compilation"]

    assert compilation["resolution_subjects"] == 0
    assert compilation["fully_resolved"] is True
    assert compilation["positional_rows"] > 0
    assert compilation["positional_rows_placed"] == compilation["positional_rows"]


def test_an_unresolved_compile_reports_the_shortfall_the_warning_describes(tmp_path: Path) -> None:
    """`--no-resolve` is the pre-RM43 shape on demand: the table is not consulted, so nothing is filled.

    The counts and the prose must agree, since they are the same facts twice — a catalog reading one
    and a human reading the other must not reach different conclusions.
    """
    out = tmp_path / "unresolved"
    result = compile_module(_EXAMPLES / "pgx_slco1b1_simvastatin", out, resolve_with_ensembl=False)
    compilation = json.loads((out / "manifest.json").read_text())["compilation"]

    assert compilation["positional_rows"] > 0
    assert compilation["positional_rows_placed"] < compilation["positional_rows"]
    unjoinable = compilation["positional_rows"] - compilation["positional_rows_placed"]
    assert any(f"{unjoinable} of {compilation['positional_rows']} row(s)" in w for w in result.warnings)


def test_a_legacy_manifest_does_not_claim_zero_positional_rows() -> None:
    """The field's second job: `None` is *this compiler did not say*, `0` is *no such table*.

    Defaulting to `0` would have a pre-0.6 manifest report "no positional rows" for the 1,482-row
    artifact that produced the report — the vacuous-`fully_resolved` failure re-made inside the field
    written to close it.
    """
    legacy = Compilation.model_validate({"compile_success": True, "compiler_version": "0.5.4"})
    assert legacy.positional_rows is None
    assert legacy.positional_rows_placed is None
    assert Compilation(positional_rows=0, positional_rows_placed=0).positional_rows == 0

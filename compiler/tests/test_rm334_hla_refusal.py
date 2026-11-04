"""RM334's HLA grammar on the real paths: `validate` and `compile` refuse alike, a good name round-trips.

The rule lives on `AlleleFunctionRow` (`schema/tests/test_rm334_hla_grammar.py` pins its cases). What
only the compiler can answer is that the refusal reaches both entry points with the row it is about
(`@validate-refuses-all`), in both modes, and that a well-formed HLA row is an ordinary
`allele_function.csv` row through `compile → reverse → compile` (Principle 7).

The fixture is a copy of `reference_examples/apoe_epsilon` plus an `allele_function.csv`, the shape a
longevitymap v2 module takes: APOE's ε alleles beside HLA-DRB1*15:01 and HLA-B*57:01.
"""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module, validate_spec

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"


def _spec(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    spec = tmp_path / "hla_spec"
    shutil.copytree(_EXAMPLE, spec)
    # The example's attestation binds the input files this fixture adds to; it is not under test.
    (spec / "verification.json").unlink()
    with (spec / "allele_function.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gene", "allele"])
        writer.writerows(rows)
    return spec


_GOOD: list[tuple[str, str]] = [("APOE", "e4"), ("HLA-DRB1", "*15:01"), ("HLA-B", "*57:01:01")]


@pytest.mark.parametrize("strict", [False, True])
def test_a_malformed_hla_name_is_refused_by_validate_and_compile_naming_its_row(
    tmp_path: Path, strict: bool
) -> None:
    spec = _spec(tmp_path, [*_GOOD, ("HLA-DRB1", "*1501")])

    validation = validate_spec(spec, strict=strict)
    assert not validation.valid
    compiled = compile_module(spec, tmp_path / "out", strict=strict)
    assert not compiled.success

    for errors in (validation.errors, compiled.errors):
        hla = [e for e in errors if "IPD-IMGT/HLA" in e]
        # One refusal, on the fourth data row (line 5 with the header), naming the value given.
        assert len(hla) == 1, errors
        assert hla[0].startswith("allele_function.csv line 5")
        assert "'*1501'" in hla[0]
    assert validation.errors == compiled.errors


def test_a_well_formed_hla_row_compiles_and_round_trips(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _GOOD)
    validation = validate_spec(spec, strict=True)
    assert validation.valid, validation.errors

    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    df = pl.read_parquet(tmp_path / "a1" / "allele_function.parquet")
    assert list(zip(df["gene"].to_list(), df["allele"].to_list(), strict=True)) == _GOOD

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "rev") == content_signature(spec)

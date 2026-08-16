"""RM55's fix on the compile path: the two new authored columns, and the notices they produce.

The schema tier owns the semantics (`schema/tests/test_measure_tiling.py`). What has to hold here is
what only the compiler can break: the columns reach the parquet and survive `compile → reverse →
compile` (a column missing from a reverse writer is silent data loss, which is the third of the three
touch points and the one that gets missed), the notices print **once** although `compile_module` runs
`validate_spec` inside itself, and the pre-flight says everything the compile says.
"""

import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.binning import (
    DEPRECATED_MODIFIER_PHRASE,
    FRACTIONAL_MEASURE_PHRASE,
)

_YAML = """\
schema_version: "1.0"
module:
  name: measure_tiling
  title: Measure Tiling Probe
  description: A probe module for the 0.6 measure_tiling column.
  report_title: tiling probe
  icon: dna
  color: "#b5651d"
defaults:
  curator: audit
  method: literature-review
genome_build: GRCh38
"""

_HEADER = (
    "gene,modifier_gene,modifier_cn,modifier_copy_number,measure_kind,measure_tiling,"
    "measure_min,measure_max,conclusion,unresolved\n"
)

#: A quantised catalog count, written exactly as it always was — the shape whose meaning must not move.
_QUANTISED = (
    "SMN1,,,,copy_number,,0,0,zero copies,false\n"
    "SMN1,,,,copy_number,,1,1,one copy,false\n"
    "SMN1,,,,copy_number,,2,2,two copies,false\n"
    "SMN1,,,,copy_number,,,,no copy number was called,true\n"
)

#: The same axis declared continuous, tiled the way a continuous axis has to be tiled — adjacent bins
#: sharing an endpoint, which is the tiling the schema refused before this release.
_CONTINUOUS = (
    "SMN1,,,,copy_number,continuous,0,1.5,one copy or fewer,false\n"
    "SMN1,,,,copy_number,continuous,1.5,2.5,about two copies,false\n"
    "SMN1,,,,copy_number,continuous,2.5,,a duplication,false\n"
    "SMN1,,,,copy_number,continuous,,,no copy number was called,true\n"
)

#: The deprecated dosage column, on several rows, so "once per table" is a claim with something to
#: collapse.
_DEPRECATED = (
    "SMN1,SMN2,2,,copy_number,,0,0,SMA type I,false\n"
    "SMN1,SMN2,3,,copy_number,,0,0,SMA type II,false\n"
    "SMN1,SMN2,4,,copy_number,,0,0,SMA type III,false\n"
)

#: Its replacement, holding a dosage the integer column cannot.
_FRACTIONAL_MODIFIER = (
    "SMN1,SMN2,,2.5,copy_number,,0,0,SMA with a partial SMN2 duplication,false\n"
)


def _spec(tmp_path: Path, copynumbers: str, name: str = "spec") -> Path:
    spec = tmp_path / name
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "copynumbers.csv").write_text(_HEADER + copynumbers)
    return spec


def _warnings(spec: Path, out: Path, *, strict: bool = False) -> list[str]:
    result = compile_module(spec, out, strict=strict)
    assert result.success, result.errors
    return list(result.warnings)


def _matching(warnings: list[str], fragment: str) -> list[str]:
    return [w for w in warnings if fragment in w]


# ── The columns reach the artifact, and come back ──────────────────────────────────────────────


def test_both_new_columns_reach_the_parquet_with_the_types_the_model_declares(
    tmp_path: Path,
) -> None:
    """`_build_table` derives its schema from `model_fields`, so this should need no compiler edit —
    which is a prediction, and the point of the test is to check it rather than assume it.

    The `@property` alias must **not** appear: it is not a model field, and a derived column in the
    parquet is a second spelling of a number the row already carries.
    """
    result = compile_module(_spec(tmp_path, _CONTINUOUS + _FRACTIONAL_MODIFIER), tmp_path / "out")
    assert result.success, result.errors
    schema = pl.read_parquet_schema(tmp_path / "out" / "copynumbers.parquet")
    assert schema["measure_tiling"] == pl.Utf8
    assert schema["modifier_copy_number"] == pl.Float64
    assert schema["modifier_cn"] == pl.Int64
    assert "effective_modifier_copy_number" not in schema

    values = pl.read_parquet(tmp_path / "out" / "copynumbers.parquet")
    assert set(values["measure_tiling"].drop_nulls().to_list()) == {"continuous"}
    assert values["modifier_copy_number"].drop_nulls().to_list() == [2.5]


def test_the_new_columns_survive_compile_reverse_compile(tmp_path: Path) -> None:
    """The third touch point — a column missing from the reverse `fieldnames` round-trips as silent
    data loss, so every new authored column owes this (P7).

    Asserted on the *cells* and on `content_signature`, not only on the signature: a signature match
    would also hold if reverse dropped a column the recompile then omitted from the hash the same way.
    """
    spec = _spec(tmp_path, _CONTINUOUS + _FRACTIONAL_MODIFIER)
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    reversed_csv = (tmp_path / "rev" / "copynumbers.csv").read_text()
    assert reversed_csv.count("continuous") == 4
    assert "2.5" in reversed_csv
    assert validate_spec(tmp_path / "rev").valid

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert first.manifest.content_signature == second.manifest.content_signature
    assert first.manifest.artifact.digest == second.manifest.artifact.digest

    # A second lap, because "recompiles" and "is a fixed point" are different claims.
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    assert (tmp_path / "rev2" / "copynumbers.csv").read_text() == reversed_csv


def test_a_table_that_declares_nothing_keeps_its_authored_identity(tmp_path: Path) -> None:
    """Absent means the kind's default, so an unset optional column is omitted from the hash and the
    authored identity of every already-published module is unchanged (P3).

    Demonstrated by hashing the same rows with and without the tiling declared: the two differ, and
    the undeclared one is what a pre-0.6 module is.
    """
    plain = compile_module(_spec(tmp_path, _QUANTISED, "plain"), tmp_path / "a")
    declared = compile_module(
        _spec(tmp_path, _QUANTISED.replace(",copy_number,,", ",copy_number,quantised,"), "declared"),
        tmp_path / "b",
    )
    assert plain.success and declared.success
    assert plain.manifest.content_signature != declared.manifest.content_signature


# ── The notices, on the real compile path ──────────────────────────────────────────────────────


def test_the_rm55_warning_is_silent_on_a_continuous_table_and_fires_on_a_quantised_one(
    tmp_path: Path,
) -> None:
    """Its central claim stops being true where the effective tiling is continuous, so the sentence
    must stop being said there — while the table that really is a grid still hears it."""
    quantised = _warnings(_spec(tmp_path, _QUANTISED, "q"), tmp_path / "outq")
    continuous = _warnings(_spec(tmp_path, _CONTINUOUS, "c"), tmp_path / "outc")
    assert len(_matching(quantised, FRACTIONAL_MEASURE_PHRASE)) == 1
    assert _matching(quantised, FRACTIONAL_MEASURE_PHRASE)[0].startswith("copynumbers.csv: ")
    assert _matching(continuous, FRACTIONAL_MEASURE_PHRASE) == []


def test_the_inference_line_reaches_the_published_manifest(tmp_path: Path) -> None:
    """A consumer reindexing from a published `manifest.json` has no spec directory left, and *how
    the bins were read* is exactly the thing they must not have to guess at."""
    spec = _spec(tmp_path, _QUANTISED.replace("2,2,two copies", "2,2.5,about two copies"))
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    published = json.loads((tmp_path / "out" / "manifest.json").read_text())["compilation"][
        "warnings"
    ]
    inferred = _matching(published, "tiling inferred")
    assert len(inferred) == 1
    assert "2.5" in inferred[0]
    # …and having been read as continuous, the table no longer hears the RM55 line.
    assert _matching(published, FRACTIONAL_MEASURE_PHRASE) == []


def test_conflicting_declarations_in_one_group_refuse_the_compile(tmp_path: Path) -> None:
    """An error, not a warning: the rules run per group and there is no tiling to run them under."""
    conflicting = (
        "SMN1,,,,copy_number,quantised,0,1,low,false\n"
        "SMN1,,,,copy_number,continuous,2,3,high,false\n"
    )
    result = compile_module(_spec(tmp_path, conflicting), tmp_path / "out")
    assert not result.success
    assert any("conflicting measure_tiling" in e for e in result.errors), result.errors


# ── The deprecation ────────────────────────────────────────────────────────────────────────────


def test_the_deprecation_prints_once_per_table_and_not_once_per_row(tmp_path: Path) -> None:
    """Three rows use the column; `compile_module` runs `validate_spec` inside itself, so an
    un-deduplicated per-row notice would be six lines. It is one."""
    warnings = _warnings(_spec(tmp_path, _DEPRECATED), tmp_path / "out")
    found = _matching(warnings, DEPRECATED_MODIFIER_PHRASE)
    assert len(found) == 1
    assert found[0].startswith("copynumbers.csv: ")
    assert "modifier_copy_number" in found[0]


def test_the_deprecated_column_still_compiles_in_both_modes(tmp_path: Path) -> None:
    """Warn-only is the whole of what a deprecation in a minor may do (P3) — the field still reads
    and behaves exactly as before, and `strict` has nothing to escalate."""
    lax = _warnings(_spec(tmp_path, _DEPRECATED, "lax"), tmp_path / "outl", strict=False)
    strict = _warnings(_spec(tmp_path, _DEPRECATED, "str"), tmp_path / "outs", strict=True)
    assert _matching(lax, DEPRECATED_MODIFIER_PHRASE) == _matching(
        strict, DEPRECATED_MODIFIER_PHRASE
    )


def test_the_replacement_column_says_nothing(tmp_path: Path) -> None:
    """A warning an author has already acted on is noise."""
    warnings = _warnings(_spec(tmp_path, _FRACTIONAL_MODIFIER), tmp_path / "out")
    assert _matching(warnings, DEPRECATED_MODIFIER_PHRASE) == []


def test_both_dosage_columns_on_one_row_refuse_at_load(tmp_path: Path) -> None:
    both = "SMN1,SMN2,2,2.0,copy_number,,0,0,SMA,false\n"
    result = compile_module(_spec(tmp_path, both), tmp_path / "out")
    assert not result.success
    assert any("two spellings of one dosage" in e for e in result.errors), result.errors


# ── validate/compile parity ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rows, phrase",
    [
        (_QUANTISED, FRACTIONAL_MEASURE_PHRASE),
        (_DEPRECATED, DEPRECATED_MODIFIER_PHRASE),
        (_QUANTISED.replace("2,2,two copies", "2,2.5,about two copies"), "tiling inferred"),
    ],
    ids=["RM55 conditional", "modifier_cn deprecation", "inferred tiling"],
)
def test_validate_reports_exactly_what_compile_reports(
    tmp_path: Path, rows: str, phrase: str
) -> None:
    """The author's pre-flight must not be quieter than the compile that follows it — all three are
    pure computation over authored bytes with no `output_dir`, which is the standing rule."""
    spec = _spec(tmp_path, rows)
    from_validate = list(validate_spec(spec).warnings)
    from_compile = _warnings(spec, tmp_path / "out")
    assert _matching(from_validate, phrase)
    assert _matching(from_validate, phrase) == _matching(from_compile, phrase)

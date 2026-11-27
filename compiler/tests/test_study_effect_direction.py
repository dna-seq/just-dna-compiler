"""RM435 on a copy of HFE, which has both study rows and the GWAS parquet precedent."""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    compile_module,
    content_signature,
    reverse_module,
    spec_tables,
    validate_spec,
)
from just_dna_format.integrity import content_signature as hash_tables
from pydantic import RootModel

_HFE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"
_CODE = "study_effect_direction_disagrees_with_size"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    path = shutil.copytree(_HFE, tmp_path / "spec")
    (path / "verification.json").unlink()  # it attests the original inputs
    return path


def _write(spec: Path, rows: list[dict[str, str]]) -> None:
    with (spec / "studies.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
        writer.writeheader()
        writer.writerows(rows)


def test_absent_and_empty_direction_keep_the_reference_signature(spec: Path) -> None:
    rows = _read(spec / "studies.csv")
    # Rebuild the baseline from the original study CSV's own columns. An added model default
    # leaking into the hash would move both a missing header and a blank one together.
    tables, build = spec_tables(_HFE)
    original_columns = set(rows[0])
    tables["studies.csv"] = [
        RootModel(row.model_dump(mode="json", include=original_columns, exclude_none=True))
        for row in tables["studies.csv"]
    ]
    baseline = hash_tables(tables, build)
    assert content_signature(_HFE) == baseline
    rows[0]["effect_direction"] = ""
    _write(spec, rows)
    assert content_signature(spec) == baseline
    rows[0]["effect_direction"] = "decrease"
    _write(spec, rows)
    assert content_signature(spec) != baseline


def test_parquet_type_matches_gwas_even_when_direction_is_absent(spec: Path, tmp_path: Path) -> None:
    out = tmp_path / "compiled"
    result = compile_module(spec, out)
    assert result.success, result.errors
    study = pl.read_parquet(out / "studies.parquet")
    assert (
        study.schema["effect_direction"]
        == pl.read_parquet_schema(out / "gwas_effects.parquet")["effect_direction"]
    )
    assert study["effect_direction"].null_count() == study.height


def test_round_trip_with_and_without_a_size(spec: Path, tmp_path: Path) -> None:
    rows = _read(spec / "studies.csv")
    alleles = {r["rsid"]: r["ref"] for r in _read(spec / "resolution.csv")}
    rows[0].update(
        effect_allele=alleles[rows[0]["rsid"]],
        effect_direction="increase",
        effect_size="0.3",
        effect_measure="beta",
    )
    rows[1].update(effect_allele=alleles[rows[1]["rsid"]], effect_direction="decrease")
    _write(spec, rows)
    expected = [r.get("effect_direction") or None for r in rows]
    out, rev = tmp_path / "first", tmp_path / "rev"
    first = compile_module(spec, out)
    assert first.success and first.manifest, first.errors
    assert pl.read_parquet(out / "studies.parquet")["effect_direction"].to_list() == expected
    reverse_module(out, rev)
    assert [r["effect_direction"] or None for r in _read(rev / "studies.csv")] == expected
    second = compile_module(rev, tmp_path / "second")
    assert second.success and second.manifest, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature


@pytest.mark.parametrize("strict", [False, True])
def test_direction_without_allele_warns_and_keeps_the_row(spec: Path, tmp_path: Path, strict: bool) -> None:
    rows = _read(spec / "studies.csv")
    rows[0]["effect_direction"] = "increase"
    _write(spec, rows)
    validated = validate_spec(spec, strict=strict)
    compiled = compile_module(spec, tmp_path / "out", strict=strict)
    assert validated.valid and compiled.success, (validated.errors, compiled.errors)
    for result in (validated, compiled):
        assert result.warnings_summary["paired_field_half_stated"] == 1
        assert sum("state effect_direction with effect_allele empty" in w for w in result.warnings) == 1
        assert _CODE not in result.warnings_summary
    study = pl.read_parquet(tmp_path / "out" / "studies.parquet")
    assert study.height == len(rows)
    assert study["effect_direction"][0] == "increase" and study["effect_allele"][0] is None


@pytest.mark.parametrize("strict", [False, True])
def test_disagreement_and_withholding_reach_each_command_once(
    spec: Path, tmp_path: Path, strict: bool
) -> None:
    rows = _read(spec / "studies.csv")
    # Include both sides of both nulls, plus a replication with direction alone.
    cases = [
        ("beta", "-0.2", "decrease", "agree"),
        ("OR", "1.2", "increase", "agree"),
        ("beta", "0.2", "increase", "agree"),
        ("OR", "0.8", "decrease", "agree"),
        ("beta", "-0.3", "increase", "disagree"),
        ("OR", "1.3", "decrease", "disagree"),
        ("beta", "0", "decrease", "withhold"),
        ("OR", "1", "increase", "withhold"),
        ("NR", "2", "decrease", "withhold"),
        ("custom", "-2", "increase", "withhold"),
        ("", "", "decrease", "incomplete"),
    ]
    alleles = {r["rsid"]: r["ref"] for r in _read(spec / "resolution.csv")}
    disagreements = []
    for row, (measure, size, direction, verdict) in zip(rows[: len(cases)], cases, strict=True):
        row.update(
            effect_allele=alleles[row["rsid"]],
            effect_direction=direction,
            effect_size=size,
            effect_measure=measure,
        )
        if verdict == "disagree":
            disagreements.append(row)
    _write(spec, rows)
    validated = validate_spec(spec, strict=strict)
    compiled = compile_module(spec, tmp_path / "out", strict=strict)
    assert validated.valid and compiled.success and compiled.manifest, (validated.errors, compiled.errors)
    for result in (validated, compiled):
        assert result.stats["study_effect_direction_withheld"] == sum(
            verdict == "withhold" for *_, verdict in cases
        )
    for result in (validated, compiled, compiled.manifest.compilation):
        assert result.warnings_summary[_CODE] == 1
        [finding] = [w for w in result.warnings if "effect_direction disagrees with effect_size" in w]
        assert f"{len(disagreements)} row(s)" in finding
        for row in disagreements:
            assert (
                f"{row['rsid']} (PMID {row['pmid']}): "
                f"{row['effect_direction']} with {row['effect_measure']} {row['effect_size']}"
            ) in finding

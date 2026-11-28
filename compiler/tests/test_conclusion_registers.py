"""RM302: authored wordings survive the same compiler paths as the detailed conclusion."""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.compiler.tables import _TABLE_KINDS
from just_dna_compiler.draft import DRAFTABLE, authoring_requirements
from just_dna_format.base import field_category, field_first_seen
from just_dna_format.binning import MeasureBinRow
from just_dna_format.pgx import DiplotypeRow, PharmVariantRow
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import RESERVED_NAME_REASONS
from pydantic import ValidationError

_ROOT = Path(__file__).resolve().parents[2]
_REGISTERS = ("conclusion_lay", "conclusion_concise")
_CARRIERS = (VariantRow, DiplotypeRow, PharmVariantRow, MeasureBinRow)
_TABLES = {"variants.csv": "annotations.parquet"} | {
    csv_name: parquet for csv_name, parquet, model in _TABLE_KINDS if issubclass(model, _CARRIERS)
}


def _spec(tmp_path: Path, example: Path) -> Path:
    spec = shutil.copytree(example, tmp_path / "spec")
    (spec / "verification.json").unlink(missing_ok=True)
    return spec


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)


def _identities(spec: Path, out: Path) -> tuple[str, str]:
    result = compile_module(spec, out)
    assert result.success and result.manifest, result.errors
    return result.manifest.content_signature, result.manifest.artifact.digest


def test_exact_register_carriers_and_requiredness() -> None:
    for model in _ALL_MODELS.values():
        fields = set(_REGISTERS) & model.model_fields.keys()
        assert fields == (set(_REGISTERS) if issubclass(model, _CARRIERS) else set())
        if fields:
            assert field_category(model, "conclusion") == "required"
            for name in fields:
                assert field_category(model, name) == "optional"
                assert field_first_seen(model)[name] == "0.10.0"
    for table in _TABLES:
        assert set(_REGISTERS).isdisjoint(DRAFTABLE[table]._KEY_FIELDS)
        assert set(_REGISTERS) <= set(authoring_requirements(table)["optional"])


def test_language_is_reserved_across_the_authored_surface() -> None:
    assert all("language" not in model.model_fields for model in _ALL_MODELS.values())
    with pytest.raises(ValidationError, match="language.*separate axis from register"):
        VariantRow.model_validate({"language": "de"})
    assert "language" in RESERVED_NAME_REASONS


@pytest.mark.parametrize("table,parquet", _TABLES.items())
def test_registers_round_trip(tmp_path: Path, table: str, parquet: str) -> None:
    # Use the shortest shipped example of each kind to exercise its real row and reverse writer.
    examples = (_ROOT / "reference_examples").glob(f"*/{table}")
    example = min(examples, key=lambda p: (p.stat().st_size, p.as_posix()))
    spec = _spec(tmp_path, example.parent)
    path = spec / table
    rows = _read(path)
    original = _identities(spec, tmp_path / "original")
    for register in _REGISTERS:
        rows[0][register] = "  "
    _write(path, rows)
    assert _identities(spec, tmp_path / "empty") == original
    assert set(_REGISTERS).isdisjoint(pl.read_parquet_schema(tmp_path / "empty" / parquet))
    model = DRAFTABLE[table].model_validate({name: value or None for name, value in rows[0].items()})
    assert all(getattr(model, name) is None for name in _REGISTERS)

    # State each register on its own first: either changes the signature independently.
    for register in _REGISTERS:
        rows[0][register] = rows[0]["conclusion"]
        _write(path, rows)
        out = tmp_path / register
        assert _identities(spec, out)[0] != original[0]
        assert set(_REGISTERS) & pl.read_parquet_schema(out / parquet).keys() == {register}
        rows[0][register] = ""
    rows[0]["conclusion_lay"] = rows[0]["conclusion"]
    rows[-1]["conclusion_concise"] = rows[-1].get("phenotype") or rows[-1]["conclusion"]
    _write(path, rows)
    expected = [tuple(row.get(name) or None for name in _REGISTERS) for row in rows]

    first = _identities(spec, tmp_path / "first")
    frame = pl.read_parquet(tmp_path / "first" / parquet)
    assert frame.select(_REGISTERS).rows() == expected
    restored = reverse_module(tmp_path / "first", tmp_path / "restored")
    assert [tuple(r[name] or None for name in _REGISTERS) for r in _read(restored / table)] == expected
    assert _identities(restored, tmp_path / "second") == first


def test_mixed_case_genotype_rejoins_its_register(tmp_path: Path) -> None:
    spec = _spec(tmp_path, _ROOT / "reference_examples" / "grch37_build")
    path = spec / "variants.csv"
    rows = _read(path)
    het = next(row for row in rows if row["genotype"] == "A/G")
    het.update(genotype="a/G", conclusion_lay=het["conclusion"])
    _write(path, rows)
    first = _identities(spec, tmp_path / "first")
    restored = reverse_module(tmp_path / "first", tmp_path / "restored")
    assert (het["genotype"], het["conclusion_lay"]) in {
        (row["genotype"], row["conclusion_lay"]) for row in _read(restored / path.name)
    }
    assert _identities(restored, tmp_path / "second") == first


@pytest.mark.parametrize("register", _REGISTERS)
@pytest.mark.parametrize(
    "left,right", [("", "first"), ("first", ""), ("first", "first"), ("first", "second")]
)
def test_duplicate_claim_register_conflict(tmp_path: Path, register: str, left: str, right: str) -> None:
    spec = _spec(tmp_path, _ROOT / "reference_examples" / "grch37_build")
    path = spec / "variants.csv"
    rows = _read(path)
    first = rows[0]
    rows += [dict(first, **{register: right})]
    first[register] = left
    _write(path, rows)
    result = validate_spec(spec)
    assert any("Duplicate (variant, genotype)" in error for error in result.errors)
    conflicts = [error for error in result.errors if "different wordings for the same claim" in error]
    if left and right and left != right:
        assert len(conflicts) == 1 and register in conflicts[0]
    else:
        assert conflicts == []


def test_tools_leave_register_wording_to_authors() -> None:
    compiler = _ROOT / "compiler/src/just_dna_compiler"
    sources = [
        *(_ROOT / "enricher/src").rglob("*.py"),
        *(p for p in compiler.rglob("*.py") if p.stem in {"scaffold", "hints"}),
    ]
    assert {
        path.relative_to(_ROOT)
        for path in sources
        if any(register in path.read_text(encoding="utf-8") for register in _REGISTERS)
    } == set()

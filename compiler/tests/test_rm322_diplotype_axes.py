"""`negatives` and `category` on `diplotypes.csv` (0.8, RM322).

APOE is scored once, as an ε diplotype, so the module's headline locus is a `DiplotypeRow` — and before
0.8 that row could state neither the trade-off a protective allele carries (`negatives`) nor the group
the report files it under (`category`), both of which a `variants.csv` row has carried since 0.2. The
maintainer cut the item to exactly these two columns on 2026-11-04 (`priority`, `actionability` and
`flags` were cut, not deferred).

What only the real paths can answer, and so what is asserted here:

* both columns are the **same columns** `VariantRow` has: free text, the same description, and no
  vocabulary on `category` on either model (a closed set here would be a second, stricter grammar for
  one word);
* both reach `diplotypes.parquet` as nullable strings carrying the authored cell, row for row;
* `compile → reverse → compile` writes them back — header included, since a reverse writer that drops
  a column fails silently (`@three-touch-points`) — and lands on the same `artifact.digest` and
  `content_signature` (Principle 7);
* both are authored content, so filling either moves `content_signature`, while a module that never
  writes them, or writes the header with every cell empty, keeps the signature it had (P3/P8).

The fixture is a copy of `reference_examples/apoe_epsilon`, the module the item was found against. The
two cells per row are generated here and read back off the CSV the test wrote, so every expectation is
computed from what was authored rather than restated.
"""

import csv
import shutil
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module, validate_spec
from just_dna_format.base import field_first_seen, field_vocabularies
from just_dna_format.pgx import DiplotypeRow
from just_dna_format.spec import VariantRow

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"
_NEW_COLUMNS: tuple[str, ...] = ("negatives", "category")
_KEY: tuple[str, ...] = ("haplotype_a", "haplotype_b")


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _spec_with_axes(tmp_path: Path, name: str, fill: bool) -> Path:
    """A copy of the APOE example carrying both columns.

    With `fill`, the ε4-carrying rows state a trade-off and a category, the ε2 rows a different
    category and no trade-off, and ε3/ε3 neither — so the column carries distinct values *and* empty
    cells, and a writer that collapsed one into the other could not pass. Without `fill`, the header
    is present and every cell is empty.
    """
    spec = tmp_path / name
    shutil.copytree(_EXAMPLE, spec)
    # The example is closed, and its attestation binds the bytes this edit changes; the attestation
    # is not what this test is about, so the copy carries none.
    (spec / "verification.json").unlink()
    header, rows = _read_rows(spec / "diplotypes.csv")
    for row in rows:
        pair = {row["haplotype_a"], row["haplotype_b"]}
        row["negatives"] = ""
        row["category"] = ""
        if not fill:
            continue
        if "e4" in pair:
            row["negatives"] = f"{row['phenotype']}: higher LDL cholesterol beside the Alzheimer's risk"
            row["category"] = "neurodegeneration"
        elif "e2" in pair:
            row["category"] = "lipid metabolism"
    _write_rows(spec / "diplotypes.csv", header + list(_NEW_COLUMNS), rows)
    return spec


def _authored(spec: Path) -> dict[tuple[str, ...], dict[str, str | None]]:
    """The authored cells per diplotype, keyed by the pair; an empty cell is the unstated `None`."""
    _, rows = _read_rows(spec / "diplotypes.csv")
    return {tuple(row[c] for c in _KEY): {c: row.get(c) or None for c in _NEW_COLUMNS} for row in rows}


def test_both_columns_are_the_variant_row_columns_of_the_same_name() -> None:
    """Copied, not re-invented: same annotation, same description, and no vocabulary on either.

    `VariantRow.category` binds no vocabulary; a closed set on the diplotype copy alone would make the
    one word legal in one table and refused in the other, which is the inconsistency
    `validate_haplotype_name` was written to remove.
    """
    for name in _NEW_COLUMNS:
        mine, theirs = DiplotypeRow.model_fields[name], VariantRow.model_fields[name]
        assert mine.annotation == theirs.annotation == (str | None)
        assert mine.description == theirs.description
        assert mine.default is None
    assert not set(_NEW_COLUMNS) & set(field_vocabularies(DiplotypeRow))
    assert not set(_NEW_COLUMNS) & set(field_vocabularies(VariantRow))
    assert {name: field_first_seen(DiplotypeRow)[name] for name in _NEW_COLUMNS} == dict.fromkeys(
        _NEW_COLUMNS, "0.8.0"
    )


def test_the_fixture_carries_distinct_values_and_empty_cells_in_both_columns(tmp_path: Path) -> None:
    """The fixture earns its place, or the round trip below asserts over a uniform column."""
    authored = _authored(_spec_with_axes(tmp_path, "filled", fill=True))
    for name in _NEW_COLUMNS:
        values = [cells[name] for cells in authored.values()]
        assert None in values
        assert len({v for v in values if v is not None}) >= 1
    assert len({cells["category"] for cells in authored.values()} - {None}) == 2


def test_both_columns_reach_the_diplotype_parquet_as_nullable_strings(tmp_path: Path) -> None:
    spec = _spec_with_axes(tmp_path, "filled", fill=True)
    validation = validate_spec(spec, strict=True)
    assert validation.valid, validation.errors
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors

    df = pl.read_parquet(tmp_path / "out" / "diplotypes.parquet")
    for name in _NEW_COLUMNS:
        assert df.schema[name] == pl.Utf8
    materialized = {
        tuple(row[c] for c in _KEY): {c: row[c] for c in _NEW_COLUMNS} for row in df.iter_rows(named=True)
    }
    authored = _authored(spec)
    assert len(df) == len(_read_rows(spec / "diplotypes.csv")[1])
    assert materialized == authored


def test_both_columns_survive_reverse_and_recompile_to_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec_with_axes(tmp_path, "filled", fill=True)
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    header, _ = _read_rows(tmp_path / "rev" / "diplotypes.csv")
    assert set(_NEW_COLUMNS) <= set(header)
    assert _authored(tmp_path / "rev") == _authored(spec)

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "rev") == content_signature(spec)


def test_both_columns_are_authored_content_and_an_unwritten_one_hashes_as_before(tmp_path: Path) -> None:
    """Inside `content_signature` when stated; invisible to it when not (P3/P8, Principle 4).

    `negatives` is the claim RM322 exists to make authorable, so a module that states it is different
    content from one that does not. A module that never wrote either column — every published one —
    keeps its signature byte for byte, and so does one carrying the header with every cell empty.
    """
    baseline = content_signature(_EXAMPLE)
    assert content_signature(_spec_with_axes(tmp_path, "empty", fill=False)) == baseline

    filled = _spec_with_axes(tmp_path, "filled", fill=True)
    assert content_signature(filled) != baseline

    for name in _NEW_COLUMNS:
        spec = _spec_with_axes(tmp_path, f"only_{name}", fill=True)
        header, rows = _read_rows(spec / "diplotypes.csv")
        for other in set(_NEW_COLUMNS) - {name}:
            for row in rows:
                row[other] = ""
        _write_rows(spec / "diplotypes.csv", header, rows)
        assert content_signature(spec) != baseline, name

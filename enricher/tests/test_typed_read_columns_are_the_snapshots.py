"""Every hand-kept typed column list a remote answer's rows are read through is the snapshot's (0.9, review
round 1, item 4; `@registry-completeness`).

A keyed reader runs one SQL body over the local files and over a remote answer's rows; the rows are typed by
a module-level `(name, duckdb type)` list handed to `resolver._rows_connection` or `_typed_rows_connection`.
Each list restates a schema some builder writes, so each is held against that builder's output here: CIViC,
ClinPGx, ClinVar-GKM and the drug labels against their builders' schema functions, Open Targets against the
slice its `subset_snapshot` cut, ClinVar against a snapshot built from the ClinVar slice, and Ensembl, whose
builder is prepare-annotations', against the split slice it published. The lists are found by an AST walk
over the call sites, so a list added without a source here fails the walk rather than going unchecked.
"""

import ast
import importlib
from collections.abc import Callable
from pathlib import Path

import duckdb
import just_dna_enricher
import polars as pl
import pytest
from just_dna_enricher import (
    civic_build,
    clinpgx_build,
    clinvar_gkm_build,
    drug_labels_build,
    lookup,
    remote,
)
from just_dna_enricher.clinvar_build import build_snapshot as build_clinvar

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_ENSEMBL_SLICE = _ASSETS / "ensembl_split_multialt" / "split" / "data" / "homo_sapiens-split.parquet"
_OPENTARGETS = _ASSETS / "opentargets_slice" / "data"
_CALLS = {"_rows_connection", "_typed_rows_connection"}
#: A snapshot's integer type a typed list may declare wider, losslessly: Ensembl's `start` is `UINTEGER` on
#: disk and `BIGINT` in the rows, so a position compares with the readers' `BIGINT` literals.
_WIDENED = {
    (narrow, "BIGINT") for narrow in ("UINTEGER", "INTEGER", "USMALLINT", "SMALLINT", "UTINYINT", "TINYINT")
}


def _typed_lists() -> set[tuple[str, str]]:
    """`(module, name)` of every list a reader hands a rows connection as its columns, from the call sites."""
    found: set[tuple[str, str]] = set()
    for path in sorted(_PACKAGE.rglob("*.py")):
        module = path.relative_to(_PACKAGE).with_suffix("").as_posix().replace("/", ".")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name not in _CALLS:
                continue
            specs = (
                [node.args]
                if name == "_rows_connection"
                else [a.elts for a in node.args if isinstance(a, ast.Tuple)]
            )
            for spec in specs:
                assert len(spec) > 1 and isinstance(spec[1], ast.Name), (
                    f"{module}:{node.lineno} types a rows connection by something other than a named list"
                )
                found.add((module, spec[1].id))
    return found


def _described(path: Path | str) -> dict[str, str]:
    """A parquet's columns and their duckdb types, in order."""
    quoted = str(path).replace("'", "''")
    return {
        str(name): str(kind)
        for name, kind, *_ in duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{quoted}')").fetchall()
    }


def _of_schema(schema: dict, tmp: Path) -> dict[str, str]:
    """A builder's polars schema as duckdb reads it from the parquet the builder writes with it."""
    target = tmp / "schema.parquet"
    pl.DataFrame(schema=schema).write_parquet(target)
    return _described(target)


def _clinvar(tmp: Path) -> dict[str, str]:
    root = build_clinvar(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", tmp / "clinvar").out_dir
    return _described(min((root / "data").glob("*.parquet")))


#: `(module, list)` -> (the columns and types its source writes, whether the list is the whole table).
_SOURCES: dict[tuple[str, str], tuple[Callable[[Path], dict[str, str]], bool]] = {
    ("civic_draft", "_CIVIC_COLUMNS"): (lambda tmp: _of_schema(civic_build._polars_schema(), tmp), True),
    ("clinpgx", "_ANNOTATION_COLUMNS"): (lambda tmp: _of_schema(clinpgx_build._schema(), tmp), True),
    ("clinvar_gkm", "_WITNESS_COLUMNS"): (
        lambda tmp: _of_schema(clinvar_gkm_build._witness_schema(), tmp),
        True,
    ),
    ("drug_labels", "_LABEL_COLUMN_TYPES"): (lambda tmp: _of_schema(drug_labels_build._schema(), tmp), True),
    ("opentargets", "_VARIANT_COLUMNS"): (lambda tmp: _described(_OPENTARGETS / "variants.parquet"), True),
    ("opentargets", "_CONSEQUENCE_COLUMNS"): (
        lambda tmp: _described(_OPENTARGETS / "consequences-00000.parquet"),
        True,
    ),
    ("opentargets", "_MEMBER_COLUMNS"): (
        lambda tmp: _described(_OPENTARGETS / "credible_set_members-00000.parquet"),
        True,
    ),
    # Read subsets: the reader's SQL names these and no other (a column it named and the list lacked would
    # fail every remote test with a binder error), so each listed column is held to the snapshot's type.
    ("clinvar", "_CLINVAR_READ_COLUMNS"): (_clinvar, False),
    ("resolver", "_ENSEMBL_READ_COLUMNS"): (lambda tmp: _described(_ENSEMBL_SLICE), False),
}


def test_every_typed_list_a_reader_types_remote_rows_by_has_a_source_here() -> None:
    """The walk over the call sites and this registry are one set: a new list owes a source."""
    assert _typed_lists() == set(_SOURCES)


@pytest.mark.parametrize(("module", "name"), sorted(_SOURCES))
def test_a_typed_list_is_the_schema_its_builder_writes(module: str, name: str, tmp_path: Path) -> None:
    declared = dict(getattr(importlib.import_module(f"just_dna_enricher.{module}"), name))
    source, whole = _SOURCES[(module, name)]
    written = source(tmp_path)
    if whole:
        assert list(declared) == list(written), "the list names the table's columns, in the table's order"
    assert set(declared) <= set(written), sorted(set(declared) - set(written))
    differing = {
        column: (kind, written[column])
        for column, kind in declared.items()
        if kind != written[column] and (written[column], kind) not in _WIDENED
    }
    assert not differing, differing


@pytest.mark.parametrize(
    ("lane", "files"),
    [
        ("ensembl", ["homo_sapiens-chr1.parquet", "homo_sapiens-chrX.parquet", "homo_sapiens-chrMT.parquet"]),
        ("clinvar", ["clinvar.parquet"]),
    ],
)
def test_the_table_a_snapshot_link_asks_remotely_is_the_one_its_files_are_named_as(
    lane: str, files: list[str], tmp_path: Path
) -> None:
    """`lookup._REMOTE_TABLES` names each link's table as `remote.table_name` names its `data/` files."""
    if lane == "clinvar":
        root = build_clinvar(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", tmp_path / "clinvar").out_dir
        files = [p.name for p in (root / "data").glob("*.parquet")]
    assert {remote.table_name(f"data/{name}") for name in files} == {lookup._REMOTE_TABLES[lane]}
    assert set(lookup._REMOTE_TABLES) <= set(remote.REMOTE_LANES)

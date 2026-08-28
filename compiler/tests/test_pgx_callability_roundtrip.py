"""`requires_callable` on `haplotypes.csv` / `pharm_variants.csv` through the compiler (0.7, RM70).

The schema half is pinned in `schema/tests/test_pgx_callability.py`; this is the half that only the
real compile path can answer. Three things have to hold and none of them is visible from the model:

* the column reaches parquet as a **nullable boolean**, not a string. The PGx parquets take their
  schema from `_polars_type` over the model's annotations rather than from a hand-kept list, so a
  `bool | None` that landed as `Utf8` would carry `"None"` and `"False"` as two ordinary strings and
  the tri-state would die at the materialization boundary with nothing raising;
* the three states survive `compile → reverse`, because `_scalar_cell` renders `None` as an empty
  cell and `False` as `"false"`, and a writer that collapsed either would round-trip a claim the
  author never made (P7);
* a module that never wrote the column hashes exactly as it did before 0.7 (P3/P8).

The fixture is `reference_examples/cyp2c9_warfarin_grch37`, which is the module the item was found
against and the one that now carries the column on both tables. Every expected value is read off the
authored CSVs at runtime — the point of the test is that the artifact agrees with what was authored,
so a hardcoded census would only assert that two constants match.
"""

import csv
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module

_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "reference_examples" / "cyp2c9_warfarin_grch37"
)
#: (authored CSV, compiled parquet, the columns that identify one row across the round trip).
_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("haplotypes.csv", "haplotypes.parquet", ("haplotype_name", "rsid", "allele")),
    ("pharm_variants.csv", "pharm_variants.parquet", ("rsid", "genotype", "annotation_id")),
)

#: How a CSV cell spells each of the three states. Shared by the reader and the assertions below so a
#: rendering change cannot be absorbed by restating it twice.
_CELL_TO_STATE: dict[str, bool | None] = {"true": True, "false": False, "": None}


def _authored(csv_name: str, key_columns: tuple[str, ...]) -> dict[tuple[str, ...], bool | None]:
    """The authored callability claim per row, keyed by identity, read straight off the CSV."""
    with (_EXAMPLE / csv_name).open(newline="", encoding="utf-8") as f:
        return {
            tuple(row[c] for c in key_columns): _CELL_TO_STATE[row["requires_callable"]]
            for row in csv.DictReader(f)
        }


def test_the_example_states_all_three_callability_states_across_its_two_locus_tables() -> None:
    """The fixture earns its place, or the tests below are asserting over a uniform column.

    A corpus that only ever writes `true` cannot show that `false` survives distinct from blank, and
    the whole item is about that distinction. `haplotypes.csv` records CPIC's own assumption (`false`
    — an uncalled position is read as reference), while `pharm_variants.csv` is keyed on genotype and
    so splits three ways: the reference-homozygote rows require a callability proof, the rows naming
    an alternate allele do not, and the rows whose reference allele this module never resolved say
    nothing at all rather than guessing.
    """
    observed = set()
    for csv_name, _, key_columns in _TABLES:
        observed |= set(_authored(csv_name, key_columns).values())
    assert observed == {True, False, None}


@pytest.mark.parametrize("csv_name,parquet,key_columns", _TABLES, ids=lambda v: str(v))
def test_a_pgx_callability_claim_reaches_parquet_as_a_nullable_boolean(
    csv_name: str, parquet: str, key_columns: tuple[str, ...], tmp_path: Path
) -> None:
    """Typed, not stringified — and carrying the same claim the author wrote, row for row."""
    result = compile_module(_EXAMPLE, tmp_path / "out")
    assert result.success, result.errors

    df = pl.read_parquet(tmp_path / "out" / parquet)
    assert df.schema["requires_callable"] == pl.Boolean

    materialized = {
        tuple(str(row[c]) for c in key_columns): row["requires_callable"]
        for row in df.iter_rows(named=True)
    }
    assert materialized == _authored(csv_name, key_columns)


@pytest.mark.parametrize("csv_name,parquet,key_columns", _TABLES, ids=lambda v: str(v))
def test_a_pgx_callability_claim_survives_reverse_without_collapsing_blank_into_false(
    csv_name: str, parquet: str, key_columns: tuple[str, ...], tmp_path: Path
) -> None:
    """P7 on the column itself, not only on the digest.

    A digest comparison would catch a lost cell, but it would not say *which* of the three states was
    lost, and the failure mode worth naming is the specific one: an unstated row re-emitted as
    `false` reads as the module granting permission to treat a no-call as reference. So the reversed
    cells are compared against the authored ones directly, and the reversed spec is recompiled to a
    fixed point on both identities.
    """
    first = compile_module(_EXAMPLE, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    with (tmp_path / "rev" / csv_name).open(newline="", encoding="utf-8") as f:
        reversed_claims = {
            tuple(row[c] for c in key_columns): _CELL_TO_STATE[row["requires_callable"]]
            for row in csv.DictReader(f)
        }
    assert reversed_claims == _authored(csv_name, key_columns)

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature


def test_a_module_that_never_writes_the_column_keeps_the_signature_it_already_had(
    tmp_path: Path,
) -> None:
    """The additive guarantee, run against the real loader rather than argued from `exclude_none`.

    Two spellings of one module: the pre-0.7 CSVs, which have no `requires_callable` header at all,
    and the same rows with the header present and every cell empty. They must hash identically, which
    is what says the column is optional with respect to every module published before it existed. It
    fails the moment the field is given a `False` default, or the moment an empty cell stops loading
    as `None`.
    """
    yaml = (
        "schema_version: '1.0'\n"
        "module:\n"
        "  name: callability_optional\n"
        "  title: Callability optional\n"
        "  description: A PGx module authored before the column existed\n"
        "  report_title: Callability optional\n"
    )
    tables = {
        "haplotypes.csv": (
            ("haplotype_name,rsid,allele,gene\n", "*2,rs1799853,T,CYP2C9\n"),
            ("haplotype_name,rsid,allele,gene,requires_callable\n", "*2,rs1799853,T,CYP2C9,\n"),
        ),
        "pharm_variants.csv": (
            ("rsid,gene,drug,conclusion\n", "rs9923231,VKORC1,warfarin,lower dose\n"),
            (
                "rsid,gene,drug,conclusion,requires_callable\n",
                "rs9923231,VKORC1,warfarin,lower dose,\n",
            ),
        ),
    }

    signatures = []
    for index in (0, 1):
        spec = tmp_path / f"spelling{index}"
        spec.mkdir()
        (spec / "module_spec.yaml").write_text(yaml, encoding="utf-8")
        for csv_name, spellings in tables.items():
            header, row = spellings[index]
            (spec / csv_name).write_text(header + row, encoding="utf-8")
        signatures.append(content_signature(spec))

    assert signatures[0] == signatures[1]

"""A parquet's resolution locus carries every `resolution.csv` column, or says why not (RM380).

`reverse_module` rebuilds `resolution.csv` from the loci a parquet carries (`resolution_loci` on every
variant parquet, `proxy_loci` on `studies.parquet`), so a column the locus struct lacks does not come
back. The struct was a hand-kept list beside `ResolutionRow`, and nothing compared the two: each 0.8
column the enricher began to write (`placement_witness`/`placement_verdict`, `left_aligned`,
`source_release`) reached the table and was dropped by the first round trip, and the second lap's
compile then read a table that no longer said what the first one read.

The guard is the registry walk the manifest already has one level up
(`test_reverse_carries_what_compile_carried`): every model field is carried or excluded with a reason,
never both. The behavioural half reads the decision back over every reference example: each reversed
row equals the table's own row on every carried column.
"""

import csv
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.parquets import (
    RESOLUTION_LOCUS_DTYPE,
    RESOLUTION_LOCUS_EXCLUDED,
    RESOLUTION_LOCUS_FIELDS,
)
from just_dna_compiler.compiler.reverse import (
    REVERSED_RESOLUTION_FIELDS,
    STUDIES_CSV_FIELDS,
    VARIANTS_CSV_FIELDS,
)
from just_dna_format.base import authored_field_names
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import StudyRow, VariantRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def test_every_resolution_column_is_carried_or_excluded() -> None:
    model = set(ResolutionRow.model_fields)
    carried = set(RESOLUTION_LOCUS_FIELDS)
    excluded = set(RESOLUTION_LOCUS_EXCLUDED)
    assert model == carried | excluded, (
        f"carried by no locus and excluded by no reason: {sorted(model - carried - excluded)}; "
        f"named but not a ResolutionRow column: {sorted((carried | excluded) - model)}"
    )
    assert not carried & excluded
    assert all(len(reason.split()) >= 5 for reason in RESOLUTION_LOCUS_EXCLUDED.values())


def test_the_struct_is_the_carried_list() -> None:
    assert [field.name for field in RESOLUTION_LOCUS_DTYPE.fields] == list(RESOLUTION_LOCUS_FIELDS)


def test_the_reversed_header_is_the_model_minus_what_reverse_cannot_know() -> None:
    """Reverse writes every carried column plus the ones it stamps itself, in the model's order."""
    written = set(REVERSED_RESOLUTION_FIELDS)
    assert written >= set(RESOLUTION_LOCUS_FIELDS)
    assert list(REVERSED_RESOLUTION_FIELDS) == [
        name for name in ResolutionRow.model_fields if name in written
    ]


def _table(path: Path) -> list[ResolutionRow]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [ResolutionRow(**{k: v or None for k, v in row.items()}) for row in csv.DictReader(handle)]


def _carried(rows: list[ResolutionRow], genome_build: str) -> dict[str, list[tuple]]:
    """Each key's positioned rows on the module's build, as the tuple of carried columns."""
    by_key: dict[str, list[tuple]] = {}
    for row in rows:
        if row.genome_build == genome_build and row.chrom is not None and row.start is not None:
            by_key.setdefault(row.variant_key, []).append(
                tuple(getattr(row, name) for name in RESOLUTION_LOCUS_FIELDS)
            )
    return {key: sorted(loci, key=repr) for key, loci in by_key.items()}


def _examples_with_a_table() -> list[Path]:
    found = sorted(
        d
        for d in _EXAMPLES.iterdir()
        if (d / "module_spec.yaml").is_file() and (d / "resolution.csv").is_file()
    )
    assert found, f"no reference example under {_EXAMPLES} carries a resolution.csv"
    return found


@pytest.mark.parametrize("spec", _examples_with_a_table(), ids=lambda p: p.name)
def test_a_reversed_table_equals_the_original_on_every_carried_column(spec: Path, tmp_path: Path) -> None:
    """Every key the reversed table names comes back with the original's rows, column for column.

    A key the reversed table does not name is a row about nothing the artifact carries (the round-trip
    matrix's `table_says_more`) or one that placed nothing; neither has a parquet row to ride on.
    """
    out, back = tmp_path / "out", tmp_path / "back"
    result = compile_module(spec, out)
    assert result.success, result.errors
    genome_build = result.manifest.genome_build
    reverse_module(out, back)
    original = _carried(_table(spec / "resolution.csv"), genome_build)
    returned = _carried(_table(back / "resolution.csv"), genome_build)
    assert returned, f"{spec.name}: the reversed table names no positioned row"
    assert set(returned) <= set(original), sorted(set(returned) - set(original))
    differing = {key: (original[key], loci) for key, loci in returned.items() if original[key] != loci}
    assert not differing, (
        f"{spec.name}: {len(differing)} key(s) came back changed, e.g. {next(iter(differing.items()))}"
    )


def test_every_carried_column_survives_on_a_stamped_table(tmp_path: Path) -> None:
    """The corpus does not exercise every column (no example records `source_release` or `caid` yet), so
    one example's table is stamped with a value in each carried column it leaves empty, and the round
    trip must give each one back. `left_aligned=false` is the tri-state case: a `False` must not come
    back empty."""
    example = _EXAMPLES / "hfe_hemochromatosis"
    spec = tmp_path / "spec"
    shutil.copytree(example, spec)
    with (spec / "resolution.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    stamps = {
        "caid": "CA123",
        "authority": "clinvar",
        "placement_witness": "clinvar_gkm",
        "placement_verdict": "unplaced",
        "left_aligned": "false",
        "source_release": "clinvar_2026-07-01",
    }
    fieldnames = [*rows[0], *(name for name in stamps if name not in rows[0])]
    with (spec / "resolution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, **stamps})
    lap1 = compile_module(spec, tmp_path / "o1")
    assert lap1.success, lap1.errors
    reverse_module(tmp_path / "o1", tmp_path / "back")
    returned = [r for r in _table(tmp_path / "back" / "resolution.csv") if r.start is not None]
    assert returned
    expected = ResolutionRow(variant_key="x", **stamps)
    for name in stamps:
        assert {getattr(r, name) for r in returned} == {getattr(expected, name)}, name
    lap2 = compile_module(tmp_path / "back", tmp_path / "o2")
    assert lap2.success, lap2.errors
    assert lap2.manifest.artifact.digest == lap1.manifest.artifact.digest
    assert lap2.manifest.content_signature == lap1.manifest.content_signature
    assert lap2.manifest.compilation.resolution_signature == lap1.manifest.compilation.resolution_signature


@pytest.mark.parametrize(
    ("header", "model"),
    [(VARIANTS_CSV_FIELDS, VariantRow), (STUDIES_CSV_FIELDS, StudyRow)],
    ids=["variants.csv", "studies.csv"],
)
def test_a_hand_kept_reverse_header_is_the_models_authored_columns(
    header: tuple[str, ...], model: type
) -> None:
    """The class beyond the locus struct (RM380): reverse's two hand-kept headers, held to their models.

    Kept by hand because the reversed column order is the order a person reads, but a column the model
    has and the header lacks is a column the round trip drops (`@three-touch-points`)."""
    assert len(header) == len(set(header))
    assert set(header) == set(authored_field_names(model))

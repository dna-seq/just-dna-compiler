"""The drug labels' keyed function (0.9, RM431 ask 5, the pm's reading 4): `drug_labels.lookup_genes` over a
snapshot built from `assets/clinpgx_drug_labels_slice/` in-test, read in duckdb, raising as
`load_drug_labels` does where it cannot read.

Expected rows are the snapshot's own, read with polars at run time and filtered by the rule the function
states (a gene is a member of the `;`-joined `genes` cell), never copied off a dump.
"""

import zipfile
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import drug_labels, drug_labels_build
from just_dna_enricher.drug_labels import (
    CELL_SEPARATOR,
    LABELS_PARQUET,
    DrugLabelError,
    DrugLabelUnavailable,
    lookup_genes,
)
from just_dna_format.spelling import gene_key

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinpgx_drug_labels_slice"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("drug-labels")
    archive = tmp / "drugLabels.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(SLICE.iterdir()):
            handle.write(path, path.name)
    return drug_labels_build.build_drug_label_snapshot(
        archive, tmp / "snap", source_url="file://clinpgx_drug_labels_slice"
    ).out_dir


def _rows(snapshot: Path) -> pl.DataFrame:
    return pl.read_parquet(snapshot / "data" / LABELS_PARQUET)


def _members(cell: str | None) -> set[str]:
    return {gene_key(member) for member in (cell or "").split(CELL_SEPARATOR) if member.strip()}


def _naming(frame: pl.DataFrame, gene: str) -> list[dict]:
    """The labels whose `genes` cell names `gene`, in the keyed function's order: every column, nulls last."""
    named = frame.filter(
        pl.col("genes").map_elements(lambda cell: gene_key(gene) in _members(cell), return_dtype=pl.Boolean)
    )
    return named.sort(named.columns, nulls_last=True).to_dicts()


def test_the_columns_a_remote_answer_is_typed_by_are_the_builders_schema() -> None:
    types = {pl.Utf8: "VARCHAR"}
    assert drug_labels._LABEL_COLUMN_TYPES == tuple(
        (name, types[dtype]) for name, dtype in drug_labels_build._schema().items()
    )


def test_a_gene_answers_every_label_naming_it_inside_a_multi_gene_cell_too(snapshot: Path) -> None:
    frame = _rows(snapshot)
    multi = [cell for cell in frame["genes"].drop_nulls() if len(_members(cell)) > 1]
    assert multi, "the slice holds labels naming several genes (`CYP2C9; VKORC1`)"
    inside = max(_members(multi[0]))
    single = min({cell for cell in frame["genes"].drop_nulls() if len(_members(cell)) == 1})
    asked = [inside.upper(), f" {single.lower()} ", "NOT_A_GENE"]
    answer = lookup_genes(snapshot, asked)
    assert answer == {inside.upper(): _naming(frame, inside), f" {single.lower()} ": _naming(frame, single)}
    assert all(answer.values()), "both genes are on labels in the slice, so an empty answer cannot pass"


def test_a_label_naming_two_asked_genes_is_under_both(snapshot: Path) -> None:
    frame = _rows(snapshot)
    cell = next(cell for cell in frame["genes"].drop_nulls() if len(_members(cell)) > 1)
    first, second = sorted(_members(cell))[:2]
    answer = lookup_genes(snapshot, [first, second])
    shared = [row for row in answer[first] if row["genes"] == cell]
    assert shared and shared == [row for row in answer[second] if row["genes"] == cell]


def test_no_key_asks_nothing(snapshot: Path) -> None:
    assert lookup_genes(snapshot, []) == {}
    assert lookup_genes(snapshot, ["  "]) == {}


def test_a_missing_snapshot_is_unavailable_naming_it(tmp_path: Path) -> None:
    with pytest.raises(DrugLabelUnavailable, match="no drug-label snapshot"):
        lookup_genes(tmp_path / "absent", ["CYP2C19"])


def test_an_unreadable_snapshot_is_a_failed_lookup_never_an_empty_one(tmp_path: Path) -> None:
    broken = tmp_path / "labels" / "data"
    broken.mkdir(parents=True)
    (broken / LABELS_PARQUET).write_bytes(b"not a parquet file")
    with pytest.raises(DrugLabelError, match="could not be read"):
        lookup_genes(tmp_path / "labels", ["CYP2C19"])

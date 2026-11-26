"""ClinPGx's keyed functions (0.9, RM431 ask 5, the pm's reading 4): `clinpgx.lookup_rsids` and
`clinpgx.lookup_genes` over a snapshot built from `assets/clinpgx_annotations_slice/` in-test, read in
duckdb, raising as `load_snapshot` does where it cannot read.

Expected rows are the snapshot's own, read with polars at run time and filtered by the rule each
function states, never copied off a dump.
"""

import zipfile
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import clinpgx, clinpgx_build
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, lookup_genes, lookup_rsids
from just_dna_format.spelling import gene_key

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinpgx_annotations_slice"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("clinpgx")
    archive = tmp / "summaryAnnotations.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(SLICE.iterdir()):
            handle.write(path, path.name)
    return clinpgx_build.build_snapshot(
        archive, tmp / "snap", source_url="file://clinpgx_annotations_slice"
    ).out_dir


def _rows(snapshot: Path) -> pl.DataFrame:
    return pl.read_parquet(snapshot / "data" / "annotations.parquet")


def _ordered(frame: pl.DataFrame) -> list[dict]:
    """The snapshot's rows in the keyed functions' order: every column, left to right, nulls last."""
    return frame.sort(frame.columns, nulls_last=True).to_dicts()


def _members(cell: str | None) -> set[str]:
    return {gene_key(member) for member in (cell or "").split(";") if member.strip()}


def test_the_columns_a_remote_answer_is_typed_by_are_the_builders_schema() -> None:
    types = {pl.Utf8: "VARCHAR"}
    assert clinpgx._ANNOTATION_COLUMNS == tuple(
        (name, types[dtype]) for name, dtype in clinpgx_build._schema().items()
    )


def test_an_rsid_answers_its_annotations_with_or_without_its_prefix(snapshot: Path) -> None:
    frame = _rows(snapshot)
    rsid = min(set(frame["rsid"].drop_nulls()))
    bare = rsid.removeprefix("rs")
    answer = lookup_rsids(snapshot, [rsid, bare.upper(), bare, "rs1"])
    expected = _ordered(frame.filter(pl.col("rsid") == rsid))
    assert expected, "the slice holds annotations under its first rsID, so an empty answer cannot pass"
    assert answer == {rsid: expected, bare.upper(): expected, bare: expected}
    assert "rs1" not in answer, "an rsID ClinPGx holds nothing under is not a key"


def test_a_gene_answers_every_annotation_naming_it_compared_as_gene_key_compares(snapshot: Path) -> None:
    frame = _rows(snapshot)
    genes = sorted({member for cell in frame["gene"].drop_nulls() for member in _members(cell)})
    first = genes[0]
    asked = [first.upper(), f" {first} ", "NOT_A_GENE"]
    expected = _ordered(
        frame.filter(pl.col("gene").map_elements(lambda c: first in _members(c), return_dtype=pl.Boolean))
    )
    assert expected
    assert lookup_genes(snapshot, asked) == {first.upper(): expected, f" {first} ": expected}


def test_a_gene_is_a_member_of_a_multi_gene_cell_as_the_drafter_reads_one(
    tmp_path: Path, snapshot: Path
) -> None:
    """ClinPGx writes some annotations' `gene` as `KLC1;XRCC3` (399 of 16,117 rows on the 2026-08 snapshot);
    the slice has none, so one is written here from a real row with a second gene appended."""
    frame = _rows(snapshot)
    row = frame.filter(pl.col("gene").is_not_null()).head(1)
    gene = row["gene"][0]
    joined = row.with_columns(pl.lit(f"{gene}; XRCC3").alias("gene"))
    data = tmp_path / "joined" / "data"
    data.mkdir(parents=True)
    joined.write_parquet(data / "annotations.parquet")
    expected = _ordered(joined)
    assert lookup_genes(tmp_path / "joined", ["xrcc3", gene]) == {"xrcc3": expected, gene: expected}


def test_no_key_asks_nothing(snapshot: Path) -> None:
    assert lookup_rsids(snapshot, []) == {}
    assert lookup_genes(snapshot, ["  "]) == {}


def test_a_missing_snapshot_is_a_failed_lookup_naming_what_could_not_be_read(tmp_path: Path) -> None:
    with pytest.raises(ClinPgxEnrichmentError, match="no ClinPGx snapshot"):
        lookup_rsids(tmp_path / "absent", ["rs4149056"])


def test_an_unreadable_snapshot_is_a_failed_lookup_never_an_empty_one(tmp_path: Path) -> None:
    broken = tmp_path / "clinpgx" / "data"
    broken.mkdir(parents=True)
    (broken / "annotations.parquet").write_bytes(b"not a parquet file")
    with pytest.raises(ClinPgxEnrichmentError, match="could not be read"):
        lookup_genes(tmp_path / "clinpgx", ["SLCO1B1"])

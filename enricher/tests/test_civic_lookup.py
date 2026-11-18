"""CIViC's keyed functions (0.9, RM431 ask 5): `lookup_genes` and `lookup_rsids` over a snapshot built from
`assets/civic_slice/` in-test, read in duckdb, with the raising reader's semantics (`_snapshot_rows`).

Expected rows are the snapshot's own, read with polars at run time and filtered by the same rule.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import civic_build, civic_draft
from just_dna_enricher.civic_build import build_snapshot
from just_dna_enricher.civic_draft import CivicDraftError, lookup_genes, lookup_rsids
from just_dna_format.spelling import gene_key

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_snapshot(
        SLICE / "ClinicalEvidenceSummaries.tsv",
        SLICE / "VariantSummaries.tsv",
        SLICE / "MolecularProfileSummaries.tsv",
        tmp_path_factory.mktemp("civic") / "snap",
        release="01-Aug-2026",
    ).out_dir


def _rows(snapshot: Path) -> pl.DataFrame:
    return pl.read_parquet(snapshot / "data" / civic_build.CIVIC_PARQUET)


def _ordered(frame: pl.DataFrame) -> list[dict]:
    """The snapshot's rows in the keyed functions' order: every column, left to right, nulls last."""
    return frame.sort(frame.columns, nulls_last=True).to_dicts()


def test_the_columns_a_remote_answer_is_typed_by_are_the_builders_schema() -> None:
    types = {pl.Utf8: "VARCHAR", pl.Int64: "BIGINT"}
    assert civic_draft._CIVIC_COLUMNS == tuple(
        (name, types[dtype]) for name, dtype in civic_build._polars_schema().items()
    )


def test_a_gene_answers_its_rows_compared_as_gene_key_compares_and_keyed_as_asked(snapshot: Path) -> None:
    frame = _rows(snapshot)
    genes = sorted(set(frame["gene"].drop_nulls()))
    first = genes[0]
    asked = [first, f"  {first.lower()} ", "NOT_A_GENE"]
    answer = lookup_genes(snapshot, asked)
    expected = _ordered(
        frame.filter(pl.col("gene").map_elements(gene_key, return_dtype=pl.Utf8) == gene_key(first))
    )
    assert expected, "the slice holds rows for its first gene, so an empty answer cannot pass"
    assert answer == {first: expected, f"  {first.lower()} ": expected}
    assert "NOT_A_GENE" not in answer, "a gene CIViC holds nothing for is not a key"


def test_an_rsid_answers_its_rows_with_or_without_its_prefix(snapshot: Path) -> None:
    frame = _rows(snapshot)
    rsid = min(set(frame["rsid"].drop_nulls()))
    bare = rsid.removeprefix("rs")
    answer = lookup_rsids(snapshot, [rsid, bare, "rs1"])
    expected = _ordered(frame.filter(pl.col("rsid") == rsid))
    assert expected
    assert answer == {rsid: expected, bare: expected}


def test_no_key_asks_nothing(snapshot: Path) -> None:
    assert lookup_genes(snapshot, []) == {}
    assert lookup_rsids(snapshot, ["  "]) == {}


def test_a_missing_snapshot_is_a_failed_lookup_naming_what_could_not_be_read(tmp_path: Path) -> None:
    with pytest.raises(CivicDraftError, match="no CIViC snapshot"):
        lookup_genes(tmp_path / "absent", ["VHL"])


def test_an_unreadable_snapshot_is_a_failed_lookup_never_an_empty_one(tmp_path: Path) -> None:
    broken = tmp_path / "civic" / "data"
    broken.mkdir(parents=True)
    (broken / civic_build.CIVIC_PARQUET).write_bytes(b"not a parquet file")
    with pytest.raises(CivicDraftError, match="could not be read"):
        lookup_rsids(tmp_path / "civic", ["rs1"])

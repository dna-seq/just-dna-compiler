"""RM452: a NULL `start` is no place, at both of the scan's reads, rather than a `TypeError`.

Found by the RM431 builder with a synthetic split-core row (`start` NULL, UINTEGER); no published Ensembl release
on this machine carries one (0 rows, 2026-11-18), so both reads are guarded against a defect in the data, never a
case any module has met. The rsID-to-position scan left such a row out and asked the next link; the
position-to-rsID back-fill gave a probe with a chrom and no start no candidates, as one with no chrom already had.
"""

import logging
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher.resolver import _lookup_rsid_candidates, lookup_loci


def _core(root: Path, rows: str) -> Path:
    (root / "data").mkdir(parents=True)
    duckdb.sql(
        f"COPY (SELECT * FROM (VALUES {rows}) AS t(chrom, start, ref, alt, id, row_idx)) "
        f"TO '{root}/data/homo_sapiens-chr1.parquet' (FORMAT parquet)"
    )
    return root


def test_a_row_with_no_start_places_nothing_and_says_so(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The builder's repro, as it ran: one row naming the rsID, `start` NULL."""
    root = _core(
        tmp_path / "ensembl", "('1', CAST(NULL AS UINTEGER), 'A', 'G', 'rs2100212723', CAST(0 AS UINTEGER))"
    )
    with caplog.at_level(logging.WARNING):
        found, _, _ = lookup_loci(root, ["rs2100212723"], [])
    assert found == {}
    assert "only on rows with no chrom or start" in caplog.text and "rs2100212723" in caplog.text


def test_a_placed_row_beside_an_unplaced_one_still_answers(tmp_path: Path) -> None:
    root = _core(
        tmp_path / "ensembl",
        "('1', CAST(NULL AS UINTEGER), 'A', 'G', 'rs1', CAST(0 AS UINTEGER)), "
        "('1', CAST(100 AS UINTEGER), 'A', 'G', 'rs1', CAST(1 AS UINTEGER))",
    )
    found, _, _ = lookup_loci(root, ["rs1"], [])
    assert [(lo["chrom"], lo["start"], lo["ref"], lo["alts"]) for lo in found["rs1"]] == [
        ("1", 100, "A", "G")
    ]


def test_a_probe_with_a_chrom_and_no_start_gets_no_candidates() -> None:
    """The back-fill's own `int(start)`, reached when another probe in the same call is whole."""
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT '1' AS chrom, 100 AS start, 'A' AS ref, 'G' AS alt, 'rs1' AS id")
    found = _lookup_rsid_candidates(con, "t", "id", [("1", 100, "A", "G"), ("1", None, "A", None)])
    assert found == {("1", 100, "A", "G"): ["rs1"], ("1", None, "A", None): []}

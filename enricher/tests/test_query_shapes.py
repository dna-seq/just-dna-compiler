"""The batch readers must hash their probes, not OR-chain them (S3).

The failure this pins is invisible at unit scale and catastrophic at panel scale, which is exactly
the shape that regresses silently: DuckDB cannot fold a disjunction of equality *conjunctions* into a
hash probe, so `WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` is evaluated against every row
of the reference and the cost grows with `alleles × rows`. On the real 4.4M-record snapshot that was
88 s for 5,000 alleles against 0.21 s joined, and a 297-gene panel simply never finished.

Every timing assertion here is **relative** — the OR-chain shape is measured in the same test, on the
same machine, against the same data — so a slow or loaded runner moves both numbers together. The
structural assertion (the plan contains a hash join) carries the invariant on its own and does not
depend on the clock at all.
"""

import time
from pathlib import Path

import duckdb
import polars as pl
import pytest
from just_dna_enricher import clinvar
from just_dna_enricher.resolver import _lookup_rsid_candidates, probe_table

#: Big enough that an OR-chain is unmistakably slower (measured ~30x), small enough to build in a
#: test: at this size the chained shape takes seconds and the joined one hundredths.
_ROWS = 200_000
_PROBES = 2_000


def _snapshot(tmp_path: Path, n_rows: int = _ROWS) -> Path:
    """A synthetic ClinVar snapshot of `n_rows` distinct alleles spread over 22 contigs."""
    root = tmp_path / "cv"
    data = root / "data"
    data.mkdir(parents=True)
    i = pl.int_range(0, n_rows, eager=True)
    pl.DataFrame(
        {
            "chrom": (1 + i % 22).cast(pl.Utf8),
            "start": (i * 7) % 250_000_000,
            "ref": pl.Series(["A"] * n_rows),
            "alt": pl.Series(["G"] * n_rows),
            "rsid": ("rs" + i.cast(pl.Utf8)),
            "clin_sig": pl.Series(["pathogenic"] * n_rows),
            "clin_sig_raw": pl.Series(["Pathogenic"] * n_rows),
            "review_status": pl.Series(["criteria provided, single submitter"] * n_rows),
            "review_stars": pl.Series([1] * n_rows),
            "condition": pl.Series(["a condition"] * n_rows),
            "variation_id": i.cast(pl.Utf8),
            "gene": ("GENE" + (i % 500).cast(pl.Utf8)),
        }
    ).write_parquet(data / "chr.parquet")
    return root


def _probe_alleles(reference: Path, n: int = _PROBES) -> list[tuple[str, int, str, str]]:
    """`n` alleles taken from the snapshot itself, deterministically spread across every contig."""
    con = clinvar._connect(reference)
    try:
        rows = con.execute(
            f"SELECT chrom, start, ref, alt FROM clinvar ORDER BY variation_id::BIGINT % {n}, "
            f"variation_id::BIGINT LIMIT {n}"
        ).fetchall()
    finally:
        con.close()
    return [(str(c), int(s), str(r), str(a)) for c, s, r, a in rows]


def _or_chained_clin_sig(reference: Path, alleles: list[tuple[str, int, str, str]]) -> list[tuple]:
    """The shape this module exists to keep out: one equality conjunction per allele, OR'd."""
    con = clinvar._connect(reference)
    try:
        conds = " OR ".join("(chrom = ? AND start = ? AND ref = ? AND alt = ?)" for _ in alleles)
        params = [value for row in alleles for value in row]
        return con.execute(
            f"""
            SELECT chrom, start, ref, alt, clin_sig, clin_sig_raw, review_status, review_stars,
                   condition, variation_id
            FROM clinvar WHERE {conds}
            ORDER BY chrom, start, ref, alt, review_stars DESC, variation_id
            """,
            params,
        ).fetchall()
    finally:
        con.close()


def test_lookup_clin_sig_is_a_hash_join_not_an_or_chain(tmp_path: Path) -> None:
    """The plan itself, so the invariant does not rest on a stopwatch."""
    reference = _snapshot(tmp_path, n_rows=1_000)
    con = clinvar._connect(reference)
    try:
        probe_table(
            con,
            "_wanted_alleles",
            [("chrom", "VARCHAR"), ("start", "BIGINT"), ("ref", "VARCHAR"), ("alt", "VARCHAR")],
            [("1", 7, "A", "G")],
        )
        plan = con.execute(
            "EXPLAIN SELECT c.variation_id FROM clinvar c JOIN _wanted_alleles w "
            "ON c.chrom = w.chrom AND c.start = w.start AND c.ref = w.ref AND c.alt = w.alt"
        ).fetchall()[0][1]
    finally:
        con.close()
    assert "HASH_JOIN" in plan


def test_clin_sig_lookup_returns_exactly_what_the_or_chain_did(tmp_path: Path) -> None:
    """Same rows, same grouping — the join is a performance change and nothing else."""
    reference = _snapshot(tmp_path, n_rows=20_000)
    alleles = _probe_alleles(reference, n=500)
    expected: dict[tuple[str, int, str, str], list[dict]] = {}
    for chrom, start, ref, alt, cs, raw, status, stars, condition, vid in _or_chained_clin_sig(
        reference, alleles
    ):
        expected.setdefault((str(chrom), int(start), str(ref), str(alt)), []).append(
            {
                "clin_sig": cs,
                "clin_sig_raw": raw,
                "review_status": status,
                "review_stars": int(stars) if stars is not None else None,
                "condition": condition,
                "variation_id": vid,
            }
        )
    assert clinvar.lookup_clin_sig(reference, alleles) == expected


def test_clin_sig_lookup_beats_the_or_chain_by_an_order_of_magnitude(tmp_path: Path) -> None:
    """Both shapes, same data, same process — a relative bound, so a slow runner moves both."""
    reference = _snapshot(tmp_path)
    alleles = _probe_alleles(reference)

    start = time.perf_counter()
    chained = _or_chained_clin_sig(reference, alleles)
    chained_seconds = time.perf_counter() - start

    start = time.perf_counter()
    joined = clinvar.lookup_clin_sig(reference, alleles)
    joined_seconds = time.perf_counter() - start

    assert len(joined) == len(alleles) == len(chained)
    assert joined_seconds * 5 < chained_seconds, (
        f"the joined lookup took {joined_seconds:.3f}s against the OR-chain's {chained_seconds:.3f}s "
        f"— the quadratic shape is back"
    )


def test_rsid_candidate_lookup_matches_the_or_chained_answer(tmp_path: Path) -> None:
    """The reverse map is shared with the Ensembl link, so its answer must not move either."""
    reference = _snapshot(tmp_path, n_rows=20_000)
    alleles = _probe_alleles(reference, n=300)
    positions = [(chrom, start, ref, alt) for chrom, start, ref, alt in alleles]
    con = clinvar._connect(reference)
    try:
        candidates = _lookup_rsid_candidates(con, "clinvar", "rsid", positions)
        conds = " OR ".join("(chrom = ? AND start = ?)" for _ in positions)
        params = [value for chrom, start, _, _ in positions for value in (chrom, start)]
        chained = con.execute(
            f"SELECT DISTINCT chrom, start, rsid FROM clinvar WHERE ({conds}) AND rsid LIKE 'rs%' "
            f"ORDER BY chrom, start, rsid",
            params,
        ).fetchall()
    finally:
        con.close()
    assert {(c, s): r for c, s, r in chained} == {
        (chrom, start): rsids[0]
        for (chrom, start, _, _), rsids in candidates.items()
        if rsids
    }


def test_select_by_gene_uses_in_and_keeps_its_row_order(tmp_path: Path) -> None:
    """`gene IN (…)` is pushed into the parquet reader; `gene = ? OR …` is not. Same rows, same order."""
    reference = _snapshot(tmp_path, n_rows=20_000)
    genes = [f"GENE{n}" for n in range(200)]
    con = clinvar._connect(reference)
    try:
        conds = " OR ".join("gene = ?" for _ in genes)
        cursor = con.execute(
            f"""
            SELECT chrom, start, ref, alt, rsid, gene, clin_sig, review_status, review_stars,
                   condition, variation_id
            FROM clinvar WHERE ({conds})
            ORDER BY gene, chrom, start, ref, alt, review_stars DESC, variation_id
            """,
            list(genes),
        )
        columns = [d[0] for d in cursor.description]
        chained = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()
    assert clinvar.select_by_gene(reference, genes) == chained
    assert chained  # the fixture really does carry these genes


@pytest.mark.parametrize("hostile", ["O'Brien", "a'b''c", "'; DROP TABLE clinvar; --"])
def test_probe_table_escapes_quotes_rather_than_binding(hostile: str) -> None:
    """The rows are rendered as literals for speed, so the escaping is load-bearing."""
    con = duckdb.connect(":memory:")
    try:
        probe_table(con, "_probe", [("value", "VARCHAR"), ("n", "BIGINT")], [(hostile, 7)])
        assert con.execute("SELECT value, n FROM _probe").fetchall() == [(hostile, 7)]
    finally:
        con.close()


def test_probe_table_keeps_a_null_apart_from_an_empty_string() -> None:
    """`None` is not `''` — the house algebra applies to a probe table like everywhere else."""
    con = duckdb.connect(":memory:")
    try:
        probe_table(con, "_probe", [("value", "VARCHAR")], [(None,), ("",)])
        assert con.execute("SELECT value FROM _probe ORDER BY value NULLS LAST").fetchall() == [
            ("",),
            (None,),
        ]
    finally:
        con.close()

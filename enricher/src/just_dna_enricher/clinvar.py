"""ClinVar resolver link — the *core* half of the ClinVar reference (no polars, `duckdb` only).

`lookup_loci` mirrors `resolver.lookup_loci` exactly (same signature, same determinism discipline) so
`enrich()` treats the ClinVar cache and the Ensembl cache identically — a `rsid → [loci]` /
`pos → rsid` batch lookup over an injected parquet directory. It reads only `chrom/start/ref/alt`;
the snapshot's annotation columns (`clin_sig`, `gene`, `condition`, ...) are ignored here — that is
annotation, not a resolution fact (orthogonal axes, Principle 5). Inject-only: the caller provisions
the reference (`download.ensure_clinvar_snapshot` or a local cache); this never fetches.

The snapshot ships as parquet only (built by `clinvar_build`, `[dev]`); there is no prebuilt
``.duckdb`` for ClinVar, so this connects a `read_parquet` view directly.
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import duckdb

from just_dna_enricher.resolver import _lookup_rsid_candidates

logger = logging.getLogger(__name__)


class ClinVarReferenceError(FileNotFoundError):
    """Raised when a provided ClinVar reference has no usable parquet files."""


def _connect(reference: Path) -> duckdb.DuckDBPyConnection:
    """Open an in-memory connection exposing a `clinvar` view over the reference's parquet files."""
    reference = Path(reference)
    parquet_glob: Optional[Path] = None
    if (reference / "data").is_dir() and any((reference / "data").glob("*.parquet")):
        parquet_glob = reference / "data"
    elif reference.is_dir() and any(reference.glob("*.parquet")):
        parquet_glob = reference
    if parquet_glob is None:
        raise ClinVarReferenceError(f"no usable ClinVar parquet files at {reference}")
    # DuckDB can't bind a parameter inside CREATE VIEW ... read_parquet(). The pattern is a local
    # path from our own cache resolution, not user input; single-quote-escape it defensively.
    pattern = f"{parquet_glob}/*.parquet".replace("'", "''")
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW clinvar AS SELECT * FROM read_parquet('{pattern}')")
    return con


def lookup_loci(
    reference: Path,
    rsids: list[str],
    positions: list[tuple[Optional[str], Optional[int], Optional[str], Optional[str]]],
) -> tuple[dict[str, list[dict]], dict[tuple, list[str]], list[str]]:
    """`(rsid -> [loci], (chrom,start,ref,alt) -> [candidate rsids], warnings)` over ClinVar.

    Signature-identical to `resolver.lookup_loci`, so the enrich chain calls either link with the same
    code. The reverse map reuses `resolver._lookup_rsid_candidates` (allele-aware, all candidates) over
    the `clinvar` view's `rsid` column — one implementation, no drift. Inject-only; never fetches.
    """
    warnings: list[str] = []
    con = _connect(reference)
    try:
        rsid_to_loci = (
            _lookup_positions_by_rsid(con, sorted(set(rsids)), warnings) if rsids else {}
        )
        pos_candidates = (
            _lookup_rsid_candidates(con, "clinvar", "rsid", positions) if positions else {}
        )
    finally:
        con.close()
    return rsid_to_loci, pos_candidates, warnings


def _lookup_positions_by_rsid(
    con: duckdb.DuckDBPyConnection, rsids: list[str], warnings: list[str]
) -> dict[str, list[dict]]:
    """Batch lookup: rsid -> [{chrom, start, ref, alts}, ...] (all loci, deterministically ordered).

    Mirrors `resolver._lookup_positions_by_rsid`: every locus is returned so a one-to-many rsid
    expands to one row per locus, and `string_agg(DISTINCT alt, ',' ORDER BY alt)` + an explicit
    `ORDER BY rsid, chrom, start, ref` keep both the alt list and the emitted order stable (P7)."""
    if not rsids:
        return {}
    placeholders = ", ".join("?" for _ in rsids)
    rows = con.execute(
        f"""
        SELECT rsid, chrom, start, ref, string_agg(DISTINCT alt, ',' ORDER BY alt) AS alts
        FROM clinvar
        WHERE rsid IN ({placeholders})
        GROUP BY rsid, chrom, start, ref
        ORDER BY rsid, chrom, start, ref
        """,
        rsids,
    ).fetchall()
    result: dict[str, list[dict]] = defaultdict(list)
    for rsid, chrom, start, ref, alts in rows:
        result[rsid].append(
            {"chrom": str(chrom), "start": int(start), "ref": str(ref), "alts": str(alts)}
        )
    for rsid in rsids:
        if rsid not in result:
            warnings.append(f"{rsid}: not found in ClinVar, position remains unset")
    return dict(result)

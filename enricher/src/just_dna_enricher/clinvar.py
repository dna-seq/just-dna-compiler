"""ClinVar resolver link — the *core* half of the ClinVar reference (no polars, `duckdb` only).

`lookup_loci` mirrors `resolver.lookup_loci` exactly (same signature, same determinism discipline) so
`enrich()` treats the ClinVar cache and the Ensembl cache identically — a `rsid → [loci]` /
`pos → rsid` batch lookup over an injected parquet directory. **The resolver link** reads only
`chrom/start/ref/alt`; the snapshot's annotation columns (`clin_sig`, `gene`, `condition`, ...) stay
out of `resolution.csv`, because they are annotation rather than resolution facts (orthogonal axes,
Principle 5). Inject-only: the caller provisions the reference (`download.ensure_clinvar_snapshot` or
a local cache); this never fetches.

`lookup_clin_sig` is the second, separate reader over the same view: it serves the clinical
cross-check in `clinical.py`, which compares a module's authored `clin_sig` against ClinVar's. Keeping
it here (data access) and the comparison there (judgement) is the same split `sequences.py` draws
between reading bases and deciding what a disagreement means.

The snapshot ships as parquet only (built by `clinvar_build`, `[dev]`); there is no prebuilt
``.duckdb`` for ClinVar, so this connects a `read_parquet` view directly.
"""

import logging
from collections import defaultdict
from pathlib import Path

import duckdb

from just_dna_enricher.locations import CITATIONS_DIRNAME
from just_dna_enricher.resolver import _lookup_rsid_candidates, probe_table

logger = logging.getLogger(__name__)


class ClinVarReferenceError(FileNotFoundError):
    """Raised when a provided ClinVar reference has no usable parquet files."""


def _connect(reference: Path) -> duckdb.DuckDBPyConnection:
    """Open an in-memory connection exposing a `clinvar` view over the reference's parquet files."""
    reference = Path(reference)
    parquet_glob: Path | None = None
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
    positions: list[tuple[str | None, int | None, str | None, str | None]],
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


def lookup_clin_sig(
    reference: Path,
    alleles: list[tuple[str, int, str, str]],
) -> dict[tuple[str, int, str, str], list[dict]]:
    """`(chrom, start, ref, alt) -> [{clin_sig, clin_sig_raw, review_status, review_stars, ...}]`.

    Allele-exact by construction, and that is the whole point: an rsID is a *position/multi-allelic*
    tag, so one rsID at one locus can carry a pathogenic, a benign and an uncertain allele
    (`rs33922842` in HBB does exactly that). Looking up clinical significance by rsID would therefore
    manufacture disagreements out of ClinVar agreeing with itself.

    A list rather than a single record because ClinVar genuinely holds several submissions for one
    allele — different conditions, different review levels. Ordered by descending `review_stars` then
    `variation_id` so the best-reviewed record leads and the order is stable (Principle 7).
    """
    if not alleles:
        return {}
    con = _connect(reference)
    try:
        wanted = list(dict.fromkeys(alleles))
        probe_table(
            con,
            "_wanted_alleles",
            [("chrom", "VARCHAR"), ("start", "BIGINT"), ("ref", "VARCHAR"), ("alt", "VARCHAR")],
            wanted,
        )
        rows = con.execute(
            """
            SELECT c.chrom, c.start, c.ref, c.alt, c.clin_sig, c.clin_sig_raw, c.review_status,
                   c.review_stars, c.condition, c.variation_id
            FROM clinvar c
            JOIN _wanted_alleles w
              ON c.chrom = w.chrom AND c.start = w.start AND c.ref = w.ref AND c.alt = w.alt
            ORDER BY c.chrom, c.start, c.ref, c.alt, c.review_stars DESC, c.variation_id
            """
        ).fetchall()
    finally:
        con.close()
    result: dict[tuple[str, int, str, str], list[dict]] = defaultdict(list)
    for chrom, start, ref, alt, clin_sig, raw, status, stars, condition, variation_id in rows:
        result[(str(chrom), int(start), str(ref), str(alt))].append(
            {
                "clin_sig": clin_sig,
                "clin_sig_raw": raw,
                "review_status": status,
                "review_stars": int(stars) if stars is not None else None,
                "condition": condition,
                "variation_id": variation_id,
            }
        )
    return dict(result)


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


def select_by_gene(
    reference: Path,
    genes: list[str],
    *,
    clin_sig: frozenset[str] | None = None,
    min_review_stars: int = 0,
) -> list[dict]:
    """Rows for a gene panel: the third reader over the same view, serving the drafting provider.

    Kept here with the other two because this module owns the snapshot's schema; deciding what a row
    *means* for a module stays in `clinvar_draft`, the same data-access/judgement split `lookup_loci`
    and `clinical.py` already draw.

    `min_review_stars` is the honest quality dial for a panel — a 0-star "no assertion criteria"
    submission and a 3-star expert-panel review are not the same evidence, and a panel that mixes them
    silently is worse than one that says which floor it drew. Ordered deterministically so a re-draft
    appends nothing new (Principle 7): the emitted row order is authored order, and authored order is
    digest-visible.
    """
    wanted = [g.strip() for g in genes if g.strip()]
    if not wanted:
        return []
    con = _connect(reference)
    try:
        # `gene IN (…)` rather than `gene = ? OR …`: DuckDB hashes the first and evaluates the second
        # against every row (4,793 genes: 1.02 s against 15.22 s). Same rows, same order.
        params: list[object] = list(wanted)
        clause = f"gene IN ({', '.join('?' for _ in wanted)})"
        if clin_sig:
            clause += f" AND clin_sig IN ({', '.join('?' for _ in clin_sig)})"
            params.extend(sorted(clin_sig))
        if min_review_stars:
            clause += " AND review_stars >= ?"
            params.append(min_review_stars)
        cursor = con.execute(
            f"""
            SELECT chrom, start, ref, alt, rsid, gene, clin_sig, review_status, review_stars,
                   condition, variation_id
            FROM clinvar
            WHERE {clause}
            ORDER BY gene, chrom, start, ref, alt, review_stars DESC, variation_id
            """,
            params,
        )
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


# `CITATIONS_DIRNAME` comes from `locations`, where the snapshot layout lives so the builder, publisher,
# provisioner and reader cannot disagree about it. It is a sibling of `data/`, never inside it — `_connect`
# globs `data/*.parquet`, so a two-column citations file dropped in there unions with the variant parquet
# and breaks every query. Re-exported here because callers of this reader import it from here.


def citations_for(reference: Path, variation_ids: list[str]) -> dict[str, list[str]]:
    """`variation_id -> [pmid, ...]` from the optional citations table, or `{}` when absent.

    Optional on purpose: a snapshot built before `clinvar citations` existed is still a perfectly good
    resolver and cross-check reference, and refusing to read it would strand every existing cache. An
    absent table means "no citations available", which the caller reports — never "this variant has no
    literature", which would be a claim about ClinVar rather than about the file on disk.

    Ordered by pmid so a re-draft emits the same rows in the same order (Principle 7).
    """
    parquet = Path(reference) / CITATIONS_DIRNAME / "citations.parquet"
    if not parquet.is_file() or not variation_ids:
        return {}
    wanted = list(dict.fromkeys(v for v in variation_ids if v))
    if not wanted:
        return {}
    pattern = str(parquet).replace("'", "''")
    con = duckdb.connect(":memory:")
    try:
        placeholders = ", ".join("?" for _ in wanted)
        rows = con.execute(
            f"""
            SELECT variation_id, pmid FROM read_parquet('{pattern}')
            WHERE variation_id IN ({placeholders})
            ORDER BY variation_id, pmid
            """,
            wanted,
        ).fetchall()
    finally:
        con.close()
    found: dict[str, list[str]] = defaultdict(list)
    for variation_id, pmid in rows:
        found[str(variation_id)].append(str(pmid))
    return dict(found)

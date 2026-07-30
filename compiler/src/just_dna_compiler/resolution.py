"""Pure, source-independent variant resolution from an injected `resolution.csv` (0.5).

The compiler's preferred resolution path. It consumes a table of already-resolved facts
(`just_dna_format.resolution.ResolutionRow`) keyed by the frozen `variant_key`, and reproduces the
DuckDB resolver's fill / expand / verify semantics **without any `duckdb` import, SQL, or Ensembl
convention**. All source knowledge (where facts come from) lives in the separate `just-dna-enricher`
tier; this module knows only "read the facts I was handed" — the strict inject-only end state
(CONSTITUTION Principle 2).

Digest parity with the DuckDB path is deliberate and load-bearing: given the same facts, this
produces byte-identical `weights.parquet` (hence `artifact.digest`) as `resolver.resolve_variants`.
The one place row order could drift — a one-to-many expansion — is pinned by sorting the expanded
rows on `(locus_index, chrom, start, ref)`, matching the resolver's `ORDER BY id, chrom, start, ref`.
"""

import logging
from typing import Optional

from just_dna_format.base import derive_variant_key
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

logger = logging.getLogger(__name__)


def resolve_from_table(
    variants: list[VariantRow],
    resolution: dict[str, list[ResolutionRow]],
    genome_build: str = "GRCh38",
) -> tuple[list[VariantRow], list[str]]:
    """Fill/expand missing rsid or position from an injected resolution table (no network, no DuckDB).

    Mirrors `resolver.resolve_variants`:
      - **fill (1:1):** a `variant_key` with exactly one usable row fills the missing coord or rsid,
        keeping the frozen key.
      - **expand (1:N):** a `variant_key` (an rsid) with N usable rows expands to N coord-keyed rows,
        ordered by `(locus_index, chrom, start, ref)` so the parquet byte order matches the DuckDB
        path (digest parity).
      - **verify:** a row carrying both an rsid and a coordinate is checked against the table; a
        disagreement is a warning, never fatal.

    GRCh38-bound, like the DuckDB resolver (RM15): a non-GRCh38 module is skipped with a warning, and a
    resolution row whose `genome_build` differs from the module's is ignored.
    """
    if genome_build != "GRCh38":
        msg = (
            f"Resolution-table fill skipped: compiler is GRCh38-bound, module genome_build is "
            f"{genome_build!r} — positions are not re-resolved cross-build (RM15)."
        )
        logger.warning(msg)
        return variants, [msg]

    warnings: list[str] = []
    patched: list[VariantRow] = []
    for v in variants:
        rows = resolution.get(v.variant_key or "")
        loci = _usable_loci(rows, genome_build)

        if v.rsid is not None and v.chrom is None:
            # need position: fill from the table, or expand a one-to-many rsid
            if not loci:
                warnings.append(
                    f"{v.rsid}: not found in resolution table, position remains unset"
                )
                patched.append(v)
            elif len(loci) == 1:
                patched.append(v.model_copy(update=_coord_update(loci[0])))
            else:
                warnings.append(
                    f"{v.rsid} maps to {len(loci)} loci in the resolution table; expanded to "
                    f"{len(loci)} rows (one per locus, each keyed by its coordinate — a consumer "
                    f"can count them)."
                )
                for locus in _sorted_loci(loci):
                    update = _coord_update(locus)
                    update["variant_key"] = derive_variant_key(
                        None, locus.chrom, locus.start, locus.ref, locus.alts
                    )
                    patched.append(v.model_copy(update=update))

        elif v.rsid is None and v.chrom is not None:
            # need rsid: fill from the single usable row (keeps the frozen coord key)
            rsid = next((lo.rsid for lo in loci if lo.rsid is not None), None)
            if rsid is not None:
                patched.append(v.model_copy(update={"rsid": rsid}))
            else:
                warnings.append(
                    f"Position {v.variant_key}: no rsid found in resolution table"
                )
                patched.append(v)

        else:
            # both authored (verify) or nothing to do
            if v.rsid is not None and v.chrom is not None and loci:
                _verify(v, loci, warnings)
            patched.append(v)

    return patched, warnings


def _usable_loci(
    rows: Optional[list[ResolutionRow]], genome_build: str
) -> list[ResolutionRow]:
    """Rows that are for this build and record an actual locus (not a `not_found` sentinel)."""
    if not rows:
        return []
    return [
        r
        for r in rows
        if r.genome_build == genome_build and r.status != "not_found" and r.chrom is not None
    ]


def _coord_update(row: ResolutionRow) -> dict[str, object]:
    """The coordinate fields a fill copies onto a VariantRow (matches the DuckDB path's locus dict)."""
    return {"chrom": row.chrom, "start": row.start, "ref": row.ref, "alts": row.alts}


def _sorted_loci(loci: list[ResolutionRow]) -> list[ResolutionRow]:
    """Deterministic expansion order, matching the resolver's `ORDER BY id, chrom, start, ref`."""
    return sorted(
        loci, key=lambda r: (r.locus_index, r.chrom or "", r.start or 0, r.ref or "")
    )


def _verify(v: VariantRow, loci: list[ResolutionRow], warnings: list[str]) -> None:
    """Warn (never fail) when an authored rsid↔coordinate pair disagrees with the table."""
    coordkey = derive_variant_key(None, v.chrom, v.start, v.ref)
    keys = {
        derive_variant_key(None, lo.chrom, lo.start, lo.ref) for lo in loci
    }
    if keys and coordkey not in keys:
        warnings.append(
            f"{v.rsid} authored at {coordkey}, but the resolution table maps it to "
            f"{sorted(keys)} (reference disagreement)."
        )

"""The enricher's minted VRS ids, carried onto the variant parquets (RM270).

An indel's `variant_key` and its coordinate are its source's spelling, and a caller may spell the same
event another legal way, so an exact `(chrom, pos, ref, alt)` join misses it. The VRS allele id is over
the fully justified allele, so it does not depend on the spelling: it is the key a consumer who can mint
VRS from its own VCF joins on. The enricher mints it into `resolution.csv`, which has no parquet by
design, so until RM270 it reached no artifact (`@dont-discard-computed`) and a round trip dropped it.

**Copied, never minted here.** The compiler has no reference sequence (P2), so it cannot justify an
indel; and minting a substitution here would put ids in the artifact that `reverse` then writes into a
`resolution.csv` that never had them, so the second lap's manifest would count more identified alleles
than the first. Every id on a parquet is one a `resolution.csv` row recorded.

**By allele, never by position in a cell** (`@vrsid-per-alt`). A row's id list follows that row's own
`alts`, member for member, with a hole where no `resolution.csv` row names the allele. The lookup is
keyed on the spelling `(chrom, start, ref, alt)` on the module's build, not on `variant_key`: an id is a
function of the allele, so any row recording that spelling records the same id, and a coordinate-keyed
row and an expansion member find theirs the same way. Two rows recording one spelling with two different
ids withhold it, since one of them is wrong and nothing here says which. `vrs_spec` (RM304) is stated
for a row only when every id it carries was stated under the same version.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import polars as pl
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import join_vrs_ids, split_vrs_ids, vrs_spec_release

#: One allele, as `resolution.csv` spells it: `(chrom, start, REF, ALT)`, bases uppercased.
AlleleKey = tuple[str, int, str, str]

#: A withheld allele: two rows recorded it with two different ids.
_CONTESTED = object()


@dataclass
class VrsIds:
    """`allele -> (vrs_id, vrs_spec)` over a `resolution.csv`, on one build. Empty answers nothing."""

    _ids: dict[AlleleKey, object] = field(default_factory=dict)

    @classmethod
    def of(cls, rows: Sequence[ResolutionRow], genome_build: str) -> "VrsIds":
        index = cls()
        for row in rows:
            if row.genome_build != genome_build or row.chrom is None or row.start is None or not row.ref:
                continue
            alts = [alt.strip() for alt in (row.alts or "").split(",")] if row.alts else []
            for alt, vrs_id in zip(alts, split_vrs_ids(row.vrs_id), strict=False):
                if not alt or vrs_id is None:
                    continue
                key = (row.chrom, row.start, row.ref.upper(), alt.upper())
                spec = vrs_spec_release(row.vrs_spec)
                seen = index._ids.get(key)
                if seen is None:
                    index._ids[key] = (vrs_id, spec)
                elif seen is not _CONTESTED and seen[0] != vrs_id:  # type: ignore[index]
                    index._ids[key] = _CONTESTED
                elif seen is not _CONTESTED and seen[1] != spec:  # type: ignore[index]
                    # One id stated under two versions, or under one and none: the id stands, the
                    # version is unknown.
                    index._ids[key] = (vrs_id, None)
        return index

    def lookup(
        self, chrom: str | None, start: int | None, ref: str | None, alts: Sequence[str | None] | None
    ) -> tuple[list[str | None] | None, str | None]:
        """`(ids parallel to alts, vrs_spec)` for one parquet row, or `(None, None)` when none is known."""
        if chrom is None or start is None or not ref or not alts:
            return None, None
        found = [
            self._ids.get((chrom, start, ref.upper(), alt.strip().upper())) if alt else None for alt in alts
        ]
        named = [hit for hit in found if hit is not None and hit is not _CONTESTED]
        if not named:
            return None, None
        ids = [hit[0] if hit is not None and hit is not _CONTESTED else None for hit in found]  # type: ignore[index]
        specs = {hit[1] for hit in named}  # type: ignore[index]
        return ids, (specs.pop() if len(specs) == 1 else None)


def with_vrs_columns(table: pl.DataFrame, ids: VrsIds) -> pl.DataFrame:
    """A positional table's parquet with `vrs_id` (comma-joined, parallel to its `alts`) and `vrs_spec`.

    The shape of the table's own `alts`, a comma-joined string, which is also `resolution.csv`'s, so
    `reverse` writes the cell back unchanged.
    """
    cells: list[str | None] = []
    specs: list[str | None] = []
    for row in table.select("chrom", "start", "ref", "alts").iter_rows(named=True):
        alts = row["alts"].split(",") if row["alts"] else None
        found, spec = ids.lookup(row["chrom"], row["start"], row["ref"], alts)
        cells.append(join_vrs_ids(found) if found is not None else None)
        specs.append(spec)
    return table.with_columns(
        pl.Series("vrs_id", cells, dtype=pl.Utf8), pl.Series("vrs_spec", specs, dtype=pl.Utf8)
    )

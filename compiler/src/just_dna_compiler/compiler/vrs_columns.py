"""The enricher's minted VRS ids, carried onto the variant parquets (RM270).

An indel's `variant_key` and its coordinate are its source's spelling, and a caller may spell the same
event another legal way, so an exact `(chrom, pos, ref, alt)` join misses it. The VRS allele id is over
the fully justified allele, so it does not depend on the spelling: it is the key a consumer who can mint
VRS from its own VCF joins on. The enricher mints it into `resolution.csv`, which has no parquet by
design, so until RM270 it reached no artifact (`@dont-discard-computed`) and a round trip dropped it.

**Copied, never minted here.** The compiler has no reference sequence (P2), so it cannot justify an
indel; and minting a substitution here would put ids in the artifact that `reverse` then writes into a
`resolution.csv` that never had them, so the second lap's manifest would count more identified alleles
than the first.

**From the row's own `resolution.csv` row, by allele** (`@vrsid-per-alt`). A parquet row reads the
`resolution.csv` rows filed under the key `reverse` files it under (`resolution_key`) at its own
`(chrom, start, ref)`, and takes each of its own ALTs' ids member for member, with a hole where none is
recorded. Never an id another subject's row recorded for the same spelling: that would be true of the
allele, but `reverse` would then write it under this row's key, and the round trip would gain ids the
table never held. Two rows of one key recording one allele with two different ids withhold it, since one
of them is wrong. `vrs_spec` (RM304) is copied as the cell states it, when every id the row carries came
from rows stating the same one.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import polars as pl
from just_dna_format.base import derive_variant_key
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import join_vrs_ids, split_vrs_ids


def resolution_key(
    row: Mapping[str, Any], chrom: str, start: int, alts_cell: str | None, genome_build: str
) -> str:
    """The `resolution.csv` key a parquet row belongs to: the identity the AUTHOR wrote.

    Shared by `reverse` (which files the row it re-emits under it) and the id lookup above (which reads
    the row filed there), so the two cannot disagree about which row a parquet row came from.
    Recomputed from `authored_ident` rather than read off the parquet's own `variant_key`, because on
    the weights side those two differ exactly where it matters: a one-to-many rsID expansion re-keys
    each emitted row onto its own locus, so the stored key names a locus while the injected table
    named the rsID. Reading the stored column there would file N rows under N keys and leave the
    collapsed authored row joining to none of them.

    Falls back to the stored key, then to a fresh derivation, for an artifact compiled before
    `authored_ident` existed.
    """
    if (authored := row.get("authored_ident")) is not None:
        authored_set = set(authored)
        return derive_variant_key(
            row.get("rsid") if "rsid" in authored_set else None,
            chrom if "chrom" in authored_set else None,
            start if "start" in authored_set else None,
            row.get("ref") if "ref" in authored_set else None,
            alts_cell if "alts" in authored_set else None,
            build=genome_build,
        )
    return row.get("variant_key") or derive_variant_key(
        row.get("rsid"), chrom, start, row.get("ref"), alts_cell, build=genome_build
    )


@dataclass
class VrsIds:
    """`(key, chrom, start, REF) -> {ALT: (vrs_id, vrs_spec)}` over a `resolution.csv`, on one build."""

    _ids: dict[tuple[str, str, int, str], dict[str, tuple[str, str | None]]] = field(default_factory=dict)
    #: Alleles two rows of one key record with two different ids: withheld.
    _contested: set[tuple[str, str, int, str, str]] = field(default_factory=set)

    @classmethod
    def of(cls, rows: Sequence[ResolutionRow], genome_build: str) -> "VrsIds":
        index = cls()
        for row in rows:
            if row.genome_build != genome_build or row.chrom is None or row.start is None or not row.ref:
                continue
            alts = [alt.strip().upper() for alt in row.alts.split(",")] if row.alts else []
            ids = split_vrs_ids(row.vrs_id)
            if len(ids) != len(alts):
                # `ResolutionRow` refuses this at load; a row that reached here some other way is
                # withheld whole rather than paired by position.
                continue
            locus = (row.variant_key, row.chrom, row.start, row.ref.upper())
            recorded = index._ids.setdefault(locus, {})
            for alt, vrs_id in zip(alts, ids, strict=True):
                if not alt or vrs_id is None:
                    continue
                seen = recorded.get(alt)
                if seen is not None and seen[0] != vrs_id:
                    index._contested.add((*locus, alt))
                elif seen is None or seen[1] == row.vrs_spec:
                    recorded[alt] = (vrs_id, row.vrs_spec)
                else:
                    # One id stated under two versions, or under one and none: the version is unknown.
                    recorded[alt] = (vrs_id, None)
        return index

    def lookup(
        self,
        key: str,
        chrom: str | None,
        start: int | None,
        ref: str | None,
        alts: Sequence[str | None] | None,
    ) -> tuple[list[str | None] | None, str | None]:
        """`(ids parallel to alts, vrs_spec)` for one parquet row, or `(None, None)` when none is recorded."""
        if chrom is None or start is None or not ref or not alts:
            return None, None
        locus = (key, chrom, start, ref.upper())
        recorded = self._ids.get(locus, {})
        found: list[tuple[str, str | None] | None] = []
        for alt in alts:
            allele = alt.strip().upper() if alt else ""
            found.append(None if not allele or (*locus, allele) in self._contested else recorded.get(allele))
        named = [hit for hit in found if hit is not None]
        if not named:
            return None, None
        specs = {spec for _id, spec in named}
        return [hit[0] if hit is not None else None for hit in found], (
            specs.pop() if len(specs) == 1 else None
        )


def with_vrs_columns(table: pl.DataFrame, ids: VrsIds, genome_build: str) -> pl.DataFrame:
    """A positional table's parquet with `vrs_id` (comma-joined, parallel to its `alts`) and `vrs_spec`.

    The shape of the table's own `alts`, a comma-joined string, which is also `resolution.csv`'s, so
    `reverse` writes the cell back unchanged. The key is the row's stored `variant_key`, which on these
    tables already is the authored-subset key `resolution.csv` files the row under (`reverse` reads it
    the same way).
    """
    cells: list[str | None] = []
    specs: list[str | None] = []
    for row in table.select("variant_key", "chrom", "start", "ref", "alts").iter_rows(named=True):
        alts = row["alts"].split(",") if row["alts"] else None
        key = row["variant_key"] or resolution_key(row, row["chrom"], row["start"], row["alts"], genome_build)
        found, spec = ids.lookup(key, row["chrom"], row["start"], row["ref"], alts)
        cells.append(join_vrs_ids(found) if found is not None else None)
        specs.append(spec)
    return table.with_columns(
        pl.Series("vrs_id", cells, dtype=pl.Utf8), pl.Series("vrs_spec", specs, dtype=pl.Utf8)
    )

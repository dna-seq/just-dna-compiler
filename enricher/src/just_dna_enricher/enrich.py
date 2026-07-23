"""`enrich` — fill the source-independent resolution table for a module spec, then hand off to compile.

The resolver chain, first-hit-wins: an existing/human-authored row (authoritative, never clobbered) →
the local cache (a downloaded snapshot, offline) → live Ensembl (V2 GraphQL → V1 REST). It writes
`resolution.csv` beside the spec; the compiler then consumes it with no source knowledge and no
network. Two modes: `best_effort` fills what it can and records the rest as `not_found`; `strict`
fails unless every in-scope variant resolves to a position (the network analogue of the compiler's
`strict=True`). `--offline` clamps the chain to the cache alone (guaranteed zero egress).
"""

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.cache import resolve_ensembl_reference
from just_dna_compiler.compiler import _load_csv_rows
from just_dna_compiler.resolver import lookup_loci
from just_dna_format.base import derive_variant_key
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.download import ensure_snapshot
from just_dna_enricher.ensembl import EnsemblResolver

logger = logging.getLogger(__name__)

_FIELDNAMES = [
    "variant_key", "rsid", "chrom", "start", "ref", "alts",
    "genome_build", "locus_index", "source", "status", "fetched_at",
]


class EnrichmentError(RuntimeError):
    """Raised in strict mode when the chain cannot fully resolve the module."""


@dataclass
class EnrichmentResult:
    rows: list[ResolutionRow]
    unresolved: list[str] = field(default_factory=list)  # variant_keys with no resolved position
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"

    @property
    def fully_resolved(self) -> bool:
        return not self.unresolved


def enrich(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    offline: bool = False,
    ensembl_cache: Optional[Path] = None,
    download: bool = True,
    genome_build: str = "GRCh38",
    write: bool = True,
    resolver: Optional[EnsemblResolver] = None,
) -> EnrichmentResult:
    """Resolve a spec's variants into `resolution.csv`. See the module docstring for the chain/modes."""
    spec_dir = Path(spec_dir)
    variants: list[VariantRow] = []
    variants_path = spec_dir / "variants.csv"
    if variants_path.exists():
        variants, errors, _ = _load_csv_rows(variants_path, VariantRow, "variants.csv")
        if errors:
            raise EnrichmentError(f"variants.csv is invalid: {errors[0]}")

    # Existing/human rows are authoritative — merge, never clobber.
    existing: dict[str, list[ResolutionRow]] = {}
    resolution_path = spec_dir / "resolution.csv"
    if resolution_path.exists():
        rows, errors, _ = _load_csv_rows(resolution_path, ResolutionRow, "resolution.csv")
        if errors:
            raise EnrichmentError(f"existing resolution.csv is invalid: {errors[0]}")
        for row in rows:
            existing.setdefault(row.variant_key, []).append(row)

    if genome_build != genome_build.strip() or genome_build != "GRCh38":
        logger.warning("Enrichment is GRCh38-bound; genome_build=%r resolves nothing (RM15).", genome_build)

    # Partition the variants that still need work (skip those an existing row already covers).
    need_pos = [
        v for v in variants
        if v.rsid is not None and v.chrom is None and v.variant_key not in existing
    ]
    need_rsid = [
        v for v in variants
        if v.rsid is None and v.chrom is not None and v.variant_key not in existing
    ]

    rsid_to_loci: dict[str, list[dict]] = {}
    pos_to_rsid: dict[str, str] = {}
    source_of_rsid: dict[str, str] = {}

    # ── cache link (offline, first) ──────────────────────────────────────────────────────────
    reference = resolve_ensembl_reference(ensembl_cache)
    if reference is None and not offline and download:
        try:
            ensure_snapshot(ensembl_cache)
            reference = resolve_ensembl_reference(ensembl_cache)
        except Exception as exc:  # provisioning is best-effort; degrade to live/offline
            logger.warning("Snapshot provisioning failed (%s); continuing without cache.", exc)
    if reference is not None and (need_pos or need_rsid) and genome_build == "GRCh38":
        rsids = [v.rsid for v in need_pos if v.rsid]
        positions = [(v.chrom, v.start, v.ref) for v in need_rsid]
        rsid_to_loci, pos_to_rsid, _ = lookup_loci(reference, rsids, positions)
        for rsid in rsid_to_loci:
            source_of_rsid[rsid] = "cache"

    # ── live Ensembl link (V2→V1), for cache misses, unless offline ────────────────────────────
    if not offline and genome_build == "GRCh38":
        missing = [v.rsid for v in need_pos if v.rsid and v.rsid not in rsid_to_loci]
        if missing:
            owned = resolver is None
            client = resolver or EnsemblResolver()
            try:
                for rsid in missing:
                    loci, src = client.resolve_rsid(rsid)
                    if loci:
                        rsid_to_loci[rsid] = loci
                        source_of_rsid[rsid] = src or "ensembl"
            finally:
                if owned:
                    client.close()

    # ── assemble the table (a row for every variant; expansion → N rows) ───────────────────────
    out: list[ResolutionRow] = []
    unresolved: list[str] = []
    for v in variants:
        key = v.variant_key or derive_variant_key(v.rsid, v.chrom, v.start, v.ref)
        if key in existing:
            out.extend(existing[key])
            if not any(r.chrom is not None for r in existing[key]):
                unresolved.append(key)
            continue
        if v.rsid is not None and v.chrom is None:
            loci = rsid_to_loci.get(v.rsid, [])
            if loci:
                src = source_of_rsid.get(v.rsid, "cache")
                for i, locus in enumerate(loci):
                    out.append(ResolutionRow(
                        variant_key=key, rsid=v.rsid, genome_build=genome_build,
                        locus_index=i, source=src, status="resolved", **locus,
                    ))
            else:
                out.append(ResolutionRow(variant_key=key, rsid=v.rsid, genome_build=genome_build,
                                         source="ensembl" if not offline else "cache", status="not_found"))
                unresolved.append(key)
        elif v.rsid is None and v.chrom is not None:
            rsid = pos_to_rsid.get(key)
            out.append(ResolutionRow(
                variant_key=key, rsid=rsid, chrom=v.chrom, start=v.start, ref=v.ref, alts=v.alts,
                genome_build=genome_build, source="cache" if rsid else "authored", status="resolved",
            ))
        else:
            # already complete, or has a position — a full record, nothing to resolve
            out.append(ResolutionRow(
                variant_key=key, rsid=v.rsid, chrom=v.chrom, start=v.start, ref=v.ref, alts=v.alts,
                genome_build=genome_build, source="authored", status="resolved",
            ))

    out.sort(key=lambda r: (r.variant_key, r.locus_index))
    sources = sorted({r.source for r in out if r.source})
    result = EnrichmentResult(rows=out, unresolved=sorted(set(unresolved)), sources=sources, mode=mode)

    if mode == "strict" and result.unresolved:
        raise EnrichmentError(
            f"strict enrichment: {len(result.unresolved)} variant(s) unresolved after the chain "
            f"(cache/Ensembl): {result.unresolved}. Provide a complete cache/online access, add the "
            f"loci by hand to resolution.csv, or enrich with mode='best_effort'."
        )

    if write:
        _write_resolution_csv(out, resolution_path)
    return result


def _write_resolution_csv(rows: list[ResolutionRow], output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "variant_key": r.variant_key,
                    "rsid": r.rsid or "",
                    "chrom": r.chrom if r.chrom is not None else "",
                    "start": r.start if r.start is not None else "",
                    "ref": r.ref or "",
                    "alts": r.alts or "",
                    "genome_build": r.genome_build,
                    "locus_index": r.locus_index,
                    "source": r.source or "",
                    "status": r.status or "",
                    "fetched_at": r.fetched_at or "",
                }
            )

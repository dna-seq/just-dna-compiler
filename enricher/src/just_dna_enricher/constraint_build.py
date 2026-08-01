"""gnomAD gene-constraint snapshot builder — the ``[dev]`` half of the gene-metrics pass.

Turns gnomAD's v4.1 constraint metrics TSV into a small gene-level parquet the enricher reads offline
(`gnomad_constraint/data/*.parquet`), in the same on-disk layout as the Ensembl and ClinVar snapshots.
Modelled directly on `clinvar_build`, down to the streaming download with the `.part` rename and the
`release.json` provenance record.

**Why this one can ship offline and frequency cannot** is pure size. The source TSV is 95.5 MB — per
*transcript*, 55 columns — and reduces to one row per gene with a curated column subset, landing in
single-digit MB. The v4.1 *frequency* data is 58 GB of exomes plus 742 GB of genomes, so there is no
equivalent slice to build.

**The row pick is the hard part, and it is load-bearing rather than cosmetic.** The TSV is
per-transcript and mixes RefSeq with Ensembl rows for the same gene, and — verified against the real
file, not assumed — **both carry `mane_select=true`**::

    A1BG   1                 NM_130786.4       canonical=true  mane_select=true    <- RefSeq
    A1BG   ENSG00000121410   ENST00000263100   canonical=true  mane_select=true    <- Ensembl
    A1BG   ENSG00000121410   ENST00000600966   canonical=false mane_select=false

(BRCA1 and MYH7 show the same shape, so this is the file's general structure, not an A1BG quirk.) A
naive "first `mane_select` row wins" therefore returns whichever the file happens to list first, and
for A1BG that is the RefSeq row whose `gene_id` is the bare NCBI id `1` — useless as a stable
identity. The rule here is **`mane_select` AND an `ENSG`-shaped `gene_id`**, falling back to
`canonical` on ENSG, and recording the gene as unresolved rather than guessing. `_pick_row` is fed the
rows in both orders by a test, because same-input-different-order is exactly what the naive
implementation gets wrong.

Builder-only (`just-dna-enricher[dev]`): `polars` is a guarded import, so the runtime gene-metrics
path (which reads the built parquet through DuckDB) never needs it and the core install stays
polars-free (Goal 2).
"""

import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterator, Optional

import httpx

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

# Verified with a live request: HTTP 200, content-length 95546041, last modified 2024-04-18. Note the
# path is `release/4.1/`, NOT `release/v4.1/` — two plausible-looking guesses 404'd, and anonymous
# bucket listing is disabled on both the GCS and S3 mirrors, so this came from the UCSC track makedoc
# and was then checked directly rather than inferred.
DEFAULT_CONSTRAINT_URL = (
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/"
    "gnomad.v4.1.constraint_metrics.tsv"
)

# The curated column subset, mapping source column → `GeneMetricsRow` field. The `lof_hc_lc.*` and
# `mis_pphen.*` families are deliberately left out of this pass: they are refinements of the same two
# axes, and carrying all 55 columns would trade the small-snapshot property for data nobody asked for.
_COLUMN_MAP: dict[str, str] = {
    "gene_id": "gene_id",
    "transcript": "transcript",
    "lof.pLI": "pli",
    "lof.oe_ci.upper": "loeuf",   # LOEUF — stored under the name clinical readers ask for it by
    "lof.oe": "oe_lof",
    "lof.oe_ci.lower": "oe_lof_lower",
    "lof.z_score": "lof_z",
    "mis.oe": "oe_mis",
    "mis.z_score": "mis_z",
    "syn.z_score": "syn_z",
    "lof.obs": "obs_lof",
    "lof.exp": "exp_lof",
    "constraint_flags": "constraint_flags",
}
_INT_FIELDS = frozenset({"obs_lof"})
_FLOAT_FIELDS = frozenset(
    {"pli", "loeuf", "oe_lof", "oe_lof_lower", "lof_z", "oe_mis", "mis_z", "syn_z", "exp_lof"}
)
# gnomAD writes a missing cell as an empty string or the R-flavoured `NA`; both mean "no value".
_NULLS = frozenset({"", "NA", "na", "NaN", "nan", "None", "null"})


def _empty_schema() -> dict:
    """The parquet schema (column order + dtypes) — fixed so a rebuild is byte-identical (P7).

    Built lazily so importing this module without the `[dev]` polars extra does not fail; only
    *building* needs polars.
    """
    return {
        "gene": pl.Utf8,
        "gene_id": pl.Utf8,
        "transcript": pl.Utf8,
        "mane_select": pl.Boolean,
        "pli": pl.Float64,
        "loeuf": pl.Float64,
        "oe_lof": pl.Float64,
        "oe_lof_lower": pl.Float64,
        "lof_z": pl.Float64,
        "mis_z": pl.Float64,
        "syn_z": pl.Float64,
        "oe_mis": pl.Float64,
        "obs_lof": pl.Int64,
        "exp_lof": pl.Float64,
        "constraint_flags": pl.Utf8,
    }


def _is_true(value: Optional[str]) -> bool:
    return (value or "").strip().lower() == "true"


def _is_ensembl_gene(gene_id: Optional[str]) -> bool:
    """Whether `gene_id` is an Ensembl gene id rather than a bare NCBI number.

    This one predicate is what separates the two `mane_select=true` rows for a gene, so it is a named
    function rather than an inline `startswith` buried in the pick.
    """
    return (gene_id or "").strip().upper().startswith("ENSG")


def _pick_row(rows: list[dict]) -> Optional[dict]:
    """Choose the one row whose metrics represent a gene, or `None` when no row qualifies.

    Order of preference: MANE Select on an ENSG gene id → canonical on an ENSG gene id → nothing.
    Within a tier, ties break on `transcript` so the result cannot depend on file order — the property
    the both-orders test pins. Returning `None` (recording the gene unresolved) is deliberate: a gene
    whose only rows are RefSeq has no ENSG identity to carry, and inventing one would be worse than
    saying so.
    """
    for predicate in (
        lambda r: _is_true(r.get("mane_select")) and _is_ensembl_gene(r.get("gene_id")),
        lambda r: _is_true(r.get("canonical")) and _is_ensembl_gene(r.get("gene_id")),
    ):
        candidates = [r for r in rows if predicate(r)]
        if candidates:
            return min(candidates, key=lambda r: r.get("transcript") or "")
    return None


def _coerce(field_name: str, raw: Optional[str]) -> object:
    """Parse one TSV cell into its typed value, mapping gnomAD's `NA`/empty to `None`."""
    text = (raw or "").strip()
    if text in _NULLS:
        return None
    if field_name in _INT_FIELDS:
        try:
            return int(float(text))
        except ValueError:
            return None
    if field_name in _FLOAT_FIELDS:
        try:
            return float(text)
        except ValueError:
            return None
    return text or None


def _gene_record(gene: str, row: dict) -> dict:
    """Reduce a picked TSV row to the snapshot's gene-level record."""
    record: dict[str, object] = {"gene": gene, "mane_select": _is_true(row.get("mane_select"))}
    for source_column, field_name in _COLUMN_MAP.items():
        record[field_name] = _coerce(field_name, row.get(source_column))
    return record


def _iter_rows(tsv: Path) -> Iterator[dict]:
    """Stream the TSV as dicts. Streamed rather than read whole: the real file is 95.5 MB, and the
    output is three orders of magnitude smaller, so there is no reason to hold the input in memory."""
    with open(tsv, "r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle, delimiter="\t")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


@dataclass
class ConstraintBuildResult:
    """Outcome of a snapshot build (paths + provenance + what was dropped and why)."""

    out_dir: Path
    parquet_file: Path
    gene_count: int
    source_sha256: str
    source_rows: int = 0
    unresolved_genes: list[str] = field(default_factory=list)


def download_constraint_tsv(dest: Path, url: str = DEFAULT_CONSTRAINT_URL) -> Path:
    """Stream the gnomAD constraint TSV to ``dest`` (atomic ``.part`` rename), returning the path.

    Same shape as `clinvar_build.download_clinvar_vcf`: core ``httpx``, sha256 computed while
    streaming. Provisioning-only — the gene-metrics pass never calls this; it reads a prebuilt cache.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading gnomAD constraint TSV from %s ...", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
                hasher.update(chunk)
    tmp.replace(dest)
    logger.info("Downloaded %s (sha256 %s)", dest, hasher.hexdigest())
    return dest


def build_snapshot(
    tsv: Path, out_dir: Path, *, source_url: str = DEFAULT_CONSTRAINT_URL
) -> ConstraintBuildResult:
    """Convert the constraint TSV into `data/gnomad_constraint.parquet` + `release.json`.

    One row per gene, chosen by `_pick_row`, sorted by `gene` so a rebuild is byte-identical
    (Principle 7); `release.json`'s `built_at` is the only per-run-varying byte and lives outside the
    parquet, exactly as in the ClinVar builder.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the gnomAD constraint snapshot; install the publisher/dev "
            "surface with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    tsv = Path(tsv)
    if not tsv.exists():
        raise FileNotFoundError(f"gnomAD constraint TSV not found at {tsv}")
    out_dir = Path(out_dir)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    by_gene: dict[str, list[dict]] = {}
    source_rows = 0
    for row in _iter_rows(tsv):
        gene = (row.get("gene") or "").strip()
        if not gene:
            continue
        source_rows += 1
        by_gene.setdefault(gene, []).append(row)

    records: list[dict] = []
    unresolved: list[str] = []
    for gene in sorted(by_gene):
        picked = _pick_row(by_gene[gene])
        if picked is None:
            unresolved.append(gene)
            continue
        records.append(_gene_record(gene, picked))

    schema = _empty_schema()
    frame = pl.DataFrame(records, schema=schema).sort("gene")
    parquet_path = data_dir / "gnomad_constraint.parquet"
    frame.write_parquet(parquet_path)

    source_sha256 = _sha256_file(tsv)
    _write_release_json(
        out_dir,
        source_url=source_url,
        source_sha256=source_sha256,
        gene_count=frame.height,
        source_rows=source_rows,
        unresolved_count=len(unresolved),
    )
    logger.info(
        "Built gnomAD constraint snapshot: %d genes from %d transcript rows → %s "
        "(%d gene(s) had no MANE/canonical Ensembl row and were dropped)",
        frame.height, source_rows, parquet_path, len(unresolved),
    )
    return ConstraintBuildResult(
        out_dir=out_dir,
        parquet_file=parquet_path,
        gene_count=frame.height,
        source_sha256=source_sha256,
        source_rows=source_rows,
        unresolved_genes=unresolved,
    )


def _write_release_json(
    out_dir: Path,
    *,
    source_url: str,
    source_sha256: str,
    gene_count: int,
    source_rows: int,
    unresolved_count: int,
) -> Path:
    """Write ``release.json`` — the provenance beside the parquet. `built_at` is deliberately outside
    the parquet so the parquet itself stays byte-reproducible."""
    release = {
        "source_url": source_url,
        "source_sha256": source_sha256,
        "gene_count": gene_count,
        "source_rows": source_rows,
        "unresolved_count": unresolved_count,
        "dataset": "gnomad_v4.1_constraint",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "builder_version": _builder_version(),
    }
    path = out_dir / "release.json"
    path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

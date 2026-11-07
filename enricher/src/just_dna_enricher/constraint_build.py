"""gnomAD gene-constraint snapshot builder — the ``[dev]`` half of the gene-metrics pass.

Turns a gnomAD v4 constraint metrics TSV (4.1.2 by default since RM410) into a small gene-level parquet the enricher reads offline
(`gnomad_constraint/data/*.parquet`), in the same on-disk layout as the Ensembl and ClinVar snapshots.
Modelled directly on `clinvar_build`, down to the streaming download with the `.part` rename and the
`release.json` provenance record.

**Why this one can ship offline and frequency cannot** is pure size. The source TSV is 95.5 MB for 4.1
(574.5 MB bgzipped for 4.1.2, 113 columns) — per *transcript* — and reduces to one row per gene with a curated column subset, landing in
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
import gzip
import hashlib
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.normalize import now_utc_iso
from just_dna_format.snapshot import SnapshotRelease, SnapshotWrite, begin_snapshot_write

from just_dna_enricher.gnomad import normalize_constraint_flags
from just_dna_enricher.net import EndpointRetired, stream_to_file

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

#: The gnomAD constraint release this lane builds when nothing pins one (RM410). 4.1.2, not 4.1.1: 4.1.1
#: recomputed the metrics (low-coverage coding loci by allele number, chrX and chrY for the first time,
#: a revised LOFTEE `END_TRUNC`, a new LOEUF) and miscounted the rank denominator; 4.1.2 fixes only
#: the ranks. The liaison's adoption note is in `docs/UPSTREAM_DATA_SOURCES.md`.
_DEFAULT_RELEASE = "4.1.2"

#: Releases whose file is a plain TSV. Every later one ships only `….tsv.bgz` (bgzip, which a gzip
#: reader takes); a pin of a release after these is fetched under that name, so a new release needs
#: no code, and one that changed the convention again fails as a 404 naming the URL.
_PLAIN_TSV_RELEASES = frozenset({"4.0", "4.1"})

#: A gnomAD constraint release named in a file name or a URL: `gnomad.v4.1.2.constraint_metrics…`,
#: the test slice's `gnomad_v4.1_constraint_slice.tsv`, or a bucket path's `release/4.1.2/constraint/`.
_RELEASE_IN_NAME = re.compile(r"gnomad[._]v(\d+(?:\.\d+)*)[._]constraint")
_RELEASE_IN_PATH = re.compile(r"/release/(\d+(?:\.\d+)*)/constraint/")


def _constraint_url(release: str) -> str:
    """The bucket URL of `release`'s constraint metrics. Verified live for 4.1 (`.tsv`, 95.5 MB) and
    4.1.2 (`.tsv.bgz`, 574.5 MB, md5 ecec6974…); the path is `release/<v>/`, never `release/v<v>/`."""
    return (
        "https://storage.googleapis.com/gcp-public-data--gnomad/release/"
        f"{release}/constraint/{_constraint_filename(release)}"
    )


def _constraint_filename(release: str) -> str:
    suffix = ".tsv" if release in _PLAIN_TSV_RELEASES else ".tsv.bgz"
    return f"gnomad.v{release}.constraint_metrics{suffix}"


def _release_of(*names: str) -> str | None:
    """The release the first of `names` that names one names, else `None` (withheld, never guessed)."""
    for name in names:
        found = _RELEASE_IN_NAME.search(name) or _RELEASE_IN_PATH.search(name)
        if found:
            return found.group(1)
    return None


def _dataset_label(release: str | None) -> str | None:
    return f"gnomad_v{release}_constraint" if release else None


DEFAULT_CONSTRAINT_URL = _constraint_url(_DEFAULT_RELEASE)

# The curated column subset, mapping source column → `GeneMetricsRow` field. The `lof_hc_lc.*` and
# `mis_pphen.*` families are deliberately left out of this pass: they are refinements of the same two
# axes, and carrying all 55 columns would trade the small-snapshot property for data nobody asked for.
_COLUMN_MAP: dict[str, str] = {
    "gene_id": "gene_id",
    "transcript": "transcript",
    "lof.pLI": "pli",
    "lof.oe_ci.upper": "loeuf",  # LOEUF — stored under the name clinical readers ask for it by
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


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def _is_ensembl_gene(gene_id: str | None) -> bool:
    """Whether `gene_id` is an Ensembl gene id rather than a bare NCBI number.

    This one predicate is what separates the two `mane_select=true` rows for a gene, so it is a named
    function rather than an inline `startswith` buried in the pick.
    """
    return (gene_id or "").strip().upper().startswith("ENSG")


def _pick_row(rows: list[dict]) -> dict | None:
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


def _coerce(field_name: str, raw: str | None) -> object:
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
    """Reduce a picked TSV row to the snapshot's gene-level record.

    `constraint_flags` is the one column the TSV does not hand over in the shape the model documents:
    gnomAD writes its **JSON array literal** into the cell, so `_coerce` — which only maps a null
    spelling to `None` and otherwise keeps the text — stored `"[]"` for an unflagged gene and
    `'["outlier_mis","outlier_syn"]'` for a flagged one. Neither survives `if row.constraint_flags:`
    or a split on `|`, and the column is inside `GENE_METRICS_FACT_FIELDS`, so the two producers
    disagreed on `gene_metrics.signature` for the same gene (RM110). Normalized through the same
    function the live route uses, so the two legs cannot drift again.

    This cleans snapshots built from here on. The already-published v4.1 snapshot is immutable, which
    is why `gene_metrics.lookup_snapshot` normalizes on read as well.
    """
    record: dict[str, object] = {"gene": gene, "mane_select": _is_true(row.get("mane_select"))}
    for source_column, field_name in _COLUMN_MAP.items():
        record[field_name] = _coerce(field_name, row.get(source_column))
    record["constraint_flags"] = normalize_constraint_flags(record.get("constraint_flags"))
    return record


def _iter_rows(tsv: Path) -> Iterator[dict]:
    """Stream the TSV as dicts, plain or gzip-compressed, told apart by the bytes rather than the name.

    Streamed rather than read whole: 4.1.2's file is 574.5 MB compressed. bgzip is a run of gzip
    members, which `gzip.open` reads through (RM410).
    """
    with open(tsv, "rb") as probe:
        compressed = probe.read(2) == b"\x1f\x8b"
    opener = gzip.open if compressed else open
    with opener(tsv, "rt", encoding="utf-8", newline="") as handle:
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


class ConstraintBuildError(RuntimeError):
    """This lane had **no error type at all** until RM187, which is why its download leaked.

    Every other builder here owns one. This module raised whatever its inputs raised, so
    `caches._rebuild_constraint` caught `(FileNotFoundError, ImportError, OSError)` and a transport
    failure went straight past it. A lane without its own type cannot be caught *as that lane*, and
    the downloader has nothing to translate into (`@client-exception-contract`).
    """


class ConstraintUnavailable(ConstraintBuildError):
    """The gnomAD download did not answer — the fetch failed, not the file."""


class ConstraintRetired(ConstraintUnavailable, EndpointRetired):
    """The source answered HTTP 410: it retired the gnomAD constraint file (RM361, audit round 2).

    Its lane's `ConstraintUnavailable`, so every handler still catches it; marked `EndpointRetired`, so
    the reason is `retired` and the message says the file moved and to upgrade, never that the
    host was down.
    """


def download_constraint_tsv(dest: Path, url: str = DEFAULT_CONSTRAINT_URL) -> Path:
    """Stream the gnomAD constraint TSV to ``dest`` (atomic ``.part`` rename), returning the path.

    Provisioning-only — the gene-metrics pass never calls this; it reads a prebuilt cache. Shares
    `net.stream_to_file` with every other bulk download here, so the retry and the translation are
    one rule rather than eleven copies of one (RM187).
    """
    return stream_to_file(
        dest,
        url,
        error_cls=ConstraintUnavailable,
        retired=ConstraintRetired,
        what="the gnomAD constraint TSV",
        remedy="Pass --source constraint=<tsv> to build from a copy you already hold.",
    ).path


def build_snapshot(
    tsv: Path, out_dir: Path, *, source_url: str = DEFAULT_CONSTRAINT_URL
) -> ConstraintBuildResult:
    """Convert the constraint TSV into `data/gnomad_constraint.parquet` + `release.json`.

    One row per gene, chosen by `_pick_row`, sorted by `gene` so a rebuild is byte-identical
    (Principle 7); `release.json`'s `built_at` is the only per-run-varying byte and lives outside the
    parquet, exactly as in the ClinVar builder.

    The release label is read from the input's file name (gnomAD names every release's file
    `gnomad.v<release>.constraint_metrics…`), else from `source_url`'s `release/<v>/` path. It was a
    constant, `gnomad_v4.1_constraint`, so a 4.1.2 file would have been labelled 4.1 (RM410). A file
    that names neither is built with no label, which the pass withholds rather than guesses.
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
    snapshot = begin_snapshot_write(out_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(parquet_path)

    source_sha256 = _sha256_file(tsv)
    _write_release_json(
        snapshot,
        source_url=source_url,
        source_sha256=source_sha256,
        gene_count=frame.height,
        source_rows=source_rows,
        unresolved_count=len(unresolved),
        dataset=_dataset_label(_release_of(tsv.name, source_url)),
    )
    logger.info(
        "Built gnomAD constraint snapshot: %d genes from %d transcript rows → %s "
        "(%d gene(s) had no MANE/canonical Ensembl row and were dropped)",
        frame.height,
        source_rows,
        parquet_path,
        len(unresolved),
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
    snapshot: SnapshotWrite,
    *,
    source_url: str,
    source_sha256: str,
    gene_count: int,
    source_rows: int,
    unresolved_count: int,
    dataset: str | None,
) -> Path:
    """Write ``release.json`` — the provenance beside the parquet. `built_at` is deliberately outside
    the parquet so the parquet itself stays byte-reproducible."""
    release = SnapshotRelease(
        source_url=source_url,
        source_sha256=source_sha256,
        gene_count=gene_count,
        source_rows=source_rows,
        unresolved_count=unresolved_count,
        dataset=dataset,
        built_at=now_utc_iso(),
        builder_version=_builder_version(),
    )
    return snapshot.commit(release)

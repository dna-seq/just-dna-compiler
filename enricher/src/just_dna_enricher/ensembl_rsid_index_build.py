"""The Ensembl rsID index: rsID → (chrom, start), sorted by rsID, derived from the split core (0.9, RM431 ask 4).

**Why it exists.** The split repo's files are one per chromosome, each sorted by position, so a lookup
by position prunes to a row group or two and a lookup by rsID prunes nothing: every row group's `id`
spans rs1 to rs9…, and `lookup_loci` by rsID read the whole column (about 6.1 GB over 25 files, 9 to
14 s locally, RM405). The index turns that into two pruned reads: the rsID's positions here, then those
positions in the core.

**A derived lane, local only** (the pm, 2026-11-16, on the registry's answer). Its acquire stage is the
Ensembl core on disk, its parent is a field (`CacheLane.parents`), and it is built only when named,
by `cache rebuild --only ensembl_rsid_index` (`CacheLane.named_only`): never inside `ensure_snapshot`,
by `cache prepare` or by a bare `cache rebuild`, so a pull, `enrich(download=True)` and a provisioning
run pay nothing for it. It is not pulled, not published and not remote-eligible:
Ensembl by rsID is never sent remotely (RM430 decision 8).

**What the parent pin is.** The core's `manifest.json` `release_id`, which the decision names, and a
digest over the files the manifest attests under `data/` (path, size, sha256). A label alone is not a
core: one label has been seen over two sets of bytes (RM445), and a test slice states the real
release's label. `resolver.lookup_loci` reads the index only when both match the core it was handed,
and scans otherwise, saying why.

**Shape.** `data/ensembl_rsid_index-<bucket>.parquet`, one file per `INDEX_BUCKET_WIDTH` rsID numbers, in
name order the index in rsID order, three columns: `rs` (the rsID's number,
`UBIGINT`: the integer sorts as dbSNP numbers do and prunes by range), `chrom` and `start` as the core
spells them, one row per distinct `(rsID, chrom, start)`, sorted by all three. Every `id` of the
2026-07-13 release is `rs` + digits (1,391,478,689 rows measured); an `id` of another form is not
indexed, and a lookup asking one scans for it as before.

**Built in duckdb, not polars, the one builder that is** (`@duckdb-vs-polars` puts builders in polars).
The sort is of about 1.16 billion rows, and duckdb's memory ceiling and out-of-core spill are what make
that fit a workstation; polars would need the whole frame. It is also a core dependency, so the
helpers a runtime reader imports from here (`core_pin`, `INDEX_GLOB`) bring no `[dev]` extra with them.
It reads the core and writes only under `out_dir`, its spill included.
"""

import hashlib
import logging
import shutil
import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import duckdb
from just_dna_format.normalize import now_utc_iso
from just_dna_format.snapshot import (
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_MANIFEST_FILENAME,
    SnapshotRelease,
    begin_snapshot_write,
    read_release,
)

from just_dna_enricher.locations import read_snapshot_manifest, resolve_ensembl_reference

logger = logging.getLogger(__name__)

#: The index's payload files under `data/`, one per rsID bucket, named so name order is rsID order.
INDEX_FILE_PATTERN = "ensembl_rsid_index-{bucket:05d}.parquet"
INDEX_GLOB = "ensembl_rsid_index-*.parquet"
#: rsID numbers per bucket: the 2026-07-13 release's highest is rs2,552,305,714, so 26 buckets, each a
#: sort of tens of millions of rows rather than one of 1.16 billion.
INDEX_BUCKET_WIDTH = 100_000_000
#: The `id` spelling the index holds, as duckdb's `regexp_full_match` reads it.
RSID_PATTERN = "rs[0-9]+"
#: Rows per row group: a lookup reads one group per rsID, and the footer stays small (about 4,500
#: groups for the 2026-07-13 release).
INDEX_ROW_GROUP_SIZE = 262_144
#: The build's duckdb ceiling and threads: the sort spills past the ceiling into `out_dir`, so the
#: machine stays usable. Not a knob: a host that wants another ceiling calls `build_rsid_index` itself.
BUILD_MEMORY_LIMIT = "8GB"
BUILD_THREADS = 4
#: Where the build stages its file and spills its sort, inside `out_dir` and hidden from a reader.
_STAGING_DIRNAME = ".building"


class RsidIndexError(RuntimeError):
    """The index cannot be built: no core, a core its manifest does not name, or a failed write."""


def core_pin(core: Path) -> dict[str, str] | None:
    """What an index pins of the core it indexes: `release_id` and `files_sha256`, or `None`.

    `files_sha256` is the sha256 of the manifest's `data/` attestations, one `path size sha256` line
    each, sorted: the files a reader of the core reads, as the manifest states them. `None` when the
    core has no readable manifest, or one stating no `release_id` or no file under `data/`: such a core
    cannot be named, so no index is built from it or read beside it. Also `None` when a `data/` file's
    size or sha256 is unstated (review round 1, item 7): the pin is withheld, never hashed with an empty
    part, since two cores alike in release, paths and sizes would then pin alike over different bytes.
    """
    return _pin_and_refusal(core)[0]


def _moved_parent(index_dir: Path, core: Path) -> str | None:
    """Why the index at `index_dir` is not the index of `core`, or `None` when it is (review round 1, item 11).

    The one verdict the reader (`resolver._rsid_index_beside`, which then scans) and the lane's status
    (`caches.lane_status`, `prepare_lane`, which call the index stale) read. `None` too when `core` cannot
    be pinned (gone, no manifest, a file unstated): a parent that cannot be compared has not moved
    (`@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`), so it is never called stale.
    """
    current = core_pin(core)
    if current is None:
        return None
    release = read_release(index_dir)
    pinned = (release.parents or {}).get("ensembl") if release is not None else None
    if isinstance(pinned, dict) and {key: pinned.get(key) for key in current} == current:
        return None
    stated = pinned.get("release_id") if isinstance(pinned, dict) else None
    if stated == current["release_id"]:
        return f"it pins release {stated} over other files than the Ensembl core at {core} holds"
    return f"it pins {stated or 'no core'}, and the Ensembl core at {core} is {current['release_id']}"


def _pin_and_refusal(core: Path) -> tuple[dict[str, str] | None, str]:
    """`(core_pin(core), why it is None)`: the reason is empty when a pin is returned."""
    core = Path(core)
    if not core.is_dir():
        return None, f"there is no Ensembl snapshot at {core}"
    manifest = read_snapshot_manifest(core / SNAPSHOT_MANIFEST_FILENAME)
    release = (manifest.release_id or "").strip() if manifest is not None else ""
    entries = (
        [e for e in (manifest.files or ()) if e.path.startswith(f"{SNAPSHOT_DATA_DIRNAME}/")]
        if manifest
        else []
    )
    if manifest is None or not release or not entries:
        return None, (
            f"the Ensembl snapshot at {core} carries no {SNAPSHOT_MANIFEST_FILENAME} naming its release and "
            f"files, so an index of it could never be told from an index of another; the rsID index is "
            f"built from the split release only"
        )
    unstated = sorted(e.path for e in entries if e.size is None or not (e.sha256 or "").strip())
    if unstated:
        named = ", ".join(unstated[:5]) + (", …" if len(unstated) > 5 else "")
        return None, (
            f"the {SNAPSHOT_MANIFEST_FILENAME} of the Ensembl snapshot at {core} states no size or sha256 for "
            f"{len(unstated)} file{'' if len(unstated) == 1 else 's'} under {SNAPSHOT_DATA_DIRNAME}/ ({named}), "
            f"so the files an index would pin are not named whole and an index of it could be read beside "
            f"another core of the same release; re-pull the core (`cache pull --only ensembl`)"
        )
    lines = sorted(f"{entry.path} {entry.size} {entry.sha256.lower()}" for entry in entries)
    pin = {"release_id": release, "files_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest()}
    return pin, ""


@dataclass(frozen=True)
class RsidIndexBuildResult:
    """What a build wrote, and what it read."""

    out_dir: Path
    #: The payload files, in rsID order.
    files: tuple[Path, ...]
    #: Distinct `(rsID, chrom, start)` rows written.
    rows: int
    #: Rows of the core read (its files' own row counts).
    core_rows: int
    #: The pin written into `release.json`'s `parents.ensembl`.
    parent: dict[str, str]
    #: Wall-clock seconds the build took, and the payload's size.
    seconds: float
    size_bytes: int


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


def _quoted(path: Path | str) -> str:
    """A path as a SQL string literal's body: our own directories, quoted defensively."""
    return str(path).replace("'", "''")


def _one_chromosome_each(con: duckdb.DuckDBPyConnection, files: list[Path]) -> None:
    """Refuse a core whose files do not each hold one chromosome no other file holds.

    The build drops duplicate `(rsID, chrom, start)` rows one file at a time, which is the whole
    de-duplication only when no chromosome spans two files (the split layout: one file per chromosome).
    Read off each file's footer statistics; a file without them is read for its chromosomes.
    """
    seen: dict[str, Path] = {}
    for path in files:
        stats = con.execute(
            "SELECT min(stats_min_value), max(stats_max_value), count(*) FILTER (WHERE stats_min_value IS NULL) "
            f"FROM parquet_metadata('{_quoted(path)}') WHERE path_in_schema = 'chrom'"
        ).fetchone()
        if stats is not None and stats[2] == 0 and stats[0] is not None and stats[0] == stats[1]:
            chroms = {str(stats[0])}
        else:
            chroms = {
                str(c)
                for (c,) in con.execute(
                    f"SELECT DISTINCT chrom FROM read_parquet('{_quoted(path)}')"
                ).fetchall()
            }
        for chrom in chroms:
            if chrom in seen and seen[chrom] != path:
                raise RsidIndexError(
                    f"chromosome {chrom} is in both {seen[chrom].name} and {path.name}; the rsID index is built "
                    f"from the split layout, one file per chromosome"
                )
            seen[chrom] = path


def build_rsid_index(
    core: Path,
    out_dir: Path,
    *,
    memory_limit: str = BUILD_MEMORY_LIMIT,
    threads: int = BUILD_THREADS,
) -> RsidIndexBuildResult:
    """Build the rsID index of the split Ensembl `core` into `out_dir` (RM431).

    `core` is the Ensembl cache directory; it must hold a whole snapshot its own manifest attests
    (`resolve_ensembl_reference` answers it), a manifest naming its release (`core_pin`), and one
    chromosome per file, or `RsidIndexError` is raised before the index is written.

    **Two passes, so no step holds the whole index in memory** (one global `DISTINCT … ORDER BY` ran out
    of an 8 GB ceiling on the 2026-07-13 release). Each core file's distinct `(rsID, chrom, start)` rows
    are written into rsID buckets (`INDEX_BUCKET_WIDTH` numbers each), then each bucket is sorted and
    written as one payload file, `ensembl_rsid_index-<bucket>.parquet`, so the files in name order are
    the index in rsID order. Everything is staged under a hidden directory; `release.json` is withdrawn
    just before the files move into `data/` and written last, pinning the core.
    """
    started = time.monotonic()
    core = Path(core)
    resolved = resolve_ensembl_reference(core, load_dotenv_file=False) if core.is_dir() else None
    if resolved is None or resolved != core:
        raise RsidIndexError(
            f"no Ensembl snapshot at {core} to index: the rsID index is built from a whole split core "
            f"(`cache pull --only ensembl`)"
        )
    pin, refusal = _pin_and_refusal(core)
    if pin is None:
        raise RsidIndexError(refusal)
    sources = sorted((core / SNAPSHOT_DATA_DIRNAME).glob("*.parquet"))
    out_dir = Path(out_dir)
    staging = out_dir / _STAGING_DIRNAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        written, rows, core_rows = _build_staged(sources, staging, memory_limit=memory_limit, threads=threads)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    logger.info("Sorted %d rsID loci of %s into %d file(s)", rows, pin["release_id"], len(written))
    snapshot = begin_snapshot_write(out_dir)
    data = out_dir / SNAPSHOT_DATA_DIRNAME
    data.mkdir(parents=True, exist_ok=True)
    for stale in data.glob(INDEX_GLOB):
        stale.unlink()
    files = []
    for path in written:
        target = data / path.name
        path.replace(target)
        files.append(target)
    shutil.rmtree(staging, ignore_errors=True)
    parent = {**pin, "path": str(core)}
    snapshot.commit(
        SnapshotRelease(
            dataset=pin["release_id"],
            built_at=now_utc_iso(),
            builder_version=_builder_version(),
            genome_build="GRCh38",
            row_count=rows,
            record_count=core_rows,
            parents={"ensembl": parent},
        )
    )
    seconds = time.monotonic() - started
    size = sum(path.stat().st_size for path in files)
    logger.info(
        "Built the rsID index of %s: %d rows, %d bytes, %.0f s", pin["release_id"], rows, size, seconds
    )
    return RsidIndexBuildResult(
        out_dir=out_dir,
        files=tuple(files),
        rows=rows,
        core_rows=core_rows,
        parent=parent,
        seconds=seconds,
        size_bytes=size,
    )


def _build_staged(
    sources: list[Path], staging: Path, *, memory_limit: str, threads: int
) -> tuple[list[Path], int, int]:
    """The two passes into `staging`: `(the payload files in rsID order, rows written, core rows read)`."""
    parts = staging / "parts"
    sorted_dir = staging / "sorted"
    sorted_dir.mkdir(parents=True)
    parts.mkdir(parents=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"SET memory_limit = '{memory_limit}'")
        con.execute(f"SET threads = {int(threads)}")
        con.execute(f"SET temp_directory = '{_quoted(staging / 'spill')}'")
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET enable_progress_bar = false")
        _one_chromosome_each(con, sources)
        core_rows = 0
        for i, source in enumerate(sources):
            (rows_here,) = con.execute(
                f"SELECT sum(row_group_num_rows) FROM (SELECT DISTINCT row_group_id, row_group_num_rows "
                f"FROM parquet_metadata('{_quoted(source)}'))"
            ).fetchone()
            core_rows += int(rows_here or 0)
            logger.info("rsID index, pass 1: %s (%d rows)", source.name, rows_here or 0)
            con.execute(
                f"COPY (SELECT DISTINCT CAST(substr(id, 3) AS UBIGINT) // {INDEX_BUCKET_WIDTH} AS bucket, "
                f"CAST(substr(id, 3) AS UBIGINT) AS rs, chrom, start FROM read_parquet('{_quoted(source)}') "
                f"WHERE regexp_full_match(id, '{RSID_PATTERN}')) TO '{_quoted(parts / f'f{i:03d}')}' "
                "(FORMAT parquet, PARTITION_BY (bucket))"
            )
        buckets = sorted({int(p.name.split("=", 1)[1]) for p in parts.glob("*/bucket=*") if p.is_dir()})
        written: list[Path] = []
        rows = 0
        for bucket in buckets:
            target = sorted_dir / INDEX_FILE_PATTERN.format(bucket=bucket)
            logger.info("rsID index, pass 2: bucket %d", bucket)
            con.execute(
                f"COPY (SELECT rs, chrom, start FROM read_parquet('{_quoted(parts)}/*/bucket={bucket}/*.parquet') "
                f"ORDER BY rs, chrom, start) TO '{_quoted(target)}' "
                f"(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE {INDEX_ROW_GROUP_SIZE})"
            )
            (count,) = con.execute(f"SELECT count(*) FROM read_parquet('{_quoted(target)}')").fetchone()
            rows += int(count)
            written.append(target)
    except duckdb.Error as exc:
        raise RsidIndexError(f"the rsID index could not be built: {exc}") from exc
    finally:
        con.close()
    return written, rows, core_rows

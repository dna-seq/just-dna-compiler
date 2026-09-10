"""The AlphaGenome AVI artifact, re-encoded as an operator-built snapshot (RM191).

**Nothing here fetches, and that is not the usual inject-only rule** — this is the network tier, so
it is allowed to. The AVI artifact is 88.5 GB behind a sign-in whose eligibility clause bars whole
classes of holder (ALPHAGENOME_ATLAS.md § 2.1), so acquisition is the operator's act and this
builder reads the file they already have. `--input` is required for that reason and has no default
URL to fall back on.

**What it writes.** `<out>/data/alphagenome_avi-<contig>.parquet` — one row per (contig, position,
ref, alt) with `raw_score` as `Int32` at a scale of 10⁵ — plus `avi_knots.parquet`, `release.json`
and `LICENSE.txt`.

Four shape decisions, each measured rather than argued (§§ 1.4, 4.4–4.9 of the probe):

* **`Int32`×10⁵, not `Float32`.** Both published columns print at most **5 decimals**, so an integer
  scale is *exactly* lossless while `Float32` silently rounds the fifth — and is **larger**, 3.154
  bytes/row against 2.413. Wherever a source publishes fixed decimals a float is the wrong
  container: its low mantissa bits are noise the source never had, and noise does not compress.
  The builder does not take that on trust — `_scaled_scores` re-derives the scaling and refuses a
  value that does not land on the grid, so losslessness is checked over every row written rather
  than sampled.

  **Read the integer, do not divide it back.** The exactness is about the *decimal*: `raw_score_e5`
  is the printed value shifted five places, and nothing is lost. Recovering a float with
  `raw_score_e5 / 1e5` rounds a second time and lands one ulp off `float(printed)` on **53% of
  rows** — measured, not feared. Compare thresholds in the integer domain (`score >= 0.1` becomes
  `raw_score_e5 >= 10_000`) and the question never arises.
* **`PHRED` is not stored.** Measured over all 8,812,917,339 rows it is an exact within-corpus rank
  (`PHRED ≥ p` keeps `10^(-p/10)` of the corpus, to four significant figures across four decades),
  so it is 24.7 GB of a number that is a function of `raw_score`. The knot table carries the curve
  instead, in 466 KB.
* **The knot table is rebuilt here, not copied.** `docs/probes/alphagenome_knots/avi_knots.parquet`
  is *evidence*; the lane's copy is the *artifact*, and `sum(n)` over its knots must equal the rows
  this build wrote or the two halves describe different data.
* **No threshold.** The whole corpus is **34.2 GB measured** keeping `raw_score` alone — inside any
  stated budget, with the sign intact. 49.30% of rows are negative and a negative AVI is *low
  conservation*, evidence against impact, not down-regulation (§ 4.7): `abs()` would discard what
  half the corpus says. A threshold is a consumer's slice, not this artifact's shape.

**Absence is row-absence.** AVI covers about 95% of the assembly and writes **672,931 genuine
zeros**, so a position with no row is unscored and a row with `raw_score_e5 == 0` is scored zero.
Collapsing the two would be `@unreachable-not-absent` at nine-billion-row scale.
"""

import hashlib
import json
import logging
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.layout import atomic_write_text

from just_dna_enricher.locations import (
    ALPHAGENOME_KNOTS_FILENAME,
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
)

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

#: The published artifact's own name, as the Atlas download page serves it. Named so an operator can
#: check they pointed `--input` at the AVI file rather than at the splicing or SHAP one — those are
#: a **different licence class** and this lane must not read them (§ 1, § 2.5).
AVI_FILENAME = "alphagenome_variant_impact_score_snvs.tsv.gz"

#: The two artifacts this lane must refuse, by name. Both are non-commercial-only and the SHAP one
#: additionally stacks AlphaMissense, Cactus and phastCons terms — so reading either into a lane
#: whose `SourceRow` describes AVI would publish terms that do not govern the bytes.
FOREIGN_ARTIFACTS = (
    "combined_alphagenome_splicing_snvs",
    "indels_with_am_snvs",
)

#: The header the artifact carries, checked rather than assumed — a source's columns are the one
#: thing a builder may not infer (`@probe-the-real-file`).
AVI_HEADER = ("#CHROM", "POS", "REF", "ALT", "raw_score", "PHRED")

#: `raw_score` and `PHRED` both print at most five decimals, measured over the corpus, so 10⁵ is an
#: exact integer scale for either. It is not a rounding budget: `_scaled_scores` refuses a value
#: that does not land on this grid rather than rounding it quietly.
RAW_SCORE_SCALE = 100_000

#: How much decompressed text one worker holds at a time. Sized so twelve workers stay well inside
#: this machine's memory while the pipe never starves: the cost of a smaller number is more polars
#: calls, and the cost of a larger one is twelve times whatever it is.
CHUNK_BYTES = 64 * 1024 * 1024

#: **How many arrow chunks a finished contig may be written from, and it is a compression setting
#: wearing a memory setting's clothes.** Parquet writes at least one row group per chunk, and a
#: sorted `pos` column only delta-encodes well *within* a row group — so fragmenting a contig into
#: thousands of chunks quietly destroys the encoding that makes this artifact small.
#:
#: Measured on chr22's 117,479,331 rows at `zstd` level 9, varying nothing but the chunk count:
#:
#: | chunks | B/row | genome-wide |
#: | ---: | ---: | ---: |
#: | 1 (rechunked) | 3.871 | 34.1 GB |
#: | 4 – 64 | 3.871 – 3.874 | 34.1 GB |
#: | 128 | 3.904 | 34.4 GB |
#: | **1,432** (what `sink_parquet` produced) | **4.892** | **43.1 GB** |
#:
#: `pos` alone accounts for nearly all of it: 1.249 B/row at one chunk against 2.067 at 1,432. The
#: flat region up to 64 is why this is a cap rather than a rechunk — a full rechunk of chr1 is a
#: 14 GB copy for no measurable gain, while capping the count costs one small copy per group.
#:
#: Setting `row_group_size` explicitly does **not** substitute for this and makes it worse (4.7–5.1
#: B/row at every value tried): the default sizing is what adapts to the data.
MAX_CONTIG_CHUNKS = 64

#: **The quantity that actually governs is rows per chunk, not chunks**, and the two caps are here
#: together because only the second one is data-independent. Measured twice on different slices: the
#: cliff sits between 128 and 1,432 chunks on chr22's 117 M rows and between 512 and 1,432 on a 30 M
#: row slice — around twenty-odd thousand rows per chunk in both. So a cap of "64 chunks" is only
#: safe for contigs of a certain size, while a floor of "at least this many rows in a chunk" holds
#: for any input. The smallest contig here (chrY, 79 M rows) lands at 1.2 M rows per chunk under the
#: chunk cap alone, so both are satisfied today; the floor is what keeps that true for a smaller
#: contig, a filtered build, or a test fixture.
MIN_ROWS_PER_CHUNK = 250_000

#: **Wide by position: one row per locus, three ALT columns, and no stored `alt`** (RM197).
#:
#: `pos` is the **1-based VCF position, passed through unchanged** (`@start-1based`). `UInt32` holds
#: chr1's 248,956,422 with three orders of magnitude to spare.
#:
#: `alt0`/`alt1`/`alt2` are the scores for the three ALTs **in ascending base order**, and which base
#: each column means is a function of `ref` alone — see `alts_for_ref`. That is what lets the column
#: disappear: there are exactly three bases other than REF, so naming them costs nothing once `ref`
#: is known.
#:
#: **It rests on a property that was proved, not assumed.** Across all 24 contigs and all
#: 8,812,917,339 rows: every position carries exactly three rows (`rows == 3 × distinct positions`),
#: `pos` is sorted, `alt` is strictly ascending within a position, and no `alt` equals `ref`. Three
#: distinct non-ref bases must be all three of them. `test_every_position_carries_the_three_non_ref_bases`
#: re-proves it on the fixture, and the builder refuses a position that breaks it rather than
#: writing a row whose columns would mean something else.
#:
#: Measured: **3.371 B/row against 3.882 long**, so 29.7 GB rather than 34.2 — the saving is simply
#: not storing `pos` three times, and `pos` costs 1.249 B/row even perfectly delta-encoded.
PARQUET_SCHEMA: dict[str, str] = {
    "chrom": "Categorical",
    "pos": "UInt32",
    "ref": "Categorical",
    "alt0": "Int32",
    "alt1": "Int32",
    "alt2": "Int32",
}

#: The four bases, in the order `alt0`/`alt1`/`alt2` are assigned from.
BASES = ("A", "C", "G", "T")


def alts_for_ref(ref: str) -> tuple[str, str, str]:
    """The three ALT bases a locus with this REF carries, in the order the columns hold them.

    `{A,C,G,T} − ref`, ascending. This is the whole reason the wide layout costs nothing to read:
    a caller with `(pos, ref, alt)` finds its column as `alts_for_ref(ref).index(alt)`, and a reader
    reconstructing long rows walks the tuple. No lookup table travels with the artifact.
    """
    rest = tuple(b for b in BASES if b != ref.upper())
    if len(rest) != 3:
        raise AlphaGenomeBuildError(
            f"ref {ref!r} is not one of {BASES}, so it has no three-ALT complement. AVI is SNV-only "
            "and every REF it publishes is a single standard base."
        )
    return rest

#: The knot table's own columns. `phred_lo`/`phred_hi` are the **interval** a printed `raw_score`
#: spans, not a point: 2,001 of chr22's 40,204 distinct values carry up to 68 distinct `PHRED`s
#: because the file prints `raw_score` to four significant digits and `PHRED` to six. Publishing a
#: midpoint would turn a measurable ambiguity into an invisible one, and the interval is what makes
#: threshold safety *decidable* — a threshold is unsafe iff it lands inside some knot's span.
#: `n` is `UInt64`: the corpus has 8,812,917,339 rows, which is past `UInt32` (4,294,967,295), and
#: polars' `len()` defaults to the narrower type. A single contig fits; the sum across contigs does
#: not, and it wraps rather than raising.
KNOT_COLUMNS = ("raw_score_e5", "n", "phred_lo", "phred_hi")

#: Re-exported from `locations`, which owns it: the publisher and the provisioner have to agree with
#: this builder about the name, and a constant defined here would be a name only the writer knows.
KNOT_FILENAME = ALPHAGENOME_KNOTS_FILENAME

#: Where a contig's own knot aggregate is parked until the merge succeeds. **A contig's knots cannot
#: be recovered from the finished artifact** — they are built from `PHRED`, which the artifact
#: deliberately does not store — so a failure between the last contig and the merge would otherwise
#: mean re-reading 88.5 GB. That is not hypothetical: the first genome-wide build reached the merge
#: after 65 minutes and died there on a `UInt32` overflow. Removed once the merged table is written,
#: so a successful snapshot carries no trace of it.
KNOT_PARTS_DIRNAME = ".knots"


class AlphaGenomeBuildError(RuntimeError):
    """The build could not produce a snapshot. Never raised for a legitimately empty contig."""


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


@dataclass(frozen=True)
class ContigResult:
    """One contig's parquet, and what went into it."""

    contig: str
    rows: int
    path: Path


@dataclass(frozen=True)
class AviBuildResult:
    """What the build produced, with every number it computed rather than only the ones it used.

    A count computed and discarded is a count every consumer recomputes
    (`@dont-discard-computed`), and here the recomputation costs a pass over 88.5 GB.
    """

    contigs: tuple[ContigResult, ...]
    rows: int
    knots: int
    negative_rows: int
    zero_rows: int
    source_path: Path
    source_sha256: str | None
    source_mtime: str | None
    dataset: str | None

    @property
    def contig_names(self) -> tuple[str, ...]:
        return tuple(c.contig for c in self.contigs)


def _require_polars() -> None:
    """The builder is `[dev]`-only, and says so rather than dying on an AttributeError.

    The resolver path stays polars-free (CONSTITUTION Goal 2), so the import is guarded at module
    level the way `clinvar_build` and `constraint_build` guard theirs; this is the message an
    operator gets when the extra is absent.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise AlphaGenomeBuildError(
            "polars is required to build the AlphaGenome snapshot: "
            "`pip install 'just-dna-enricher[dev]'`"
        )


def check_input_is_the_avi_artifact(source: Path) -> None:
    """Refuse a file from the other two bulk artifacts, by name, before anything is read.

    Not a courtesy check. The three artifacts are **not one licence**: only AVI is in the Permissive
    class, and the merged splicing and SHAP files are non-commercial-only. A lane whose `SourceRow`
    describes AVI, silently filled from the splicing file, would publish terms that do not govern
    its bytes — which is the failure `@a-hosts-terms-are-not-its-contents-terms` names from the
    other direction. The name is what an operator actually has; the schema check below catches the
    rest.
    """
    stem = source.name
    for foreign in FOREIGN_ARTIFACTS:
        if foreign in stem:
            raise AlphaGenomeBuildError(
                f"{source.name} is not the AVI artifact. This lane reads "
                f"{AVI_FILENAME} and nothing else: the merged-splicing and feature-importance "
                "artifacts are a different licence class (non-commercial only, and the latter "
                "stacks AlphaMissense/Cactus/phastCons terms), so a snapshot mixing them would "
                "carry a SourceRow that does not describe its own bytes."
            )


def list_contigs(source: Path) -> tuple[str, ...]:
    """The contigs the tabix index knows, in the file's own order.

    Read from the index rather than assembled from a chromosome list: what the artifact covers is a
    property of the artifact, and a hand-kept roster is how a build silently skips a contig.
    """
    try:
        out = subprocess.run(
            ["tabix", "-l", str(source)], capture_output=True, text=True, check=True
        ).stdout
    except FileNotFoundError as exc:
        raise AlphaGenomeBuildError(
            "tabix is not on PATH. The AVI artifact is a bgzipped TSV with a .tbi index, and the "
            "build reads it one contig at a time through `tabix`; install htslib/samtools."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AlphaGenomeBuildError(
            f"`tabix -l {source}` failed ({exc.returncode}): {(exc.stderr or '').strip()}. "
            f"Is {source.name}.tbi beside it?"
        ) from exc
    contigs = tuple(line for line in out.splitlines() if line.strip())
    if not contigs:
        raise AlphaGenomeBuildError(f"{source} has an index but no contigs in it")
    return contigs


def _stream_lines(source: Path, contig: str, *, chunk_bytes: int = CHUNK_BYTES) -> Iterator[bytes]:
    """Yield whole-line blocks of one contig's decompressed TSV.

    Blocks rather than lines because the parser downstream is vectorised: handing polars a megabyte
    at a time is what keeps Python out of the hot path for nine billion rows. Each block ends on a
    newline, with the tail carried into the next — a chunk boundary that split a row would produce a
    ragged CSV, and `@ragged-csv-row` is a diagnosis, not something to create.
    """
    proc = subprocess.Popen(
        ["tabix", str(source), contig], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert proc.stdout is not None
    remainder = b""
    try:
        while True:
            block = proc.stdout.read(chunk_bytes)
            if not block:
                break
            block = remainder + block
            cut = block.rfind(b"\n")
            if cut == -1:  # pragma: no cover - a single line longer than the chunk
                remainder = block
                continue
            remainder, out = block[cut + 1 :], block[: cut + 1]
            yield out
        if remainder.strip():  # a final line with no trailing newline
            yield remainder + b"\n"
    finally:
        proc.stdout.close()
        stderr = proc.stderr.read() if proc.stderr else b""
        if proc.stderr:
            proc.stderr.close()
        code = proc.wait()
        if code != 0:
            raise AlphaGenomeBuildError(
                f"`tabix {source} {contig}` failed ({code}): {stderr.decode(errors='replace').strip()}"
            )


def _scaled_scores(frame, column: str, out: str):
    """Scale a printed decimal column onto the `Int32` grid, refusing anything that does not land.

    This is the losslessness claim, checked rather than asserted. A value printed with more than
    five decimals would be rounded, and a rounded score is a *different* score — so the build stops
    and names the row instead of writing a number the source never published. Running it over every
    chunk makes the guarantee a property of the artifact rather than of the 900,003-row slice it was
    measured on.
    """
    scaled = frame.select(
        (pl.col(column) * RAW_SCORE_SCALE).alias("_exact"),
    ).with_columns(pl.col("_exact").round().alias("_grid"))
    off_grid = scaled.filter((pl.col("_exact") - pl.col("_grid")).abs() > 1e-6)
    if off_grid.height:
        example = off_grid.item(0, "_exact") / RAW_SCORE_SCALE
        raise AlphaGenomeBuildError(
            f"{column} carries more precision than the Int32 scale of {RAW_SCORE_SCALE} holds "
            f"({off_grid.height} value(s), e.g. {example!r}). The artifact printed at most five "
            "decimals when this builder was written; if upstream widened the column, the scale has "
            "to widen with it rather than round."
        )
    return frame.with_columns(
        (pl.col(column) * RAW_SCORE_SCALE).round().cast(pl.Int32).alias(out)
    )


def _read_block(block: bytes):
    """Parse one block of AVI TSV. `PHRED` is read and used, then dropped — it is not stored."""
    return pl.read_csv(
        block,
        separator="\t",
        has_header=False,
        new_columns=list(AVI_HEADER),
        schema_overrides={
            "#CHROM": pl.String,
            "POS": pl.UInt32,
            "REF": pl.String,
            "ALT": pl.String,
            "raw_score": pl.Float64,
            "PHRED": pl.Float64,
        },
    )


def _build_contig(
    source: Path, contig: str, out_dir: Path, *, chunk_bytes: int = CHUNK_BYTES
) -> tuple[ContigResult, object]:
    """One contig → one parquet, plus its knot aggregate.

    Chunk parquets are written into a scratch directory and then streamed into the contig's single
    file with `sink_parquet`, so peak memory is one chunk rather than one chromosome — chr1 alone is
    ~720 M rows, and twelve of those resident at once is not a shape this machine has.
    """
    scratch = out_dir / f".{contig}.parts"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    rows = 0
    knot_parts = []
    part = 0
    #: The tail of the previous chunk, from the first row of its **last position** onward. A chunk
    #: boundary falls between two lines, and a locus is three lines, so the last position in a chunk
    #: is usually incomplete — carrying it forward is what makes `_widen`'s three-ALT requirement a
    #: statement about the *source* rather than about where the reader happened to stop.
    carried = None
    for block in _stream_lines(source, contig, chunk_bytes=chunk_bytes):
        frame = _read_block(block)
        if not frame.height:  # pragma: no cover - tabix does not emit empty blocks
            continue
        frame = _scaled_scores(frame, "raw_score", "raw_score_e5")
        if carried is not None:
            frame = pl.concat([carried, frame])
        last_pos = frame.item(-1, "POS")
        carried = frame.filter(pl.col("POS") == last_pos)
        frame = frame.filter(pl.col("POS") != last_pos)
        if not frame.height:
            # A single locus spanning a whole chunk cannot happen at any sane chunk size, but a
            # caller may pass a tiny one — a test does. Keep accumulating rather than emitting a
            # partial locus.
            continue
        knot_parts.append(
            frame.group_by("raw_score_e5").agg(
                # **`UInt64`, and the cast is load-bearing.** `pl.len()` is `UInt32`, which holds any
                # single contig (chr2, the largest, is 721 M rows) and overflows the moment the
                # per-contig tables are summed: the corpus is 8,812,917,339 rows and
                # 8,812,917,339 - 2*2**32 = 222,982,747, which is exactly what the reconciliation
                # guard reported before this cast existed. A count that silently wraps is worse than
                # one that is missing, and the only reason it was caught at all is that `sum(n)` is
                # checked against the rows actually written.
                pl.len().cast(pl.UInt64).alias("n"),
                pl.col("PHRED").min().alias("phred_lo"),
                pl.col("PHRED").max().alias("phred_hi"),
            )
        )
        _widen(frame, contig).write_parquet(
            scratch / f"{part:05d}.parquet", compression="zstd", compression_level=9
        )
        rows += frame.height
        part += 1

    # The final locus never sees a following chunk, so it is emitted here rather than dropped. This
    # is the other half of the carry: without it every contig would silently lose its last position.
    if carried is not None and carried.height:
        knot_parts.append(
            carried.group_by("raw_score_e5").agg(
                pl.len().cast(pl.UInt64).alias("n"),
                pl.col("PHRED").min().alias("phred_lo"),
                pl.col("PHRED").max().alias("phred_hi"),
            )
        )
        _widen(carried, contig).write_parquet(
            scratch / f"{part:05d}.parquet", compression="zstd", compression_level=9
        )
        rows += carried.height
        part += 1

    path = out_dir / f"alphagenome_avi-{contig}.parquet"
    if part:
        _assemble_contig(sorted(scratch.glob("*.parquet")), path)
    else:  # pragma: no cover - a contig in the index with no rows behind it
        pl.DataFrame(schema={k: getattr(pl, v) for k, v in PARQUET_SCHEMA.items()}).write_parquet(
            path, compression="zstd", compression_level=9
        )
    shutil.rmtree(scratch)

    knots = (
        pl.concat(knot_parts)
        .group_by("raw_score_e5")
        .agg(
            pl.col("n").sum().alias("n"),
            pl.col("phred_lo").min().alias("phred_lo"),
            pl.col("phred_hi").max().alias("phred_hi"),
        )
        if knot_parts
        else pl.DataFrame(
            schema={"raw_score_e5": pl.Int32, "n": pl.UInt64, "phred_lo": pl.Float64, "phred_hi": pl.Float64}
        )
    )
    parts_dir = out_dir.parent / KNOT_PARTS_DIRNAME
    parts_dir.mkdir(parents=True, exist_ok=True)
    knots.write_parquet(parts_dir / f"{contig}.parquet")
    logger.info("alphagenome %s: %d rows, %d knots", contig, rows, knots.height)
    return ContigResult(contig=contig, rows=rows, path=path), knots



#: Only one contig is assembled at a time. The parse stage is happily twelve-wide — each worker holds
#: one chunk of text — but assembly holds a **whole contig** in memory to write it as few chunks, and
#: chr1 is ~720 M rows. Twelve of those at once is not a shape any machine here has, and the parse
#: threads keep working while one of them assembles.
_ASSEMBLY = threading.Semaphore(1)




def to_long(wide):
    """One row per `(chrom, pos, ref, alt)` from the artifact's wide rows (RM197).

    **The inverse of the layout, and it needs nothing but `ref`.** The snapshot stores one row per
    position with three score columns, and which base each column means is `{A,C,G,T} − ref`
    ascending — so long form is recoverable with no stored `alt` and no lookup table travelling
    beside the data. That is what made the wide layout adoptable rather than a schema break: a
    consumer who wants `(pos, ref, alt, score)` rows calls this and gets them.

    It lives here rather than in the reader because it is a fact about the **artifact**, and three
    callers now need it to agree — `alphagenome_check`'s join, the tests, and anyone converting a
    pulled snapshot back to long after download.

    Apply it to a **filtered** frame. Over the whole corpus it is 2.9 billion loci becoming 8.8
    billion rows, which is the shape the artifact exists to avoid storing.
    """
    _require_polars()
    parts = [
        wide.filter(pl.col("ref").cast(pl.String) == base).select(
            "chrom", "pos",
            pl.col("ref").cast(pl.String),
            pl.lit(alt).alias("alt"),
            pl.col(f"alt{i}").alias("raw_score_e5"),
        )
        for base in BASES
        for i, alt in enumerate(alts_for_ref(base))
    ]
    present = [p for p in parts if p.height]
    return pl.concat(present).sort(["pos", "alt"]) if present else wide.head(0)


def _widen(frame, contig: str):
    """Long rows → one row per position with three ALT-score columns (RM197).

    **The caller must hand this whole loci.** `_stream_lines` yields whole *lines*, which is not the
    same thing: a position's three rows sit next to each other in the source, so a chunk boundary
    lands between two of them roughly once per chunk. This docstring claimed the opposite, and the
    genome-wide build refused at `chr1:1196920` — a locus that has all three ALTs in the file and two
    in the chunk. `_build_contig` now carries the trailing partial locus into the next chunk, which
    is where the fix belongs: `_widen` cannot tell a truncated locus from a malformed one, and
    should not try.

    The refusal is the interesting part. The three-ALT property was *proved* over the whole corpus
    (see `PARQUET_SCHEMA`), so a violation here means the source changed shape — and the honest
    response is to stop, because every column in this layout means something only while it holds.
    Writing a row with `alt2 = null` would silently redefine what `alt1` refers to for that locus.
    """
    wide = (
        frame.sort(["POS", "ALT"])
        .group_by("POS", maintain_order=True)
        .agg(
            pl.col("REF").first().alias("ref"),
            pl.col("ALT").alias("alts"),
            pl.col("raw_score_e5").alias("scores"),
        )
    )
    ragged = wide.filter(pl.col("scores").list.len() != 3)
    if ragged.height:
        row = ragged.row(0, named=True)
        raise AlphaGenomeBuildError(
            f"{contig}:{row['POS']} carries {len(row['scores'])} ALT(s), not 3 "
            f"({', '.join(row['alts'])}). The wide layout assigns alt0/alt1/alt2 by position in "
            "`{A,C,G,T} - ref`, which is only meaningful when all three are present — this held "
            "over all 8,812,917,339 rows when it was measured, so a violation means the artifact "
            "changed shape and the layout has to be revisited rather than padded."
        )
    mismatched = wide.filter(
        pl.col("alts").list.join("") != pl.col("ref").replace_strict(_ALT_SETS, default=None)
    )
    if mismatched.height:
        row = mismatched.row(0, named=True)
        raise AlphaGenomeBuildError(
            f"{contig}:{row['POS']} has ref {row['ref']} with ALTs {', '.join(row['alts'])}, which "
            f"is not {{A,C,G,T}} minus ref. `alts_for_ref` is what a reader uses to name these "
            "columns, so a locus that disagrees with it would be read as three different variants."
        )
    return wide.select(
        pl.lit(contig).cast(pl.Categorical).alias("chrom"),
        pl.col("POS").alias("pos"),
        pl.col("ref").cast(pl.Categorical),
        *(pl.col("scores").list.get(i).alias(f"alt{i}") for i in range(3)),
    )


#: `ref` → its three ALTs concatenated, for the vectorised check in `_widen`. Derived from
#: `alts_for_ref` rather than written out, so the two cannot disagree.
_ALT_SETS = {base: "".join(alts_for_ref(base)) for base in BASES}


def _assemble_contig(parts: list[Path], path: Path) -> None:
    """Write one contig's parquet from its chunk files, in at most `MAX_CONTIG_CHUNKS` chunks.

    **This replaced a `scan_parquet(...).sink_parquet(...)` and the swap is worth 8.9 GB.** Streaming
    the concat is the memory-cheap way to write the file and it fragments the result into one arrow
    chunk per morsel — 1,432 of them for chr22 — which parquet turns into 1,432 row groups, inside
    each of which a sorted `pos` has almost no run to delta-encode. The artifact came out 4.892 B/row
    instead of 3.871.

    The repair is not a rechunk. Chunk count only matters until about 64 (see `MAX_CONTIG_CHUNKS`),
    so the files are read in groups and each **group** is rechunked — one bounded copy at a time —
    and the groups are concatenated without a further one. A full rechunk of chr1 would be a 14 GB
    copy to buy nothing.
    """
    rows = sum(pl.scan_parquet(f).select(pl.len()).collect().item() for f in parts)
    # Two caps, and the second is the one that generalises — see `MIN_ROWS_PER_CHUNK`. A short
    # contig, a `--contig` build or a test fixture can all put fewer rows behind 64 groups than the
    # encoding needs, and then the chunk cap alone would be satisfied while the bytes were not.
    groups = max(1, min(len(parts), MAX_CONTIG_CHUNKS, max(1, rows // MIN_ROWS_PER_CHUNK)))
    step = (len(parts) + groups - 1) // groups
    with _ASSEMBLY:
        # `.rechunk()` explicitly per group rather than `pl.concat(..., rechunk=True)`, which did
        # not collapse anything here — a chunk file reads back as one arrow chunk per row group, so
        # the concat kept all 1,432 of them and the cap below caught it. The copy is bounded by one
        # group, which is what makes this affordable on chr1.
        frame = pl.concat(
            [
                pl.concat([pl.read_parquet(f) for f in parts[i : i + step]]).rechunk()
                for i in range(0, len(parts), step)
            ],
            rechunk=False,
        )
        if frame.n_chunks() > MAX_CONTIG_CHUNKS:  # pragma: no cover - the grouping bounds it
            raise AlphaGenomeBuildError(
                f"{path.name}: assembled into {frame.n_chunks()} chunks, over the cap of "
                f"{MAX_CONTIG_CHUNKS}. Writing it would cost ~26% more bytes than it should."
            )
        frame.write_parquet(path, compression="zstd", compression_level=9)


def _sha256_file(path: Path) -> str | None:
    """The artifact's own hash, or `None` when it cannot be read.

    88.5 GB takes a few minutes, which is why it is optional: an operator rebuilding a lane they
    already trust should not have to re-hash it, and a `None` here is *unknown*, never *unpinned*.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 22), b""):
                digest.update(block)
    except OSError:  # pragma: no cover
        return None
    return "sha256:" + digest.hexdigest()


def use_restrictions_text(terms_file: Path) -> str:
    """The Output Terms' **"Use restrictions" section**, verbatim, for `LICENSE.txt`.

    Restriction 3b requires it to travel *inside* a derivative rather than as a link: anyone who
    attaches their own terms — which a module's `sources.csv` is — must carry this section "as an
    enforceable provision". So the bytes go beside the data, the way ClinPGx's bundled `LICENSE.txt`
    already does (`SNAPSHOT_LICENSE_FILENAME` exists for exactly this).

    Sliced from the pinned extraction rather than paraphrased, and bounded at the next heading so
    the disclaimer sections do not ride along under a name that says "use restrictions".
    """
    text = terms_file.read_text()
    start = text.index("Use restrictions")
    end = text.index("Disclaimers and limitations of liability", start)
    section = text[start:end].strip()
    if "commercial organization" not in section:  # pragma: no cover - upstream restructured
        raise AlphaGenomeBuildError(
            f"{terms_file.name} no longer carries the Use restrictions clauses where this builder "
            "slices them; re-pin the document and re-read § 2.7 before shipping a LICENSE.txt."
        )
    return section + "\n"


def _write_release_json(
    out_dir: Path, result: AviBuildResult, *, artifact_stamp: str | None
) -> Path:
    """The snapshot's provenance — and one field of it is legally load-bearing.

    The Output Terms pin the applicable version to **the date the relevant Output was generated**
    (§ 2.7c), so `artifact_mtime` is not provenance hygiene: it fixes which terms govern these bytes,
    permanently. Recorded beside `license_sha256` for the same reason `licensing.py` records both.
    """
    release = {
        "dataset": result.dataset,
        "source_name": result.source_path.name,
        "source_sha256": result.source_sha256,
        "artifact_mtime": artifact_stamp,
        "contigs": list(result.contig_names),
        "rows": result.rows,
        "knots": result.knots,
        "negative_rows": result.negative_rows,
        "zero_rows": result.zero_rows,
        "raw_score_scale": RAW_SCORE_SCALE,
        "phred_stored": False,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    atomic_write_text(path, json.dumps(release, indent=2, sort_keys=True) + "\n")
    return path


def build_snapshot(
    source: Path,
    out_dir: Path,
    *,
    contigs: Sequence[str] | None = None,
    workers: int = 12,
    chunk_bytes: int = CHUNK_BYTES,
    hash_source: bool = True,
    terms_file: Path | None = None,
) -> AviBuildResult:
    """Re-encode the AVI artifact into `out_dir`, and rebuild the knot table from the same pass.

    `contigs` restricts the build — a test builds one, an operator builds all of them. `workers` is
    the tabix fan-out: the measured passes ran 24 contigs in 41–46 minutes at twelve, and a
    single-threaded pass over 8.8 billion rows takes roughly four times as long.

    Threads rather than processes because every worker spends its time in a `tabix` subprocess and
    in polars, both of which are outside the GIL; a process pool would buy nothing and cost the
    chunk-sized copies.
    """
    source = Path(source)
    if not source.is_file():
        raise AlphaGenomeBuildError(f"{source} is not a file. This lane never downloads (§ 2.1).")
    check_input_is_the_avi_artifact(source)

    _require_polars()
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)

    wanted = tuple(contigs) if contigs is not None else list_contigs(source)
    if contigs is not None:
        known = set(list_contigs(source))
        unknown = [c for c in wanted if c not in known]
        if unknown:
            raise AlphaGenomeBuildError(
                f"{', '.join(unknown)} not in {source.name}'s index. It knows: {', '.join(sorted(known))}"
            )

    results: list[ContigResult] = []
    knot_frames = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for contig_result, knots in pool.map(
            lambda c: _build_contig(source, c, data_dir, chunk_bytes=chunk_bytes), wanted
        ):
            results.append(contig_result)
            knot_frames.append(knots)

    knot_table = (
        pl.concat(knot_frames)
        .group_by("raw_score_e5")
        .agg(
            pl.col("n").sum().alias("n"),
            pl.col("phred_lo").min().alias("phred_lo"),
            pl.col("phred_hi").max().alias("phred_hi"),
        )
        .sort("raw_score_e5")
        .select(list(KNOT_COLUMNS))
    )
    knot_table.write_parquet(
        out_dir / KNOT_FILENAME, compression="zstd", compression_level=9
    )
    # The per-contig aggregates have served their purpose. Removed only after the merged table is on
    # disk, so a crash anywhere before this point leaves the expensive half of the build recoverable.
    shutil.rmtree(out_dir / KNOT_PARTS_DIRNAME, ignore_errors=True)

    rows = sum(c.rows for c in results)
    reconciled = int(knot_table["n"].sum()) if knot_table.height else 0
    if reconciled != rows:
        raise AlphaGenomeBuildError(
            f"the knot table describes {reconciled} rows but the build wrote {rows}. The curve and "
            "the data are two halves of one artifact; a mismatch means they came from different "
            "passes and neither can be trusted for a threshold."
        )

    negative = int(knot_table.filter(pl.col("raw_score_e5") < 0)["n"].sum()) if knot_table.height else 0
    zeros = int(knot_table.filter(pl.col("raw_score_e5") == 0)["n"].sum()) if knot_table.height else 0

    stamp = _artifact_stamp(source)
    result = AviBuildResult(
        contigs=tuple(results),
        rows=rows,
        knots=knot_table.height,
        negative_rows=negative,
        zero_rows=zeros,
        source_path=source,
        source_sha256=_sha256_file(source) if hash_source else None,
        source_mtime=stamp,
        dataset=stamp[:10] if stamp else None,
    )
    _write_release_json(out_dir, result, artifact_stamp=stamp)

    terms = terms_file or _default_terms_file()
    if terms is not None and terms.is_file():
        atomic_write_text(out_dir / SNAPSHOT_LICENSE_FILENAME, use_restrictions_text(terms))
    else:
        logger.warning(
            "no %s written: the Output Terms extraction was not found at %s. Restriction 3b "
            "requires the Use restrictions section to travel inside a derivative, so a snapshot "
            "without it cannot be passed on.",
            SNAPSHOT_LICENSE_FILENAME,
            terms,
        )
    return result


def _artifact_stamp(source: Path) -> str | None:
    """When the Output was generated, as far as the bytes on disk can say.

    The file's mtime, which for a downloaded artifact is the server's own timestamp preserved by the
    transfer. `None` when it cannot be read — unknown, and § 2.7c then has no date to resolve
    against, which is a finding rather than a default.
    """
    try:
        return (
            datetime.fromtimestamp(source.stat().st_mtime, UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    except OSError:  # pragma: no cover
        return None


def _default_terms_file() -> Path | None:
    """The pinned Output Terms extraction in the checkout, or `None` outside one."""
    candidate = Path(__file__).resolve().parents[3] / "docs" / "vendor" / "alphagenome_output_terms.txt"
    return candidate if candidate.is_file() else None


#: A contig name as the artifact spells it, for the CLI's `--contig` validation. Deliberately
#: permissive about the suffix — the index is the authority on membership and `list_contigs` asks it.
CONTIG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

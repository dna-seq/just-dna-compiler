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
* **No threshold.** The whole corpus is 34.4 GB keeping `raw_score` alone — inside any stated
  budget, with the sign intact. 49.30% of rows are negative and a negative AVI is *low
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
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.layout import atomic_write_text

from just_dna_enricher.locations import (
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

#: `pos` is the **1-based VCF position, passed through unchanged** (`@start-1based`). `UInt32` holds
#: chr1's 248,956,422 with three orders of magnitude to spare.
PARQUET_SCHEMA: dict[str, str] = {
    "chrom": "Categorical",
    "pos": "UInt32",
    "ref": "Categorical",
    "alt": "Categorical",
    "raw_score_e5": "Int32",
}

#: The knot table's own columns. `phred_lo`/`phred_hi` are the **interval** a printed `raw_score`
#: spans, not a point: 2,001 of chr22's 40,204 distinct values carry up to 68 distinct `PHRED`s
#: because the file prints `raw_score` to four significant digits and `PHRED` to six. Publishing a
#: midpoint would turn a measurable ambiguity into an invisible one, and the interval is what makes
#: threshold safety *decidable* — a threshold is unsafe iff it lands inside some knot's span.
KNOT_COLUMNS = ("raw_score_e5", "n", "phred_lo", "phred_hi")

KNOT_FILENAME = "avi_knots.parquet"


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
    for block in _stream_lines(source, contig, chunk_bytes=chunk_bytes):
        frame = _read_block(block)
        if not frame.height:  # pragma: no cover - tabix does not emit empty blocks
            continue
        frame = _scaled_scores(frame, "raw_score", "raw_score_e5")
        knot_parts.append(
            frame.group_by("raw_score_e5").agg(
                pl.len().alias("n"),
                pl.col("PHRED").min().alias("phred_lo"),
                pl.col("PHRED").max().alias("phred_hi"),
            )
        )
        frame.select(
            pl.col("#CHROM").cast(pl.Categorical).alias("chrom"),
            pl.col("POS").alias("pos"),
            pl.col("REF").cast(pl.Categorical).alias("ref"),
            pl.col("ALT").cast(pl.Categorical).alias("alt"),
            pl.col("raw_score_e5"),
        ).write_parquet(scratch / f"{part:05d}.parquet", compression="zstd", compression_level=9)
        rows += frame.height
        part += 1

    path = out_dir / f"alphagenome_avi-{contig}.parquet"
    if part:
        pl.scan_parquet(scratch / "*.parquet").sink_parquet(
            path, compression="zstd", compression_level=9
        )
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
            schema={"raw_score_e5": pl.Int32, "n": pl.UInt32, "phred_lo": pl.Float64, "phred_hi": pl.Float64}
        )
    )
    logger.info("alphagenome %s: %d rows, %d knots", contig, rows, knots.height)
    return ContigResult(contig=contig, rows=rows, path=path), knots


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

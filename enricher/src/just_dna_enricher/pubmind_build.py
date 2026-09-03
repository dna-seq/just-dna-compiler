"""Build the PubMind snapshot (`[dev]`) — derived, operator-built, and never published (RM134 § A).

PubMind (Wang & Wang, *Nat Commun*, doi:10.1038/s41467-026-76834-4) extracts variant–disease
pathogenicity assertions from the literature with an LLM. It is a **source**, of the same kind as
ClinVar: an authoritative *annotation* source. Nothing it produces may enter `resolution.csv` — its
coordinates are PyEnsembl back-mappings of extracted text, and `resolution.csv`'s `authority` column
is a different word for a different thing (`@source-vs-authority`).

**There is exactly one per-variant channel and it is the ANNOVAR-redistributed bulk table.** The web
API has two endpoints, neither takes a variant, and both state that per-record detail is withheld. So
`hg38_pubmind_db.txt.gz` is the input, and its columns are VCF-style despite the ANNOVAR packaging:
there is not a single `-` allele in the 2026-08-24 file, a one-base deletion appears as
`1 1014264 1014265 CC C` with the anchor base retained, and `Start` is the 1-based POS
(`@start-1based`). A join therefore needs no coordinate translation. Whether the indels are
left-normalized is **not** established, which is why they are stamped rather than silently mixed in.

**Two thirds of the file is not a genotypable position, and every dropped row is counted.** When
PubMind recovers only a protein change from the text it back-maps through the transcript and writes
out every codon that could encode it. A codon block differing at exactly one base is a single
substitution wearing three letters, so it is decomposed onto that base and stamped `derivation=codon`;
a block needing two or three simultaneous substitutions asserts a change to the protein, not to a
position, and is dropped. Silent truncation reads as full coverage, so the drop counters and the kept
count sum to the input row count and all of them land in `release.json` (`@dont-discard-computed`).

**A contested coordinate keeps every PVID as its own row, and that is the finding.** Consolidation
into a PVID is keyed on the *text* the model extracted — gene symbol plus cDNA or protein change —
never on a coordinate, so one physical variant fragments into many PVIDs whose verdicts disagree.
Collapsing them would mean choosing a winner by an ordering nobody defined, which is `mode()` over an
unsorted group and is what the deterministic-ordering rule bans outright. `release.json` records how
many keys are contested and how far the multiplicity goes.

**`pubmind publish` refuses, on the PharmVar precedent** (`@gated-source-caches`). The ANNOVAR-shipped
table publishes no data terms of its own: the software licence covers the software, the paper is
CC BY-NC-ND, and only CHOP can say what the bytes are under. Unknown is not permissive
(`@no-named-licence`), and a bulk file arriving under terms we cannot establish is not a file we may
pass on. The command exists and refuses with the reason, because a missing command reads as an
oversight somebody will helpfully add.

Builder-only: `polars` is a guarded `[dev]` import, exactly as in the sibling builders.
"""

import csv
import gzip
import hashlib
import json
import logging
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.clin_sig import normalize_clin_sig
from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME
from just_dna_enricher.net import stream_to_file

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: The open substitute the PubMind README offers for the licensed full database, redistributed by
#: ANNOVAR. It is the only channel that answers "what does PubMind say about this coordinate".
DEFAULT_PUBMIND_URL = (
    "https://www.openbioinformatics.org/annovar/download/hg38_pubmind_db.txt.gz"
)

#: Recorded rather than implied: the file is `hg38_`, and a reader must be able to see the assembly
#: without inferring it from a filename.
PUBMIND_GENOME_BUILD = "GRCh38"

PUBMIND_PARQUET = "pubmind.parquet"

#: Where a kept row's coordinate came from, so a consumer can exclude a class without re-deriving why.
#:
#: `direct` — the source row was already one base against one base.
#: `codon` — an equal-length multi-base block differing at exactly one position, decomposed onto it.
#:   Every such block in the 2026-08-24 file is a codon triplet; the rule is stated over the block
#:   rather than over the length, because "differs at one base" is what makes it decomposable.
#: `indel` — a length-changing row, kept but marked: left-normalization is unverified upstream.
PUBMIND_DERIVATIONS: frozenset[str] = frozenset({"direct", "codon", "indel"})

#: Why a source row produced no output row. The set is walked rather than restated, so
#: `input_rows == record_count + sum(dropped.values())` is an equality over it and a new reason
#: cannot be added without joining the sum (`@registry-completeness`).
PUBMIND_DROP_REASONS: tuple[str, ...] = (
    # A contig this workspace does not model. Real filter, not a formality: an ANNOVAR release
    # carrying a scaffold would otherwise land rows the karyotype sort has no index for.
    "off_target_chrom",
    # `A>0`, `A>N` and one `T>TTA…N` in the 2026-08-24 file: 16 rows whose alt is not an allele.
    "non_acgt",
    # 523 rows in the same file assert a change from a base to itself, which is not a variant.
    "ref_equals_alt",
    # No PVID. The PVID is PubMind's *record* id, and this whole snapshot is organized around record
    # identity: a verdict with no id cannot be attributed, cannot be deduped against its twin, and
    # cannot join the multiplicity accounting. Dropped rather than carried with a null, because a null
    # id would silently merge distinct records under `identical_duplicate`.
    "no_pvid",
    # A `Start` that is not a number. The one cell that used to be parsed without a guard, which meant
    # a blank or truncated line killed the whole build mid-stream instead of being counted.
    "unparsable_position",
    # A codon block needing two or three simultaneous substitutions, or a longer MNV block. It is a
    # statement about the protein, not about a position a consumer can genotype.
    "multi_substitution",
    # Two source rows that decompose onto the same base with identical values in every column — the
    # model enumerated two ref codons for one amino-acid change. Collapsed because the second row
    # carries nothing the first does not; counted because a silent collapse is a silent count.
    "identical_duplicate",
)

_ACGT_RE = re.compile(r"^[ACGT]+$")
_VALID_CHROMS = frozenset([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])
#: Karyotype order for the emitted rows (deterministic; a parquet has no inherent order to recover).
_CHROM_ORDER: tuple[str, ...] = tuple([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])
_CHROM_INDEX: dict[str, int] = {c: i for i, c in enumerate(_CHROM_ORDER)}

#: The ANNOVAR table's own column names, probed 2026-08-28 against the 2026-08-24 file.
_COL_CHROM = "#Chr"
_COL_START = "Start"
_COL_REF = "Ref"
_COL_ALT = "Alt"
_COL_PVID = "PVID"
_COL_SIG = "PubMindDB_pathogenicity_sum"
_COL_SCORE = "PubMindDB_paper_level_pathogenicity_score"
_COL_CONFIDENCE = "PubMindDB_confidence"
_REQUIRED_COLUMNS: tuple[str, ...] = (
    _COL_CHROM, _COL_START, _COL_REF, _COL_ALT, _COL_PVID, _COL_SIG, _COL_SCORE, _COL_CONFIDENCE,
)


class PubMindBuildError(RuntimeError):
    """A PubMind snapshot could not be built from the table given."""


class PubMindUnavailable(PubMindBuildError):
    """The ANNOVAR-distributed table could not be reached.

    A **subclass**, so `except PubMindBuildError` keeps catching everything it did while a caller who
    wants to tell "the source is down" from "your table is malformed" can. That distinction has to be
    carried by the *type*: neither `exc.__cause__` nor a message is pinned as an API, so a reword
    would flip a consumer's verdict from `unchecked` to "your data is wrong".

    The subclassing makes a caller's `except` **order** load-bearing — list this arm before its parent
    or it is dead code (`@client-exception-contract`).
    """


@dataclass(frozen=True)
class PubMindDownload:
    """What a download established about the bytes — each half `None` when the server did not say.

    All three of `sha256`, `etag` and `last_modified` are recorded because all three are available,
    and because an upstream revision then becomes a finding rather than a silent change of answer.
    """

    path: Path
    sha256: str | None
    #: The URL the bytes actually came from, so `release.json` states a provenance the build
    #: established rather than the module's default.
    url: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class PubMindBuildResult:
    """Outcome of a build: the paths, the counts kept, and every count dropped."""

    out_dir: Path
    parquet_file: Path
    input_rows: int
    record_count: int
    #: Keyed by `PUBMIND_DROP_REASONS`, every member present so a zero is a measured zero.
    dropped: dict[str, int] = field(default_factory=dict)
    #: `derivation` → rows carrying it. Every member of `PUBMIND_DERIVATIONS` present.
    derivations: dict[str, int] = field(default_factory=dict)
    #: Distinct `(chrom, start, ref, alt)` keys in the output.
    allele_keys: int = 0
    #: Keys carrying more than one PVID, and the worst multiplicity. Kept, never collapsed.
    multi_pvid_keys: int = 0
    max_pvids_per_key: int = 0
    #: Keys whose PVIDs do not all report the same normalized `clin_sig` — the reason the
    #: multiplicity matters rather than being tidy-up work.
    contested_keys: int = 0
    #: Cells the source wrote in a shape the numeric column cannot hold. Withheld as null rather than
    #: guessed at, and counted so "no score" and "a score we could not read" stay distinguishable.
    unparsable_score: int = 0
    unparsable_confidence: int = 0
    source_sha256: str | None = None
    #: A release id derived from the source bytes, because PubMind publishes no version string of
    #: its own — the same answer PharmVar's and CPIC's builders reach for the same reason. `None`
    #: when the source file could not be hashed: an unknown release, never a fabricated one.
    dataset: str | None = None


def download_pubmind_table(
    dest: Path, url: str = DEFAULT_PUBMIND_URL
) -> PubMindDownload:
    """Stream the ANNOVAR-redistributed table to `dest` (atomic `.part` rename).

    Mirrors `clinvar_build.download_clinvar_vcf`, and additionally keeps the `ETag` and
    `Last-Modified` the server sends: PubMind publishes no version string of its own, so those two
    headers plus the sha256 are the whole of what pins which bytes a snapshot was built from.
    """
    # **This handler used to leave its `.part` behind** — the only one of the eleven that forgot,
    # which is the drift a shared body ends (`@a-failed-fetch-is-not-a-no-op`).
    streamed = stream_to_file(
        dest, url, error_cls=PubMindUnavailable, what="the PubMind table",
        remedy=(
            "It is a single dated bulk file on a third party's server, so a move or a rotation "
            "looks exactly like this — pass `--table` with a copy you already hold."
        ),
    )
    return PubMindDownload(
        path=streamed.path, sha256=streamed.sha256, url=url,
        etag=streamed.etag, last_modified=streamed.last_modified,
    )


def _schema() -> dict:
    """Fixed column order + dtypes, so a rebuild is byte-identical (Principle 7).

    Join key first and annotation after, the split `clinvar_build._empty_schema` established —
    except that here *no* column is a resolver link, which is the point above made structural.
    Built lazily so importing this module without the `[dev]` polars extra does not fail.
    """
    return {
        "chrom": pl.Utf8,
        "start": pl.Int64,          # the 1-based VCF position, never converted
        "ref": pl.Utf8,
        "alt": pl.Utf8,
        "pvid": pl.Utf8,            # their *record* id, not a variant id
        "clin_sig": pl.Utf8,        # normalized into VALID_CLIN_SIG, by the one shared normalizer
        "clin_sig_raw": pl.Utf8,    # the source token verbatim, so the mapping stays auditable
        "pathogenicity_score": pl.Float64,   # null means *not computed*, never 0.0
        "confidence": pl.Int64,     # 0–3, PubMind's evidence-depth count, not ClinVar's stars
        "derivation": pl.Utf8,
    }


def _open_table(table: Path) -> Iterator[dict[str, str]]:
    """Yield the table's rows as dicts, from a `.gz` or a plain text file."""
    opener = gzip.open if table.suffix == ".gz" else open
    with opener(table, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
        # `restval=""` so a truncated line yields empty cells rather than `None`: without it a short
        # row was silently *kept*, its blank `clin_sig` reading as "PubMind states no classification"
        # at a coordinate PubMind never spoke about, and counted by no drop reason at all.
        reader = csv.DictReader(handle, delimiter="\t", restval="")
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise PubMindBuildError(
                f"{table} is missing the column(s) {missing}; found {reader.fieldnames}. Refusing "
                f"rather than guessing — a silently mis-parsed table would put someone else's "
                f"numbers behind PubMind's name."
            )
        yield from reader


def _score(raw: str | None) -> tuple[float | None, bool]:
    """`(value, unparsable)` — an empty cell is a plain absence, a malformed one is a finding.

    `NaN` and `inf` are *rejected* rather than stored, and that is not pedantry: `float()` accepts both,
    so they would slip past the counter as parsed values and then poison every comparison downstream.
    A routine cell in a bioinformatics TSV.
    """
    text = (raw or "").strip()
    if not text:
        return None, False
    try:
        value = float(text)
    except ValueError:
        return None, True
    return (value, False) if math.isfinite(value) else (None, True)


def _confidence(raw: str | None) -> tuple[int | None, bool]:
    """PubMind's 0-3 evidence-depth count. Non-integral is withheld, never truncated.

    `int(float("2.7"))` is `2`, which would record a definite count the source did not state — and
    `int(float("nan"))` raises. Both are unparsable: withhold and count.
    """
    text = (raw or "").strip()
    if not text:
        return None, False
    try:
        value = float(text)
    except ValueError:
        return None, True
    if not math.isfinite(value) or value != int(value):
        return None, True
    return int(value), False


def build_snapshot(
    table: Path,
    out_dir: Path,
    *,
    source_url: str | None = None,
    source_sha256: str | None = None,
    source_etag: str | None = None,
    source_last_modified: str | None = None,
) -> PubMindBuildResult:
    """Convert the ANNOVAR-redistributed PubMind table into `data/pubmind.parquet` + `release.json`.

    Rows are emitted sorted by `(chrom in karyotype order, start, ref, alt, pvid)`, so a rebuild from
    the same input is byte-identical (Principle 7); `release.json`'s `built_at` is the only
    per-run-varying byte and lives outside the parquet.

    **Every provenance argument defaults to `None` rather than to the module's constants**, and
    `source_url` in particular: only a caller that actually fetched can say where the bytes came from.
    Defaulting it to `DEFAULT_PUBMIND_URL` would have written the ANNOVAR URL into the `release.json`
    of a snapshot built from a file on local disk — asserting a provenance the build never established,
    in the one file whose whole job is to pin which bytes it was built from.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the PubMind snapshot; install the publisher/dev surface "
            "with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    table = Path(table)
    if not table.exists():
        raise FileNotFoundError(f"PubMind table not found at {table}")
    out_dir = Path(out_dir)
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)

    dropped = dict.fromkeys(PUBMIND_DROP_REASONS, 0)
    input_rows = 0
    unparsable_score = unparsable_confidence = 0
    records: list[dict] = []

    for row in _open_table(table):
        input_rows += 1
        chrom = (row[_COL_CHROM] or "").strip().removeprefix("chr")
        if chrom in ("M", "chrM"):
            chrom = "MT"
        if chrom not in _VALID_CHROMS:
            dropped["off_target_chrom"] += 1
            continue
        ref = (row[_COL_REF] or "").strip().upper()
        alt = (row[_COL_ALT] or "").strip().upper()
        if not (_ACGT_RE.match(ref) and _ACGT_RE.match(alt)):
            dropped["non_acgt"] += 1
            continue
        if ref == alt:
            dropped["ref_equals_alt"] += 1
            continue
        pvid = (row[_COL_PVID] or "").strip()
        if not pvid:
            dropped["no_pvid"] += 1
            continue
        position = (row[_COL_START] or "").strip()
        if not position.isdigit():
            dropped["unparsable_position"] += 1
            continue
        start = int(position)
        if len(ref) != len(alt):
            derivation = "indel"
        elif len(ref) == 1:
            derivation = "direct"
        else:
            differing = [i for i in range(len(ref)) if ref[i] != alt[i]]
            if len(differing) != 1:
                dropped["multi_substitution"] += 1
                continue
            index = differing[0]
            start, ref, alt = start + index, ref[index], alt[index]
            derivation = "codon"
        raw_sig = row[_COL_SIG] or None
        score, bad_score = _score(row.get(_COL_SCORE))
        confidence, bad_confidence = _confidence(row.get(_COL_CONFIDENCE))
        unparsable_score += bad_score
        unparsable_confidence += bad_confidence
        records.append(
            {
                "chrom": chrom,
                "start": start,
                "ref": ref,
                "alt": alt,
                "pvid": pvid,
                "clin_sig": normalize_clin_sig(raw_sig),
                "clin_sig_raw": raw_sig,
                "pathogenicity_score": score,
                "confidence": confidence,
                "derivation": derivation,
            }
        )

    # Two source rows can decompose onto one base with identical values in every column (the model
    # enumerated two ref codons for one amino-acid change). Collapse only on the *whole* row: a pair
    # differing anywhere — a different verdict, a different score — is two claims and stays two rows,
    # because the dedup key decides which columns may become several rows (`@dedup-key-decides-rows`).
    seen: set[tuple] = set()
    unique: list[dict] = []
    for record in records:
        signature = tuple(record.values())
        if signature in seen:
            dropped["identical_duplicate"] += 1
            continue
        seen.add(signature)
        unique.append(record)

    unique.sort(key=lambda r: (_CHROM_INDEX[r["chrom"]], r["start"], r["ref"], r["alt"], r["pvid"]))
    frame = pl.DataFrame(unique, schema=_schema())
    parquet_file = data_dir / PUBMIND_PARQUET
    frame.write_parquet(parquet_file, compression="zstd")

    derivations = dict.fromkeys(sorted(PUBMIND_DERIVATIONS), 0)
    by_key: dict[tuple[str, int, str, str], set[str | None]] = {}
    sigs_by_key: dict[tuple[str, int, str, str], set[str]] = {}
    for record in unique:
        derivations[record["derivation"]] += 1
        key = (record["chrom"], record["start"], record["ref"], record["alt"])
        by_key.setdefault(key, set()).add(record["pvid"])
        sigs_by_key.setdefault(key, set()).add(record["clin_sig"])

    result = PubMindBuildResult(
        out_dir=out_dir,
        parquet_file=parquet_file,
        input_rows=input_rows,
        record_count=frame.height,
        dropped=dropped,
        derivations=derivations,
        allele_keys=len(by_key),
        multi_pvid_keys=sum(1 for pvids in by_key.values() if len(pvids) > 1),
        max_pvids_per_key=max((len(p) for p in by_key.values()), default=0),
        contested_keys=sum(1 for sigs in sigs_by_key.values() if len(sigs) > 1),
        unparsable_score=unparsable_score,
        unparsable_confidence=unparsable_confidence,
        source_sha256=source_sha256 if source_sha256 is not None else _sha256_file(table),
    )
    result.dataset = None if result.source_sha256 is None else f"pubmind_{result.source_sha256[:12]}"
    _write_release_json(
        out_dir,
        result,
        source_url=source_url,
        source_etag=source_etag,
        source_last_modified=source_last_modified,
    )
    logger.info(
        "Built the PubMind snapshot: %d of %d row(s) kept → %s (dropped: %s; %d contested key(s) of "
        "%d, worst %d PVIDs)",
        result.record_count, result.input_rows, parquet_file,
        ", ".join(f"{name} {count}" for name, count in dropped.items()),
        result.contested_keys, result.allele_keys, result.max_pvids_per_key,
    )
    return result


def _sha256_file(path: Path) -> str | None:
    """sha256 of a file, or `None` if it cannot be read — an unknown digest, never a missing one."""
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                hasher.update(chunk)
    except OSError as exc:
        logger.warning("Could not hash %s (%s); recording an unknown source_sha256.", path, exc)
        return None
    return hasher.hexdigest()


def _write_release_json(
    out_dir: Path,
    result: PubMindBuildResult,
    *,
    source_url: str | None,
    source_etag: str | None,
    source_last_modified: str | None,
) -> Path:
    """Write `release.json` — the provenance, every drop count, and the multi-PVID finding.

    A plain write rather than `clinvar_build._merge_release_block`: that shape exists so two blocks
    can cohabit one snapshot directory (ClinVar's citations beside its records), and this snapshot
    directory holds one thing.

    All three of `source_url`, `source_etag` and `source_last_modified` are `None` when the table came
    off local disk — unknown rather than absent, which is why they are recorded as null instead of
    omitted, and why none of them takes a default the build did not establish.
    """
    release = {
        "source_url": source_url,
        "source_sha256": result.source_sha256,
        "dataset": result.dataset,
        "source_etag": source_etag,
        "source_last_modified": source_last_modified,
        "genome_build": PUBMIND_GENOME_BUILD,
        "input_rows": result.input_rows,
        "record_count": result.record_count,
        "dropped": result.dropped,
        "derivations": result.derivations,
        "allele_keys": result.allele_keys,
        "multi_pvid_keys": result.multi_pvid_keys,
        "max_pvids_per_key": result.max_pvids_per_key,
        "contested_keys": result.contested_keys,
        "unparsable_score": result.unparsable_score,
        "unparsable_confidence": result.unparsable_confidence,
        "redistributable": False,
        "notice": (
            "The ANNOVAR-distributed PubMind table publishes no data terms of its own; the software "
            "licence covers the software and the paper is CC BY-NC-ND. Unknown is not permissive, so "
            "this snapshot is operator-built and inject-only: do not publish or pass it on. Every "
            "verdict here is an LLM's reading of the literature, and a PVID is a record id keyed on "
            "extracted text rather than on a coordinate."
        ),
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"

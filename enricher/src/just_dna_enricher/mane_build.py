"""Build the MANE snapshot (`[dev]`) — the numbering frame, as a cache instead of a sentence (RM168).

MANE (Matched Annotation from NCBI and EMBL-EBI) publishes one agreed transcript per protein-coding
gene, matched base-for-base between a RefSeq and an Ensembl accession. This workspace already leaned
on it: the CIViC identity protocol pins a numbering frame with `MANE.GRCh38.v1.5.summary.txt.gz`,
*"downloaded once and cited"* — a procedure step in a probe document, where every other reference
table here is a cache with a location and a recorded release. The 33 curated name→identity answers
that shipped with that protocol were derived in a frame nothing in the code could read. This builder
is that frame, cached and pinned.

**MANE is the default, not the answer, and the bound is measured rather than asserted.** The summary
carries CDKN2A twice for one gene — `NM_000077.5` MANE Select beside `NM_058195.4` MANE Plus Clinical,
with different CDS numbering — and only ~0.4 % of rows are MANE Plus Clinical, which is exactly the
class a remembered accession hides and a table shows. RUNX1, by contrast, is a *single* row, so the
27-residue RUNX1c/RUNX1b offset the identity protocol derived by translating each isoform's CDS is
**not in MANE and cannot be**. The table therefore makes the CDKN2A class of problem visible and is
silent on the RUNX1 class, and a pass that treated it as an oracle would be wrong in a way the file
itself cannot warn about. `MANE_status` is carried as a column and never collapsed; a builder keeping
one row per gene would drop the Plus Clinical rows and reintroduce the blind spot this item closes.

**Scope is a transcript-identity aid.** Generating `c.`/`p.` notation is a separately deferred
feature with its own unanswered questions, and nothing here proposes it.

**Three files, because the third of them is the currency check and the second is the negative
roster.** Shipping the summary without the thing that notices it going stale is the defect this item
is about, and all three together are under 1.2 MB:

* `summary` — one row per MANE transcript; the cross-map (NCBI GeneID, Ensembl gene, HGNC id, symbol,
  both nuc/prot accession pairs, GRCh38 coordinates) as well as the frame.
* `changed_select_accessions` — every gene whose MANE Select moved, with the release it moved from
  and **`Update_Affects_CDS`**: the numbering-frame axis, stated by the source. A gene absent from
  this table has had a stable frame, which is a positive statement the cache can make and a memory
  cannot.
* `protein_coding_genes_not_in_mane` — the genes MANE deliberately has no answer for, each with a
  reason. `@unreachable-not-absent` served by the source: "MANE has no answer for this gene" is
  distinguishable from "nobody asked", with the reason attached, and `pending MANE review` is a third
  state that is neither. The reason vocabulary is **derived from the file** and recorded in
  `release.json`; it is not restated here, because a seven-member list written down beside the file is
  a registry nothing iterates (`@registry-completeness`).

**The versioned directory is pinned, never `current/`.** `release_1.5/` back to `release_0.5/` all
exist, so a pin is a URL rather than a hope. `current/` is still the right place to *discover* the
newest version — its `README_versions.txt` names it — and resolving that to a versioned URL before
downloading anything is the honest shape.

**`release.json` copies `README_versions.txt` rather than restating it.** That file is 96 bytes and
publishes `MANE Version`, `NCBI RefSeq Annotation Release` and `Ensembl Release`; two of the three
appear in no filename, so parsing a filename would reconstruct *less* information than the source
hands over (`@probe-the-real-file`). It is parsed generically, label by label, so a line MANE adds
travels through instead of being dropped by a reader that knew three names.

**Three parquets under `data/`, keyed by filename, on the CPIC precedent.** CPIC's snapshot already
holds five distinct schemas in one `data/` directory; the glob-union hazard
(`@snapshot-layout-locations`) belongs to readers that union `data/*.parquet` into a single view, and
this snapshot ships no reader — anything reading it later reads by filename.

**Terms: NCBI publishes a policy, not a licence** (`@no-named-licence`, and see `MANE_TERMS`). MANE
is a joint NCBI/EMBL-EBI product and only NCBI's side was read, so nothing here asserts anything
about EMBL-EBI's terms for the same tables.

Builder-only: `polars` is a guarded `[dev]` import, exactly as in the sibling builders.
"""

import csv
import gzip
import hashlib
import json
import logging
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: NCBI's MANE directory. The versioned children (`release_1.5/` … `release_0.5/`) are what a build
#: pins; `current/` is only ever read to discover which version that is.
MANE_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human"

#: The mutable pointer. Named as a constant because it is used exactly once, for discovery, and
#: naming it is what makes "never download from here" checkable rather than a comment.
MANE_CURRENT_DIRNAME = "current"

#: The 96-byte provenance file. Present in `current/` and in every versioned directory, unprefixed.
MANE_VERSIONS_FILENAME = "README_versions.txt"

#: The label `README_versions.txt` gives the release number, verbatim. Everything else in that file
#: is copied through without this module having to know its name.
MANE_VERSION_LABEL = "MANE Version"

#: MANE is GRCh38-only; recorded rather than implied, so a reader need not infer it from a filename.
MANE_GENOME_BUILD = "GRCh38"


@dataclass(frozen=True)
class ManeTable:
    """One of the three files a MANE release publishes that this snapshot carries.

    A registry rather than three sets of parallel constants: the downloader, the builder, the CLI and
    `release.json` all walk it, so adding a fourth file is one entry instead of four edits
    (`@registry-completeness`).
    """

    #: The key used in `release.json`, in `ManeBuildResult.rows` and as the CLI's local-file flag.
    name: str
    #: The part of the source filename after the `MANE.GRCh38.v<release>.` prefix.
    source_suffix: str
    #: The basename written under `data/`.
    parquet: str


MANE_TABLES: tuple[ManeTable, ...] = (
    ManeTable("summary", "summary.txt.gz", "summary.parquet"),
    ManeTable(
        "changed_select_accessions",
        "changed_select_accessions.txt.gz",
        "changed_select_accessions.parquet",
    ),
    ManeTable(
        "protein_coding_genes_not_in_mane",
        "protein_coding_genes_not_in_mane.txt.gz",
        "protein_coding_genes_not_in_mane.parquet",
    ),
)

MANE_TABLE_NAMES: tuple[str, ...] = tuple(table.name for table in MANE_TABLES)


class ManeBuildError(RuntimeError):
    """A MANE snapshot could not be built from the files given."""


class ManeUnavailable(ManeBuildError):
    """A MANE release file could not be reached.

    A **subclass**, so `except ManeBuildError` keeps catching everything it did while a caller who
    wants to tell "NCBI is unreachable" from "the file you handed me is malformed" can. The
    distinction is carried by the type rather than by a message, because a reword must not be able to
    flip a caller's verdict (`@client-exception-contract`) — and the subclassing makes a caller's
    `except` **order** load-bearing: list this arm before its parent or it is dead code.
    """


@dataclass(frozen=True)
class ManeDownload:
    """What a download established about one file's bytes — each half `None` where the server was
    silent. The `ETag` and `Last-Modified` are kept beside the sha256 because a versioned directory
    is supposed to be immutable, and recording all three is what would turn a revision of one into a
    finding rather than a silent change of answer."""

    path: Path
    sha256: str | None
    url: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class ManeBuildResult:
    """Outcome of a build: the paths, what each table holds, and the residue nothing could parse."""

    out_dir: Path
    #: `table name -> written parquet path`, every member of `MANE_TABLES` present.
    parquet_files: dict[str, Path] = field(default_factory=dict)
    #: `table name -> rows written`. One row out per row in, so this is also the input count.
    rows: dict[str, int] = field(default_factory=dict)
    #: The release this was pinned to (`"1.5"`), or `None` when no `README_versions.txt` was read —
    #: an unknown release, never one reconstructed from a filename.
    release: str | None = None
    #: `README_versions.txt` verbatim, label → value. Empty when the file was not read.
    versions: dict[str, str] = field(default_factory=dict)
    #: `mane_grch38_v1.5`, or `None` when the release is unknown.
    dataset: str | None = None
    #: `MANE_status` → rows carrying it, derived from the file. The MANE Plus Clinical count is the
    #: whole argument for carrying the column, so it is published rather than logged and dropped.
    mane_status_counts: dict[str, int] = field(default_factory=dict)
    #: `Update_Affects_CDS` verbatim token → rows. The numbering-frame axis, as the source states it.
    update_affects_cds_counts: dict[str, int] = field(default_factory=dict)
    #: Exclusion reason → genes, derived from the negative roster rather than from a list here.
    excluded_reasons: dict[str, int] = field(default_factory=dict)
    #: `table name -> rows whose NCBI GeneID could not be read`. Withheld as null and kept, never
    #: dropped: the accessions on such a row are still readable, and a silent drop reads as coverage.
    unparsable_gene_id: dict[str, int] = field(default_factory=dict)
    #: `Update_Affects_CDS` cells that are neither `Yes` nor `No`. The boolean is withheld, the
    #: verbatim token kept, and the count published so "the source said nothing" and "the source said
    #: something we cannot hold" stay distinguishable.
    unparsable_update_affects_cds: int = 0
    #: Summary rows carrying a `chr_start` or `chr_end` the integer column cannot hold. The row is
    #: kept — its accessions are the frame and they are still readable — the coordinate is withheld,
    #: and the count is published for the same reason as the two above it.
    unparsable_coordinate: int = 0
    #: `table name -> sha256 of the input file`, plus `README_versions.txt` under its own name.
    source_sha256: dict[str, str | None] = field(default_factory=dict)


# ── URLs ────────────────────────────────────────────────────────────────────────────────────────


def mane_release_dir_url(release: str) -> str:
    """The versioned directory for a release, e.g. `…/MANE_human/release_1.5`."""
    return f"{MANE_FTP_BASE}/release_{release}"


def mane_release_url(release: str, source_suffix: str) -> str:
    """The URL of one release file.

    MANE repeats the version in every filename (`release_1.5/MANE.GRCh38.v1.5.summary.txt.gz`), which
    is a shape a caller should not have to know — the same reason `civic_build.civic_release_url`
    exists.
    """
    return f"{mane_release_dir_url(release)}/MANE.GRCh38.v{release}.{source_suffix}"


def mane_versions_url(release: str | None = None) -> str:
    """`README_versions.txt` in a pinned release, or in `current/` when `release` is `None`.

    The `None` case is the **only** read of the mutable path, and it exists so a build can discover
    which version is newest before pinning it. Nothing is downloaded from `current/`.
    """
    directory = MANE_CURRENT_DIRNAME if release is None else f"release_{release}"
    return f"{MANE_FTP_BASE}/{directory}/{MANE_VERSIONS_FILENAME}"


# ── parsing ─────────────────────────────────────────────────────────────────────────────────────


def parse_versions(text: str) -> dict[str, str]:
    """`README_versions.txt` as `label -> value`, verbatim and in file order.

    Parsed generically rather than into three named fields: the file is a tab-separated label/value
    list, and a reader that knew exactly `MANE Version`, `NCBI RefSeq Annotation Release` and
    `Ensembl Release` would silently drop a fourth line MANE added. Blank lines and lines with no tab
    are skipped rather than raising — this is provenance, and a provenance failure is not a data
    failure.
    """
    versions: dict[str, str] = {}
    for line in text.splitlines():
        label, tab, value = line.partition("\t")
        if not tab:
            continue
        label, value = label.strip(), value.strip()
        if label:
            versions[label] = value
    return versions


def parse_ncbi_gene_id(raw: str | None) -> int | None:
    """The numeric NCBI GeneID from either spelling MANE uses, or `None`.

    **The source spells its own key two ways**, and the whole point of the three tables is that they
    join: `summary` writes `GeneID:1029` while `changed_select_accessions` and
    `protein_coding_genes_not_in_mane` write a bare `1029`. One normalizer, tested on both raw
    spellings (`@one-normalizer-two-spellings`), so a cross-table question — *has this gene's frame
    ever moved?* — is a join on one integer rather than a string comparison that silently never
    matches. `None` for anything else: unreadable, never guessed.
    """
    text = (raw or "").strip().removeprefix("GeneID:").strip()
    return int(text) if text.isdigit() else None


def parse_yes_no(raw: str | None) -> tuple[bool | None, bool]:
    """`(value, unparsable)` for a `Yes`/`No` cell — three outcomes, as the house algebra requires.

    An empty cell is a plain absence (`None`, not unparsable); anything that is neither `Yes` nor
    `No` is withheld **and** counted, because a token we cannot hold is a finding while silence is
    not.
    """
    text = (raw or "").strip().casefold()
    if not text:
        return None, False
    if text == "yes":
        return True, False
    if text == "no":
        return False, False
    return None, True


def _text(raw: str | None) -> str | None:
    """A cell verbatim apart from surrounding whitespace, with the empty cell as `None`."""
    text = (raw or "").strip()
    return text or None


#: Where `csv.DictReader` parks a long row's surplus fields. A name no MANE header can collide with,
#: because a collision would make a ragged row invisible to the check that reads this key.
_RAGGED_EXTRA = "__fields_past_the_header__"


def _open_table(path: Path, expected: tuple[str, ...]) -> Iterator[dict[str, str]]:
    """Yield a MANE TSV's rows as dicts, from a `.gz` or a plain text file.

    **All three files put a `#` on the first header cell** (`#NCBI_GeneID`, `#GeneID`), so the
    fieldnames are rewritten before the rows are read — otherwise every lookup of the join key would
    miss by one character and read as an empty column.

    The header is checked against `expected` **before the first row**, so a file with the wrong
    columns and no data rows refuses just as loudly as one with a million: a check that only runs
    inside the loop cannot see an empty table.

    **A ragged row is refused, not counted** (`@ragged-csv-row`). Everywhere else in this builder a
    bad *cell* withholds its own value and keeps the row, because the rest of the row is still the
    source's own statement. A row with the wrong number of fields is not that: the cells past the
    break are shifted, so a short summary row would land in the numbering frame carrying null
    accessions and read as coverage, and a shifted one would put the wrong accession under the right
    gene. Whole-file damage is a structural failure, and `strict` or not, a structural failure is the
    one thing a builder may refuse.

    **Decompression and decoding failures are translated too.** `gzip.open` is chosen on the suffix,
    so a file that is named `.gz` and is not one — a proxy that decompressed the download and kept
    the name, or a truncated copy — otherwise escapes as `BadGzipFile` or `EOFError` past the CLI's
    handler and prints a traceback where the operator wanted one line
    (`@client-exception-contract`, the same rule one layer in: a caller of this module may not be
    made to catch `gzip`'s tree to learn that a file could not be read). `EOFError` is deliberately
    named beside `OSError`: a truncated gzip raises it and it is **not** an `OSError`.
    """
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8", newline="") as handle:  # type: ignore[operator]
            # `restval=None` and a `restkey`, so a ragged row is *visible*: a short row leaves `None`
            # in the columns it never reached, and a long one parks its surplus under the restkey. A
            # genuinely empty cell is `""`, so neither is a false positive.
            reader = csv.DictReader(
                handle, delimiter="\t", restkey=_RAGGED_EXTRA, restval=None
            )
            fieldnames = list(reader.fieldnames or [])
            if fieldnames:
                fieldnames = [fieldnames[0].lstrip("#"), *fieldnames[1:]]
                reader.fieldnames = fieldnames
            missing = [column for column in expected if column not in fieldnames]
            if missing:
                raise ManeBuildError(
                    f"{path} is missing the column(s) {missing}; found {fieldnames}. Refusing rather "
                    f"than guessing — a silently mis-parsed table would put someone else's "
                    f"accessions behind MANE's name, and this snapshot exists to be a numbering frame."
                )
            for number, row in enumerate(reader, start=1):
                surplus = row.pop(_RAGGED_EXTRA, None) or []
                absent = [name for name, value in row.items() if value is None]
                if surplus or absent:
                    raise ManeBuildError(
                        f"{path} data row {number} has {len(fieldnames) - len(absent) + len(surplus)}"
                        f" field(s) where the header declares {len(fieldnames)}. Refusing: the cells "
                        f"past the break are shifted, so this row would enter the numbering frame "
                        f"with the wrong accession under the right gene."
                    )
                yield row
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise ManeBuildError(
            f"could not read {path}: {exc}. If the name ends in .gz, check it really is gzipped — a "
            f"proxy that decompressed the download and kept the name looks exactly like this."
        ) from exc


# ── the three tables ────────────────────────────────────────────────────────────────────────────

_SUMMARY_COLUMNS: tuple[str, ...] = (
    "NCBI_GeneID", "Ensembl_Gene", "HGNC_ID", "symbol", "name", "RefSeq_nuc", "RefSeq_prot",
    "Ensembl_nuc", "Ensembl_prot", "MANE_status", "GRCh38_chr", "chr_start", "chr_end", "chr_strand",
)
_CHANGED_COLUMNS: tuple[str, ...] = (
    "NCBI_GeneID", "Symbol", "Current_MANE_Select_RefSeq", "Current_MANE_Select_Ensembl",
    "Current_MANE_Version", "Old_MANE_Select_RefSeq", "Old_MANE_Select_Ensembl", "Old_MANE_Version",
    "Update_Affects_CDS",
)
_NOT_IN_MANE_COLUMNS: tuple[str, ...] = ("GeneID", "HGNC_id", "gene_symbol", "status")


def _summary_schema() -> dict:
    """Fixed column order + dtypes, so a rebuild from the same input is byte-identical (P7).

    `GRCh38_chr` stays the `NC_` RefSeq accession the source publishes rather than being mapped to a
    chromosome name: this is a transcript-identity aid, and re-spelling a coordinate system is the
    scope creep the item bars. The `MANE_status` and version cells stay verbatim for the same reason
    — `0.91` is a MANE release, not a number.
    """
    return {
        "ncbi_gene_id": pl.Int64,
        "ensembl_gene": pl.Utf8,
        "hgnc_id": pl.Utf8,
        "symbol": pl.Utf8,
        "name": pl.Utf8,
        "refseq_nuc": pl.Utf8,
        "refseq_prot": pl.Utf8,
        "ensembl_nuc": pl.Utf8,
        "ensembl_prot": pl.Utf8,
        "mane_status": pl.Utf8,
        "grch38_chr": pl.Utf8,
        "chr_start": pl.Int64,
        "chr_end": pl.Int64,
        "chr_strand": pl.Utf8,
    }


def _changed_schema() -> dict:
    """`update_affects_cds` beside `update_affects_cds_raw`, the split `clin_sig`/`clin_sig_raw`
    established: a queryable tri-state boolean, and the source's own token so the mapping stays
    auditable."""
    return {
        "ncbi_gene_id": pl.Int64,
        "symbol": pl.Utf8,
        "current_mane_select_refseq": pl.Utf8,
        "current_mane_select_ensembl": pl.Utf8,
        "current_mane_version": pl.Utf8,
        "old_mane_select_refseq": pl.Utf8,
        "old_mane_select_ensembl": pl.Utf8,
        "old_mane_version": pl.Utf8,
        "update_affects_cds": pl.Boolean,
        "update_affects_cds_raw": pl.Utf8,
    }


def _not_in_mane_schema() -> dict:
    return {
        "ncbi_gene_id": pl.Int64,
        "hgnc_id": pl.Utf8,
        "gene_symbol": pl.Utf8,
        "status": pl.Utf8,
    }


def _int(raw: str | None) -> int | None:
    """A coordinate cell as an integer, or `None` for anything this cannot read.

    `removeprefix("-")` rather than `lstrip("-")`, which strips *every* leading dash: `"--5"` would
    then pass the guard and raise inside `int()`. A cell parser in a builder whose rule is
    withhold-and-count has no business owning a traceback path.
    """
    text = (raw or "").strip()
    return int(text) if text.removeprefix("-").isdigit() else None


def _read_summary(path: Path, result: ManeBuildResult) -> list[dict]:
    records: list[dict] = []
    for row in _open_table(path, _SUMMARY_COLUMNS):
        gene_id = parse_ncbi_gene_id(row["NCBI_GeneID"])
        if gene_id is None:
            result.unparsable_gene_id["summary"] += 1
        status = _text(row["MANE_status"])
        result.mane_status_counts[status or ""] = result.mane_status_counts.get(status or "", 0) + 1
        start, end = _int(row["chr_start"]), _int(row["chr_end"])
        # A stated cell the integer column cannot hold is a finding; a blank one is a plain absence.
        if (start is None and row["chr_start"].strip()) or (end is None and row["chr_end"].strip()):
            result.unparsable_coordinate += 1
        records.append(
            {
                "ncbi_gene_id": gene_id,
                "ensembl_gene": _text(row["Ensembl_Gene"]),
                "hgnc_id": _text(row["HGNC_ID"]),
                "symbol": _text(row["symbol"]),
                "name": _text(row["name"]),
                "refseq_nuc": _text(row["RefSeq_nuc"]),
                "refseq_prot": _text(row["RefSeq_prot"]),
                "ensembl_nuc": _text(row["Ensembl_nuc"]),
                "ensembl_prot": _text(row["Ensembl_prot"]),
                "mane_status": status,
                "grch38_chr": _text(row["GRCh38_chr"]),
                "chr_start": start,
                "chr_end": end,
                "chr_strand": _text(row["chr_strand"]),
            }
        )
    # CDKN2A's two rows differ only past the gene id, so `refseq_nuc` is what makes the order total.
    records.sort(key=_gene_then(("refseq_nuc", "ensembl_nuc")))
    return records


def _read_changed(path: Path, result: ManeBuildResult) -> list[dict]:
    records: list[dict] = []
    for row in _open_table(path, _CHANGED_COLUMNS):
        gene_id = parse_ncbi_gene_id(row["NCBI_GeneID"])
        if gene_id is None:
            result.unparsable_gene_id["changed_select_accessions"] += 1
        affects, unparsable = parse_yes_no(row["Update_Affects_CDS"])
        result.unparsable_update_affects_cds += unparsable
        raw = _text(row["Update_Affects_CDS"])
        key = raw or ""
        result.update_affects_cds_counts[key] = result.update_affects_cds_counts.get(key, 0) + 1
        records.append(
            {
                "ncbi_gene_id": gene_id,
                "symbol": _text(row["Symbol"]),
                "current_mane_select_refseq": _text(row["Current_MANE_Select_RefSeq"]),
                "current_mane_select_ensembl": _text(row["Current_MANE_Select_Ensembl"]),
                "current_mane_version": _text(row["Current_MANE_Version"]),
                "old_mane_select_refseq": _text(row["Old_MANE_Select_RefSeq"]),
                "old_mane_select_ensembl": _text(row["Old_MANE_Select_Ensembl"]),
                "old_mane_version": _text(row["Old_MANE_Version"]),
                "update_affects_cds": affects,
                "update_affects_cds_raw": raw,
            }
        )
    records.sort(key=_gene_then(("current_mane_select_refseq",)))
    return records


def _read_not_in_mane(path: Path, result: ManeBuildResult) -> list[dict]:
    records: list[dict] = []
    for row in _open_table(path, _NOT_IN_MANE_COLUMNS):
        gene_id = parse_ncbi_gene_id(row["GeneID"])
        if gene_id is None:
            result.unparsable_gene_id["protein_coding_genes_not_in_mane"] += 1
        status = _text(row["status"])
        # The reason vocabulary is whatever the file holds. Derived here rather than declared beside
        # it, so a reason MANE adds is counted instead of silently joining an "other" bucket.
        result.excluded_reasons[status or ""] = result.excluded_reasons.get(status or "", 0) + 1
        records.append(
            {
                "ncbi_gene_id": gene_id,
                "hgnc_id": _text(row["HGNC_id"]),
                "gene_symbol": _text(row["gene_symbol"]),
                "status": status,
            }
        )
    records.sort(key=_gene_then(("gene_symbol",)))
    return records


def _gene_then(columns: tuple[str, ...]) -> Callable[[dict], tuple]:
    """A total sort key: gene id first, unreadable ids last, then the named tie-breakers.

    Parquet bytes depend on row order, so a rebuild is only byte-identical if the order is total —
    and `None` cannot be compared to an `int`, which is why the null-ness is its own leading term.
    """

    def key(record: dict) -> tuple:
        gene_id = record["ncbi_gene_id"]
        return (gene_id is None, gene_id or 0, *((record[c] or "") for c in columns))

    return key


_READERS = {
    "summary": (_read_summary, _summary_schema),
    "changed_select_accessions": (_read_changed, _changed_schema),
    "protein_coding_genes_not_in_mane": (_read_not_in_mane, _not_in_mane_schema),
}


# ── download ────────────────────────────────────────────────────────────────────────────────────


def download_mane_file(dest: Path, url: str) -> ManeDownload:
    """Stream one release file to `dest` (atomic `.part` rename), returning what it established.

    Mirrors `civic_build.download_civic_file`, down to removing the partial file on failure: a
    `.part` left behind is the one residue a re-run would have to reason about.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading %s ...", url)
    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
            response.raise_for_status()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    hasher.update(chunk)
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        # Translated rather than leaked: a caller of this package may not be made to depend on
        # httpx's exception tree to know that a fetch failed (`@client-exception-contract`).
        raise ManeUnavailable(
            f"could not download {url}: {exc}. Pass the local file instead of --download if you "
            f"already hold a copy."
        ) from exc
    tmp.replace(dest)
    return ManeDownload(
        path=dest, sha256=hasher.hexdigest(), url=url, etag=etag, last_modified=last_modified
    )


def discover_current_release() -> str:
    """The newest MANE version, read from `current/README_versions.txt`.

    The **one** request that touches the mutable path, and it takes 96 bytes. Its answer is then
    resolved to a versioned URL before anything is downloaded, which is what makes a build pinnable
    after the fact: `current/` moves, `release_1.5/` does not.
    """
    url = mane_versions_url(None)
    try:
        response = httpx.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ManeUnavailable(f"could not read {url}: {exc}") from exc
    release = parse_versions(response.text).get(MANE_VERSION_LABEL)
    if not release:
        raise ManeUnavailable(
            f"{url} does not state a {MANE_VERSION_LABEL!r}; refusing to guess a release from a "
            f"filename. Pass --release to pin one by hand."
        )
    return release


# ── build ───────────────────────────────────────────────────────────────────────────────────────


def build_snapshot(
    inputs: Mapping[str, Path],
    out_dir: Path,
    *,
    versions_file: Path | None = None,
    release: str | None = None,
    downloads: Mapping[str, ManeDownload] | None = None,
) -> ManeBuildResult:
    """Convert one pinned MANE release into `data/*.parquet` + `release.json`.

    `inputs` is keyed by `MANE_TABLE_NAMES` and must carry all three: the summary is the frame, the
    changed-accession list is the currency check, and the negative roster is what distinguishes "MANE
    has no answer for this gene" from "nobody asked". A snapshot missing any of them is the defect
    RM168 is about.

    Rows are emitted in a total order (gene id, then accession), so a rebuild from the same inputs is
    byte-identical (Principle 7); `release.json`'s `built_at` is the only per-run-varying byte and it
    lives outside the parquet.

    **`release` and every URL default to `None` rather than to this module's constants.** Only a
    caller that actually fetched can say where the bytes came from, and only a `README_versions.txt`
    that was read can say which release they are. Defaulting either would write a provenance the
    build never established into the one file whose whole job is to pin it.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the MANE snapshot; install the publisher/dev surface with "
            "`pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    missing = [name for name in MANE_TABLE_NAMES if name not in inputs]
    if missing:
        raise ManeBuildError(
            f"a MANE snapshot needs all three release files; missing {missing}. The summary alone is "
            f"a cache with nothing to notice it going stale, which is the defect this snapshot exists "
            f"to close."
        )
    paths = {name: Path(inputs[name]) for name in MANE_TABLE_NAMES}
    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"MANE {name} file not found at {path}")

    out_dir = Path(out_dir)
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)

    result = ManeBuildResult(
        out_dir=out_dir,
        unparsable_gene_id=dict.fromkeys(MANE_TABLE_NAMES, 0),
    )
    result.versions = _read_versions(versions_file)
    result.release = result.versions.get(MANE_VERSION_LABEL) or release
    result.dataset = None if result.release is None else f"mane_grch38_v{result.release}"

    for table in MANE_TABLES:
        read, schema = _READERS[table.name]
        records = read(paths[table.name], result)
        frame = pl.DataFrame(records, schema=schema())
        parquet_file = data_dir / table.parquet
        frame.write_parquet(parquet_file, compression="zstd")
        result.parquet_files[table.name] = parquet_file
        result.rows[table.name] = frame.height

    given = downloads or {}
    result.source_sha256 = {
        name: (given[name].sha256 if name in given else _sha256_file(paths[name]))
        for name in MANE_TABLE_NAMES
    }
    # Always keyed, `None` when no `README_versions.txt` was read: a key that vanishes is a different
    # statement from a key whose value is null, and only the second is true here.
    result.source_sha256[MANE_VERSIONS_FILENAME] = (
        None if versions_file is None else _sha256_file(Path(versions_file))
    )

    _write_release_json(out_dir, result, downloads=given)
    logger.info(
        "Built the MANE snapshot (%s): %s → %s. %d gene(s) excluded over %d reason(s); %d changed "
        "MANE Select accession(s).",
        result.dataset or "release unknown",
        ", ".join(f"{name} {count}" for name, count in result.rows.items()),
        data_dir,
        result.rows["protein_coding_genes_not_in_mane"],
        len(result.excluded_reasons),
        result.rows["changed_select_accessions"],
    )
    return result


def _read_versions(versions_file: Path | None) -> dict[str, str]:
    """`README_versions.txt` as a dict, or `{}` when there is none or it cannot be read.

    Unreadable provenance is reported and the build continues: a provenance failure is not a data
    failure, so the tables are still written and the release is recorded as unknown
    (`@release-json-provenance`).
    """
    if versions_file is None:
        return {}
    try:
        text = Path(versions_file).read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "Could not read %s (%s); recording an unknown release rather than guessing one.",
            versions_file, exc,
        )
        return {}
    return parse_versions(text)


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


def _per_input(downloads: Mapping[str, ManeDownload], attribute: str) -> dict[str, str | None]:
    """One header value per input table, `None` where this build did not fetch that file.

    Every table name is present rather than only the fetched ones, so the reader sees *unknown*
    rather than *absent*: a key missing from a dict and a key whose value is null are different
    statements, and only the second one is true of a locally-built snapshot.
    """
    return {
        name: (getattr(downloads[name], attribute) if name in downloads else None)
        for name in MANE_TABLE_NAMES
    }


def _write_release_json(
    out_dir: Path, result: ManeBuildResult, *, downloads: Mapping[str, ManeDownload]
) -> Path:
    """Write `release.json` — the provenance MANE hands over, plus what this build measured.

    Written **atomically** (`@atomic-sidecar-write`): a `release.json` truncated mid-write parses as
    valid JSON that is simply missing keys, and `locations.read_release` would believe it.

    `versions` is `README_versions.txt` copied label for label. The three labels it carries are the
    MANE version, the RefSeq annotation release and the Ensembl release, and two of those appear in
    no filename — which is why this copies the file instead of parsing a name.

    **`source_url`, `source_etag` and `source_last_modified` are per input and null on a local
    build.** A `README_versions.txt` handed over on disk establishes which *release* the files claim
    to be; it does not establish that they came from NCBI, and writing the versioned URL into a
    snapshot built from local bytes would assert a provenance this build never saw. `release_url`
    likewise names the directory that was actually fetched from, not the one a release number implies.
    """
    release = {
        "dataset": result.dataset,
        "mane_release": result.release,
        "versions": result.versions,
        "genome_build": MANE_GENOME_BUILD,
        "release_url": (
            mane_release_dir_url(result.release)
            if downloads and result.release is not None
            else None
        ),
        "source_url": _per_input(downloads, "url"),
        "source_sha256": result.source_sha256,
        "source_etag": _per_input(downloads, "etag"),
        "source_last_modified": _per_input(downloads, "last_modified"),
        "rows": result.rows,
        "mane_status_counts": result.mane_status_counts,
        "update_affects_cds_counts": result.update_affects_cds_counts,
        "excluded_reasons": result.excluded_reasons,
        "unparsable_gene_id": result.unparsable_gene_id,
        "unparsable_update_affects_cds": result.unparsable_update_affects_cds,
        "unparsable_coordinate": result.unparsable_coordinate,
        "notice": (
            "MANE is the default transcript, not the answer. A gene with two rows (MANE Select "
            "beside MANE Plus Clinical) has two CDS numbering frames and the column says which; a "
            "gene with one row says nothing about isoforms MANE does not carry, and a pass that "
            "treated this table as an oracle would be wrong in a way the table cannot report. "
            "NCBI states a policy rather than a licence: it places no restrictions on use or "
            "distribution and also declines to grant unrestricted permission, so every licence axis "
            "is unknown. Only NCBI's side of this joint NCBI/EMBL-EBI product was read."
        ),
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    atomic_write_text(path, json.dumps(release, indent=2, sort_keys=True) + "\n")
    return path


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"

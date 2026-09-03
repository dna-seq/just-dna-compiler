"""Build the ClinPGx summary-annotation snapshot (`[dev]`).

Turns the ClinPGx `summaryAnnotations.zip` bulk download into a flat parquet snapshot the pass reads
offline, following the ClinVar builder exactly: stream the archive, emit deterministically-sorted
parquet, and write a `release.json` recording provenance beside it.

**One thing here is not in the ClinVar builder, and it is the point of the whole licensing design.**
ClinPGx ships a `LICENSE.txt` *inside* the same archive as the data, so this builder extracts it and
records both the text and its sha256 into `release.json`. The pass then stamps that hash onto every
`SourceRow` it emits, which makes the recorded terms provably contemporaneous with the recorded data —
strictly stronger than a lookup in a table that was true once. Both halves of such a table went stale
inside a single release: `api.pharmgkb.org` was retired on 2026-07-20 and CPIC's licence page moved
when it merged into ClinPGx.

**The grain is (annotation, genotype), not annotation.** A ClinPGx summary annotation names a variant
and a drug in `summary_annotations.tsv`, then gives one row *per genotype* in
`summary_ann_alleles.tsv` — the large majority carry exactly three, and the calls can be opposed
(rs4149056/simvastatin reads "decreased response" for CC and CT, "increased" for TT). Flattening to
the annotation would throw away the axis the module keys on, so the two files are joined here. How
many carry three is a property of today's download, so it is counted per build and never written down
(the count this docstring used to carry outlived the file it was measured on by fourteen months).

**The archive is identified before it is read, and the retired spelling is refused (RM175).** PharmGKB
became ClinPGx on 2025-07-29 and renamed clinical annotations to *summary annotations*; the archive
followed, `clinical_ann*` becoming `summary_ann*` and `Clinical Annotation ID` becoming `Summary
Annotation ID`. `clinicalAnnotations.zip` was last written on 2025-07-05, is on no downloads page, and
the API still answers it **200** through a 303 to that frozen object — so a stale URL in a config
cannot be told from a live one at the HTTP layer, and every earlier build of this lane came out of a
snapshot fourteen months old. `require_current_archive` therefore refuses an archive carrying the old
member names by name, rather than letting a plausible parquet come out of it.

**`CREATED_*.txt` is the release id.** ClinPGx publishes no version number, and the archives are not
refreshed in lockstep — `relationships.zip` was a year newer than `clinicalAnnotations.zip` when this
was written, which RM175 later explained: that archive had stopped being rebuilt at all — so the
per-archive creation date is the only honest `dataset` label.
"""

import csv
import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME

try:  # polars is a `[dev]` dependency — the runtime pass reads parquet, only the builder writes it
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ClinPgxArchiveError(RuntimeError):
    """The archive handed to the builder is not the one ClinPGx publishes today."""


@dataclass(frozen=True)
class ArchiveVintage:
    """One published spelling of the annotation archive: its zip name, its members, its id column.

    Two exist because the source renamed all four in one go (RM175), and a reader that knows only the
    current spelling can say "member missing" but not *why* it is missing.
    """

    archive: str
    annotations: str
    alleles: str
    id_column: str


#: What ClinPGx publishes and rebuilds today. Every name the builder reads comes from here.
CURRENT_ARCHIVE = ArchiveVintage(
    archive="summaryAnnotations.zip",
    annotations="summary_annotations.tsv",
    alleles="summary_ann_alleles.tsv",
    id_column="Summary Annotation ID",
)
#: The pre-rename spelling. It exists to be **named in a refusal** and is never read from: nothing
#: returns it, so no parquet can come out of a 2025 archive by any path through this module.
RETIRED_ARCHIVE = ArchiveVintage(
    archive="clinicalAnnotations.zip",
    annotations="clinical_annotations.tsv",
    alleles="clinical_ann_alleles.tsv",
    id_column="Clinical Annotation ID",
)

DEFAULT_CLINPGX_URL = (
    f"https://api.clinpgx.org/v1/download/file/data/{CURRENT_ARCHIVE.archive}"
)
#: The archive member the terms arrive in. A source-format detail, so it stays here — unlike the name
#: the *snapshot* stores it under, which is `locations.SNAPSHOT_LICENSE_FILENAME` because four other
#: parties have to agree on it. They are the same string today and are not the same fact.
ARCHIVE_LICENSE_MEMBER = "LICENSE.txt"
_CREATED_RE = re.compile(r"^CREATED_(?P<date>\d{4}-\d{2}-\d{2})\.txt$")
# The per-genotype annotation text routinely runs to several hundred characters; the field limit
# csv defaults to is smaller than some of them.
_CSV_FIELD_LIMIT = 1_000_000


@dataclass
class ClinPgxBuildResult:
    out_dir: Path
    parquet_path: Path
    row_count: int
    annotation_count: int
    created_date: str | None
    source_sha256: str
    license_sha256: str | None
    genes: list[str] = field(default_factory=list)


def _schema() -> dict:
    """Fixed column order + dtypes, so a rebuild is byte-identical (Principle 7)."""
    return {
        "annotation_id": pl.Utf8,
        "subject": pl.Utf8,          # the `Variant/Haplotypes` cell, verbatim
        "rsid": pl.Utf8,             # populated only when the subject is an rsID
        "gene": pl.Utf8,
        "genotype": pl.Utf8,         # verbatim as ClinPGx writes it (`CC`, `*1/*17`, `C/del`)
        "evidence_level": pl.Utf8,
        "phenotype_category": pl.Utf8,
        "drugs": pl.Utf8,
        "phenotypes": pl.Utf8,
        "annotation_text": pl.Utf8,
        "url": pl.Utf8,
    }


def download_clinpgx_zip(dest: Path, url: str = DEFAULT_CLINPGX_URL) -> tuple[Path, str]:
    """Stream the ClinPGx bulk archive to `dest`, returning `(path, sha256)`.

    Atomic `.part` rename and a hash computed while streaming, matching the ClinVar downloader.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading ClinPGx summary annotations from %s ...", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as response:
        response.raise_for_status()
        with open(tmp, "wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
                hasher.update(chunk)
    tmp.replace(dest)
    digest = hasher.hexdigest()
    logger.info("Downloaded %s (sha256 %s)", dest, digest)
    return dest, digest


def read_license(archive: zipfile.ZipFile) -> str | None:
    """The `LICENSE.txt` ClinPGx bundles with the data, or None if the archive has none.

    Read from the archive rather than fetched separately on purpose: the terms that govern *these*
    bytes are the ones shipped alongside them.

    A member that is present and blank answers `None`, the same as no member at all: both builders
    hash whatever this returns into `license_sha256` and write it beside the data, and an empty file
    would pin the terms to the hash of the empty string and hand the drafter a licence to read that
    says nothing. Decided here rather than in the two callers, so the rule cannot hold in one build
    and not the other.
    """
    for name in archive.namelist():
        if Path(name).name == ARCHIVE_LICENSE_MEMBER:
            text = archive.read(name).decode("utf-8", errors="replace")
            return text if text.strip() else None
    return None


def read_created_date(archive: zipfile.ZipFile) -> str | None:
    """The `CREATED_<date>.txt` marker — ClinPGx's only release identifier."""
    for name in archive.namelist():
        match = _CREATED_RE.match(Path(name).name)
        if match:
            return match.group("date")
    return None


def _tsv_rows(archive: zipfile.ZipFile, member: str) -> list[dict[str, str]]:
    with archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        reader = csv.DictReader(text, delimiter="\t")
        return [dict(row) for row in reader]


def _member(archive: zipfile.ZipFile, filename: str) -> str:
    for name in archive.namelist():
        if Path(name).name == filename:
            return name
    raise ClinPgxArchiveError(f"{filename} not found in the ClinPGx archive")


def require_current_archive(archive: zipfile.ZipFile) -> ArchiveVintage:
    """`CURRENT_ARCHIVE` if this zip is the one ClinPGx publishes today, else a refusal that says why.

    Three arms, three diagnoses (`@answered-is-not-absent`): the current spelling, the retired one,
    and an archive that is neither. The middle arm is the reason this function exists — the retired
    `clinicalAnnotations.zip` still answers 200 and still parses, so without a check by *name* a stale
    URL builds a plausible parquet out of the database as it stood before the 2025-07-29 rename
    (`@specific-rejection`: a generic "member missing" is a dead end where naming the rename is a fix).
    """
    members = {Path(name).name for name in archive.namelist()}
    if CURRENT_ARCHIVE.annotations in members:
        return CURRENT_ARCHIVE
    if RETIRED_ARCHIVE.annotations in members:
        raise ClinPgxArchiveError(
            f"this archive carries `{RETIRED_ARCHIVE.annotations}`, the member name ClinPGx retired "
            f"on 2025-07-29 when clinical annotations were renamed to summary annotations. "
            f"`{RETIRED_ARCHIVE.archive}` is a frozen object last written 2025-07-05 that the API "
            f"still answers 200, so building from it would publish the database as it stood before "
            f"the rename. Build from `{CURRENT_ARCHIVE.archive}` instead ({DEFAULT_CLINPGX_URL}), "
            f"whose members are `{CURRENT_ARCHIVE.annotations}` and "
            f"`{CURRENT_ARCHIVE.alleles}` and whose id column is `{CURRENT_ARCHIVE.id_column}`."
        )
    raise ClinPgxArchiveError(
        f"no `{CURRENT_ARCHIVE.annotations}` in this archive, and no "
        f"`{RETIRED_ARCHIVE.annotations}` either, so it is not the ClinPGx annotation archive at "
        f"all. Expected `{CURRENT_ARCHIVE.archive}` from {DEFAULT_CLINPGX_URL}; it holds "
        f"{sorted(members)}."
    )


def build_snapshot(
    zip_path: Path, out_dir: Path, *, source_url: str = DEFAULT_CLINPGX_URL,
    source_sha256: str | None = None,
) -> ClinPgxBuildResult:
    """`summaryAnnotations.zip` → `clinpgx/data/annotations.parquet` + `release.json` + `LICENSE.txt`.

    Joins the summary table to its per-genotype child so the snapshot's grain is
    (annotation, genotype) — the grain `PharmVariantRow` keys on. Rows are sorted by
    `(annotation_id, genotype)` so a rebuild is byte-identical; `built_at` is the only per-run byte
    and lives in `release.json`, outside the parquet.

    Raises `ClinPgxArchiveError` on the retired `clinicalAnnotations.zip`, which parses fine and is
    fourteen months stale (RM175) — see `require_current_archive`.
    """
    if pl is None:  # pragma: no cover
        raise ImportError(
            "polars is required to build the ClinPGx snapshot; install the dev surface with "
            "`pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    csv.field_size_limit(_CSV_FIELD_LIMIT)
    zip_path, out_dir = Path(zip_path), Path(out_dir)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        vintage = require_current_archive(archive)  # refuses the retired 2025 spelling by name
        license_text = read_license(archive)
        created = read_created_date(archive)
        summaries = _tsv_rows(archive, _member(archive, vintage.annotations))
        alleles = _tsv_rows(archive, _member(archive, vintage.alleles))

    by_id = {row[vintage.id_column]: row for row in summaries}
    records: list[dict] = []
    for allele in alleles:
        summary = by_id.get(allele[vintage.id_column])
        if summary is None:
            continue  # an orphan child row; the summary is the authority for what exists
        subject = (summary.get("Variant/Haplotypes") or "").strip()
        records.append(
            {
                "annotation_id": allele[vintage.id_column],
                "subject": subject,
                # Only a single rsID subject is a variant identity. A haplotype subject (`CYP2C19*2`)
                # or a multi-variant one is left null rather than mangled into a fake rsID.
                "rsid": subject if re.fullmatch(r"rs\d+", subject) else None,
                "gene": (summary.get("Gene") or "").strip() or None,
                "genotype": (allele.get("Genotype/Allele") or "").strip() or None,
                "evidence_level": (summary.get("Level of Evidence") or "").strip() or None,
                "phenotype_category": (summary.get("Phenotype Category") or "").strip() or None,
                "drugs": (summary.get("Drug(s)") or "").strip() or None,
                "phenotypes": (summary.get("Phenotype(s)") or "").strip() or None,
                "annotation_text": (allele.get("Annotation Text") or "").strip() or None,
                "url": (summary.get("URL") or "").strip() or None,
            }
        )

    frame = pl.DataFrame(records, schema=_schema()).sort(
        ["annotation_id", "genotype"], nulls_last=True
    )
    parquet_path = data_dir / "annotations.parquet"
    frame.write_parquet(parquet_path, compression="zstd")

    license_sha = (
        "sha256:" + hashlib.sha256(license_text.encode("utf-8")).hexdigest()
        if license_text is not None
        else None
    )
    if license_text is not None:
        # Kept beside the data so a holder of the snapshot can read the terms without the archive.
        (out_dir / SNAPSHOT_LICENSE_FILENAME).write_text(license_text, encoding="utf-8")

    genes = sorted({r["gene"] for r in records if r["gene"]})
    digest = source_sha256 or _sha256_file(zip_path)
    release = {
        "source_url": source_url,
        "source_sha256": digest,
        "created_date": created,
        "dataset": f"clinpgx_{created}" if created else "clinpgx",
        "license_sha256": license_sha,
        "row_count": len(records),
        "annotation_count": len(by_id),
        "built_at": now_utc_iso(),
    }
    (out_dir / RELEASE_FILENAME).write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")

    logger.info(
        "ClinPGx snapshot: %d rows across %d annotations (%s), %d genes → %s",
        len(records), len(by_id), created or "undated", len(genes), parquet_path,
    )
    return ClinPgxBuildResult(
        out_dir=out_dir,
        parquet_path=parquet_path,
        row_count=len(records),
        annotation_count=len(by_id),
        created_date=created,
        source_sha256=digest,
        license_sha256=license_sha,
        genes=genes,
    )


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

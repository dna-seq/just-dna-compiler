"""Build the ClinPGx clinical-annotation snapshot (`[dev]`).

Turns the ClinPGx `clinicalAnnotations.zip` bulk download into a flat parquet snapshot the pass reads
offline, following the ClinVar builder exactly: stream the archive, emit deterministically-sorted
parquet, and write a `release.json` recording provenance beside it.

**One thing here is not in the ClinVar builder, and it is the point of the whole licensing design.**
ClinPGx ships a `LICENSE.txt` *inside* the same archive as the data, so this builder extracts it and
records both the text and its sha256 into `release.json`. The pass then stamps that hash onto every
`SourceRow` it emits, which makes the recorded terms provably contemporaneous with the recorded data —
strictly stronger than a lookup in a table that was true once. Both halves of such a table went stale
inside a single release: `api.pharmgkb.org` was retired on 2026-07-20 and CPIC's licence page moved
when it merged into ClinPGx.

**The grain is (annotation, genotype), not annotation.** A ClinPGx clinical annotation names a variant
and a drug in `clinical_annotations.tsv`, then gives one row *per genotype* in
`clinical_ann_alleles.tsv` — 4,618 of 5,113 carry exactly three, and the calls can be opposed
(rs4149056/simvastatin reads "decreased response" for CC and CT, "increased" for TT). Flattening to
the annotation would throw away the axis the module keys on, so the two files are joined here.

**`CREATED_*.txt` is the release id.** ClinPGx publishes no version number, and the archives are not
refreshed in lockstep — `relationships.zip` was a year newer than `clinicalAnnotations.zip` when this
was written — so the per-archive creation date is the only honest `dataset` label.
"""

import csv
import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

try:  # polars is a `[dev]` dependency — the runtime pass reads parquet, only the builder writes it
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_CLINPGX_URL = "https://api.clinpgx.org/v1/download/file/data/clinicalAnnotations.zip"
SNAPSHOT_DIRNAME = "clinpgx"
RELEASE_FILENAME = "release.json"
LICENSE_FILENAME = "LICENSE.txt"
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
    created_date: Optional[str]
    source_sha256: str
    license_sha256: Optional[str]
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
    logger.info("Downloading ClinPGx clinical annotations from %s ...", url)
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


def read_license(archive: zipfile.ZipFile) -> Optional[str]:
    """The `LICENSE.txt` ClinPGx bundles with the data, or None if the archive has none.

    Read from the archive rather than fetched separately on purpose: the terms that govern *these*
    bytes are the ones shipped alongside them.
    """
    for name in archive.namelist():
        if Path(name).name == LICENSE_FILENAME:
            return archive.read(name).decode("utf-8", errors="replace")
    return None


def read_created_date(archive: zipfile.ZipFile) -> Optional[str]:
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
    raise ValueError(f"{filename} not found in the ClinPGx archive")


def build_snapshot(
    zip_path: Path, out_dir: Path, *, source_url: str = DEFAULT_CLINPGX_URL,
    source_sha256: Optional[str] = None,
) -> ClinPgxBuildResult:
    """`clinicalAnnotations.zip` → `clinpgx/data/annotations.parquet` + `release.json` + `LICENSE.txt`.

    Joins the summary table to its per-genotype child so the snapshot's grain is
    (annotation, genotype) — the grain `PharmVariantRow` keys on. Rows are sorted by
    `(annotation_id, genotype)` so a rebuild is byte-identical; `built_at` is the only per-run byte
    and lives in `release.json`, outside the parquet.
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
        license_text = read_license(archive)
        created = read_created_date(archive)
        summaries = _tsv_rows(archive, _member(archive, "clinical_annotations.tsv"))
        alleles = _tsv_rows(archive, _member(archive, "clinical_ann_alleles.tsv"))

    by_id = {row["Clinical Annotation ID"]: row for row in summaries}
    records: list[dict] = []
    for allele in alleles:
        summary = by_id.get(allele["Clinical Annotation ID"])
        if summary is None:
            continue  # an orphan child row; the summary is the authority for what exists
        subject = (summary.get("Variant/Haplotypes") or "").strip()
        records.append(
            {
                "annotation_id": allele["Clinical Annotation ID"],
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
        (out_dir / LICENSE_FILENAME).write_text(license_text, encoding="utf-8")

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
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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

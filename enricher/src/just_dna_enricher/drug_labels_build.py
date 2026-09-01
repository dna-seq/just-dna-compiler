"""Build the regulator drug-label snapshot the label cross-check reads (`[dev]`, RM166).

ClinPGx publishes `drugLabels.zip` on the same endpoint `clinicalAnnotations.zip` comes from, and
`clinpgx_build` downloads exactly one of the twelve archives that endpoint serves. This is the
second: 59 KB holding `LICENSE.txt`, `README.pdf`, `drugLabels.tsv` (1,433 rows when probed on
2026-08-05) and `drugLabels.byGene.tsv` (238 rows, a pivot of the same labels by gene symbol — it
carries no fact the label table does not, so nothing here reads it).

**Its own `release.json`, never the annotation lane's.** `clinpgx_build`'s module docstring records
that `relationships.zip` was a *year* newer than `clinicalAnnotations.zip`, so assuming ClinPGx's
archives refresh in lockstep is a mistake this lane has already made once. `drugLabels.zip` carries
its own `CREATED_<date>.txt` and it is what labels this snapshot — `clinpgx_drug_labels_<date>`,
distinct from the annotation lane's `clinpgx_<date>` because the two archives are two surfaces with
two denominators (`@two-surfaces-two-denominators`).

**Every cell is stored verbatim.** Seven of the fifteen columns are flag-shaped — a blank or one
constant string (`Prescribing Info`, `Cancer Genome`) — and coercing them to booleans would have this
builder decide that `Biomarker Flag` is one, which it is not: it carries *three* values, `On FDA
Biomarker List` and `Formerly on FDA Biomarker List` beside the blank. So nothing is coerced, a blank
becomes `None`, and the reader decides what a cell means (`@verbatim-except-order`).

**No `--offline`, and the licence gate lives at the CLI.** A builder's off-switch is passing the local
archive instead of downloading one, and `check_declared_use` gates the *fetch* — which is the command,
not this module (`@acquisition-gate-is-not-a-read-gate`). `clinpgx build` puts the gate in the command
body for the same reason and this follows it rather than inventing a third answer.
"""

import csv
import hashlib
import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.clinpgx_build import read_created_date, read_license
from just_dna_enricher.drug_labels import (
    DEFAULT_DRUG_LABELS_URL,
    LABEL_COLUMNS,
    LABELS_PARQUET,
    SOURCE_NAME,
    DrugLabelError,
    DrugLabelUnavailable,
)
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
)

try:  # polars is a `[dev]` dependency — the runtime check reads parquet, only the builder writes it
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: The archive member this builder reads, and the one it deliberately does not.
LABELS_MEMBER = "drugLabels.tsv"
BY_GENE_MEMBER = "drugLabels.byGene.tsv"

#: Source column → snapshot column. A hand-kept parallel list is how `SOURCES_FIELDNAMES` lost a
#: column, so the snapshot's column order is derived from this mapping and asserted against
#: `LABEL_COLUMNS`, which is what the reader binds to.
#:
#: `Source` becomes `regulator` and that rename is the item's rule rather than a tidy-up: the file
#: carries five agencies, and `source` is already this tier's word for *the licensed source*, which
#: here is ClinPGx for every row.
COLUMN_MAP: dict[str, str] = {
    "PharmGKB ID": "label_id",
    "Name": "label_name",
    "Source": "regulator",
    "Biomarker Flag": "biomarker_flag",
    "Testing Level": "testing_level",
    "Has Prescribing Info": "has_prescribing_info",
    "Has Dosing Info": "has_dosing_info",
    "Has Alternate Drug": "has_alternate_drug",
    "Has Other Prescribing Guidance": "has_other_prescribing_guidance",
    "Cancer Genome": "cancer_genome",
    "Prescribing": "prescribing",
    "Chemicals": "chemicals",
    "Genes": "genes",
    "Variants/Haplotypes": "variants",
    "Latest History Date (YYYY-MM-DD)": "latest_history_date",
}

# The label names run past `csv`'s default field limit on the combination products.
_CSV_FIELD_LIMIT = 1_000_000


@dataclass
class DrugLabelBuildResult:
    """Where the snapshot landed, what it holds, and what it came from."""

    out_dir: Path
    parquet_path: Path
    release_file: Path
    label_count: int
    created_date: str | None
    dataset: str | None
    source_url: str
    source_sha256: str
    license_sha256: str | None
    regulators: list[str] = field(default_factory=list)
    testing_levels: list[str] = field(default_factory=list)


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


def _schema() -> dict:
    """Fixed column order, every column Utf8 — see the docstring on why nothing is coerced."""
    return dict.fromkeys(LABEL_COLUMNS, pl.Utf8)


def download_drug_labels_zip(
    dest: Path, url: str = DEFAULT_DRUG_LABELS_URL
) -> tuple[Path, str]:
    """Stream `drugLabels.zip` to `dest` (atomic `.part` rename), returning `(path, sha256)`.

    Core `httpx` with the hash taken while streaming, the shape every bulk builder here uses —
    `download.py` is HuggingFace snapshot provisioning and `net.py` is pacing for live API clients,
    so neither is what a one-file download reaches for.

    **`httpx`'s exceptions do not leave this function** (`@client-exception-contract`): a retired
    endpoint is a 404, and it must reach the CLI as `DRUG-LABEL BUILD FAILED: …` rather than as a raw
    `HTTPStatusError` traceback. The half-written `.part` goes with it.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading the ClinPGx drug labels from %s ...", url)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=None) as response:
            response.raise_for_status()
            with open(tmp, "wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
                    hasher.update(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise DrugLabelUnavailable(
            f"could not download the drug-label archive from {url}: {exc}"
        ) from exc
    tmp.replace(dest)
    digest = hasher.hexdigest()
    logger.info("Downloaded %s (sha256 %s)", dest, digest)
    return dest, digest


def _member(archive: zipfile.ZipFile, filename: str) -> str:
    for name in archive.namelist():
        if Path(name).name == filename:
            return name
    raise DrugLabelError(f"{filename} not found in the drug-label archive")


def _rows(archive: zipfile.ZipFile) -> list[dict[str, str | None]]:
    """`drugLabels.tsv` → the snapshot's records, renamed and blank-to-`None`, in file order."""
    with archive.open(_member(archive, LABELS_MEMBER)) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        reader = csv.DictReader(text, delimiter="\t")
        missing = sorted(set(COLUMN_MAP) - set(reader.fieldnames or ()))
        if missing:
            # Structural: a renamed upstream column would otherwise land as a whole column of nulls,
            # and a check reading `testing_level` would then report five regulators saying nothing.
            raise DrugLabelError(
                f"{LABELS_MEMBER} is missing {len(missing)} expected column(s): {missing}"
            )
        return [
            {
                target: ((row.get(source) or "").strip() or None)
                for source, target in COLUMN_MAP.items()
            }
            for row in reader
        ]


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_drug_label_snapshot(
    zip_path: Path,
    out_dir: Path,
    *,
    source_url: str = DEFAULT_DRUG_LABELS_URL,
    source_sha256: str | None = None,
) -> DrugLabelBuildResult:
    """`drugLabels.zip` → `data/drug_labels.parquet` + `LICENSE.txt` + `release.json`.

    Rows are sorted by `label_id` so a rebuild is byte-identical (Principle 7); `built_at` is the only
    per-run byte and it lives in `release.json`, outside the parquet.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the drug-label snapshot; install the dev surface with "
            "`pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    csv.field_size_limit(_CSV_FIELD_LIMIT)
    zip_path, out_dir = Path(zip_path), Path(out_dir)
    if not zip_path.is_file():
        raise DrugLabelError(f"no drug-label archive at {zip_path}")

    try:
        with zipfile.ZipFile(zip_path) as archive:
            license_text = read_license(archive)
            created = read_created_date(archive)
            records = _rows(archive)
    except zipfile.BadZipFile as exc:
        raise DrugLabelError(f"{zip_path} is not a readable zip archive: {exc}") from exc
    if not records:
        raise DrugLabelError(
            f"{source_url} parsed to zero labels; refusing to record it as a snapshot"
        )

    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(records, schema=_schema()).sort("label_id", nulls_last=True)
    parquet_path = data_dir / LABELS_PARQUET
    frame.write_parquet(parquet_path, compression="zstd")

    license_sha: str | None = None
    if license_text is not None:
        # Written before it is hashed, and hashed from what was written: `clinpgx_draft` reads this
        # file rather than `release.json`'s stated hash, so the two must describe the same bytes.
        license_path = out_dir / SNAPSHOT_LICENSE_FILENAME
        atomic_write_text(license_path, license_text)
        license_sha = "sha256:" + hashlib.sha256(
            license_path.read_bytes()
        ).hexdigest()

    regulators = sorted({r["regulator"] for r in records if r["regulator"]})
    levels = sorted({r["testing_level"] for r in records if r["testing_level"]})
    digest = source_sha256 or _sha256_file(zip_path)
    dataset = f"{SOURCE_NAME}_drug_labels_{created}" if created else None
    release_file = _write_release_json(
        out_dir,
        source_url=source_url,
        source_sha256=digest,
        created_date=created,
        dataset=dataset,
        license_sha256=license_sha,
        label_count=len(records),
        regulators=regulators,
        testing_levels=levels,
    )

    logger.info(
        "Drug-label snapshot: %d label(s) from %d regulator(s) (%s) → %s",
        len(records), len(regulators), created or "undated", parquet_path,
    )
    return DrugLabelBuildResult(
        out_dir=out_dir,
        parquet_path=parquet_path,
        release_file=release_file,
        label_count=len(records),
        created_date=created,
        dataset=dataset,
        source_url=source_url,
        source_sha256=digest,
        license_sha256=license_sha,
        regulators=regulators,
        testing_levels=levels,
    )


def _write_release_json(
    out_dir: Path,
    *,
    source_url: str,
    source_sha256: str,
    created_date: str | None,
    dataset: str | None,
    license_sha256: str | None,
    label_count: int,
    regulators: list[str],
    testing_levels: list[str],
) -> Path:
    """The provenance beside the parquet, written atomically.

    No shared helper, deliberately — each builder owns its own, because the fields that matter differ
    per source. `regulators` and `testing_levels` are recorded because the check's denominator is
    *which agencies this snapshot could answer for*, and a number computed and dropped is one every
    reader recomputes (`@dont-discard-computed`).
    """
    release = {
        "source": SOURCE_NAME,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "created_date": created_date,
        "dataset": dataset,
        "license_sha256": license_sha256,
        "label_count": label_count,
        "regulators": regulators,
        "testing_levels": testing_levels,
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    atomic_write_text(path, json.dumps(release, indent=2, sort_keys=True) + "\n")
    return path

"""The reference-snapshot layout and its provenance record, `release.json` (RM303).

A reference snapshot is `data/*.parquet` (or one named payload file), optional parquet sidecar
directories beside `data/`, `LICENSE.txt`, and `release.json`. Six parties have to agree on those
names and on what `release.json` says: the builder writes it, the publisher uploads it, the
provisioner fetches it, the resolver judges the directory, the reporter prints its label, and a pass
reads its release. Every disagreement so far was silent, so the names and the record live here, in
the tier every party already depends on, and nowhere else.

This module is the **contract** half: names, a model, a reader, a writer and a payload predicate.
It reads no environment and fetches nothing. Where a snapshot lives on a given machine (the cache
base, the per-lane variables, `.env`, the pull record) is deployment, and stays in the enricher.

**Old spellings are read, never written.** Snapshots already published keep their keys. The model
reads `rows` and `licence` into the canonical fields, and ClinVar's `clinvar_file_date` into
`dataset`, so a republish writes the canonical spelling rather than anyone editing a published file.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from just_dna_format.layout import atomic_write_text

logger = logging.getLogger(__name__)

# ── the layout ──────────────────────────────────────────────────────────────────────────────────

#: The records: what the readers glob. A sidecar is a **sibling** of this directory, never inside
#: it, because the readers build their view from `data/*.parquet`.
SNAPSHOT_DATA_DIRNAME = "data"

#: ClinVar's literature links, the one sidecar directory any snapshot carries today.
CITATIONS_DIRNAME = "citations"

#: Optional parquet sidecar directories a snapshot may carry beside `data/`. Absent is normal.
SNAPSHOT_SIDECAR_DIRNAMES: tuple[str, ...] = (CITATIONS_DIRNAME,)

#: The provenance record beside the data. It describes every part of the snapshot.
RELEASE_FILENAME = "release.json"

#: The terms a snapshot was taken under, kept beside the bytes they govern.
SNAPSHOT_LICENSE_FILENAME = "LICENSE.txt"

#: The AlphaGenome AVI lane's reconstruction curve: a root-level file beside `data/`, not optional.
ALPHAGENOME_KNOTS_FILENAME = "avi_knots.parquet"

#: Every file a snapshot may carry at its root beside `data/` and its sidecar directories. **The
#: order is the publish order, and `RELEASE_FILENAME` is last**: the description must never arrive
#: before the bytes it describes.
SNAPSHOT_ROOT_FILENAMES: tuple[str, ...] = (
    SNAPSHOT_LICENSE_FILENAME,
    ALPHAGENOME_KNOTS_FILENAME,
    RELEASE_FILENAME,
)

#: The payload of the two snapshots that hold no parquet: ACMG's list and STRchive's catalogue.
ACMG_SNAPSHOT_FILENAME = "acmg_sf.csv"
STRCHIVE_CATALOGUE_FILENAME = "STRchive-loci.json"


def holds_snapshot_payload(directory: Path, *, payload_filename: str | None = None) -> bool:
    """Whether `directory` holds a snapshot's payload — judged by the payload, never by `is_dir()`.

    With `payload_filename`, the payload is that one file at the root. Without it, the payload is at
    least one parquet under `data/`, or bare at the root (the shape a single-file snapshot was
    handed over in before `data/` existed). A directory holding only `release.json`, or nothing, is
    not a snapshot: an interrupted build leaves exactly that behind.

    Says nothing about whether a pull finished; that is the provisioner's record of one machine's
    copy, and it lives with the provisioner.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return False
    if payload_filename is not None:
        return (directory / payload_filename).is_file()
    data_dir = directory / SNAPSHOT_DATA_DIRNAME
    return (data_dir.is_dir() and any(data_dir.glob("*.parquet"))) or any(directory.glob("*.parquet"))


# ── the record ──────────────────────────────────────────────────────────────────────────────────

#: ClinVar's release label prefix, as `SourceRow.dataset` carries it.
CLINVAR_DATASET_PREFIX = "clinvar_"


def clinvar_release_label(file_date: str | None, source_sha256: str | None) -> str | None:
    """ClinVar's release label: `clinvar_<##fileDate>`, else `clinvar_sha256:<digest>`, else `None`.

    One formula, called by the builder that writes `dataset` and by the reader of a ClinVar snapshot
    built before the builder wrote one. A VCF whose header states no file date still has the digest
    of the bytes, which names the release exactly. With neither, the label is unknown and withheld.
    """
    date = str(file_date or "").strip()
    if date:
        return f"{CLINVAR_DATASET_PREFIX}{date}"
    digest = str(source_sha256 or "").strip().removeprefix("sha256:")
    return f"{CLINVAR_DATASET_PREFIX}sha256:{digest}" if digest else None


#: `licence` was CIViC's spelling; `license` is the field (the spelling `module_spec.yaml` uses).
_OLD_LICENSE_KEY = "licence"
#: `rows` was three builders' spelling: an int (a total) in one, a per-file map in two.
_OLD_ROWS_KEY = "rows"
#: The key only ClinVar's builder writes; its presence is what marks a ClinVar release.
_CLINVAR_DATE_KEY = "clinvar_file_date"


class SnapshotRelease(BaseModel):
    """A snapshot's `release.json`: the keys some reader reads are typed, every other key rides along.

    Every typed field is optional, and **unstated is `None`**, never a default: a key the file does
    not carry is not an answer. Writes go through `write_release`, which drops the fields the
    builder never set and keeps the ones it set to `None` — a recorded `null` is a stated unknown.
    Values are kept verbatim: `source_sha256` is prefixed by some builders and bare in others, and
    `built_at` has two timestamp shapes.
    """

    model_config = ConfigDict(extra="allow")

    #: The release label: which release of the source this snapshot holds.
    dataset: str | None = None
    #: Where the bytes came from, and their digest.
    source_url: str | None = None
    source_sha256: str | None = None
    #: When and by which builder version the snapshot was cut.
    built_at: str | None = None
    builder_version: str | None = None
    #: The licence identifier, and the digest of the licence text that travels as `LICENSE.txt`.
    license: str | None = None
    license_sha256: str | None = None
    #: How many rows the snapshot holds in total, and per payload file where it holds several.
    row_count: int | None = None
    row_counts: dict[str, int] | None = None
    #: How many source records the build read (ClinVar's VCF records; pubmind's and CIViC's).
    record_count: int | None = None
    #: The assembly the snapshot's coordinates are on.
    genome_build: str | None = None
    #: A derived snapshot's pins on the snapshots it was built from, keyed by lane.
    parents: dict[str, dict[str, Any]] | None = None
    #: ClinVar's `##fileDate`, the date its label is built from.
    clinvar_file_date: str | None = None
    #: CIViC's status basis: which rows the release the snapshot was built from serves.
    status_basis: str | None = None
    #: The ACMG secondary-findings list version.
    sf_version: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _read_old_spellings(cls, data: Any) -> Any:
        """Map the old spellings onto the canonical fields. The canonical key wins when both are stated."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if _OLD_LICENSE_KEY in data:
            data.setdefault("license", data.pop(_OLD_LICENSE_KEY))
        if _OLD_ROWS_KEY in data:
            rows = data[_OLD_ROWS_KEY]
            # A map is per payload file and a number is a total: two fields, never one overloaded one.
            if isinstance(rows, dict):
                data.setdefault("row_counts", data.pop(_OLD_ROWS_KEY))
            elif rows is None or (isinstance(rows, int) and not isinstance(rows, bool)):
                data.setdefault("row_count", data.pop(_OLD_ROWS_KEY))
        if "dataset" not in data and _CLINVAR_DATE_KEY in data:
            label = clinvar_release_label(data.get(_CLINVAR_DATE_KEY), data.get("source_sha256"))
            if label is not None:
                data["dataset"] = label
        return data

    def to_json(self) -> str:
        """The bytes `write_release` puts on disk: the set keys only, sorted, newline-terminated."""
        return json.dumps(self.model_dump(mode="json", exclude_unset=True), indent=2, sort_keys=True) + "\n"


def read_release(reference: Path) -> SnapshotRelease | None:
    """A snapshot directory's `release.json` as a `SnapshotRelease`, or `None` when absent or unreadable.

    `None` is the answer for both, as it was when this returned a dict: a caller must not be able to
    mistake "this snapshot does not say" for a release, so callers branch on `None`. Unreadable
    covers a file that does not parse, one that is not a JSON object, and one whose typed key holds a
    value of the wrong kind. Each is logged, because a provenance failure is not a data failure and
    the snapshot itself stays usable.
    """
    path = Path(reference) / RELEASE_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Could not read %s (%s); treating the release as unstated.", path, exc)
        return None
    if not isinstance(payload, dict):
        logger.warning("%s is not a JSON object; treating the release as unstated.", path)
        return None
    try:
        return SnapshotRelease.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "%s does not fit the snapshot record (%s); treating the release as unstated.", path, exc
        )
        return None


def write_release(directory: Path, release: SnapshotRelease) -> Path:
    """Write `release` as `directory/release.json`, atomically, and return the path.

    The one way a builder writes the record, so every snapshot carries the canonical spellings.
    Atomic because a `release.json` truncated mid-write parses as valid JSON that is simply missing
    keys, and a reader would believe it.
    """
    return atomic_write_text(Path(directory) / RELEASE_FILENAME, release.to_json())

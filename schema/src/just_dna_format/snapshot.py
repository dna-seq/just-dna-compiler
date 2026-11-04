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
from dataclasses import dataclass
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

#: The per-file manifest a snapshot built outside this workspace may carry instead of `release.json`
#: (RM372): prepare-annotations' Ensembl release states its release id and every file's size and
#: sha256 here. Named in this tier because it is a root file every party moves; what it says is read
#: by the enricher, the only tier that judges a cache against it.
SNAPSHOT_MANIFEST_FILENAME = "manifest.json"

#: Every file a snapshot may carry at its root beside `data/` and its sidecar directories. **The
#: order is the publish order, and `RELEASE_FILENAME` is last**: the description must never arrive
#: before the bytes it describes.
SNAPSHOT_ROOT_FILENAMES: tuple[str, ...] = (
    SNAPSHOT_LICENSE_FILENAME,
    ALPHAGENOME_KNOTS_FILENAME,
    SNAPSHOT_MANIFEST_FILENAME,
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


def _canonical(data: dict) -> dict:
    """A raw `release.json` object with its old spellings mapped onto the canonical keys."""
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
        digest = data.get("source_sha256")
        label = clinvar_release_label(
            data.get(_CLINVAR_DATE_KEY), digest if isinstance(digest, str) else None
        )
        if label is not None:
            data["dataset"] = label
    return data


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
    #: Where the bytes came from, and their digest. One per input, keyed by the input's name, for a
    #: snapshot built from several downloads (MANE); a per-input `None` is an input that came off
    #: local disk, whose origin the build did not see.
    source_url: str | dict[str, str | None] | None = None
    source_sha256: str | dict[str, str | None] | None = None
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
    #: Open Targets: how many parts of each dataset the build read, and how many the release has. A
    #: snapshot read short of the total is partial, and a pass over it must say so (RM369).
    parts_read: dict[str, int] | None = None
    parts_total: dict[str, int] | None = None
    #: ClinVar-GKM: the weekly release the Parquet set was cut from, and the VRS version its ids were
    #: minted under, as the source declares it (RM369).
    source_release: str | None = None
    vrs_version: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _read_old_spellings(cls, data: Any) -> Any:
        """Map the old spellings onto the canonical fields. The canonical key wins when both are stated."""
        return _canonical(data) if isinstance(data, dict) else data

    def to_json(self) -> str:
        """The bytes `write_release` puts on disk: the set keys only, sorted, newline-terminated."""
        return json.dumps(self.model_dump(mode="json", exclude_unset=True), indent=2, sort_keys=True) + "\n"


def _load(path: Path) -> tuple[dict | None, str | None]:
    """The parsed JSON object at `path`, or `None` and why it is not one."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "not a JSON object"
    return payload, None


def read_release(reference: Path) -> SnapshotRelease | None:
    """A snapshot directory's `release.json` as a `SnapshotRelease`, or `None` when absent or unreadable.

    `None` is the answer for both, as it was when this returned a dict: a caller must not be able to
    mistake "this snapshot does not say" for a release, so callers branch on `None`. Unreadable is a
    file that does not parse, or one that is not a JSON object.

    **A typed key holding the wrong kind of value costs that key, never the record.** It is read as
    unstated and the warning names it; every other key, the label included, is still read. The
    snapshot's own provenance is worth more than one malformed count. `release_is_unreadable` says
    whether a record was read whole, for the writer that must not replace a file it could not read.
    """
    path = Path(reference) / RELEASE_FILENAME
    if not path.is_file():
        return None
    payload, problem = _load(path)
    if payload is None:
        logger.warning("Could not read %s (%s); treating the release as unstated.", path, problem)
        return None
    canonical = _canonical(payload)
    try:
        return SnapshotRelease.model_validate(canonical)
    except ValidationError as exc:
        bad = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        logger.warning("%s: %s do not fit the snapshot record; read as unstated.", path, ", ".join(bad))
    try:
        return SnapshotRelease.model_validate({k: v for k, v in canonical.items() if k not in bad})
    except ValidationError:
        return None


def release_is_unreadable(reference: Path) -> bool:
    """Whether `reference` holds a `release.json` that cannot be read whole.

    Present and not parseable, not an object, or with a typed key `read_release` had to drop. Told
    apart from absence for the caller that has to act on it: a provenance failure is not a data
    failure, so the snapshot stays usable and says so; and a writer merging into the file must leave
    it alone rather than replace the only statement of where the data came from. Logs nothing:
    `read_release` is where the warning is said.
    """
    path = Path(reference) / RELEASE_FILENAME
    if not path.is_file():
        return False
    payload, _ = _load(path)
    if payload is None:
        return True
    try:
        SnapshotRelease.model_validate(payload)
    except ValidationError:
        return True
    return False


def release_label(reference: Path) -> str | None:
    """The release a snapshot directory states, its `dataset`, or `None` when it states none.

    The one reader of the label, for `cache status` and for every pass that stamps it onto
    `SourceRow.dataset`, so a reader of the cache and a reader of a module see the same string. No
    fallback and no guess: a blank, absent or unreadable label is an unknown, and an unknown is
    withheld rather than written as a label something could match.
    """
    release = read_release(reference)
    label = (release.dataset or "").strip() if release is not None else ""
    return label or None


def write_release(directory: Path, release: SnapshotRelease) -> Path:
    """Write `release` as `directory/release.json`, atomically, and return the path.

    Every snapshot carries the canonical spellings because every record is written here. Atomic
    because a `release.json` truncated mid-write parses as valid JSON that is simply missing keys, and
    a reader would believe it. **A builder does not call this**: it opens a write with
    `begin_snapshot_write`, whose `commit` calls it after the old record was withdrawn (RM369).
    """
    return atomic_write_text(Path(directory) / RELEASE_FILENAME, release.to_json())


# ── the write order: withdraw the record, move the bytes, describe them (RM369) ──────────────────


def _withdraw(directory: Path) -> None:
    """Remove `directory/release.json`, if there is one. The one place a record is withdrawn."""
    (Path(directory) / RELEASE_FILENAME).unlink(missing_ok=True)


@dataclass(frozen=True)
class SnapshotWrite:
    """An open write into a snapshot whose record has been withdrawn; `commit` describes the result."""

    directory: Path

    def commit(self, release: SnapshotRelease) -> Path:
        """Write `release` as the snapshot's record, after every byte it describes is in place."""
        return write_release(self.directory, release)


def begin_snapshot_write(directory: Path) -> SnapshotWrite:
    """Withdraw `directory`'s `release.json` before its payload changes, and return the write handle.

    The order is the contract: **withdraw, move the bytes, describe them.** A builder that swapped its
    payload in first and wrote the record after left, on a crash between the two (a full disk, a
    killed process), new bytes under the previous build's record, and every reader believed it. With
    the record withdrawn first, the worst a crash leaves is a snapshot that states no release, which
    every reader already treats as an unknown and withholds.

    **Call it immediately before the first byte of the live payload moves**, never at the top of a
    build: a download or a parse that fails before then leaves the old snapshot whole, and it should
    stay described. And a build that fails after it is **not** given its old record back, because a
    restored record would describe bytes the failed build may have changed.

    The handle's `commit` is the only way a builder writes `release.json`, so describing a snapshot
    without having withdrawn the old description is not expressible.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    _withdraw(directory)
    return SnapshotWrite(directory)


@dataclass(frozen=True)
class BlockWrite:
    """An open write into one block of a snapshot's record; `commit` merges the new block in."""

    directory: Path
    name: str
    #: `False` when the record was present and unreadable, and is being left alone.
    readable: bool

    def commit(self, block: dict[str, Any]) -> bool:
        """Merge `block` under `name` into the record; `False` when the record could not be read."""
        if not self.readable or release_is_unreadable(self.directory):
            logger.warning(
                "the snapshot's release.json in %s is present but unreadable; leaving it alone rather "
                "than overwriting its provenance. The %s block was not recorded.",
                self.directory,
                self.name,
            )
            return False
        existing = read_release(self.directory)
        stated = existing.model_dump(exclude_unset=True) if existing is not None else {}
        write_release(self.directory, SnapshotRelease.model_validate({**stated, self.name: block}))
        return True


def begin_block_write(directory: Path, name: str) -> BlockWrite:
    """Withdraw block `name` from `directory`'s record before the bytes it describes change.

    For a second half that writes a sidecar beside a snapshot another build owns (ClinVar's
    citations): the half owns one block of the record, never the record, so it withdraws that block
    and leaves the rest. Read-modify-write rather than rewrite, and an unreadable record is left
    alone, because overwriting it would destroy the only statement of where the data came from.
    """
    directory = Path(directory)
    if release_is_unreadable(directory):
        return BlockWrite(directory, name, readable=False)
    existing = read_release(directory)
    if existing is not None and name in (existing.model_extra or {}):
        stated = existing.model_dump(exclude_unset=True)
        stated.pop(name)
        write_release(directory, SnapshotRelease.model_validate(stated))
    return BlockWrite(directory, name, readable=True)

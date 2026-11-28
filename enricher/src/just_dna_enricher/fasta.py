"""Index a local FASTA and read GRCh38 sequence by verified refget accession (RM385)."""

import codecs
import json
import logging
import os
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from ga4gh.core import digests
from just_dna_format.layout import atomic_writer
from just_dna_format.vrs import REFGET_GRCh38, refget_accession

from just_dna_enricher._refseq import GRCH38_ACCESSIONS

logger = logging.getLogger(__name__)

FASTA_SCHEME = "fasta+file:"
VALID_FASTA_CONTIG_STATUS: frozenset[str] = frozenset({"bound", "digest_mismatch", "absent"})
_CHROM = {accession: chrom for chrom, accession in REFGET_GRCh38.items()}


class FastaConfigurationError(ValueError):
    """The operator's reference cannot be opened as an indexed, uncompressed FASTA."""


@dataclass(frozen=True)
class FastaContigIdentity:
    """How an indexed FASTA entry compares with one GRCh38 primary sequence."""

    chrom: str
    fasta_name: str | None
    expected_accession: str
    found_digest: str | None
    status: str

    def __post_init__(self) -> None:
        if self.status not in VALID_FASTA_CONTIG_STATUS:
            raise ValueError(f"unknown FASTA contig status: {self.status!r}")

    def identity_problem(self) -> str | None:
        """The reason identity prevents a read, or None when the contig is bound."""
        if self.status == "absent":
            return f"local FASTA: no such contig {self.chrom}"
        if self.status == "digest_mismatch":
            return (
                f"local FASTA: {self.chrom} digest mismatch "
                f"(found {self.found_digest}, expected {self.expected_accession})"
            )
        return None


@dataclass(frozen=True)
class _Entry:
    name: str
    length: int
    offset: int
    bases: int
    width: int

    def position(self, base: int) -> int:
        line, column = divmod(base, self.bases)
        return self.offset + line * self.width + column

    def read(self, stream: BinaryIO, start: int, end: int) -> bytes:
        if start == end:
            return b""
        first = self.position(start)
        stream.seek(first)
        size = self.position(end - 1) + 1 - first
        data = stream.read(size)
        # A stale index with the wrong wrap width can still yield the correct *whole*
        # sequence when newlines are stripped. Its random seeks would return other bases.
        gap = self.width - self.bases
        first_break = self.bases - start % self.bases
        newline = (b"", b"\n", b"\r\n")[gap]
        for i, char in enumerate(newline):
            column = data[first_break + i :: self.width]
            if column.count(char) != len(column):
                raise ValueError("FASTA line endings do not match the .fai")
        bases = data.translate(None, b"\r\n").upper()
        if len(data) != size or len(bases) != end - start:
            raise ValueError("FASTA length or line wrapping does not match the .fai")
        return bases

    def digest(self, stream: BinaryIO) -> str:
        # The library takes a single buffer. Strip line endings in chunks to keep peak
        # storage near one chromosome, with no second chromosome-sized uppercase copy.
        sequence = bytearray()
        for start in range(0, self.length, 1024 * 1024):
            sequence.extend(self.read(stream, start, min(self.length, start + 1024 * 1024)))
        return "SQ." + digests.sha512t24u(sequence)


# Bound each sequence read even for a chromosome written on one unwrapped line.
_READ_SIZE = 1024 * 1024
_SEQUENCE_WHITESPACE = re.compile(rb"\s")


def _index_path(path: Path) -> Path:
    return Path(f"{path}.fai")


def _compressed(path: Path, magic: bytes) -> bool:
    return magic == b"\x1f\x8b" or path.suffix.lower() in {".gz", ".bgz", ".bgzf"}


def _primary_accession(name: str) -> str | None:
    return refget_accession(GRCH38_ACCESSIONS.get(name, name))


def _header_name(stream: BinaryIO, header: bytes, line: int) -> str:
    """Keep the first token and consume even a long description in bounded reads."""
    # Decode across buffers; an undecodable byte in the discarded description is harmless.
    decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")
    token: list[str] = []
    complete = False
    chunk = header[1:]
    while chunk:
        if not complete:
            fragment = decoder.decode(chunk)
            if not token:
                fragment = fragment.lstrip()
            separator = re.search(r"\s", fragment)
            if separator is not None:
                fragment = fragment[: separator.start()]
                complete = True
            if fragment:
                token.append(fragment)
        if chunk.endswith(b"\n"):
            break
        chunk = stream.readline(_READ_SIZE)
    name = "".join(token)
    if not name:
        raise FastaConfigurationError(f"line {line}: missing contig name")
    if not name.isprintable():
        raise FastaConfigurationError(f"line {line}: invalid contig name {name!r}, expected printable UTF-8")
    return name


def _sequence_line(stream: BinaryIO, chunk: bytes, name: str, line: int) -> tuple[int, int]:
    """Measure one physical line, including a CRLF split at the read boundary."""
    width = 0
    while chunk:
        if len(chunk) == _READ_SIZE and chunk.endswith(b"\r"):
            chunk += stream.read(1)
        width += len(chunk)
        ending = 2 if chunk.endswith(b"\r\n") else int(chunk.endswith(b"\n"))
        if _SEQUENCE_WHITESPACE.search(chunk, 0, len(chunk) - ending):
            raise FastaConfigurationError(
                f"contig {name}, line {line}: whitespace in sequence or invalid line ending"
            )
        if not chunk.isascii():
            raise FastaConfigurationError(f"contig {name}, line {line}: non-ASCII sequence")
        if ending or len(chunk) < _READ_SIZE:
            return width - ending, width
        chunk = stream.readline(_READ_SIZE)
    return width, width


def _scan_index(stream: BinaryIO) -> list[_Entry]:
    entries: list[_Entry] = []
    names: set[str] = set()
    primaries: set[str] = set()
    line = 1
    header = stream.readline(_READ_SIZE)
    if not header.startswith(b">"):
        raise FastaConfigurationError("before first contig, line 1: expected FASTA header")

    while header:
        name = _header_name(stream, header, line)
        if name in names:
            raise FastaConfigurationError(f"contig {name}, line {line}: duplicate name")
        names.add(name)
        accession = _primary_accession(name)
        if accession is not None:
            if accession in primaries:
                raise FastaConfigurationError(
                    f"contig {name}, line {line}: ambiguous entries for {_CHROM[accession]}"
                )
            primaries.add(accession)

        header_line = line
        offset = stream.tell()
        length = bases = width = previous_bases = 0
        while True:
            line += 1
            chunk = stream.readline(_READ_SIZE)
            if not chunk or chunk.startswith(b">"):
                header = chunk
                break
            size, byte_width = _sequence_line(stream, chunk, name, line)
            if not size:
                raise FastaConfigurationError(f"contig {name}, line {line}: empty sequence line")
            if not length:
                bases, width = size, byte_width
            elif previous_bases != bases:
                raise FastaConfigurationError(
                    f"contig {name}, line {line - 1}: short line before end of contig (wrap width {bases})"
                )
            elif size > bases:
                raise FastaConfigurationError(f"contig {name}, line {line}: exceeds wrap width {bases}")
            elif byte_width != size and byte_width - size != width - bases:
                raise FastaConfigurationError(f"contig {name}, line {line}: mixed line endings")
            length += size
            previous_bases = size
        if not length:
            raise FastaConfigurationError(f"contig {name}, line {header_line}: no sequence")
        entries.append(_Entry(name, length, offset, bases, width))
    return entries


def write_fasta_index(path: Path) -> Path:
    """Index an uncompressed FASTA in one pass and atomically replace its five-column .fai."""
    index = _index_path(path)
    try:
        with path.open("rb") as stream:
            if _compressed(path, stream.peek(2)[:2]):
                raise FastaConfigurationError(
                    f"before first contig, line 1: compressed FASTA is unsupported: {path}"
                )
            entries = _scan_index(stream)
        # A shared reference index takes ordinary creation permissions under the operator's umask.
        # Only clean up after exclusive creation succeeds: a colliding name belongs to another writer.
        part_path = index.with_name(f".{index.name}.{uuid4().hex}.part")
        part = part_path.open("x", encoding="utf-8", newline="\n")  # noqa: SIM115 — closed before replace
        try:
            with part:
                for entry in entries:
                    part.write(
                        f"{entry.name}\t{entry.length}\t{entry.offset}\t{entry.bases}\t{entry.width}\n"
                    )
                part.flush()
                os.fsync(part.fileno())
            part_path.replace(index)
        finally:
            part_path.unlink(missing_ok=True)
    except OSError as exc:
        raise FastaConfigurationError(f"cannot index FASTA {path}: {exc}") from exc
    return index


def _stamp(stat: os.stat_result) -> tuple[int, int]:
    return stat.st_size, stat.st_mtime_ns


@dataclass
class _CacheState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Set on a failed sidecar write. Fresh proxies for a read-only reference reuse these digests.
    memory: dict[str, str] | None = None


@lru_cache(maxsize=64)
def _cache_state(path: Path, fasta_stamp: tuple[int, int], index_stamp: tuple[int, int]) -> _CacheState:
    return _CacheState()


class FastaReference:
    """The get_metadata/get_sequence interface used by vrs-python. Never opens a network source."""

    def __init__(self, uri: str) -> None:
        parsed = urlsplit(uri)
        self.path = Path(unquote(parsed.path))
        if (
            not uri.startswith(FASTA_SCHEME + "///")
            or parsed.netloc
            or not self.path.is_absolute()
            or parsed.path.startswith("//")
            or parsed.query
            or parsed.fragment
        ):
            raise FastaConfigurationError("expected a local absolute path: fasta+file:///abs/path.fa")
        self.index = _index_path(self.path)
        self.cache = Path(f"{self.path}.refget.json")
        self._entries: dict[str, _Entry] = {}
        try:
            with self.path.open("rb") as stream:
                if _compressed(self.path, stream.read(2)):
                    raise FastaConfigurationError(f"compressed FASTA is unsupported: {self.path}")
            self.stamp = _stamp(self.path.stat())
            self.index_stamp = _stamp(self.index.stat())
            for line in self.index.read_text().splitlines():
                name, length, offset, bases, width = line.split("\t")
                entry = _Entry(name, int(length), int(offset), int(bases), int(width))
                if (
                    entry.length < 1
                    or entry.offset < 0
                    or entry.bases < 1
                    or entry.width - entry.bases not in (0, 1, 2)
                ):
                    raise ValueError(f"invalid .fai coordinates for {name}")
                accession = _primary_accession(name)
                if accession:
                    if accession in self._entries:
                        raise ValueError(f"ambiguous .fai entries for {_CHROM[accession]}")
                    self._entries[accession] = entry
        except (OSError, ValueError) as exc:
            raise FastaConfigurationError(f"cannot open indexed FASTA {self.path}: {exc}") from exc
        self._state = _cache_state(self.cache, self.stamp, self.index_stamp)
        self._digests = self._load_cache()

    def current(self) -> bool:
        """Whether the FASTA and its index still have their opening sizes and modification times."""
        return self.stamp == _stamp(self.path.stat()) and self.index_stamp == _stamp(self.index.stat())

    def _load_cache(self) -> dict[str, str]:
        try:
            saved = json.loads(self.cache.read_bytes())
        except (OSError, ValueError):
            return {}
        if (
            isinstance(saved, dict)
            and saved.get("fasta") == list(self.stamp)
            and saved.get("fai") == list(self.index_stamp)
            and isinstance(saved.get("digests"), dict)
        ):
            return {k: v for k, v in saved["digests"].items() if k in self._entries and isinstance(v, str)}
        return {}

    def _save_cache(self) -> None:
        try:
            with atomic_writer(self.cache) as handle:
                json.dump(
                    {
                        "fasta": self.stamp,
                        "fai": self.index_stamp,
                        "digests": self._load_cache() | self._digests,
                    },
                    handle,
                )
        except OSError as exc:
            self._state.memory = self._digests
            logger.warning("Could not write %s (%s); keeping FASTA digests in memory", self.cache, exc)

    def _identity(self, accession: str, stream: BinaryIO) -> FastaContigIdentity:
        chrom = _CHROM[accession]
        entry = self._entries.get(accession)
        if entry is None:
            return FastaContigIdentity(chrom, None, accession, None, "absent")
        with self._state.lock:
            if _stamp(os.fstat(stream.fileno())) != self.stamp:
                raise OSError(f"local FASTA changed while reading {chrom}")
            known = self._digests if self._state.memory is None else self._state.memory
            if accession not in known:
                digest = entry.digest(stream)
                if _stamp(os.fstat(stream.fileno())) != self.stamp:
                    raise OSError(f"local FASTA changed while digesting {chrom}")
                known[accession] = digest
                if self._state.memory is None:
                    self._save_cache()
            actual = known[accession]
        status = "bound" if actual == accession else "digest_mismatch"
        return FastaContigIdentity(chrom, entry.name, accession, actual, status)

    def contig_identity(self, chroms: Iterable[str] | None = None) -> dict[str, FastaContigIdentity]:
        """Return identities keyed by canonical GRCh38 chromosome, for all primaries by default.

        A cold full pass reads and hashes every indexed primary in full (about 155 seconds at
        nice 19 on the registry's Ensembl FASTA). A subset hashes only the requested contigs,
        and later reads reuse the same cached digests. An off-table request raises ValueError.
        """
        if chroms is None:
            chroms = REFGET_GRCh38
        elif isinstance(chroms, str):
            chroms = (chroms,)
        records = {}
        with self.path.open("rb") as stream:
            for chrom in chroms:
                accession = refget_accession(chrom)
                if accession is None:
                    raise ValueError(f"local FASTA: {chrom} is outside the GRCh38 refget table")
                record = self._identity(accession, stream)
                records[record.chrom] = record
        if not self.current():
            raise OSError(f"indexed FASTA changed while checking contig identity: {self.path}")
        return records

    def _verified(self, identifier: str, stream: BinaryIO) -> _Entry:
        accession = identifier.removeprefix("ga4gh:")
        if accession not in _CHROM:
            raise ValueError(f"local FASTA: {identifier} is outside the GRCh38 refget table")
        problem = self._identity(accession, stream).identity_problem()
        if problem is not None:
            raise ValueError(problem)
        return self._entries[accession]

    def get_metadata(self, identifier: str) -> dict[str, int]:
        """Return the verified primary contig's length. An absent or mismatched contig raises ValueError."""
        with self.path.open("rb") as stream:
            return {"length": self._verified(identifier, stream).length}

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        """Read uppercased bases from the verified contig over a zero-based, half-open interval."""
        with self.path.open("rb") as stream:
            entry = self._verified(identifier, stream)
            lo, hi, _ = slice(start, end).indices(entry.length)
            result = entry.read(stream, lo, max(lo, hi))
            if _stamp(os.fstat(stream.fileno())) != self.stamp:
                raise OSError(f"local FASTA changed while reading {identifier}")
            return result.decode("ascii")

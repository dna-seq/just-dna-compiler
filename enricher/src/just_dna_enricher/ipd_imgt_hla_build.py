"""Build a per-host IPD-IMGT/HLA witness from the curators' verbatim release files."""

import csv
import io
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from just_dna_format.integrity import sha256_bytes
from just_dna_format.snapshot import (
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
    SnapshotRelease,
    begin_snapshot_write,
    read_release,
)
from tenacity import retry

from just_dna_enricher.licensing import IPD_IMGT_HLA_TERMS, LicenseRefusal, check_declared_use
from just_dna_enricher.locations import IPD_ALLELE_FILES
from just_dna_enricher.net import (
    EndpointRetired,
    _jittered_backoff,
    _log_give_up,
    _log_retry,
    attempt_floor,
    raise_if_retired,
    release_dataset,
    retry_if_transient,
)
from just_dna_enricher.transaction import spec_lock

DEFAULT_PIN = "3.66.0"
RAW_REPOSITORY = "https://raw.githubusercontent.com/ANHIG/IMGTHLA"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
LICENCE = "LICENCE.md"


class IpdHlaUnavailable(RuntimeError):
    """The release could not be obtained or its files could not answer the question."""


class IpdHlaRetired(IpdHlaUnavailable, EndpointRetired):
    """The curators no longer serve this tagged path (404/410)."""


def _url(pin: str, name: str) -> str:
    if not VERSION.fullmatch(pin):
        raise IpdHlaUnavailable(f"Expected a numeric IPD-IMGT/HLA release pin, got {pin!r}")
    return f"{RAW_REPOSITORY}/v{pin}-alpha/{name}"


_CITING = re.compile(r"citing\s+the\s+following;?", re.IGNORECASE)
_OPPOSED = re.compile(r"opposed\s+to\s+the\s+mirroring", re.IGNORECASE)


def _notice(data: bytes) -> str:
    """The citations the tagged licence asks for, and its two conditions, for the source row's `notice`.

    Not the whole LICENCE.md: it also carries funding, a disclaimer and a CE-marking section, none of
    them terms, and `license_sha256` already pins the full text. The citations sit between "citing the
    following" and the paragraph opposing mirroring (3.66.0); a licence without that shape refuses,
    rather than writing a notice that silently drops the papers.
    """
    text = data.decode("utf-8")
    lower = text.lower()
    if "creative commons" not in lower and "creativecommons.org" not in lower:
        raise IpdHlaUnavailable(f"{LICENCE} does not contain the expected IPD licence notice")
    # The licence wraps its prose, so "citing\nthe following" spans a line break in 3.66.0.
    opening = _CITING.search(text)
    closing = _OPPOSED.search(text)
    if opening is None or closing is None or closing.start() <= opening.end():
        raise IpdHlaUnavailable(f"{LICENCE} does not state its citations where the IPD licence does")
    # From the end of "citing the following;" to the paragraph that opposes mirroring.
    body = text[opening.end() : text.rfind("\n\n", 0, closing.start())]
    citations = [" ".join(block.split()) for block in body.split("\n\n") if block.strip()]
    if not citations:
        raise IpdHlaUnavailable(f"{LICENCE} names no citations")
    return (
        "CC BY-ND. Cite:\n\n"
        + "\n\n".join(citations)
        + "\n\nThe curators oppose mirroring their data and ask that a modified version is distributed "
        "only with their permission."
    )


def _table(data: bytes, name: str) -> tuple[str, dict[str, str]]:
    stream = io.StringIO(data.decode("utf-8"), newline="")
    if stream.readline().rstrip("\r\n") != f"# file: {name}":
        raise IpdHlaUnavailable(f"Unexpected IPD-IMGT/HLA file header for {name}")
    versions = []
    for line in stream:
        if not line.startswith("#"):
            break
        if line.startswith("# version: IPD-IMGT/HLA "):
            versions.append(line.removeprefix("# version: IPD-IMGT/HLA ").strip())
    else:
        raise IpdHlaUnavailable(f"{name} has no CSV header")
    if len(versions) != 1 or not VERSION.fullmatch(versions[0]):
        raise IpdHlaUnavailable(f"{name} has no unambiguous IPD-IMGT/HLA version")
    columns = ["AlleleID", "Allele"]
    if name == IPD_ALLELE_FILES[1]:
        columns.append("Description")
    if next(csv.reader([line])) != columns:
        raise IpdHlaUnavailable(f"Unexpected CSV header in {name}")
    rows: dict[str, str] = {}
    # A later `#` line opens another section, which repeats the CSV header before its rows. The real
    # `Deleted_alleles.txt` of 3.66.0 has two, `# Deleted Alleles` and `# Alleles With Suffix Changes`
    # (the names withdrawn when a suffix was added, `A*01:159` becoming `A*01:159Q`); both are
    # withdrawals and both are read. The first section's title is consumed with the file header above.
    expect_header = False
    for fields in csv.reader(stream, strict=True):
        if fields and fields[0].startswith("#"):
            expect_header = True
            continue
        if expect_header:
            if fields != columns:
                raise IpdHlaUnavailable(f"Unexpected CSV header after a section line in {name}")
            expect_header = False
            continue
        if len(fields) != len(columns) or not all(fields):
            raise IpdHlaUnavailable(f"Invalid CSV row in {name}, expected {len(columns)} populated fields")
        rows[fields[1]] = fields[-1]
    if not rows:
        raise IpdHlaUnavailable(f"{name} has no allele rows")
    return versions[0], rows


def _read_table(data: bytes, name: str) -> tuple[str, dict[str, str]]:
    try:
        return _table(data, name)
    except (UnicodeError, csv.Error) as exc:
        raise IpdHlaUnavailable(f"Unreadable {name}: {exc}") from exc


@dataclass
class IpdHlaClient:
    transport: httpx.BaseTransport | None = None

    @retry(
        before_sleep=_log_retry,
        retry_error_callback=_log_give_up,
        stop=attempt_floor(3),
        wait=_jittered_backoff(base=1, cap=15),
        retry=retry_if_transient(),
        reraise=True,
    )
    def _get(self, url: str) -> bytes:
        with httpx.Client(transport=self.transport, timeout=30, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def fetch(self, pin: str, name: str) -> bytes:
        url = _url(pin, name)
        try:
            data = self._get(url)
        except httpx.HTTPStatusError as exc:
            raise_if_retired(exc, IpdHlaRetired, "IPD-IMGT/HLA")
            if exc.response.status_code == 404:
                raise IpdHlaRetired(
                    f"IPD-IMGT/HLA no longer serves {url} ({exc.response.status_code})"
                ) from exc
            raise IpdHlaUnavailable(f"Could not read {url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise IpdHlaUnavailable(f"Could not read {url}: {exc}") from exc
        if name in IPD_ALLELE_FILES and data.split(b"\n", 1)[0].rstrip(b"\r") != f"# file: {name}".encode():
            raise IpdHlaUnavailable(f"Unexpected IPD-IMGT/HLA file header for {url}")
        return data


@dataclass
class AlleleLists:
    release: str
    assigned: set[str]
    deleted: dict[str, str]
    notice: str
    #: The tagged LICENCE.md whole, which the licence row's `license_sha256` binds; `notice` is its citations.
    licence_text: str


def _lists(contents: dict[str, bytes], pin: str | None) -> AlleleLists:
    active, deleted = IPD_ALLELE_FILES
    version, assigned = _read_table(contents[active], active)
    other, withdrawn = _read_table(contents[deleted], deleted)
    if version != other or (pin is not None and version != pin):
        raise IpdHlaUnavailable(
            f"Release mismatch: {active} states {version}, {deleted} states {other}, pin {pin}"
        )
    try:
        notice = _notice(contents[LICENCE])
    except UnicodeError as exc:
        raise IpdHlaUnavailable(f"Unreadable {LICENCE}: {exc}") from exc
    return AlleleLists(
        release_dataset(IPD_IMGT_HLA_TERMS.source, version),
        set(assigned),
        withdrawn,
        notice,
        contents[LICENCE].decode("utf-8"),
    )


def build_snapshot(
    out_dir: Path,
    *,
    pin: str = DEFAULT_PIN,
    source: Path | None = None,
    declared_use: str = "unstated",
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Stage and validate the entire release before touching a previously described snapshot."""
    files = (*IPD_ALLELE_FILES, LICENCE)
    urls = {name: _url(pin, name) for name in files}
    if source is None:
        reason = check_declared_use(IPD_IMGT_HLA_TERMS, declared_use)
        if reason is not None:
            raise LicenseRefusal(reason)
    elif source.name != IPD_ALLELE_FILES[0]:
        raise IpdHlaUnavailable(f"Supply {IPD_ALLELE_FILES[0]} with its companion files beside it")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    client = IpdHlaClient(transport)
    with tempfile.TemporaryDirectory(dir=out_dir.parent) as temporary:
        stage = Path(temporary)
        contents = {}
        for name in files:
            contents[name] = (
                client.fetch(pin, name) if source is None else source.with_name(name).read_bytes()
            )
            with (stage / (name + ".part")).open("xb") as part:
                part.write(contents[name])
        lists = _lists(contents, pin)
        digests = {name: sha256_bytes(contents[name]) for name in IPD_ALLELE_FILES}
        out_dir.mkdir(exist_ok=True)
        with spec_lock(out_dir, error=IpdHlaUnavailable):
            snapshot = begin_snapshot_write(out_dir)
            payload = out_dir / SNAPSHOT_DATA_DIRNAME
            payload.mkdir(exist_ok=True)
            for name in IPD_ALLELE_FILES:
                (stage / (name + ".part")).replace(payload / name)
            (stage / (LICENCE + ".part")).replace(out_dir / SNAPSHOT_LICENSE_FILENAME)
            snapshot.commit(
                SnapshotRelease(
                    dataset=lists.release,
                    source_url=urls if source is None else None,
                    source_sha256=digests,
                    license=IPD_IMGT_HLA_TERMS.license,
                    license_sha256=sha256_bytes(contents[LICENCE]),
                )
            )
    return lists.release


def load_lists(directory: Path) -> AlleleLists:
    release = read_release(directory)
    if release is None:
        raise IpdHlaUnavailable(f"No readable IPD-IMGT/HLA release in {directory}")
    contents = {name: (directory / SNAPSHOT_DATA_DIRNAME / name).read_bytes() for name in IPD_ALLELE_FILES}
    digests = {name: sha256_bytes(body) for name, body in contents.items()}
    contents[LICENCE] = (directory / SNAPSHOT_LICENSE_FILENAME).read_bytes()
    if digests != release.source_sha256 or sha256_bytes(contents[LICENCE]) != release.license_sha256:
        raise IpdHlaUnavailable(f"Files in {directory} differ from the recorded IPD-IMGT/HLA release")
    lists = _lists(contents, None)
    if lists.release != release.dataset:
        raise IpdHlaUnavailable(
            f"The lists in {directory} disagree with its recorded release {release.dataset}"
        )
    return lists

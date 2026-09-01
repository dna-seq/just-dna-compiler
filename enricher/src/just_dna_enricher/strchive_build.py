"""Build the STRchive snapshot the repeat-band check and the repeat drafter read.

The catalogue is one 300 KB JSON file in a public MIT-licensed repository, so this builder is the
smallest in the tree: stream the file, hash it while streaming, write it beside a `release.json`. No
parquet, no reduction — the shape the readers want is the shape the source publishes, and reducing it
would put a second schema between the source and the check for no gain.

**A release tag, not `main`.** The upstream default branch moves, and a comparison whose reference is
"whatever was there that afternoon" cannot be re-run. `--release v2.26.0` pins the raw URL to a tag
and `release.json` records the label, which is what the verification record then names. Building from
`main` is allowed and records `dataset=None` rather than inventing a label out of a date or a
checksum — nobody-asked is a third state, and an unlabelled snapshot is honestly unlabelled.

**No `--offline` and no `--use`**, both for the reasons the tier already settled. A builder's
off-switch is passing the local file instead of `--download`, and `check_declared_use` gates a
*fetch*: STRchive's terms are an MIT grant, so the gate would return the same answer on every run.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.strchive import (
    CATALOGUE_FILENAME,
    RELEASE_FILENAME,
    SOURCE_NAME,
    StrchiveError,
    StrchiveUnavailable,
    load_strchive_catalogue,
)

logger = logging.getLogger(__name__)

#: The catalogue on the default branch. Used when no release is pinned, and named here rather than
#: assembled at the call site so `release.json` records the URL the bytes actually came from.
DEFAULT_STRCHIVE_URL = (
    "https://raw.githubusercontent.com/dashnowlab/STRchive/main/data/STRchive-loci.json"
)


def catalogue_url(release: str | None = None) -> str:
    """The raw URL for one release tag, or the default branch when nothing is pinned."""
    if not release:
        return DEFAULT_STRCHIVE_URL
    return (
        f"https://raw.githubusercontent.com/dashnowlab/STRchive/{release}/data/{CATALOGUE_FILENAME}"
    )


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


@dataclass
class StrchiveBuildResult:
    """Where the snapshot landed, what it holds, and what it came from."""

    out_dir: Path
    catalogue_file: Path
    release_file: Path
    locus_count: int
    source_sha256: str
    source_url: str
    dataset: str | None


def download_catalogue(dest: Path, url: str = DEFAULT_STRCHIVE_URL) -> tuple[Path, str]:
    """Stream the catalogue to `dest` (atomic `.part` rename), returning the path and its sha256.

    Core `httpx` with the hash taken while streaming, the same shape every bulk builder here uses —
    `download.py` is HuggingFace snapshot provisioning and `net.py` is pacing for live API clients, so
    neither is what a one-file download reaches for.

    **`httpx`'s exceptions do not leave this function** (`@client-exception-contract`): a mistyped
    release tag is a 404, and it must reach the CLI as `STRCHIVE BUILD FAILED: …` rather than as a
    raw `HTTPStatusError` traceback. The half-written `.part` goes with it, so a failed run leaves the
    directory as it found it.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading the STRchive catalogue from %s ...", url)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=None) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as handle:
                for chunk in resp.iter_bytes():
                    handle.write(chunk)
                    hasher.update(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise StrchiveUnavailable(
            f"could not download the STRchive catalogue from {url}: {exc}"
        ) from exc
    tmp.replace(dest)
    digest = hasher.hexdigest()
    logger.info("Downloaded %s (sha256 %s)", dest, digest)
    return dest, digest


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_strchive_snapshot(
    out_dir: Path,
    *,
    catalogue: Path | None = None,
    release: str | None = None,
    url: str | None = None,
) -> StrchiveBuildResult:
    """Put `STRchive-loci.json` + `release.json` in `out_dir`, from a local file or a download.

    The catalogue is copied rather than re-serialized: a rebuild is byte-identical to the upstream
    file, so `source_sha256` describes what a reader can verify with `sha256sum` and not a
    re-encoding of it. Parsing happens only to refuse an unusable download before it is committed.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / CATALOGUE_FILENAME
    # **The incoming bytes land beside the snapshot, never on it, until they have parsed.** Writing
    # the catalogue first and validating after would let a bad rebuild leave new bytes under the
    # previous run's `release.json`, whose `source_sha256`, `locus_count` and `dataset` then describe
    # a file that is gone — and `check-repeat-bands` would attest the new catalogue under the old
    # release label. The stale `release.json` is removed before the rename, so the only window a
    # reader can see is *catalogue with no provenance*, which reads honestly as an unlabelled release.
    incoming = out_dir / (CATALOGUE_FILENAME + ".incoming")

    if catalogue is not None:
        source = Path(catalogue)
        if not source.is_file():
            raise StrchiveError(f"no STRchive catalogue at {source}")
        source_url = url or f"file://{source.resolve()}"
        atomic_write_text(incoming, source.read_text(encoding="utf-8"))
    else:
        source_url = url or catalogue_url(release)
        download_catalogue(incoming, source_url)
    source_sha256 = _sha256_file(incoming)

    parsed = load_strchive_catalogue(incoming)
    if not parsed.loci:
        incoming.unlink(missing_ok=True)
        raise StrchiveError(f"{source_url} parsed to zero loci; refusing to record it as a snapshot")
    (out_dir / RELEASE_FILENAME).unlink(missing_ok=True)
    incoming.replace(target)

    dataset = f"{SOURCE_NAME}_{release}" if release else None
    release_file = _write_release_json(
        out_dir,
        source_url=source_url,
        source_sha256=source_sha256,
        locus_count=len(parsed.loci),
        dataset=dataset,
    )
    return StrchiveBuildResult(
        out_dir=out_dir,
        catalogue_file=target,
        release_file=release_file,
        locus_count=len(parsed.loci),
        source_sha256=source_sha256,
        source_url=source_url,
        dataset=dataset,
    )


def _write_release_json(
    out_dir: Path,
    *,
    source_url: str,
    source_sha256: str,
    locus_count: int,
    dataset: str | None,
) -> Path:
    """The provenance beside the catalogue, written atomically.

    There is no shared helper for this and deliberately so — each builder owns its own, because the
    fields that matter differ per source. `built_at` is the only per-run-varying byte and it lives
    here rather than in the catalogue, which stays identical to what upstream published.
    """
    release = {
        "source": SOURCE_NAME,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "locus_count": locus_count,
        "dataset": dataset,
        "license": "MIT",
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    atomic_write_text(path, json.dumps(release, indent=2, sort_keys=True) + "\n")
    return path

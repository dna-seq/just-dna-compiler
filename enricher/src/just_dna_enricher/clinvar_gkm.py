"""ClinGen's ClinVar-GKM, cut to its indels: an offline witness for where an indel sits (RM305).

**What this lane is for, and what it is not.** Three checks need to know whether a placement is right
(RM267's two authorities, RM270's respelling, RM292's named witness), and each compares today against a
source that shares our failure. ClinVar-GKM republishes ClinVar in GA4GH form, through a pipeline that
is not ours, with a spelling-independent VRS id on every allele. That makes it a **witness**: the lane
answers *where does an independent party place this indel*, and nothing else. It runs no check of its
own; a check names it as what it checked against. Clinical significance still comes from the `clinvar`
lane.

**Indels only** (decided 2026-11-04). The ~4.6 M alleles are mostly substitutions, whose placement is
not in doubt and whose ids the format tier mints with the stdlib. What is kept is every allele whose
SPDI deletes and inserts a *different* number of bases: a net insertion or a net deletion. That drops
substitutions, same-length MNVs, and the reference-agreeing `ReferenceLengthExpression` alleles
(`NC_000021.9:g.45504512_45504520=`, deleting and inserting the same sequence), whichever state type
carries them. An allele with no SPDI expression (GRCh37- or transcript-only names) and one off the
GRCh38 primary assembly (one T2T accession) are dropped too; the build counts each class.

**Where the bytes come from.** One Parquet set under `https://data.clinvar-gkm.org/v1/1.1/parquet/`,
**overwritten in place every week**, with no dated or archived copies (docs/probes/LANES_0_8.md §3.1).
So a release cannot be pinned by URL. The pin is `(source_release, sha256)` from the set's own
`manifest.json`, and the builder refuses bytes that do not match it: a file overwritten between the
manifest read and the download is **drift**, and a build from it would describe one release with
another's bytes. Both inputs are downloaded whole and read locally, which is what the source asks
("Download the Parquet files you need, then query them locally. The R2 hosting has rate limits and is
designed for file downloads, not as a remote query endpoint"). A whole download also keeps the one
failure the probe saw off this path: an R2 range request that came back `200` with the whole file. A
truncated or partial body cannot pass the size and digest check either way.

**Two keys every row has, and one most rows have.** The VRS id and the gnomAD-style VCF spelling
(`4-87310240-T-TA`) are on every allele; the rsID is on about 71% of the indels (LANES §3.5), and lives
in `variation.parquet`, joined through the variation's `DefiningAlleleConstraint`. A reader keys on the
first two and treats the rsID as secondary.

**The VRS version is declared, not measured.** ClinVar-GKM's 1.0.0 changelog says its ids are minted
under VRS 2.1.1; neither the Parquet nor its manifest carries a version (LANES §3.6). So `release.json`
records `vrs_version` with the basis beside it. This tier mints under 2.0 (RM304), and 2.0 and 2.1 move
the ids of some ambiguous insertions, so **a VRS-id comparison against this witness is only sound when
the minor matches** (`ids_comparable`). Until vrs-python ships 2.1, the VCF spelling is the key a
comparison uses on every row; the caller supplies it left-normalized, since the `gnomad` expression is.
"""

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from just_dna_format.snapshot import SNAPSHOT_DATA_DIRNAME, SnapshotRelease, read_release
from just_dna_format.vrs import vrs_spec_release
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.net import PacingGate, attempt_floor

try:  # the one guarded optional import (CLAUDE.md): polars reads the slice
    import polars as pl
except ImportError:  # pragma: no cover - exercised only without polars
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: The licensed source, as `SourceRow.source` spells it and as `licensing.CLINVAR_GKM_TERMS` does. Its
#: own name, not a second surface of `clinvar`: ClinGen's transformation is a different publisher's
#: work under different terms, and `@write-the-sourcerow` refuses a second surface claiming the lane's
#: `(source, layer)` row.
CLINVAR_GKM_SOURCE = "clinvar_gkm"

#: The release line this tier reads. 1.1.0 moved every URL here; `v1/1.0` is frozen and carries no
#: Parquet (`v1/1.0/parquet/allele.parquet` answers 404).
CLINVAR_GKM_BASE_URL = "https://data.clinvar-gkm.org/v1/1.1"
PARQUET_MANIFEST_URL = f"{CLINVAR_GKM_BASE_URL}/parquet/manifest.json"
RELEASE_INDEX_URL = f"{CLINVAR_GKM_BASE_URL}/index.json"
ALLELE_FILE = "allele.parquet"
VARIATION_FILE = "variation.parquet"
#: The two inputs, in the order they are fetched.
INPUT_FILES: tuple[str, ...] = (ALLELE_FILE, VARIATION_FILE)


def parquet_url(name: str) -> str:
    """The URL of one file of the published Parquet set."""
    return f"{CLINVAR_GKM_BASE_URL}/parquet/{name}"


#: The slice, under `data/`.
WITNESS_PARQUET = "clinvar_gkm-indels.parquet"

#: The release label's prefix. Not ClinVar's `clinvar_`: ClinVar-GKM's own `dataset` string
#: (`clinvar_2026_10_24_v2_6_1`) would sit in ClinVar's label space and read as a ClinVar release.
CLINVAR_GKM_DATASET_PREFIX = "clinvar_gkm_"

#: The VRS version ClinVar-GKM mints under, **declared** by its 1.0.0 changelog ("First official
#: release on the finalized GKM standards — VRS 2.1.1, …"); the bytes state none.
CLINVAR_GKM_VRS_VERSION = "2.1.1"
CLINVAR_GKM_VRS_VERSION_BASIS = (
    "declared by the ClinVar-GKM 1.0.0 changelog (2026-10-12); neither the Parquet nor its "
    "manifest.json states a VRS version"
)

#: Pause between the manifest/index requests. The host rate-limits with 429 and states no budget; two
#: small JSON reads per build need no more than courtesy.
CLINVAR_GKM_MIN_INTERVAL = 1.0

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ClinVarGkmError(RuntimeError):
    """The ClinVar-GKM lane could not be built or read."""


class ClinVarGkmUnavailable(ClinVarGkmError):
    """The source could not be asked at all: a failed request, never "it published nothing".

    A subclass so an `except ClinVarGkmError` keeps catching it, and a caller that has to tell
    *unreachable* from *unreadable* can (`@client-exception-contract`): the narrow arm goes first.
    """


class ClinVarGkmMismatch(ClinVarGkmError):
    """The bytes are not the ones the manifest states: the set was overwritten, or the body is partial."""


# ── the source's own record ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ManifestFile:
    """One file of the published Parquet set, as `manifest.json` states it."""

    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class GkmManifest:
    """`parquet/manifest.json`: which release the one Parquet set holds, and each file's digest.

    `source_release` is the ClinVar release the set was built from, and the half of the pin a label
    is made of. The licence fields are kept verbatim because the snapshot's `LICENSE.txt` quotes them.
    """

    source_release: str
    files: dict[str, ManifestFile]
    dataset: str | None = None
    build_date: str | None = None
    schema_version: str | None = None
    license_id: str | None = None
    license_scope: str | None = None
    attribution: str | None = None
    disclaimer: str | None = None
    data_use_policy: str | None = None

    def file(self, name: str) -> ManifestFile:
        """The manifest's entry for `name`, or a refusal: a build cannot verify a file it does not list."""
        entry = self.files.get(name)
        if entry is None:
            raise ClinVarGkmError(f"manifest.json lists no {name}; the set's layout changed")
        return entry


def parse_manifest(text: str) -> GkmManifest:
    """Read `manifest.json`. A missing release or file digest is a refusal, never a default."""
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise ClinVarGkmError(f"manifest.json is not JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClinVarGkmError("manifest.json is not a JSON object")
    release = str(raw.get("source_release") or "").strip()
    if not release:
        raise ClinVarGkmError("manifest.json states no source_release, so nothing can be pinned")
    files: dict[str, ManifestFile] = {}
    entries = raw.get("files") or []
    if not isinstance(entries, list):
        raise ClinVarGkmError(f"manifest.json's files is not a list: {entries!r}")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ClinVarGkmError(f"manifest.json has a file entry that is not an object: {entry!r}")
        name, size, sha = entry.get("name"), entry.get("size"), entry.get("sha256")
        sized = isinstance(size, int) and not isinstance(size, bool)
        if not isinstance(name, str) or not sized or not isinstance(sha, str):
            raise ClinVarGkmError(f"manifest.json has a file entry without name/size/sha256: {entry!r}")
        files[name] = ManifestFile(name, size, sha.strip().lower())
    licence = raw.get("license") if isinstance(raw.get("license"), dict) else {}
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return GkmManifest(
        source_release=release,
        files=files,
        dataset=raw.get("dataset"),
        build_date=raw.get("build_date"),
        schema_version=raw.get("schema_version"),
        license_id=licence.get("id"),
        license_scope=licence.get("scope"),
        attribution=raw.get("attribution"),
        disclaimer=raw.get("disclaimer"),
        data_use_policy=source.get("data_use_policy"),
    )


def clinvar_gkm_release_label(source_release: str | None) -> str | None:
    """`clinvar_gkm_<source_release>`, or `None` when no release is stated.

    One formula, called by the builder that writes `dataset` and by the currency probe that reads the
    live manifest, so a snapshot and the source name one release with one string.
    """
    stated = str(source_release or "").strip()
    return f"{CLINVAR_GKM_DATASET_PREFIX}{stated}" if stated else None


@dataclass
class ClinVarGkmClient:
    """The two small JSON documents that say what the source publishes now.

    `parquet_manifest()` is the Parquet set's own record; `latest_release()` is the release line's
    index, whose `latest_release` is the newest **weekly** release. They differ: the Parquet set is
    rebuilt from a weekly release a few days after it lands, so on 2026-11-04 the set held 2026-10-24
    while the line's newest release was 2026-10-31 (LANES §3.2). `@client-exception-contract`: transport
    and status failures are retried, then arrive as `ClinVarGkmUnavailable`, never as an `httpx` type.
    """

    manifest_url: str = PARQUET_MANIFEST_URL
    index_url: str = RELEASE_INDEX_URL
    timeout: float = 30.0
    client: httpx.Client | None = None
    gate: PacingGate | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(CLINVAR_GKM_MIN_INTERVAL)

    def _http(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self.client

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=1.0, max=15.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _get_text(self, url: str) -> str:
        assert self.gate is not None
        self.gate.wait()
        response = self._http().get(url)
        response.raise_for_status()
        return response.text

    def _fetch(self, url: str, what: str) -> str:
        try:
            return self._get_text(url)
        except httpx.HTTPError as exc:
            raise ClinVarGkmUnavailable(f"could not read ClinVar-GKM's {what} ({url}): {exc}") from exc

    def file_url(self, name: str) -> str:
        """A file of the Parquet set: it sits beside the manifest that describes it."""
        return f"{self.manifest_url.rsplit('/', 1)[0]}/{name}"

    def parquet_manifest(self) -> GkmManifest:
        """The published Parquet set's manifest. Raises `ClinVarGkmUnavailable` when unreachable."""
        return parse_manifest(self._fetch(self.manifest_url, "Parquet manifest"))

    def latest_release_or_none(self) -> str | None:
        """`latest_release`, withheld as `None` when the index cannot be read.

        The index answers one informational question (does the Parquet set lag the line?). Its
        outage may not speak for the manifest's questions (`@one-registrys-outage-may-not-speak-for-
        another`), so a build and a currency check go on without it and say the lag is unknown.
        """
        try:
            return self.latest_release()
        except ClinVarGkmError as exc:
            logger.warning("ClinVar-GKM's release index could not be read (%s); the lag is unknown.", exc)
            return None

    def latest_release(self) -> str | None:
        """The release line's newest weekly release, or `None` when the index states none."""
        try:
            raw = json.loads(self._fetch(self.index_url, "release index"))
        except ValueError as exc:
            raise ClinVarGkmError(f"the release index is not JSON: {exc}") from exc
        stated = str(raw.get("latest_release") or "").strip() if isinstance(raw, dict) else ""
        return stated or None

    def current_release(self) -> str | None:
        """The currency probe: the label a rebuild today would write, read off the live manifest.

        The **Parquet set's** release, not the line's newest weekly one. A module drafted against this
        lane can only ever be as current as the set, so comparing it against a release no Parquet
        carries would report every module behind for the week the set lags, with nothing to re-draft
        from. The set's own lag is `LaneCurrency.source_lags`, kept apart.
        """
        return clinvar_gkm_release_label(self.parquet_manifest().source_release)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None


def release_older(first: str | None, second: str | None) -> bool | None:
    """Tri-state `first < second` over two `YYYY-MM-DD` dates; `None` when either is not one."""
    if not first or not second or not _DATE_PATTERN.match(first) or not _DATE_PATTERN.match(second):
        return None
    return date.fromisoformat(first) < date.fromisoformat(second)


def require_polars() -> None:
    if pl is None:  # pragma: no cover - exercised only without polars
        raise ImportError("polars is required to build or read the ClinVar-GKM snapshot")


# ── currency ────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LaneCurrency:
    """A built snapshot against what the source publishes now — three questions, kept apart.

    * `behind`: the source has published a newer Parquet set, so a rebuild would get newer bytes.
    * `drifted`: the source's set names **the same** release with different bytes. The pin caught an
      in-place overwrite the label cannot see.
    * `source_lags`: the published set is older than the line's newest weekly release. Nothing here
      can fix that (no Parquet exists for the newer release), so it is reported, never folded into
      `behind`: a rebuild would change nothing.

    Each is tri-state; `unchecked` names why none could be answered (`@currency-asks-the-source-not-
    the-cache`: the published release comes over the wire, never from the snapshot's own record).
    """

    pinned_release: str | None
    #: `((input file, digest), …)` over both inputs, in `INPUT_FILES` order; `None` when not all stated.
    pinned_sha256: tuple[tuple[str, str | None], ...] | None
    published_release: str | None = None
    published_sha256: tuple[tuple[str, str | None], ...] | None = None
    latest_release: str | None = None
    unchecked: str | None = None

    @property
    def behind(self) -> bool | None:
        if self.unchecked is not None:
            return None
        return release_older(self.pinned_release, self.published_release)

    @property
    def drifted(self) -> bool | None:
        if self.unchecked is not None or not self.pinned_sha256 or not self.published_sha256:
            return None
        if self.pinned_release is None or self.pinned_release != self.published_release:
            return None
        return self.pinned_sha256 != self.published_sha256

    @property
    def source_lags(self) -> bool | None:
        if self.unchecked is not None:
            return None
        return release_older(self.published_release, self.latest_release)

    def sentences(self) -> list[str]:
        """What an operator is told: each answered question that found something, and every unknown."""
        if self.unchecked is not None:
            return [f"clinvar_gkm currency unchecked: {self.unchecked}"]
        out: list[str] = []
        if self.behind:
            out.append(
                f"clinvar_gkm: the snapshot holds {self.pinned_release} and the source publishes "
                f"{self.published_release}; rebuild with `clinvar-gkm build`"
            )
        elif self.behind is None:
            out.append(
                "clinvar_gkm: whether the snapshot is behind could not be decided (an unstated release)"
            )
        if self.drifted:
            moved = [
                name
                for (name, ours), (_, theirs) in zip(
                    self.pinned_sha256 or (), self.published_sha256 or (), strict=True
                )
                if ours != theirs
            ]
            out.append(
                f"clinvar_gkm: the source's {', '.join(moved)} for {self.pinned_release} is no longer the "
                f"bytes this snapshot was cut from (overwritten in place); rebuild"
            )
        if self.source_lags:
            out.append(
                f"clinvar_gkm: the source's Parquet set holds {self.published_release} while its newest "
                f"weekly release is {self.latest_release}; no Parquet exists for that release yet"
            )
        return out


def bare_digest(value: str | None) -> str | None:
    """A digest without its `sha256:` prefix(es), lower case; `None` for blank."""
    stated = (value or "").strip().lower()
    while stated.startswith("sha256:"):
        stated = stated.removeprefix("sha256:")
    return stated or None


def _pinned_digests(release: SnapshotRelease) -> tuple[tuple[str, str | None], ...] | None:
    """Both inputs' digests as the snapshot records them, or `None` when it does not record both."""
    digests = release.source_sha256
    if not isinstance(digests, dict):
        return None
    pinned = tuple((name, bare_digest(digests.get(name))) for name in INPUT_FILES)
    return pinned if all(digest for _, digest in pinned) else None


def _published_digests(manifest: GkmManifest) -> tuple[tuple[str, str | None], ...] | None:
    published = tuple(
        (name, manifest.files[name].sha256 if name in manifest.files else None) for name in INPUT_FILES
    )
    return published if all(digest for _, digest in published) else None


def lane_currency(
    snapshot_dir: Path,
    *,
    client: ClinVarGkmClient | None = None,
    offline: bool = False,
) -> LaneCurrency:
    """Ask the source whether `snapshot_dir` is current. Reads the snapshot; writes nothing."""
    release = read_release(Path(snapshot_dir)) or SnapshotRelease()
    pinned_release = getattr(release, "source_release", None)
    pinned = LaneCurrency(pinned_release=pinned_release, pinned_sha256=_pinned_digests(release))
    if offline:
        return LaneCurrency(pinned.pinned_release, pinned.pinned_sha256, unchecked="offline")
    asker = client or ClinVarGkmClient()
    try:
        manifest = asker.parquet_manifest()
    except ClinVarGkmUnavailable as exc:
        return LaneCurrency(pinned.pinned_release, pinned.pinned_sha256, unchecked=f"unreachable ({exc})")
    except ClinVarGkmError as exc:
        return LaneCurrency(pinned.pinned_release, pinned.pinned_sha256, unchecked=f"unreadable ({exc})")
    return LaneCurrency(
        pinned_release=pinned.pinned_release,
        pinned_sha256=pinned.pinned_sha256,
        published_release=manifest.source_release,
        published_sha256=_published_digests(manifest),
        latest_release=asker.latest_release_or_none(),
    )


# ── the reader a check calls ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WitnessPlacement:
    """Where ClinVar-GKM places one allele: one row of the slice.

    Flat, one row per `(allele, rsID)`: an allele with two rsIDs is two rows (4 alleles on
    2026-10-24), and an rsID naming two alleles (a multi-allelic site) returns both. A lookup never
    picks one (`@multiplicity-is-a-finding`).
    """

    vrs_id: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gnomad: str
    spdi: str
    state_type: str | None
    clinvar_variation_id: str | None
    rsid: str | None

    @property
    def vcf_key(self) -> str:
        """`chrom:pos:ref:alt`, the coordinate form `variant_key` uses for one ALT."""
        return f"{self.chrom}:{self.pos}:{self.ref}:{self.alt}"


def normalize_chrom(chrom: str) -> str:
    """A contig as the `gnomad` expression spells it: no `chr`, upper case, `M` read as `MT`."""
    token = chrom.strip()
    if token[:3].lower() == "chr":
        token = token[3:]
    token = token.upper()
    return "MT" if token == "M" else token


@dataclass
class ClinVarGkmWitness:
    """The loaded slice, and the three lookups a check makes against it.

    `[]` from any lookup means **not witnessed**, never *placed wrong*: the lane holds indels only, a
    ClinVar-GKM release holds only what ClinVar holds, and 29% of the indels carry no rsID.
    """

    snapshot_dir: Path
    release: SnapshotRelease
    frame: "pl.DataFrame"

    @classmethod
    def load(cls, snapshot_dir: Path) -> "ClinVarGkmWitness":
        require_polars()
        directory = Path(snapshot_dir)
        path = directory / SNAPSHOT_DATA_DIRNAME / WITNESS_PARQUET
        if not path.is_file():
            raise ClinVarGkmError(f"{directory} holds no {SNAPSHOT_DATA_DIRNAME}/{WITNESS_PARQUET}")
        return cls(directory, read_release(directory) or SnapshotRelease(), pl.read_parquet(path))

    @property
    def vrs_version(self) -> str | None:
        """The VRS version the witness's ids were minted under, as `release.json` declares it."""
        stated = getattr(self.release, "vrs_version", None)
        return str(stated) if stated else None

    @property
    def dataset(self) -> str | None:
        return (self.release.dataset or "").strip() or None

    def ids_comparable(self, our_vrs_spec: str | None) -> bool | None:
        """Whether a VRS id we minted under `our_vrs_spec` may be compared to the witness's ids.

        Tri-state at the minor, the grain the id rule changes at (RM304): `None` when either side is
        unstated. When it is not `True`, compare by the normalized VCF spelling instead.
        """
        ours, theirs = vrs_spec_release(our_vrs_spec), vrs_spec_release(self.vrs_version)
        if ours is None or theirs is None:
            return None
        return ours == theirs

    def _rows(self, mask) -> list[WitnessPlacement]:
        return [WitnessPlacement(**row) for row in self.frame.filter(mask).iter_rows(named=True)]

    def by_vrs_id(self, vrs_id: str) -> list[WitnessPlacement]:
        return self._rows(pl.col("vrs_id") == vrs_id.strip())

    def by_rsid(self, rsid: str) -> list[WitnessPlacement]:
        token = rsid.strip().lower()
        return self._rows(pl.col("rsid") == (token if token.startswith("rs") else f"rs{token}"))

    def by_rsids(self, rsids: Iterable[str]) -> dict[str, list[WitnessPlacement]]:
        """`by_rsid` over many rsIDs in one filter, keyed by the rsID as asked; an absent one is absent.

        One pass over the slice rather than one per rsID: a module asks about every rsID it places
        (RM267), and the slice is every ClinVar indel.
        """
        asked = {(t if (t := r.strip().lower()).startswith("rs") else f"rs{t}"): r for r in rsids}
        found: dict[str, list[WitnessPlacement]] = {}
        for row in self._rows(pl.col("rsid").is_in(list(asked))):
            found.setdefault(asked[str(row.rsid)], []).append(row)
        return found

    def by_vcf(self, chrom: str, pos: int, ref: str, alt: str) -> list[WitnessPlacement]:
        """Exact match on the left-normalized VCF spelling. The caller normalizes; this never does."""
        return self._rows(
            (pl.col("chrom") == normalize_chrom(chrom))
            & (pl.col("pos") == int(pos))
            & (pl.col("ref") == ref.strip().upper())
            & (pl.col("alt") == alt.strip().upper())
        )

    def lookup(self, key: str) -> list[WitnessPlacement]:
        """A `variant_key`, a VRS id or an rsID → the placements the witness holds for it.

        A coordinate key must carry exactly one ALT (`chrom:start:ref:alt`): a position-only key names
        no allele, and a multi-ALT key names several, so both are refused rather than half-answered.
        """
        token = key.strip()
        if token.startswith("ga4gh:VA."):
            return self.by_vrs_id(token)
        if re.fullmatch(r"(?i)rs\d+", token):
            return self.by_rsid(token)
        parts = token.split(":")
        if len(parts) == 4 and parts[1].isdigit() and "," not in parts[3]:
            return self.by_vcf(parts[0], int(parts[1]), parts[2], parts[3])
        raise ValueError(
            f"{key!r} is not a VRS id, an rsID or a one-ALT coordinate key (chrom:start:ref:alt)"
        )

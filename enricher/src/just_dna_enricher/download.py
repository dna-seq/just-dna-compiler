"""HuggingFace snapshot provisioning — the bulk-fetch side of the resolver chain.

Two reference snapshots share one download body: the Ensembl variation parquet (dbSNP's rsIDs with
Ensembl's alleles, built by prepare-annotations) and the ClinVar parquet slice (clinically-curated
GRCh38 records). Neither is a *canonical* reference — each
is a static slice with the usual pains (incompleteness, versions, reachability; HF has gone dark
mid-demo) — so each is one resolver-chain source downloaded into a cache the resolver reads directly
(`<cache>/data/*.parquet`), with a miss falling through to the next link.

`huggingface_hub` is imported lazily and guarded: it is the one HuggingFace dependency in the whole
workspace, permitted only in this network tier (the 0.5 Constitution amendment scopes the HF ban to
format + compiler). The download logic (footer-checked, atomic `.part` rename) is inherited from
just-dna-lite's pipelines byte-for-byte so no drift is born.
"""

import hashlib
import json
import logging
import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatch
from functools import partial
from pathlib import Path

import httpx
from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso
from just_dna_format.vocab import VALID_DECLARED_USE, check_vocab

from just_dna_enricher.clinvar import ClinVarReferenceError
from just_dna_enricher.licensing import check_declared_use, snapshot_group_terms
from just_dna_enricher.locations import (
    ALPHAGENOME_KNOTS_FILENAME,
    CORE_IS_NOT_A_GROUP,
    ENSEMBL_CORE_GROUP,
    ENSEMBL_GROUPS_DIRNAME,
    PULL_RECORD_FILENAME,
    PULL_RECORD_GROUPS_KEY,
    PULL_RECORD_REPLACING_KEY,
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_MANIFEST_FILENAME,
    SNAPSHOT_REPO_IDS,
    SNAPSHOT_ROOT_FILENAMES,
    SNAPSHOT_SIDECAR_DIRNAMES,
    STRCHIVE_CATALOGUE_FILENAME,
    EnsemblGroupReleaseError,
    ManifestCoverage,
    SnapshotManifest,
    SnapshotManifestFile,
    SnapshotManifestGroup,
    _unnamed_group_files,
    default_alphagenome_avi_cache_dir,
    default_civic_cache_dir,
    default_clinpgx_cache_dir,
    default_clinvar_cache_dir,
    default_clinvar_gkm_cache_dir,
    default_constraint_cache_dir,
    default_cpic_cache_dir,
    default_drug_labels_cache_dir,
    default_ensembl_cache_dir,
    default_mitomap_cache_dir,
    default_opentargets_cache_dir,
    default_strchive_cache_dir,
    env_value,
    manifest_attests,
    manifest_coverage,
    parquet_footer_ok,
    pull_record_repo,
    pulled_from,
    pulled_groups,
    read_snapshot_manifest,
    snapshot_record_missing,
)
from just_dna_enricher.resolver import EnsemblReferenceError

logger = logging.getLogger(__name__)


def _hf_dataset_root(repo_id: str) -> str:
    """The `HfFileSystem` path of a dataset repo's root: `datasets/<repo id>`."""
    return f"datasets/{repo_id}"


# What each snapshot is *made of*, so provisioning fetches its own files and nothing else.
#
# **A published dataset accumulates.** The publisher adds files and never deletes, so a repo carries
# whatever any earlier layout put there — and `just-dna-seq/clinvar/data` really does still hold a
# 159 MB `clinvar.parquet` from the single-file era beside today's 25 `clinvar-chr*.parquet`. Its
# columns are the raw VCF INFO fields (`clnsig`, `clnrevstat`, …), and the reader globs
# `data/*.parquet`, so provisioning everything hands DuckDB two schemas under one relation and every
# query dies on `Referenced column "clin_sig" not found`. Not hypothetical: that is exactly how a
# local cache built by the old builder broke the clin_sig cross-check.
#
# Naming a snapshot's files is knowledge this tier legitimately has — it is the tier that *builds*
# them (`clinvar_build`, `constraint_build`) — and it is the cheapest place to stop a stale remote file
# from becoming a local one.
_ENSEMBL_FILES = "homo_sapiens-*.parquet"
_CLINVAR_FILES = "clinvar-*.parquet"  # deliberately excludes the flat `clinvar.parquet`
_CONSTRAINT_FILES = "gnomad_constraint.parquet"
# The two gated snapshots that may be published (RM38). Both are multi-table, so the glob is the whole
# directory rather than one name — `cpic_build` writes five parquets and `clinpgx_build` one, and both
# sets are this snapshot's own; nothing foreign has ever been published into either repo.
_CLINPGX_FILES = "*.parquet"
_CPIC_FILES = "*.parquet"


# The three lanes that had a builder and a licence permitting publication, and no way to fetch the
# result (RM176). CIViC's absent `ensure_*` was recorded in the cache roster as a *gap* rather than a
# refusal — CC0 grants redistribution outright — and STRchive's MIT and the drug labels' CC BY-SA say
# the same thing on their own terms. What was missing in all three cases was plumbing, not permission.
#
# The drug labels are a **second** ClinPGx archive with its own cadence, so they get their own repo
# rather than a table inside `clinpgx/`: `summaryAnnotations.zip` and `drugLabels.zip` do not refresh
# together, and one repo holding both would date the pair from whichever was published last.
_CIVIC_FILES = "*.parquet"
_DRUG_LABELS_FILES = "*.parquet"

#: MITOMAP, added with the lane itself (RM171) rather than as a later repair — the roster's own
#: biconditional says a lane this tier builds is publishable exactly when it is pullable, and CC BY
#: 3.0 grants the redistribution outright, so shipping the builder without these two halves would
#: have recreated the gap RM176 closed three times over.
_MITOMAP_FILES = "mitomap-*.parquet"

#: AlphaGenome AVI, added with the publish half rather than after it (RM198). The lane is the first
#: whose snapshot is **useless without a root-level sidecar**: `PHRED` is not stored, so a pull that
#: brought only `data/*.parquet` would hand over scores nobody can rank. `_provision_snapshot` fetches
#: the root files from `SNAPSHOT_ROOT_FILENAMES` for every lane, so this needs no special case — it
#: needed the registry to exist, which is the other half of RM198.
_ALPHAGENOME_AVI_FILES = "alphagenome_avi-*.parquet"

#: ClinVar-GKM's indel witness (RM305), added with the lane: CC0 over ClinGen's transformation of
#: public-domain ClinVar grants redistribution, so a deployment pulls ~16 MB instead of downloading
#: ~5 GB of Parquet to cut it. The attribution and ClinVar's disclaimer travel as `LICENSE.txt`.
_CLINVAR_GKM_FILES = "clinvar_gkm-*.parquet"

#: Open Targets (RM408): six tables, four of them in numbered parts (`colocalisations-00000.parquet`,
#: …, `variants.parquet`), so the glob is the whole `data/`, as CIViC's is. The repo holds nothing else:
#: CC0-marked, with the release's own Croissant record in `release.json`.
_OPENTARGETS_FILES = "*.parquet"

#: STRchive's repo root, not a `data/` prefix: this snapshot is the upstream catalogue verbatim beside
#: its provenance, and it holds no parquet at all.
_STRCHIVE_HF_REPO = _hf_dataset_root(SNAPSHOT_REPO_IDS["strchive"])


#: What each publishable lane's `data/` consists of, by lane name — the same globs the `ensure_*`
#: closures pass, in one place because a second reader now needs them (RM186). `cache prune` asks
#: "what does this repo carry that this lane is not made of", and it can only ask by lane. The
#: closures below read this dict rather than restating the pattern, so the provisioner and the pruner
#: cannot come to disagree about what a snapshot is — the failure `@publisher-allowlist-derived`
#: records for the upload side.
#:
#: Ensembl is here and has no `publish_repo`: it is pullable, so the glob is load-bearing, and prune
#: refuses a lane this tier does not publish on its own grounds rather than by the glob being absent.
#: STRchive has no entry, because its snapshot is one JSON at the repo root and there is no `data/`
#: to be made of anything.
SNAPSHOT_FILE_GLOBS: dict[str, str] = {
    "ensembl": _ENSEMBL_FILES,
    "clinvar": _CLINVAR_FILES,
    "constraint": _CONSTRAINT_FILES,
    "clinpgx": _CLINPGX_FILES,
    "cpic": _CPIC_FILES,
    "drug_labels": _DRUG_LABELS_FILES,
    "civic": _CIVIC_FILES,
    "mitomap": _MITOMAP_FILES,
    "alphagenome_avi": _ALPHAGENOME_AVI_FILES,
    "clinvar_gkm": _CLINVAR_GKM_FILES,
    "opentargets": _OPENTARGETS_FILES,
}


#: Where each lane in `SNAPSHOT_FILE_GLOBS` is pulled from, by lane name: the second half of what a
#: pull is (RM372). A cache whose pull record names another repo is not this lane's snapshot, however
#: complete, so `cache pull` sends it down the pull route. Derived (RM384): one entry per lane in the
#: globs, each `datasets/<repo id>/data` from `locations.SNAPSHOT_REPO_IDS`, so a prefix is where a repo
#: keeps its parquet and never a second spelling of which repo. A glob lane with no repo id fails this
#: module's import with a `KeyError` naming the lane.
SNAPSHOT_REPO_PREFIXES: dict[str, str] = {
    lane: f"{_hf_dataset_root(SNAPSHOT_REPO_IDS[lane])}/{SNAPSHOT_DATA_DIRNAME}"
    for lane in SNAPSHOT_FILE_GLOBS
}


def pulled_from_elsewhere(lane: str, cache_dir: Path) -> str | None:
    """The repo `cache_dir` was pulled from when that is not `lane`'s repo, else `None` (`locations.pulled_from`)."""
    current = SNAPSHOT_REPO_PREFIXES.get(lane)
    return pulled_from(cache_dir, current) if current is not None else None


class ConstraintReferenceError(FileNotFoundError):
    """Raised when the gnomAD constraint snapshot cannot be provisioned or has no usable parquet."""


class GatedSnapshotError(FileNotFoundError):
    """Raised when a licence-gated snapshot (ClinPGx, CPIC) cannot be provisioned.

    One class for both because a caller's recovery is identical — build it locally, or point at a
    cache — and because the two are the same act: reaching a source that forbids sale through bytes the
    operator took once instead of live per request.
    """


class OpenSnapshotError(FileNotFoundError):
    """Raised when an openly-licensed snapshot (CIViC, STRchive) cannot be provisioned.

    `GatedSnapshotError`'s counterpart, and one class for both of these for its reason: the caller's
    recovery is identical — build it locally, or point at a cache. What separates the two classes is
    not the failure but the *question a reader asks next*. A gated snapshot failing may mean the
    operator never accepted the terms; these two are CC0 and MIT, so nothing here is ever a licence
    problem and a reader chasing one would be chasing nothing.
    """


class SnapshotNotPublished(FileNotFoundError):
    """The repo or prefix a lane publishes to does not exist yet — asked, and absent.

    A distinct type because it is a distinct *answer*, and the two were folded into one until the
    default `cache pull` started exiting 1 on a fresh machine. Three new lanes gained an `ensure_*`
    in RM176 whose repos nobody has created, and the bare `fs.ls` failure reached `cache pull`'s
    blanket `except Exception` as a failure — so the command that provisions a deployment reported
    an error for a snapshot that simply has not been published. Nobody-published is the same third
    state as nobody-asked (`@unreachable-not-absent`), and a caller has to be able to tell it from a
    download that broke, which means a class rather than a message (`@client-exception-contract`:
    the transport's own exception type is not this module's contract).

    It subclasses `FileNotFoundError` and not `GatedSnapshotError`/`OpenSnapshotError`, deliberately:
    a caller that catches either of those to mean "this lane is unusable" still catches this, and one
    that wants to distinguish asks for this type by name.
    """


#: Kept importable here under its old name; the check itself lives in `locations` since a resolver
#: judges a recorded file by it too (RM339).
_parquet_footer_ok = parquet_footer_ok


# ── following the hub's release (RM420) ─────────────────────────────────────────────────────────


@dataclass
class _FollowHub:
    """The provisioning commands' intent to follow the hub's release, and what the provisioner found (RM420).

    `cache pull` and `cache prepare` pass one to a lane's `ensure` as `_follow_hub`; every other caller
    passes none, so `enrich` keeps trusting a whole cache without the network (a warm cache serves
    offline, and no enrichment downloads a release mid-run). Private on `main`, because a new public
    name is minor scope.

    `release_label` is the **lane's** own label reader (`CacheLane.release_label`,
    `@the-reporter-cannot-compose-a-lanes-label`), applied to the local cache and to the published
    repo's description files alike, so Ensembl's manifest-only label needs no case here. No lane owns
    an ordering over its labels, so a differing label is followed by a pulled cache whichever way it
    differs: the operator asked for the hub's release by running the pull.

    `outcome` is `None` when no whole cache was compared (an absent or unfinished one is pulled as
    before), else one of `current` (the labels agree, or the hub states none to compare), `refreshed`
    (re-pulled to the published release), `kept` (the labels differ and nothing says the cache came
    from a pull of this repo, so it is left alone: a snapshot built here may not be uploaded yet) and
    `unknown` (the hub could not be read, so the cache serves as it is).

    `unattested` marks a refresh taken because nothing attests which release the cache's files are,
    whatever its label says (RM445): an unrecorded cache stating no release, a pull record from before
    RM420, or a resumed pull whose kept files are another release's than the one the hub now publishes.
    """

    release_label: Callable[[Path], str | None]
    repo: str | None = None
    local: str | None = None
    published: str | None = None
    outcome: str | None = None
    detail: str | None = None
    unattested: bool = False
    #: What became of each of the Ensembl lane's groups this call looked at (RM437), by group name:
    #: `pulled`, `current`, `skipped — <reason>` or `not re-pulled — <reason>`, for `cache pull` to print.
    groups: dict[str, str] = field(default_factory=dict)

    def note(self) -> str | None:
        """The line `cache pull` and `cache prepare` print beside the lane, naming both labels; `None` when quiet."""
        local = self.local or "no release label"
        if self.outcome == "refreshed" and self.unattested:
            why = f" ({self.detail})" if self.detail else ""
            return (
                f"re-pulled: nothing attested which release its files were (it stated {local}){why}, and "
                f"{self.repo} publishes {self.published}"
            )
        if self.outcome == "refreshed":
            return f"re-pulled: it held {local}, and {self.repo} publishes {self.published}"
        if self.outcome == "kept":
            return (
                f"left alone: it holds {local} and was not pulled from {self.repo}, which publishes "
                f"{self.published} (built here, or pulled before this tier kept a pull record). Move it "
                f"aside and pull to take the published release"
            )
        if self.outcome == "unknown":
            return f"served as it is: the release {self.repo} publishes could not be read ({self.detail})"
        return None


#: The pull-record key naming the sha256 of the `release.json` **the pull placed**, `None` when it
#: placed none (RM420; since RM445 a pull places none over files nothing attests, and then leaves any
#: `release.json` already there, a builder's, unvouched for). A builder pointed at a pulled cache leaves
#: the old record behind and writes its own `release.json`, so a record whose digest no longer matches
#: is not this cache's origin any more. A finished record without the key was written before RM420 and
#: is read as a pull, which is what it was (only the provisioner writes one), but not as attesting its
#: label: that pull kept whole files whatever release they were, then placed the hub's `release.json`
#: over them (RM445), so `cache pull` re-pulls it even when its label equals the hub's.
_RELEASE_DIGEST_KEY = "release_sha256"

#: The record key a pull writes **before** its first download (RM445): the sha256 of the hub's
#: `release.json` it is pulling, and only when every whole file already under a planned name is that
#: release's too. A resumed pull keeps what the interrupted one fetched only while the hub still
#: publishes that `release.json`; past a release boundary the kept files are the older release's.
#: Dropped from the record once the pull finishes, where `_RELEASE_DIGEST_KEY` says what was placed.
_PULLING_RELEASE_KEY = "pulling_release_sha256"


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _write_pull_record(cache_dir: Path, repo: str, files: list[str], *, placed_release: bool) -> None:
    """The record of a pull that finished: its repo, its files, and the `release.json` it placed.

    `placed_release` is whether this pull put the `release.json` now in the cache there. A file it did
    not place (a builder's, left beside files the pull kept) is not vouched for, so the digest is `None`
    and `_pulled_by_this_repo` does not take the cache for a pull of that release.
    """
    digest = _file_sha256(cache_dir / RELEASE_FILENAME) if placed_release else None
    record: dict[str, object] = {"repo": repo, "files": files, _RELEASE_DIGEST_KEY: digest}
    record.update(_carried_groups(cache_dir))
    atomic_write_text(cache_dir / PULL_RECORD_FILENAME, json.dumps(record, indent=2) + "\n")


def _carried_groups(cache_dir: Path) -> dict[str, object]:
    """The record's group selection, for a writer that rebuilds the record to carry over (RM437).

    The selection is sticky (`locations.PULL_RECORD_GROUPS_KEY`), and both of the provisioner's record
    writes build the record afresh, so each takes this over unchanged: a group's `release_id` moves only
    when that group's own pull finishes, never because the core's did.
    """
    payload = _pull_record(cache_dir)
    groups = payload.get(PULL_RECORD_GROUPS_KEY) if payload is not None else None
    return {PULL_RECORD_GROUPS_KEY: groups} if isinstance(groups, dict) and groups else {}


def _set_aside_unreadable_record(cache_dir: Path, repo: str, unreadable: Exception) -> Path:
    """Move an unreadable pull record aside and write a fresh one naming `repo` (review round 1, item 3).

    The fresh record names `repo`, the core files the cache's manifest attests (none without one), no release
    digest and no groups, so `_pulled_by_this_repo`
    takes the cache for a pull of it and a refresh may run; without one, a cache with a `release.json`
    reads as a local build and is never pulled again. The old record is kept under a dated name (no `:`,
    which an NTFS mount refuses), and the warning names it, the selection it loses, and the repository
    assumed. Returns where the old record went.
    """
    record = cache_dir / PULL_RECORD_FILENAME
    stamp = now_utc_iso().replace(":", "").replace("-", "")
    aside = cache_dir / f"{PULL_RECORD_FILENAME}.unreadable-{stamp}"
    n = 1
    while aside.exists():
        n += 1
        aside = cache_dir / f"{PULL_RECORD_FILENAME}.unreadable-{stamp}-{n}"
    record.rename(aside)
    # The file list is the core the cache's manifest attests, never `[]` (review round 2, class A): an empty
    # list reads as a pull that finished with nothing missing, so a short cache was returned whole. Listing
    # what the manifest attests makes an attested file that is absent or short an unfinished pull, which the
    # provisioner fetches. With no manifest nothing says which files a pull took: no list, the unknown arm.
    manifest = read_snapshot_manifest(cache_dir / SNAPSHOT_MANIFEST_FILENAME)
    attested = (
        [entry.path for entry in manifest.files if entry.path.startswith(f"{SNAPSHOT_DATA_DIRNAME}/")]
        if manifest is not None and manifest.files
        else None
    )
    atomic_write_text(record, json.dumps({"repo": repo, "files": attested}, indent=2) + "\n")
    reason = str(unreadable).split(" could not be read (", 1)[-1].split("), so nothing says", 1)[0]
    logger.warning(
        "The pull record at %s could not be read (%s); moved it to %s, and any group selection it held is "
        "lost. A fresh record takes its place, pulling as %s, which the old record may not have named: "
        "re-pull the groups you want (`just-dna-enricher cache pull --only ensembl --groups NAME[,NAME]`).",
        record,
        reason,
        aside,
        repo,
    )
    return aside


def _pull_record(cache_dir: Path) -> dict | None:
    """The pull record's payload, or `None` when there is none or it does not read as an object."""
    try:
        payload = json.loads((cache_dir / PULL_RECORD_FILENAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _pulled_by_this_repo(cache_dir: Path, repo: str) -> bool:
    """Whether `cache_dir` came from a pull of `repo` and nothing has been built over it since (RM420).

    The pull record is the witness, because only the provisioner writes one: a builder never does. A
    record naming no repo is read as this repo's, as `locations.pulled_from` reads it.
    """
    payload = _pull_record(cache_dir)
    if payload is None or pulled_from(cache_dir, repo) is not None:
        return False
    if _RELEASE_DIGEST_KEY not in payload:
        return True
    return payload[_RELEASE_DIGEST_KEY] == _file_sha256(cache_dir / RELEASE_FILENAME)


def _label_unattested(cache_dir: Path, coverage: ManifestCoverage | None) -> bool:
    """Whether a recorded cache's label is one nothing attests describes its files (RM445).

    A record without `_RELEASE_DIGEST_KEY` (written before RM420, or by a pull still under way that
    names no release it was pulling, or another than the one in the cache) does not say the `release.json` beside it was placed over files that pull fetched, and RM339's pull,
    which wrote such records, placed the hub's over files it kept whatever release they were. A
    manifest attests the files itself, by size here and by sha256 when a pull keeps one, so a lane that
    has one (Ensembl, which states its release there) is never unattested this way.
    """
    payload = _pull_record(cache_dir)
    if payload is None or _RELEASE_DIGEST_KEY in payload or coverage is not None:
        return False
    # A pull killed after placing its `release.json` and before rewriting the record: the record names
    # the release it was pulling, and that is the file in the cache.
    pulling = payload.get(_PULLING_RELEASE_KEY)
    return not (isinstance(pulling, str) and pulling == _file_sha256(cache_dir / RELEASE_FILENAME))


def _kept_release(cache_dir: Path, repo: str) -> str | None:
    """The sha256 of the `release.json` this repo's pull says the files on disk are, or `None` (RM445).

    A pull under way names the release it is pulling (`_PULLING_RELEASE_KEY`); a finished one names the
    release it placed, which counts only while that file is still the one in the cache. No record, a
    record of another repo, one from before RM420, and one whose `release.json` was replaced all answer
    `None`: nothing on disk says which release a kept file is.
    """
    payload = _pull_record(cache_dir)
    if payload is None or pulled_from(cache_dir, repo) is not None:
        return None
    if _PULLING_RELEASE_KEY in payload:
        pulling = payload[_PULLING_RELEASE_KEY]
        return pulling if isinstance(pulling, str) else None
    placed = payload.get(_RELEASE_DIGEST_KEY)
    if isinstance(placed, str) and placed == _file_sha256(cache_dir / RELEASE_FILENAME):
        return placed
    return None


def _hub_filesystem():
    """The Hub's filesystem, or `None` when `huggingface_hub` is not installed.

    A token is optional on the read side and doubles the per-IP rate allowance, so the `.env` is read
    here for the same reason the publisher reads it (`@credential-where-read`): anonymous traffic
    sleeping on a 429 looks exactly like a hung download. `env_value` reads the one key and exports
    nothing else from the file (RM301).
    """
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError:  # the one guarded optional import (CLAUDE.md)
        return None
    return HfFileSystem(token=env_value("HF_TOKEN") or get_token())


def _published_release_label(fs, repo_root: str, release_label: Callable[[Path], str | None]) -> str | None:
    """The release `repo_root` publishes, read by the lane's own label reader over its description files.

    The files are staged in a scratch directory, never in the cache: the cache's own `release.json` is
    what the answer is compared with. `release.json` is asked first and `manifest.json` only when that
    names no release (Ensembl's split repo states its release in the manifest alone). `None` when the
    repo states none. Could-not-ask raises `OSError` (`_hub_says_absent` is the one absent answer).
    """
    with tempfile.TemporaryDirectory(prefix="published-release-") as scratch:
        for name in (RELEASE_FILENAME, SNAPSHOT_MANIFEST_FILENAME):
            staged = Path(scratch) / name
            try:
                fs.get(f"{repo_root}/{name}", str(staged))
            except Exception as exc:
                staged.unlink(missing_ok=True)
                if not _hub_says_absent(exc):
                    raise OSError(f"{name}: {type(exc).__name__}: {exc}") from exc
                continue
            label = release_label(Path(scratch))
            if label is not None:
                return label
    return None


def _compare_with_hub(cache_dir: Path, repo_root: str, label: str, follow: _FollowHub) -> bool:
    """Read the published release beside the local one into `follow`; `True` when the two labels differ.

    An unreadable hub is the `unknown` outcome, with a warning, and never a difference: the cache serves
    as it is. A hub stating no release is `current`, since nothing can be compared.
    """
    follow.repo = repo_root.removeprefix("datasets/")
    follow.local = follow.release_label(cache_dir)
    fs = _hub_filesystem()
    try:
        if fs is None:
            raise OSError("huggingface_hub is not installed")
        follow.published = _published_release_label(fs, repo_root, follow.release_label)
    except OSError as exc:
        follow.outcome, follow.detail = "unknown", str(exc)
        logger.warning(
            "%s cache at %s: the release %s publishes could not be read (%s), so whether a newer one is "
            "published is unknown. Using the cache as it is.",
            label,
            cache_dir,
            follow.repo,
            exc,
        )
        return False
    if follow.published is None or follow.published == follow.local:
        follow.outcome = "current"
        return False
    return True


def _left_alone(cache_dir: Path, label: str, follow: _FollowHub) -> Path:
    """A cache whose release differs from the hub's and that did not come from a pull: kept, and said so."""
    follow.outcome = "kept"
    logger.warning("%s cache at %s %s.", label, cache_dir, follow.note())
    return cache_dir


def _refreshing(cache_dir: Path, label: str, follow: _FollowHub, *, unattested: bool = False) -> None:
    follow.outcome, follow.unattested = "refreshed", unattested
    if unattested:
        logger.warning(
            "%s cache at %s: nothing on disk attests which release its files are (it states %s), and %s "
            "publishes %s. Re-pulling: a file is kept only where the release's manifest attests it.",
            label,
            cache_dir,
            follow.local or "no release label",
            follow.repo,
            follow.published,
        )
        return
    logger.warning(
        "%s cache at %s holds %s; %s publishes %s. Re-pulling: a file is kept only where the new "
        "release's manifest attests it.",
        label,
        cache_dir,
        follow.local or "no release label",
        follow.repo,
        follow.published,
    )


def _timeout_knob() -> str:
    """Where `huggingface_hub`'s read timeout came from, for a message about one (RM339)."""
    configured = os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT")
    return f"HF_HUB_DOWNLOAD_TIMEOUT is {configured + ' s' if configured else 'unset, so 10 s'}"


#: The Hub's own names for "this repo, revision or file does not exist" (`huggingface_hub.errors`), read
#: by name so this module keeps its one guarded import. `HfFileSystem` raises `FileNotFoundError` for a
#: missing path itself.
_HUB_ABSENT_ERRORS: frozenset[str] = frozenset(
    {"RepositoryNotFoundError", "RevisionNotFoundError", "EntryNotFoundError", "RemoteEntryNotFoundError"}
)


def _hub_says_absent(exc: BaseException) -> bool:
    """Whether a Hub failure is the Hub saying *nothing is there* rather than failing to answer (RM361).

    Only that answer is `SnapshotNotPublished`, which `cache pull` reports as "not published yet" and
    does not count as a failure. A timeout, a 429, a 401/403 or a DNS failure answered nothing about
    whether anything is published, and reading it as "nothing is published" hid every outage of the
    one command that provisions a deployment.
    """
    if type(exc).__name__ == "GatedRepoError":
        return False  # a subclass of RepositoryNotFoundError that means "not allowed", not "absent"
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) in (401, 403):
        return False  # the Hub answers a private repo and an expired token as "not found" with a 401
    return isinstance(exc, FileNotFoundError) or any(
        cls.__name__ in _HUB_ABSENT_ERRORS for cls in type(exc).__mro__
    )


def _fetch_parquet(
    fs,
    remote_path: str,
    local_path: Path,
    *,
    display: str,
    label: str,
    error_cls: type[Exception],
    manifest: SnapshotManifest | None = None,
    relative: str | None = None,
) -> None:
    """One parquet, staged through `.part` and renamed only once its footer verifies, so an interrupted
    download never leaves a truncated file under the real name.

    **A read timeout names its knob** (RM339). `huggingface_hub` reads `HF_HUB_DOWNLOAD_TIMEOUT`, 10 s
    by default, and these files run to 0.5–1 GB, so a slow link failed on a bare `httpx.ReadTimeout`
    that said nothing about where the 10 s came from. Translated to the lane's own error type, after
    the transport's retries, with the files already fetched kept for the re-run.

    **With a manifest, a download is renamed into place only if the manifest attests it by sha256**
    (RM372): a file of another release, or one corrupted in transit with an intact footer, never
    becomes part of the cache.
    """
    tmp_path = local_path.with_suffix(".part")
    logger.info("  Downloading %s ...", display)
    try:
        fs.get(remote_path, str(tmp_path))
    except httpx.TimeoutException as exc:
        tmp_path.unlink(missing_ok=True)
        raise error_cls(
            f"Downloading {display} for the {label} snapshot timed out ({_timeout_knob()}). "
            f"Raise it, for example `export HF_HUB_DOWNLOAD_TIMEOUT=120`, and re-run: the files "
            f"already fetched are kept, and the pull record names the rest."
        ) from exc
    if not parquet_footer_ok(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise error_cls(f"Downloaded {display} is incomplete (missing parquet footer magic)")
    if manifest is not None and relative is not None and not manifest_attests(manifest, relative, tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise error_cls(
            f"Downloaded {display} for the {label} snapshot does not match the size and sha256 its "
            f"{SNAPSHOT_MANIFEST_FILENAME} states: the repo changed mid-pull, or the bytes were damaged "
            f"in transit. Re-run the pull."
        )
    tmp_path.replace(local_path)


def _provision_snapshot(
    cache_dir: Path,
    hf_repo_prefix: str,
    *,
    label: str,
    error_cls: type[Exception],
    filename_glob: str,
    _follow_hub: _FollowHub | None = None,
    preflight: Callable[[SnapshotManifest | None], None] | None = None,
) -> Path:
    """Provision a parquet cache from HuggingFace Hub, returning the cache directory.

    **A cache is trusted without touching the network only when its pull record says the pull
    finished** (RM339), and only for a caller that does not ask to follow the hub (RM420): every file
    the record names is present and whole. `cache pull` and `cache prepare` pass `_follow_hub`, and for
    them a whole cache is compared with the release the repo publishes: one that came from a pull of
    this repo (`_pulled_by_this_repo`) and holds another release is re-pulled down the repo-switch path
    (a file is kept only where the new manifest attests it, and without a manifest none is), and one
    that did not is left alone and reported with both labels, since a snapshot built here may not be
    uploaded yet. `enrich`'s call passes nothing and never reads the hub for a whole cache. Before the record, any
    non-empty set of whole files was trusted, and the `.part` staging that keeps each file whole is
    exactly what made an interrupted pull look finished: a cache holding 3 of 25 chromosomes verified
    file by file and was never completed. The record is written after the remote listing and **before**
    the first download (`locations.PULL_RECORD_FILENAME` says why that order is the fix), so an
    interrupted pull names what it lacks and the next call fetches only that.

    A cache with no record (built locally, or pulled before the record existed) is compared with the
    remote listing once: what is missing is fetched, what verifies is skipped, and the record is
    written. When the listing cannot be read, that cache is used as it is, with a warning that its
    completeness is unknown, because a warm cache must still serve with no network.

    **The repo's `release.json` is placed only over files it may describe** (RM445): every file this
    pull fetched, or kept because the manifest attests it, or because this repo's own pull recorded
    that the files on disk are the release the repo still publishes (`_kept_release`). A file kept
    with no such witness is of unknown release. `cache pull` fetches it again (as a release that
    moved), except in an unrecorded cache stating a release of its own, a builder's statement about its
    bytes; any other caller keeps it, places no `release.json`, and the cache states no release, so its
    label is withheld rather than false, and the record says no `release.json` was placed, which sends
    the next `cache pull` down the refresh. **A pull never fetches beside a local build** (a
    `release.json` no pull of this repo placed), on either path: a complete build is kept as it is, and
    one lacking a part the repo publishes is left untouched, nothing removed or fetched, with what it
    lacks reported as could-not-run and the two remedies named (rebuild it, or move it aside and pull).
    Before, an unrecorded August cache came out of one pull labelled with November's release.

    A corrupt file left by an interrupted download is removed and refetched rather than skipped
    forever. The returned directory holds `data/*.parquet`, which the resolver reads directly (no
    prebuilt `.duckdb` required). Shared by every parquet snapshot; they differ only in
    `hf_repo_prefix`, `label`, `filename_glob`, and the error type raised.

    `filename_glob` names the files this snapshot consists of, and it is load-bearing rather than
    tidiness — see the constants above: a published dataset keeps files from every earlier layout, and
    downloading a foreign one puts two schemas under the reader's `data/*.parquet` glob.
    """
    data_dir = cache_dir / "data"

    existing = list(data_dir.glob("*.parquet")) if data_dir.exists() else []
    foreign = [p for p in existing if not fnmatch(p.name, filename_glob)]
    for path in foreign:
        # Reported, never removed: this is someone's cache directory, and a file we did not put there
        # is not ours to delete. But it *will* break the reader, so say which file and what fixes it —
        # a bare DuckDB binder error names a column, not a cause.
        logger.warning(
            "%s cache holds %s, which is not part of this snapshot (expected %s). The reader globs "
            "data/*.parquet, so a file with another schema makes every query fail — move it aside, or "
            "rebuild the snapshot from source.",
            label,
            path.name,
            filename_glob,
        )
    corrupt = [p for p in existing if not parquet_footer_ok(p)]
    missing = snapshot_record_missing(cache_dir)
    # RM372: a complete pull of **another** repo is not this snapshot. The Ensembl lane moved repos
    # under identical file names, so a record naming the old one used to be returned untouched here.
    recorded_repo = pull_record_repo(cache_dir)
    switched_from = pulled_from(cache_dir, hf_repo_prefix)
    switched = switched_from is not None
    coverage = manifest_coverage(cache_dir)
    whole = (
        bool(existing)
        and not corrupt
        and missing == []
        and not switched
        and (coverage is None or coverage.whole)
    )
    if whole and _follow_hub is None:
        return cache_dir
    # Nothing on disk says this cache is unfinished: the one state that may still serve, as it is,
    # when the published listing cannot be read. Since RM372 that includes a whole cache of another
    # repo (the resolver reads it as the older release it is): a network outage is not a reason to
    # take it away, and "nothing is published" would be false about it.
    servable = bool(existing) and not corrupt and missing in (None, [])
    unrecorded = missing is None and servable
    repo_root = hf_repo_prefix.rsplit("/", 1)[0]

    # RM420: the provisioning commands ask whether the hub publishes another release than this cache
    # holds. Only a whole cache, or an unrecorded one, is asked about: an unfinished pull or a switched
    # repo is pulled below as before.
    refreshing = False
    suspect: frozenset[str] = frozenset()
    if _follow_hub is not None and (whole or unrecorded):
        differs = _compare_with_hub(cache_dir, repo_root, label, _follow_hub)
        if differs and whole and _pulled_by_this_repo(cache_dir, hf_repo_prefix):
            refreshing = True
            _refreshing(cache_dir, label, _follow_hub)
        elif differs and (whole or _follow_hub.local is not None):
            # Built here, or a builder's release over a stale record.
            return _left_alone(cache_dir, label, _follow_hub)
        elif whole and _follow_hub.published is not None and _label_unattested(cache_dir, coverage):
            # RM445: a record from before RM420 placed the hub's label over whatever it kept, so an
            # equal label is not a current cache. Re-pulled as a release that moved: `cache pull`
            # repairs it. (An unrecorded cache needs no case here: its completion below fetches again
            # what nothing attests when it states no release and the hub states one.)
            refreshing = True
            _refreshing(cache_dir, label, _follow_hub, unattested=True)
        elif whole:
            # RM445: a label equal to the hub's is a claim about every file, and a pull from 0.8.3 to 0.8.7
            # could place it over files it kept. A pulled cache (never a build, which differs from the hub
            # by design) is compared with the listing's sizes and LFS digests; a file that differs is
            # fetched again below. `cache pull` only: `enrich` returned a whole cache above, unread.
            if (
                _follow_hub.published is None
                or coverage is not None
                or not _pulled_by_this_repo(cache_dir, hf_repo_prefix)
            ):
                return cache_dir
            try:
                suspect = _differs_from_listing(cache_dir, hf_repo_prefix, filename_glob)
            except OSError as exc:
                _follow_hub.outcome, _follow_hub.detail = (
                    "unknown",
                    f"its files could not be compared ({exc})",
                )
                logger.warning(
                    "%s cache at %s states the release %s publishes, but the listing could not be read to "
                    "compare its files (%s). Using it as it is.",
                    label,
                    cache_dir,
                    _follow_hub.repo,
                    exc,
                )
                return cache_dir
            if not suspect:
                return cache_dir
            _follow_hub.detail = (
                f"{len(suspect)} file(s) differ from the listing: "
                + ", ".join(sorted(suspect)[:5])
                + (", …" if len(suspect) > 5 else "")
            )
            _refreshing(cache_dir, label, _follow_hub, unattested=True)

    # A local build: a `release.json` no pull of this repo placed (no record, or one that does not vouch
    # for it). A pull never fetches beside one, on either path (RM445, the pm's call): its builder's
    # description could not describe the mixture, and putting the published bytes in would be the
    # silent overwrite RM420 refuses. So nothing in it is removed or fetched; what it lacks is reported.
    is_build = (cache_dir / RELEASE_FILENAME).is_file() and not _pulled_by_this_repo(
        cache_dir, hf_repo_prefix
    )
    if switched:
        logger.warning(
            "%s cache at %s was pulled from %s; this snapshot is published at %s now. Re-pulling: a "
            "file is kept only where the new release's manifest attests it.",
            label,
            cache_dir,
            recorded_repo,
            hf_repo_prefix,
        )
    if missing:
        logger.warning(
            "%s cache at %s is an unfinished pull: %d file(s) its pull record names are absent or "
            "truncated (%s). Fetching them.",
            label,
            cache_dir,
            len(missing),
            ", ".join(missing[:5]) + (", …" if len(missing) > 5 else ""),
        )

    logger.info("Provisioning %s parquet cache from HuggingFace Hub ...", label)
    fs = _hub_filesystem()
    if fs is None:
        if servable:
            return _unverified(cache_dir, label, "huggingface_hub is not installed", _follow_hub)
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        )
    try:
        listing = fs.ls(hf_repo_prefix, detail=False)
    except Exception as exc:
        if servable:
            return _unverified(
                cache_dir,
                label,
                f"the published listing could not be read ({type(exc).__name__})",
                _follow_hub,
            )
        if not _hub_says_absent(exc):
            raise error_cls(
                f"the {label} snapshot's listing at {hf_repo_prefix} could not be read "
                f"({type(exc).__name__}: {exc}); whether anything is published there is unknown"
            ) from exc
        raise SnapshotNotPublished(
            f"nothing is published at {hf_repo_prefix} — the repo or its data/ does not exist. "
            f"Build the snapshot locally (`cache rebuild --only …`), or publish one."
        ) from exc
    remote_parquet = [f for f in listing if f.endswith(".parquet")]
    remote_files = [f for f in remote_parquet if fnmatch(f.rsplit("/", 1)[-1], filename_glob)]
    ignored = sorted(f.rsplit("/", 1)[-1] for f in remote_parquet if f not in remote_files)
    if ignored:
        logger.info(
            "Ignoring %d remote parquet file(s) outside this snapshot (%s): %s",
            len(ignored),
            filename_glob,
            ", ".join(ignored),
        )
    if not remote_files:
        if servable:
            return _unverified(
                cache_dir, label, f"{hf_repo_prefix} publishes no {filename_glob}", _follow_hub
            )
        raise error_cls(
            f"no {filename_glob} in {hf_repo_prefix} — the published snapshot carries "
            f"{len(remote_parquet)} parquet file(s), none of them this snapshot's "
            f"({', '.join(ignored) or 'none at all'})"
        )
    logger.info("Found %d remote parquet files", len(remote_files))
    # Check the descriptions before changing the cache, including on a first pull. Staging on the
    # destination filesystem lets us install the exact bytes we checked with an atomic rename.
    staging_parent = next(p for p in (cache_dir, *cache_dir.parents) if p.is_dir())
    with tempfile.TemporaryDirectory(dir=staging_parent) as scratch:
        staged_manifest = Path(scratch) / SNAPSHOT_MANIFEST_FILENAME
        try:
            manifest = _stage_manifest(
                fs, f"{repo_root}/{SNAPSHOT_MANIFEST_FILENAME}", staged_manifest, label
            )
        except OSError as exc:
            # Could not ask, which is not "publishes none": pulling on without it would accept every byte
            # unverified, so this pull stops here, and a cache nothing contradicts is served as it is.
            if servable:
                return _unverified(
                    cache_dir,
                    label,
                    f"its {SNAPSHOT_MANIFEST_FILENAME} could not be fetched ({exc})",
                    _follow_hub,
                )
            raise error_cls(
                f"the {label} repo's {SNAPSHOT_MANIFEST_FILENAME} could not be fetched ({exc}); nothing was "
                f"downloaded, because without it no file can be checked. Re-run the pull."
            ) from exc
        # The repo's `release.json`, fetched **now** and staged beside the cache like the manifest, and
        # placed with the other root files at the end only if it may describe every file the cache then
        # holds (RM445). Asked first because what may be kept depends on it: a file kept from an earlier
        # pull is this release's only when that pull was pulling this same `release.json`. Asked before the
        # manifest is placed, so a could-not-ask here leaves the cache exactly as it was.
        staged_release = Path(scratch) / RELEASE_FILENAME
        try:
            published_release = _stage_release(fs, f"{repo_root}/{RELEASE_FILENAME}", staged_release, label)
        except OSError as exc:
            # Could not ask, which is not "publishes none", as for the manifest: what may be kept and what
            # may be labelled turn on the answer, so this pull stops before anything in the cache moves.
            if servable:
                return _unverified(
                    cache_dir, label, f"its {RELEASE_FILENAME} could not be fetched ({exc})", _follow_hub
                )
            raise error_cls(
                f"the {label} repo's {RELEASE_FILENAME} could not be fetched ({exc}); nothing was downloaded, "
                f"because what a pull keeps and labels depends on it. Re-run the pull."
            ) from exc
        # The optional parquet **sidecars** beside `data/` — ClinVar's `citations/` today. Fetched here so a
        # provisioned snapshot is the same artifact a built one is: without the citations table a consumer has
        # no PMIDs, and `draft-panel` cannot produce a compilable module because `studies.csv` is mandatory.
        # They go in their own directory, never into `data/`, which is the whole reason the layout has a
        # sibling: the readers glob `data/*.parquet` and a two-column table there breaks every query.
        # Listed here, before any download, so the pull record names them with the data (RM339).
        remote_sidecars: list[tuple[str, str]] = []
        for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
            try:
                listed = fs.ls(f"{repo_root}/{sidecar}", detail=False)
            except Exception as exc:
                logger.debug("No %s/ in the %s repo (%s).", sidecar, label, type(exc).__name__)
                continue
            remote_sidecars.extend((sidecar, f) for f in listed if f.endswith(".parquet"))

        planned = [f"{SNAPSHOT_DATA_DIRNAME}/{f.rsplit('/', 1)[-1]}" for f in remote_files] + [
            f"{sidecar}/{f.rsplit('/', 1)[-1]}" for sidecar, f in remote_sidecars
        ]
        lacking = [name for name in planned if not parquet_footer_ok(cache_dir / name)]
        if is_build and lacking:
            # Could not run, never absent (`@unreachable-not-absent`): the parts the repo publishes that this
            # build lacks stay unreachable until someone provides them, and each run says so again.
            logger.warning(
                "%s cache at %s is a local build (its %s was not placed by a pull of %s) and lacks %d part(s) "
                "the repo publishes (%s). A pull never fetches beside a build, so they were not fetched and "
                "what reads them could not run: rebuild the lane with them, or move the build aside and run "
                "`cache pull`.",
                label,
                cache_dir,
                RELEASE_FILENAME,
                hf_repo_prefix,
                len(lacking),
                ", ".join(lacking[:5]) + (", …" if len(lacking) > 5 else ""),
            )
            if _follow_hub is not None:
                if _follow_hub.outcome is None:
                    _compare_with_hub(cache_dir, repo_root, label, _follow_hub)
                return _left_alone(cache_dir, label, _follow_hub)
            return cache_dir
        if manifest is not None:
            unnamed = sorted(
                name
                for name in (f.rsplit("/", 1)[-1] for f in remote_files)
                if manifest.entry(f"{SNAPSHOT_DATA_DIRNAME}/{name}") is None
            )
            if unnamed:
                raise error_cls(
                    f"{hf_repo_prefix} publishes {len(unnamed)} file(s) its own {SNAPSHOT_MANIFEST_FILENAME} "
                    f"does not attest ({', '.join(unnamed[:5])}); a cache holding them would be withheld, "
                    f"so nothing was downloaded."
                )
        if preflight is not None:
            preflight(manifest)
        data_dir.mkdir(parents=True, exist_ok=True)
        if not is_build:
            for p in corrupt:
                logger.warning("Corrupt/truncated %s parquet %s — removing for re-download", label, p.name)
                p.unlink()
        release_part = cache_dir / f"{RELEASE_FILENAME}.part"
        if published_release is not None:
            staged_release.replace(release_part)
        if manifest is not None:
            # Placed **now**, before the record and the first byte, unlike `release.json`. A manifest only
            # ever refuses: a reader withholds whatever it does not attest. So an interrupted pull leaves a
            # cache whose old files the new manifest disowns (withheld, re-pulled on the next call) rather
            # than one whose mixture nothing on disk can see.
            staged_manifest.replace(cache_dir / SNAPSHOT_MANIFEST_FILENAME)
        else:
            # The repo answered that it publishes none: a manifest already here describes other bytes.
            (cache_dir / SNAPSHOT_MANIFEST_FILENAME).unlink(missing_ok=True)

    try:
        if unrecorded:
            absent = [name for name in planned if not parquet_footer_ok(cache_dir / name)]
            if absent:
                logger.warning(
                    "%s cache at %s carries no pull record and lacks %d of the %d file(s) published (%s). "
                    "Fetching them.",
                    label,
                    cache_dir,
                    len(absent),
                    len(planned),
                    ", ".join(absent[:5]) + (", …" if len(absent) > 5 else ""),
                )
        # Read before the record below replaces it: the release this repo's own pull says the files on disk
        # are. Matching the one the repo publishes now is what lets a resumed pull keep what it fetched.
        kept_release = _kept_release(cache_dir, hf_repo_prefix)
        # A file this repo's own pull already placed was checked by sha256 on its way in; only a file of
        # unknown origin (no record, or another repo's) is hashed again. A file an older release's pull
        # placed is of unknown release, so a refresh hashes it too (RM420).
        placed_here = recorded_repo == hf_repo_prefix and not refreshing
        # A refresh replaces the release whole, as a switch does: nothing on disk says which release a whole
        # file without a manifest entry is.
        replacing = switched or refreshing
        keeps = _plan_keeps(cache_dir, remote_files, remote_sidecars, manifest, replacing, placed_here)
        # The files the listing contradicts (RM445): fetched again, whatever the record says of them.
        keeps.update({r: False for r in suspect if r in keeps})
        record_attests = published_release is not None and kept_release == published_release and not replacing
        unattested = [r for r, kept in keeps.items() if kept and not _attested(r, manifest, record_attests)]
        # An unrecorded cache stating a release of its own is a builder's (every builder writes one): its
        # `release.json` is the builder's statement about its bytes, and the pre-check above left it alone
        # where that differs from the hub's. With the hub's own label it is kept as it is, on both paths.
        own_statement = unrecorded and (cache_dir / RELEASE_FILENAME).is_file()
        if unattested and _follow_hub is not None and published_release is not None and not own_statement:
            # RM445: `cache pull` asked for the hub's release, and these files are not attested to be it
            # (an unrecorded cache stating none, or kept from a pull of an earlier release, or from one
            # that recorded none). As a release that moved, they are fetched again, never kept under the
            # new release's label. The labels are read off the staged file, the one that will be placed.
            _follow_hub.repo = repo_root.removeprefix("datasets/")
            _follow_hub.local = _follow_hub.release_label(cache_dir)
            _follow_hub.published = _staged_label(_follow_hub, release_part)
            refreshing = replacing = True
            placed_here = False
            _refreshing(cache_dir, label, _follow_hub, unattested=True)
            record_attests = False
            keeps = _plan_keeps(cache_dir, remote_files, remote_sidecars, manifest, replacing, placed_here)
            unattested = []
        # The hub's description goes in only over files this pull fetched or a manifest or the record
        # attests. Otherwise the cache states no release and its label is withheld: a kept file nothing
        # attests is of unknown release, and stating the hub's would be a confident false answer. A repo
        # publishing no `release.json` has nothing to withhold, and the pull behaves as before.
        withhold = bool(unattested) and published_release is not None
        fetching = [relative for relative, kept in keeps.items() if not kept]

        # A switch is recorded as under way until every file is the new repo's: `pull_record_repo` reads
        # `replacing` first, so an interrupted switch is still a cache of the old repo on the next call.
        record: dict[str, object] = {"repo": hf_repo_prefix, "files": planned, **_carried_groups(cache_dir)}
        if switched_from is not None:
            record[PULL_RECORD_REPLACING_KEY] = switched_from
        if published_release is not None and not any(
            parquet_footer_ok(cache_dir / r)
            and (r in suspect or not (record_attests or (keeps[r] and _attested(r, manifest, False))))
            for r in keeps
        ):
            # Every whole file already under a planned name is this release's, so whatever an interruption
            # leaves is too, and the resume may keep it.
            record[_PULLING_RELEASE_KEY] = published_release
        atomic_write_text(cache_dir / PULL_RECORD_FILENAME, json.dumps(record, indent=2) + "\n")
        if refreshing or (withhold and fetching) or suspect:
            # Withdrawn right before the first byte moves, and fetched last below, as a builder's record is
            # (`@snapshot-layout-locations`): a refresh cut short leaves a cache that states no release, which
            # the next pull reads as differing from the hub's and finishes, never old bytes beside new ones
            # described as the old release. A pull that fetches into a cache it keeps unattested files of
            # withdraws it too (RM445): the file there, an earlier pull's (a build never reaches here),
            # described the cache before these bytes arrived, and cannot describe the mixture after. With
            # nothing to fetch it stays, still describing exactly the bytes it described. A file the
            # listing contradicts withdraws it as well: the label was false about that file.
            (cache_dir / RELEASE_FILENAME).unlink(missing_ok=True)

        for remote_path in remote_files:
            filename = remote_path.rsplit("/", 1)[-1]
            relative = f"{SNAPSHOT_DATA_DIRNAME}/{filename}"
            if keeps[relative]:
                continue
            _fetch_parquet(
                fs,
                remote_path,
                data_dir / filename,
                display=filename,
                label=label,
                error_cls=error_cls,
                manifest=manifest,
                relative=relative,
            )

        for sidecar, remote_path in remote_sidecars:
            filename = remote_path.rsplit("/", 1)[-1]
            # After a switch or a refresh a whole sidecar may be the old release's, and no manifest names
            # `citations/`.
            if keeps[f"{sidecar}/{filename}"]:
                continue
            target_dir = cache_dir / sidecar
            target_dir.mkdir(parents=True, exist_ok=True)
            _fetch_parquet(
                fs,
                remote_path,
                target_dir / filename,
                display=f"{sidecar}/{filename}",
                label=label,
                error_cls=error_cls,
            )

        # `release.json` too, when the repo has one: the publisher uploads it and this only ever fetched
        # parquet, so a *provisioned* snapshot could not say which release it was while a *built* one could.
        # That is the difference between a cache and a pinnable reference — `source_sha256` is what
        # `GenePanelSpec.reference_sha256` pins against (RM4), and it cannot pin a file that was never
        # fetched. It also describes the sidecars (the citations builder merges its own block in), which is
        # what keeps a two-release artifact from being silent about it. Absence is not an error: a repo
        # published before the builder wrote one is still usable. Staged above; placed here, last, and only
        # over files it may describe (RM445).
        #
        # `LICENSE.txt` rides along for the same reason, one step further: a share-alike snapshot's terms
        # are pinned by `license_sha256`, and a consumer that holds the bytes must be able to read what
        # governs them without going back to the source archive. The publisher was dropping it; fetching it
        # here is the other half, so a *provisioned* snapshot is the same artifact a *built* one is. It
        # states the source's terms rather than a release, so it is fetched whatever was kept.
        # **Staged through `.part` like every other download here, because a failed one is not a no-op.**
        # `HfFileSystem.get` creates the local file before it discovers the remote path is missing, so
        # fetching straight to the real name left a 0-byte `LICENSE.txt` in the cache of every snapshot
        # whose repo publishes none — four of them today. An empty licence file is worse than no licence
        # file: the readers guard on `is_file()`, so an absent one withholds (`license_sha256` stays
        # `None`, with a warning) while an empty one pins the terms to the hash of the empty string. The
        # same staging also stops a re-pull whose repo has since dropped the file from truncating a good
        # local copy.
        #
        # **Walked from `locations.SNAPSHOT_ROOT_FILENAMES`, never listed here** — the publish half does
        # the same (`upload.py`), and this half did not. It iterated the pair above by hand, so
        # `avi_knots.parquet` was published and never pulled: the AVI lane stores no `PHRED`, that file is
        # what reconstructs it, and `alphagenome check` refuses a snapshot without it. A pulled lane was
        # therefore unusable while two docstrings here said the file "travels because
        # `SNAPSHOT_ROOT_FILENAMES` names it, not because this function does" (RM209). A registry beside a
        # hand-kept copy of itself is the defect shape, not the count (`@registry-completeness`). The knots
        # belong to a release as the data does, so they follow `release.json`'s rule: never placed over
        # kept files nothing attests, where new knots would reconstruct `PHRED` from the wrong release.
        placed_release = False
        for optional in SNAPSHOT_ROOT_FILENAMES:
            target = cache_dir / optional
            if optional == SNAPSHOT_MANIFEST_FILENAME:
                continue  # asked for and placed before the data
            if optional == RELEASE_FILENAME:
                if published_release is None:
                    # Asked above, and the repo has none: the old repo's or release's file goes after a
                    # switch or a refresh, as for any root file the repo does not publish.
                    if replacing and target.is_file():
                        target.unlink()
                        logger.info(
                            "Removed %s: it came with %s, and %s has none.",
                            optional,
                            switched_from or _follow_hub.local,
                            hf_repo_prefix,
                        )
                    continue
                if not withhold:
                    release_part.replace(target)
                    placed_release = True
                    continue
                release_part.unlink(missing_ok=True)
                kept_own = target.is_file()
                logger.warning(
                    "%s cache at %s keeps %d file(s) nothing attests are the release %s publishes (%s), so "
                    "its %s is not placed: %s",
                    label,
                    cache_dir,
                    len(unattested),
                    repo_root.removeprefix("datasets/"),
                    ", ".join(unattested[:5]) + (", …" if len(unattested) > 5 else ""),
                    RELEASE_FILENAME,
                    "the cache keeps its own, which still describes exactly the files it held"
                    if kept_own
                    else "the cache states no release, and `cache pull` fetches them again",
                )
                continue
            if optional == ALPHAGENOME_KNOTS_FILENAME and withhold:
                continue
            tmp_path = target.with_suffix(target.suffix + ".part")
            try:
                fs.get(f"{repo_root}/{optional}", str(tmp_path))
                tmp_path.replace(target)
            except Exception as exc:
                tmp_path.unlink(missing_ok=True)
                if replacing and target.is_file():
                    # The old repo's or release's file, describing (or licensing) bytes this pull replaced.
                    target.unlink()
                    logger.info(
                        "Removed %s: it came with %s, and %s has none.",
                        optional,
                        switched_from or _follow_hub.local,
                        hf_repo_prefix,
                    )
                logger.info(
                    "No %s in the %s repo (%s); the cache carries data only.",
                    optional,
                    label,
                    type(exc).__name__,
                )
    finally:
        # Placed by now, or never to be: a pull that stopped leaves no staged description behind.
        release_part.unlink(missing_ok=True)
    # Rewritten now that every file is in place: a switch is no longer under way, and the record states
    # the `release.json` this pull placed, so a builder's release written over it later is not taken
    # for this pull (RM420, `_pulled_by_this_repo`); a file it did not place is not vouched for (RM445).
    _write_pull_record(cache_dir, hf_repo_prefix, planned, placed_release=placed_release)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir


#: The largest kept file whose bytes `cache pull` hashes against the listing's LFS sha256 (RM445). Size
#: is compared for every file and costs a `stat`; a digest costs reading the file. A ClinVar chromosome
#: is 1-10 MB and the whole lane about 200 MB, under a second to hash; an AlphaGenome AVI shard runs to
#: gigabytes, and hashing every shard on every `cache pull` would turn a one-request check into minutes
#: of disk reads. A release that moved changes a parquet's size in practice (every core file of the two
#: Ensembl releases did, RM372), so the digest is the second witness where it is cheap, not the only one.
_LISTING_SHA256_MAX_BYTES = 256 * 1024 * 1024


def _listing_sha256(entry: dict) -> str | None:
    """The LFS sha256 a Hub listing entry states, or `None` (a file stored in git, or no `lfs` key)."""
    lfs = entry.get("lfs")
    if isinstance(lfs, dict):
        digest = lfs.get("sha256")
        return digest if isinstance(digest, str) else None
    return None


def _differs_from_listing(cache_dir: Path, hf_repo_prefix: str, filename_glob: str) -> frozenset[str]:
    """The snapshot's files, by path under the cache, that the published listing contradicts (RM445).

    Read from `HfFileSystem.ls(..., detail=True)`, whose entries carry `size` and, for an LFS file,
    `lfs` (`huggingface_hub`'s `BlobLfsInfo`, a dict whose `sha256` is the file's digest), for `data/`
    and every sidecar directory. A file differs when it is absent, its size is not the listing's, or,
    up to `_LISTING_SHA256_MAX_BYTES`, its sha256 is not the listing's. An entry stating no size
    compares nothing. A listing that cannot be read raises `OSError` (could not ask); a sidecar
    directory the repo lacks lists nothing.
    """
    fs = _hub_filesystem()
    if fs is None:
        raise OSError("huggingface_hub is not installed")
    repo_root = hf_repo_prefix.rsplit("/", 1)[0]
    listed: list[tuple[str, dict]] = []
    try:
        entries = fs.ls(hf_repo_prefix, detail=True)
    except Exception as exc:
        raise OSError(f"{type(exc).__name__}: {exc}") from exc
    listed += [(SNAPSHOT_DATA_DIRNAME, e) for e in entries if isinstance(e, dict)]
    for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
        try:
            entries = fs.ls(f"{repo_root}/{sidecar}", detail=True)
        except Exception as exc:
            if not _hub_says_absent(exc):
                raise OSError(f"{sidecar}/: {type(exc).__name__}: {exc}") from exc
            continue
        listed += [(sidecar, e) for e in entries if isinstance(e, dict)]
    differs: set[str] = set()
    for directory, entry in listed:
        name = str(entry.get("name", "")).rsplit("/", 1)[-1]
        if not name.endswith(".parquet"):
            continue
        if directory == SNAPSHOT_DATA_DIRNAME and not fnmatch(name, filename_glob):
            continue  # another layout's file, which the pull never takes
        relative = f"{directory}/{name}"
        local = cache_dir / relative
        size = entry.get("size")
        if not local.is_file() or (isinstance(size, int) and local.stat().st_size != size):
            differs.add(relative)
        elif isinstance(size, int) and size <= _LISTING_SHA256_MAX_BYTES:
            digest = _listing_sha256(entry)
            if digest is not None and digest != _file_sha256(local):
                differs.add(relative)
    return frozenset(differs)


def _stage_release(fs, remote_path: str, staged: Path, label: str) -> str | None:
    """Fetch the repo's `release.json` to `staged`, returning its sha256, or `None` when it has none.

    Three answers, as `_stage_manifest` gives: the Hub saying nothing is there (`_hub_says_absent`) is
    `None`, and the cache carries data only; any other failure is could-not-ask and raises `OSError`,
    because what a pull keeps and labels turns on the answer (RM445).
    """
    try:
        fs.get(remote_path, str(staged))
    except Exception as exc:
        staged.unlink(missing_ok=True)
        if not _hub_says_absent(exc):
            knob = f"; {_timeout_knob()}" if isinstance(exc, httpx.TimeoutException) else ""
            raise OSError(f"{type(exc).__name__}: {exc}{knob}") from exc
        logger.info(
            "No %s in the %s repo (%s); the cache carries data only.",
            RELEASE_FILENAME,
            label,
            type(exc).__name__,
        )
        return None
    return _file_sha256(staged)


def _staged_label(follow: _FollowHub, staged: Path) -> str | None:
    """The lane's own label for the staged `release.json`, read where the lane's reader looks for it."""
    with tempfile.TemporaryDirectory(prefix="staged-release-") as scratch:
        shutil.copyfile(staged, Path(scratch) / RELEASE_FILENAME)
        return follow.release_label(Path(scratch))


def _plan_keeps(
    cache_dir: Path,
    remote_files: list[str],
    remote_sidecars: list[tuple[str, str]],
    manifest: SnapshotManifest | None,
    replacing: bool,
    placed_here: bool,
) -> dict[str, bool]:
    """Every planned file, by its path under the cache, mapped to whether the file already there is kept.

    Decided whole before the first download, so a pull knows what it keeps unattested (RM445) before
    it withdraws or places anything. A data file follows `_keep`; a sidecar is kept when whole, except
    after a switch or a refresh, since no manifest names one.
    """
    keeps: dict[str, bool] = {}
    for remote_path in remote_files:
        relative = f"{SNAPSHOT_DATA_DIRNAME}/{remote_path.rsplit('/', 1)[-1]}"
        keeps[relative] = _keep(
            cache_dir / relative, relative, manifest, switched=replacing, placed_here=placed_here
        )
    for sidecar, remote_path in remote_sidecars:
        relative = f"{sidecar}/{remote_path.rsplit('/', 1)[-1]}"
        keeps[relative] = parquet_footer_ok(cache_dir / relative) and not replacing
    return keeps


def _attested(relative: str, manifest: SnapshotManifest | None, record_attests: bool) -> bool:
    """Whether a file kept under `relative` is attested to be the release being pulled (RM445).

    Two witnesses. The manifest, for a data file: `_keep` keeps one only where the manifest attests it,
    so a kept data file of a lane with a manifest is attested by construction. The pull record, for
    any file: `record_attests` when this repo's own pull says the files on disk are the release whose
    `release.json` the repo publishes now (`_kept_release`). A sidecar has no manifest entry, so only
    the record attests it.
    """
    return record_attests or (manifest is not None and relative.startswith(f"{SNAPSHOT_DATA_DIRNAME}/"))


def _stage_manifest(fs, remote_path: str, staged: Path, label: str) -> SnapshotManifest | None:
    """Fetch the repo's manifest to `staged` and read it, or `None` when it publishes none or it does not parse.

    Three answers. The Hub saying nothing is there (`_hub_says_absent`, RM361) is `None`. Any other
    failure (a timeout, a 429, a 401/403, a 5xx) is could-not-ask and propagates as an `OSError`,
    because pulling on as if there were none would accept every byte unverified. An unreadable one is
    `None` and is not left staged: placing it would make the resolver withhold the cache it describes
    (`manifest_coverage` attests nothing under an unreadable manifest).
    """
    try:
        fs.get(remote_path, str(staged))
    except Exception as exc:
        staged.unlink(missing_ok=True)
        if _hub_says_absent(exc):
            logger.info("No %s in the %s repo (%s).", SNAPSHOT_MANIFEST_FILENAME, label, type(exc).__name__)
            return None
        knob = f"; {_timeout_knob()}" if isinstance(exc, httpx.TimeoutException) else ""
        raise OSError(f"{type(exc).__name__}: {exc}{knob}") from exc
    manifest = read_snapshot_manifest(staged)
    if manifest is None:
        staged.unlink(missing_ok=True)
        logger.warning(
            "The %s repo's %s could not be read; pulling without it, and it is not placed in the cache.",
            label,
            SNAPSHOT_MANIFEST_FILENAME,
        )
    return manifest


def _keep(
    local_path: Path, relative: str, manifest: SnapshotManifest | None, *, switched: bool, placed_here: bool
) -> bool:
    """Whether a file already in the cache is kept rather than fetched again.

    With the release's manifest in hand, only a file it attests is kept (RM372): a whole file under the
    right name may be another release's, which is the whole defect. A file this repo's own pull placed
    (`placed_here`) was hashed on its way in, so its size is compared; a file of unknown origin is
    hashed. Without a manifest, a whole file is kept as before, except after a repo switch, where
    nothing on disk can say which repo a file came from.
    """
    if not parquet_footer_ok(local_path):
        return False
    if manifest is not None:
        if placed_here:
            entry = manifest.entry(relative)
            return entry is not None and entry.size == local_path.stat().st_size
        return manifest_attests(manifest, relative, local_path)
    return not switched


def _unverified(cache_dir: Path, label: str, why: str, follow: _FollowHub | None = None) -> Path:
    """Serve a cache nothing on disk calls unfinished, whose completeness could not be checked, and say so.

    The unknown arm of the three (RM339): neither trusted as complete, which is the defect, nor refused,
    which would take a working cache away from a machine with no network. The record is not written,
    so the next call that can reach the listing checks again.

    A re-pull to a newer published release (RM420) that cannot start for the same reasons serves the
    cache as it is too, before anything in it moved, and says that instead.
    """
    if follow is not None and follow.outcome == "refreshed":
        follow.outcome, follow.detail = "unknown", why
        logger.warning(
            "%s cache at %s was not re-pulled to %s: %s. Using it as it is.",
            label,
            cache_dir,
            follow.published,
            why,
        )
        return cache_dir
    if follow is not None and follow.outcome is None:
        follow.outcome, follow.detail = "unknown", why
    logger.warning(
        "%s cache at %s carries no pull record, and %s, so whether it is complete is unknown. "
        "Using it as it is; a run that can reach HuggingFace checks it against the published listing.",
        label,
        cache_dir,
        why,
    )
    return cache_dir


def ensure_snapshot(
    ensembl_cache: Path | None = None,
    *,
    groups: Sequence[str] = (),
    declared_use: str = "unstated",
    _follow_hub: _FollowHub | None = None,
) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory.

    **`groups` selects optional column groups of the split release** (RM437), pulled into
    `groups/<name>/` beside the core and read through `locations.ensembl_group_dir`, never by path. The
    valid names are the manifest's own `groups`; `core` is refused (`CORE_IS_NOT_A_GROUP`) and so is a
    name the manifest does not publish, both with `ValueError` and before any download. Each named
    group that must be fetched is judged by `check_declared_use` against its licensor's terms
    (`snapshot_group_terms`) before any download too: a named group whose terms refuse the stated use
    raises `LicenseRefusal` when it must be fetched, and under `unstated`, or with terms unknown, the
    group is skipped with the reason logged. A group already current (recorded at the manifest's
    release, every file it attests there at its size) fetches nothing, so it is not gated again
    (`@acquisition-gate-is-not-a-read-gate`; review round 2, D). The check uses the retained core's
    manifest when the pull keeps it, and the staged manifest when the pull installs a release (RM458).

    **The selection is sticky.** The pull record names every group a pull took, with the release its
    files were attested against and the declaration it was admitted under, and every later call
    re-pulls those groups whenever the core's release moves, with or without `groups`. A sticky group
    is gated by `declared_use` when that states a use, else by its recorded declaration; one that is
    skipped, refused or cannot be fetched is logged and left as it was, so `ensembl_group_dir` refuses
    it as another release, and never raises out of a call that did not name it. A group's files are
    checked against the manifest's sha256 on the way in, as the core's are. **A pull record that is there
    and cannot be read** (`locations.pulled_groups` refuses it) is moved aside under a dated name, never
    deleted, and a fresh one naming this lane's repository takes its place, with no groups and no release
    digest, before anything else runs (`_set_aside_unreadable_record`). The pull then goes on with this call's
    groups; a file the manifest attests by sha256 is kept. The warning names the moved file, says any group
    selection it held is lost, and names the repository the fresh record assumes, since the corrupt one may
    have named another. Without the fresh record the cache would read as a local build and never be pulled
    again. A local build writes no pull record, so a corrupt one came from a pull.
    """
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    named = _named_groups(groups)
    try:
        pulled_groups(cache_dir)
    except EnsemblGroupReleaseError as unreadable:  # the reader's one refusal: a record there and unreadable
        _set_aside_unreadable_record(cache_dir, SNAPSHOT_REPO_PREFIXES["ensembl"], unreadable)
    path = _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["ensembl"],
        label="Ensembl",
        error_cls=EnsemblReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["ensembl"],
        _follow_hub=_follow_hub,
        preflight=partial(_admit_named_groups, cache_dir, named, declared_use) if named else None,
    )
    _provision_groups(cache_dir, named, declared_use, _follow_hub=_follow_hub)
    return path


# ── the split release's optional groups (RM437) ─────────────────────────────────────────────────


def _named_groups(groups: Sequence[str]) -> tuple[str, ...]:
    """The group names a caller asked for, stripped and deduplicated in order; `core` refused (RM437)."""
    raw = (groups,) if isinstance(groups, str) else tuple(groups)
    named = tuple(dict.fromkeys(name.strip() for name in raw if name.strip()))
    if ENSEMBL_CORE_GROUP in named:
        raise ValueError(CORE_IS_NOT_A_GROUP)
    return named


def _effective_group_use(declared_use: str, entry: dict | None) -> str:
    """The declaration a group is gated by: the caller's when it states one, else the one the group was admitted under."""
    return _group_use(declared_use, entry)[0]


#: The pull-record key beside a group's `declared_use`: when that use was declared (0.9, the pm's RM437
#: reading 1), so a re-pull under it can say which declaration admitted the new release.
PULL_RECORD_DECLARED_AT_KEY = "declared_at"
#: What a re-pull under a recorded use says when the record states no time (one written before the key).
DECLARED_AT_UNRECORDED = "at a time the pull record does not state"


def _group_use(declared_use: str, entry: dict | None) -> tuple[str, bool]:
    """`(the use a group is gated by, whether it is the recorded one rather than the call's)`."""
    stated = check_vocab(declared_use, VALID_DECLARED_USE, "declared_use") or declared_use
    if stated != "unstated":
        return stated, False
    recorded = entry.get("declared_use") if entry is not None else None
    if isinstance(recorded, str) and recorded in VALID_DECLARED_USE:
        return recorded, True
    return "unstated", False


def _declaration(entry: dict | None, use: str, from_record: bool) -> dict[str, str]:
    """The `declared_at` a group's entry keeps: the recorded one under the recorded use, now under the call's.

    `unstated` is no declaration, so it gets no time; nor does a record that states none, under its own
    use: a time is never written for a declaration this call did not see.
    """
    if from_record:
        recorded = entry.get(PULL_RECORD_DECLARED_AT_KEY) if entry is not None else None
        return {PULL_RECORD_DECLARED_AT_KEY: recorded} if isinstance(recorded, str) and recorded else {}
    return {PULL_RECORD_DECLARED_AT_KEY: now_utc_iso()} if use != "unstated" else {}


def _recorded_use_note(use: str, declaration: dict[str, str]) -> str:
    """The words a re-pull gated by the recorded use logs: the use, and when it was declared."""
    at = declaration.get(PULL_RECORD_DECLARED_AT_KEY) or DECLARED_AT_UNRECORDED
    return f"under the use recorded for it, {use}, declared {at}; this call states none"


def _known_group(manifest: SnapshotManifest, group: str) -> SnapshotManifestGroup:
    """The manifest's record of `group`, or `ValueError` naming every group it does publish."""
    known = manifest.groups or {}
    if group not in known:
        raise ValueError(
            f"the Ensembl release {manifest.release_id or '(unlabelled)'} publishes no group {group!r}; its "
            f"groups are {', '.join(sorted(known)) or 'none'}"
        )
    return known[group]


def _group_release(manifest: SnapshotManifest, group: str) -> str:
    """The release to which a selected group's files belong."""
    release = (manifest.release_id or "").strip()
    if not release:
        raise EnsemblReferenceError(
            f"the Ensembl release's {SNAPSHOT_MANIFEST_FILENAME} states no release_id, so the {group} group "
            f"cannot be recorded as the core's release"
        )
    return release


def _group_is_current(
    cache_dir: Path, entry: dict | None, release: str, entries: Sequence[SnapshotManifestFile]
) -> bool:
    """Whether a group needs no fetch: recorded at `release`, and every file `entries` attests there at its size."""
    return (
        bool(release)
        and entry is not None
        and entry.get("release_id") == release
        and bool(entries)
        and all(
            (cache_dir / e.path).is_file()
            and e.size is not None
            and (cache_dir / e.path).stat().st_size == e.size
            for e in entries
        )
    )


def _admit_named_groups(
    cache_dir: Path, named: tuple[str, ...], declared_use: str, manifest: SnapshotManifest | None
) -> None:
    """Check every selection against the core's target before fetching any payload."""
    if manifest is None:
        raise EnsemblReferenceError(
            f"The selected Ensembl release has no readable {SNAPSHOT_MANIFEST_FILENAME}, "
            "so the requested groups cannot be checked"
        )
    records = [_known_group(manifest, group) for group in named]
    recorded = pulled_groups(cache_dir)
    release = _group_release(manifest, named[0])
    for group, record in zip(named, records, strict=True):
        if _group_is_current(cache_dir, recorded.get(group), release, _group_entries(manifest, group)):
            continue
        check_declared_use(
            snapshot_group_terms(group, record.licence),
            _effective_group_use(declared_use, recorded.get(group)),
        )


def _group_entries(manifest: SnapshotManifest, group: str) -> list[SnapshotManifestFile]:
    """The files the manifest attests for `group`, each refused unless it lies directly under `groups/<group>/`."""
    entries = manifest.group_files(group)
    if not entries:
        raise EnsemblReferenceError(
            f"the Ensembl release's {SNAPSHOT_MANIFEST_FILENAME} attests no file for the {group} group"
        )
    for entry in entries:
        directory, _, name = entry.path.rpartition("/")
        if (
            group in ("", ".", "..")
            or "/" in group
            or directory != f"{ENSEMBL_GROUPS_DIRNAME}/{group}"
            or not name.endswith(".parquet")
            or name.startswith(".")
        ):
            raise EnsemblReferenceError(
                f"the Ensembl release's {SNAPSHOT_MANIFEST_FILENAME} places a {group} file at {entry.path!r}, "
                f"outside {ENSEMBL_GROUPS_DIRNAME}/{group}/; nothing of that group was downloaded"
            )
    return entries


def _record_group(cache_dir: Path, group: str, entry: dict[str, object]) -> None:
    """Write one group's entry into the pull record, keeping every other key as it is."""
    payload = _pull_record(cache_dir) or {}
    groups = payload.get(PULL_RECORD_GROUPS_KEY)
    groups = dict(groups) if isinstance(groups, dict) else {}
    groups[group] = entry
    payload[PULL_RECORD_GROUPS_KEY] = groups
    atomic_write_text(cache_dir / PULL_RECORD_FILENAME, json.dumps(payload, indent=2) + "\n")


def _pull_one_group(
    cache_dir: Path, group: str, manifest: SnapshotManifest | None, declared_use: str, entry: dict | None
) -> str:
    """Bring one group to the core's release, returning its outcome (`_FollowHub.groups`)."""
    if manifest is None:
        raise EnsemblReferenceError(
            f"the Ensembl cache at {cache_dir} carries no readable {SNAPSHOT_MANIFEST_FILENAME}, so no group "
            f"can be attested"
        )
    record = _known_group(manifest, group)
    release = _group_release(manifest, group)
    entries = _group_entries(manifest, group)
    paths = [e.path for e in entries]
    if _group_is_current(cache_dir, entry, release, entries):
        # Nothing is taken, so nothing is gated (`@acquisition-gate-is-not-a-read-gate`).
        return _with_strays(cache_dir, group, manifest, "current")
    use, from_record = _group_use(declared_use, entry)
    declaration = _declaration(entry, use, from_record)
    note = _recorded_use_note(use, declaration) if from_record else None
    reason = check_declared_use(snapshot_group_terms(group, record.licence), use)
    if reason is not None:
        logger.warning("Ensembl group %s: skipped — %s%s", group, reason, f" ({note})" if note else "")
        return f"skipped — {reason}"
    coverage = manifest_coverage(cache_dir)
    if snapshot_record_missing(cache_dir) != [] or coverage is None or not coverage.whole:
        raise EnsemblReferenceError(
            f"the Ensembl cache at {cache_dir} is not a finished pull its {SNAPSHOT_MANIFEST_FILENAME} "
            f"attests whole, so the {group} group is not pulled beside it; run `cache pull --only ensembl` "
            f"where the hub can be read"
        )
    fs = _hub_filesystem()
    if fs is None:
        raise EnsemblReferenceError(f"huggingface_hub is required to download the Ensembl {group} group")
    repo_root = SNAPSHOT_REPO_PREFIXES["ensembl"].rsplit("/", 1)[0]
    earlier = entry.get("files") if entry is not None else None
    stale = [
        p
        for p in (earlier if isinstance(earlier, list) else [])
        if isinstance(p, str) and p not in paths and p.startswith(f"{ENSEMBL_GROUPS_DIRNAME}/{group}/")
    ]
    # Recorded as under way before the first byte moves, so an interrupted pull is never read as current.
    # The earlier release's files stay named beside the new ones until they are removed, or a resumed
    # pull would no longer know they were this lane's to remove.
    _record_group(
        cache_dir,
        group,
        {"release_id": None, "files": [*paths, *stale], "declared_use": use, **declaration},
    )
    logger.info(
        "Pulling the Ensembl %s group (%d file(s)) for %s%s ...",
        group,
        len(entries),
        release,
        f" {note}" if note else "",
    )
    for e in entries:
        local = cache_dir / e.path
        if manifest_attests(manifest, e.path, local):
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            _fetch_parquet(
                fs,
                f"{repo_root}/{e.path}",
                local,
                display=e.path,
                label="Ensembl",
                error_cls=EnsemblReferenceError,
                manifest=manifest,
                relative=e.path,
            )
        except EnsemblReferenceError:
            raise
        except Exception as exc:
            local.with_suffix(".part").unlink(missing_ok=True)
            raise EnsemblReferenceError(
                f"{e.path} of the Ensembl {group} group could not be fetched ({type(exc).__name__}: {exc}); "
                f"the files already fetched are kept, and re-running the pull fetches the rest"
            ) from exc
    for relative in stale:
        # This lane's own earlier pull put it there, and the release now in place does not name it.
        (cache_dir / relative).unlink(missing_ok=True)
        logger.info(
            "Removed %s: an earlier release's %s file the release %s does not name.", relative, group, release
        )
    _record_group(
        cache_dir, group, {"release_id": release, "files": paths, "declared_use": use, **declaration}
    )
    return _with_strays(cache_dir, group, manifest, "pulled")


def _with_strays(cache_dir: Path, group: str, manifest: SnapshotManifest, outcome: str) -> str:
    """`outcome`, or, when the group's directory holds parquet the manifest does not name, the outcome with them.

    No pull removes a file it did not put there, and `ensembl_group_dir` refuses the group while one is
    there, so the pull may not report the group as plainly current or pulled.
    """
    unnamed = _unnamed_group_files(cache_dir, group, manifest)
    if not unnamed:
        return outcome
    note = (
        f"{outcome}, but {cache_dir / ENSEMBL_GROUPS_DIRNAME / group} holds {len(unnamed)} parquet file(s) the "
        f"manifest does not name for the group ({', '.join(unnamed[:5])}{', …' if len(unnamed) > 5 else ''}); "
        f"readers refuse the group until they are moved aside"
    )
    logger.warning("Ensembl group %s: %s", group, note)
    return note


def _provision_groups(
    cache_dir: Path, named: tuple[str, ...], declared_use: str, *, _follow_hub: _FollowHub | None = None
) -> None:
    """Bring every named and every recorded group to the core's release, after the core's pull (RM437).

    Reads the manifest the core's pull left in place, so a group is always attested against the release
    the core now is. A named group's failure raises, once every group has been tried; a recorded group the
    caller did not name is logged and left as it was, whatever went wrong, so `ensembl_group_dir` refuses
    it until a pull succeeds.
    """
    recorded = pulled_groups(cache_dir)
    wanted = [*named, *(group for group in recorded if group not in named)]
    if not wanted:
        return
    manifest = read_snapshot_manifest(cache_dir / SNAPSHOT_MANIFEST_FILENAME)
    if named:
        # A whole core, a local build or a cache served during an outage may have been kept.
        # Check all selections before the first group can write beside that core.
        _admit_named_groups(cache_dir, named, declared_use, manifest)
    first_failure: Exception | None = None
    for group in wanted:
        try:
            outcome = _pull_one_group(cache_dir, group, manifest, declared_use, recorded.get(group))
        except Exception as exc:  # a group's failure may not take the others', or the core's, away
            if group in named:
                if _follow_hub is not None:
                    _follow_hub.groups[group] = f"FAILED — {exc}"
                first_failure = first_failure or exc
                continue
            logger.warning(
                "Ensembl cache at %s: the %s group, selected by an earlier pull, was not re-pulled (%s); it "
                "is refused to readers until a pull succeeds.",
                cache_dir,
                group,
                exc,
            )
            outcome = f"not re-pulled — {exc}"
        if _follow_hub is not None:
            _follow_hub.groups[group] = outcome
    if first_failure is not None:
        raise first_failure


def ensure_clinvar_snapshot(
    clinvar_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the ClinVar parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(clinvar_cache) if clinvar_cache is not None else default_clinvar_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["clinvar"],
        label="ClinVar",
        error_cls=ClinVarReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["clinvar"],
        _follow_hub=_follow_hub,
    )


def ensure_constraint_snapshot(
    constraint_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the gnomAD constraint parquet cache from HuggingFace Hub.

    The third caller of one download body — the plumbing generalized when ClinVar landed, so this is
    parameterization rather than new machinery.
    """
    cache_dir = Path(constraint_cache) if constraint_cache is not None else default_constraint_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["constraint"],
        label="gnomAD constraint",
        error_cls=ConstraintReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["constraint"],
        _follow_hub=_follow_hub,
    )


def ensure_clinpgx_snapshot(
    clinpgx_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the ClinPGx clinical-annotation snapshot from HuggingFace Hub (RM38).

    The builder shipped a release ahead of this, so the snapshot existed and no code path could reach
    it: `enrich_clinpgx` skipped itself unless a caller passed `--snapshot` by hand, which on a hosted
    deployment means the check simply never ran. Publishable because ClinPGx's recorded terms permit
    redistribution — and the `LICENSE.txt` the builder extracted travels with the parquet, which is what
    makes `license_sha256` pin anything for whoever downloads it.
    """
    cache_dir = Path(clinpgx_cache) if clinpgx_cache is not None else default_clinpgx_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["clinpgx"],
        label="ClinPGx",
        error_cls=GatedSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["clinpgx"],
        _follow_hub=_follow_hub,
    )


def ensure_cpic_snapshot(cpic_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None) -> Path:
    """Provision the CPIC snapshot from HuggingFace Hub (RM38).

    CPIC is open and unauthenticated, so the cache is not about access — it is about a *host* not
    spending one shared per-IP allowance on every caller's request, and about the terms being accepted
    once by the operator who built it rather than implicitly per request.

    There is deliberately **no `ensure_pharmvar_snapshot`** beside this. PharmVar's bulk data is pulled
    under a key its terms §2 make personal and non-transferable, and no axis `SourceTerms` records
    covers passing that on — an unestablished permission is not a permission. That snapshot stays
    operator-built and inject-only (`locations.resolve_pharmvar_reference`).
    """
    cache_dir = Path(cpic_cache) if cpic_cache is not None else default_cpic_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["cpic"],
        label="CPIC",
        error_cls=GatedSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["cpic"],
        _follow_hub=_follow_hub,
    )


def ensure_civic_snapshot(civic_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None) -> Path:
    """Provision the CIViC snapshot from HuggingFace Hub (RM176).

    The cache roster recorded this one's absence as a **gap**, in those words, beside PharmVar's and
    PubMind's refusals: CIViC is CC0 on every axis, so nothing ever barred publishing a snapshot and
    none existed only because nobody had run `civic publish`. Closing it needed a repo, not a
    permission — so the first `civic publish` is what makes this function find anything.
    """
    cache_dir = Path(civic_cache) if civic_cache is not None else default_civic_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["civic"],
        label="CIViC",
        error_cls=OpenSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["civic"],
        _follow_hub=_follow_hub,
    )


def ensure_drug_labels_snapshot(
    drug_labels_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the regulator drug-label snapshot from HuggingFace Hub (RM176).

    Publishable on the annotation lane's grounds and gated on its terms — ClinPGx's CC BY-SA permits
    redistribution and forbids sale, which is why the error type is `GatedSnapshotError` and why
    `cache pull` puts this lane through `check_declared_use` before fetching. `LICENSE.txt` rides
    along with the parquet, because a share-alike snapshot whose terms did not travel pins nothing
    for whoever holds the bytes.
    """
    cache_dir = Path(drug_labels_cache) if drug_labels_cache is not None else default_drug_labels_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["drug_labels"],
        label="ClinPGx drug labels",
        error_cls=GatedSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["drug_labels"],
        _follow_hub=_follow_hub,
    )


def ensure_mitomap_snapshot(
    mitomap_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the MITOMAP snapshot from HuggingFace Hub (RM171).

    Publishable on the source's own terms — CC BY 3.0, with commercial and clinical use stated free —
    so this is a gap-closing `ensure_*` like CIViC's rather than a permission being claimed. The glob
    is `mitomap-*.parquet` rather than `*.parquet` for the reason the constants above record: a
    published dataset keeps files from every earlier layout, and the reader would otherwise union a
    foreign schema into the same directory.
    """
    cache_dir = Path(mitomap_cache) if mitomap_cache is not None else default_mitomap_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["mitomap"],
        label="MITOMAP",
        error_cls=OpenSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["mitomap"],
        _follow_hub=_follow_hub,
    )


def ensure_clinvar_gkm_snapshot(
    clinvar_gkm_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the ClinVar-GKM indel witness from HuggingFace Hub (RM305).

    Publishable on the source's own terms (CC0 over ClinGen's transformation, ClinVar public domain
    underneath). A pulled copy is as current as the last publish, and `clinvar-gkm currency` asks the
    source whether that is still the newest Parquet set.
    """
    cache_dir = Path(clinvar_gkm_cache) if clinvar_gkm_cache is not None else default_clinvar_gkm_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["clinvar_gkm"],
        label="ClinVar-GKM",
        error_cls=OpenSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["clinvar_gkm"],
        _follow_hub=_follow_hub,
    )


def ensure_opentargets_snapshot(
    opentargets_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the trimmed Open Targets Platform snapshot from HuggingFace Hub (RM408).

    The release is CC0-marked, so a deployment pulls ~5.5 GB instead of downloading ~22 GB of
    Platform parquet to cut it. A pulled copy is the release its `release.json` names; the lane pins
    one release, so currency is a new pin, never a re-pull. Public since 0.9 (RM412): the 0.8 line
    carried it as `_ensure_opentargets_snapshot`, reached only through `CACHE_LANES`, because a new
    public function was minor scope there.
    """
    cache_dir = Path(opentargets_cache) if opentargets_cache is not None else default_opentargets_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["opentargets"],
        label="Open Targets",
        error_cls=OpenSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["opentargets"],
        _follow_hub=_follow_hub,
    )


def ensure_alphagenome_avi_snapshot(
    alphagenome_avi_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the AVI snapshot from HuggingFace Hub (RM198).

    **A pull, never a build.** The 88.5 GB source is behind an eligibility gate that bars classes of
    holder outright, so this tier cannot acquire it — but the *re-encoded* snapshot is 34 GB of
    Permissive-Use output (RM195), and `redistribution=True` records the reading that publishing it
    openly falls inside prohibition 1's carve-out. So an operator who cannot download the artifact can
    still pull the lane, which is the whole point of publishing it.

    It is also the first lane whose snapshot is **incomplete without a root-level file**: `PHRED` is
    not stored and `avi_knots.parquet` is what reconstructs it, so a pull that brought only the
    parquets would hand over scores nobody can rank. That file travels because
    `SNAPSHOT_ROOT_FILENAMES` names it, not because this function does.
    """
    cache_dir = (
        Path(alphagenome_avi_cache)
        if alphagenome_avi_cache is not None
        else default_alphagenome_avi_cache_dir()
    )
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["alphagenome_avi"],
        label="AlphaGenome AVI",
        error_cls=OpenSnapshotError,
        filename_glob=SNAPSHOT_FILE_GLOBS["alphagenome_avi"],
        _follow_hub=_follow_hub,
    )


def ensure_strchive_snapshot(
    strchive_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the STRchive catalogue from HuggingFace Hub (RM176).

    **Not `_provision_snapshot`, and the difference is the snapshot rather than the plumbing.** That
    body is parquet all the way down — it globs `data/*.parquet`, trusts a directory whose pull record says the pull finished, and
    re-fetches anything failing the `PAR1` footer check. This snapshot is one JSON catalogue at the
    repo root: there is no `data/`, no footer to check, and no way to tell a truncated JSON file from
    a short one without parsing it. So the catalogue is fetched to a `.part` path and parsed before it
    is renamed into place, which is the same guarantee the footer check gives the parquet lanes —
    an interrupted download never lands under the real name.
    """
    cache_dir = Path(strchive_cache) if strchive_cache is not None else default_strchive_cache_dir()
    return _provision_root_file_snapshot(
        cache_dir,
        _STRCHIVE_HF_REPO,
        payload=STRCHIVE_CATALOGUE_FILENAME,
        label="STRchive",
        error_cls=OpenSnapshotError,
        _follow_hub=_follow_hub,
    )


def _provision_root_file_snapshot(
    cache_dir: Path,
    hf_repo: str,
    *,
    payload: str,
    label: str,
    error_cls: type[Exception],
    _follow_hub: _FollowHub | None = None,
) -> Path:
    """Fetch a snapshot whose payload is one named file at the repo root, plus `release.json`.

    A present, parseable payload is trusted without touching the network — the whole cache, provenance
    included, as a parquet cache whose pull record says the pull finished is trusted whole — for every
    caller but `cache pull` and `cache prepare` (RM420). They pass `_follow_hub`, and a present
    catalogue is compared with the release the repo publishes: re-pulled when the labels differ and
    its pull record says it came from this repo, left alone and reported with both labels when nothing
    says so. Since RM420 a pull writes that record here too; a catalogue pulled before then carries
    none and is left alone, which costs its operator one move-aside rather than risking a build.

    A snapshot that arrived without a `release.json` stays without one until it is re-provisioned,
    which is the parquet lanes' behaviour too and is why it is not repaired here: a catalogue with no
    release label is honestly unlabelled, and the check says so rather than claiming a release it
    cannot name.
    """
    target = cache_dir / payload
    if _json_parses(target):
        if _follow_hub is None or not _compare_with_hub(cache_dir, hf_repo, label, _follow_hub):
            return cache_dir
        if not _pulled_by_this_repo(cache_dir, hf_repo):
            return _left_alone(cache_dir, label, _follow_hub)
        _refreshing(cache_dir, label, _follow_hub)

    logger.info("Provisioning the %s snapshot from HuggingFace Hub ...", label)
    fs = _hub_filesystem()
    if fs is None:
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        )

    created = not cache_dir.exists()
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".part")
    try:
        fs.get(f"{hf_repo}/{payload}", str(tmp_path))
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        if created and not any(cache_dir.iterdir()):
            # The directory this call made for the fetch, and nothing came (RM395): a pull that found
            # nothing published leaves nothing behind, as the parquet lanes' pull now does.
            cache_dir.rmdir()
        if not _hub_says_absent(exc):
            raise error_cls(
                f"{payload} in {hf_repo} could not be fetched ({type(exc).__name__}: {exc}); whether it "
                f"is published there is unknown"
            ) from exc
        raise SnapshotNotPublished(
            f"no {payload} in {hf_repo} — nothing has been published there yet. Build your own with "
            f"`just-dna-enricher {label.lower()} build --out <dir>`."
        ) from exc
    if not _json_parses(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise error_cls(f"Downloaded {payload} is not readable JSON (interrupted download?)")
    # Withdrawn right before the payload moves, and fetched last below (`@snapshot-layout-locations`):
    # the old release's record may not describe the new catalogue for a moment, let alone after a crash.
    # Whether or not this is a refresh (RM445): a `release.json` beside a catalogue that did not parse
    # described that catalogue, never the one about to replace it.
    (cache_dir / RELEASE_FILENAME).unlink(missing_ok=True)
    tmp_path.replace(target)

    # **Staged, like the payload two lines up and like every other fetch in this module** (RM219).
    # It was not, and the module documents at length why that matters: `HfFileSystem.get` creates the
    # local file *before* it discovers the remote path is missing, so an absent `release.json` left a
    # **0-byte** one behind — which `_json_parses` reads as unreadable and `LaneStatus` then reports as
    # `release_unreadable`. An absent label and a corrupt one are different states, and this turned the
    # first into the second on every repo that publishes no description.
    release_target = cache_dir / RELEASE_FILENAME
    release_tmp = release_target.with_suffix(release_target.suffix + ".part")
    placed_release = False
    try:
        fs.get(f"{hf_repo}/{RELEASE_FILENAME}", str(release_tmp))
        release_tmp.replace(release_target)
        placed_release = True
    except Exception as exc:
        release_tmp.unlink(missing_ok=True)
        logger.info(
            "No %s in the %s repo (%s); the snapshot carries no release label.",
            RELEASE_FILENAME,
            label,
            type(exc).__name__,
        )
    # The witness that this catalogue came from a pull of this repo (RM420), written last. It names no
    # files: the payload lands whole by one rename after it parses, so there is no unfinished pull for
    # a file list to describe, and `snapshot_record_missing` judges what a list names by the parquet
    # footer, which a JSON payload never has.
    _write_pull_record(cache_dir, hf_repo, [], placed_release=placed_release)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir


def _json_parses(path: Path) -> bool:
    """A JSON payload's equivalent of the parquet footer check: does it read whole?"""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True

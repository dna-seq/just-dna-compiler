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
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

import httpx
from just_dna_format.layout import atomic_write_text

from just_dna_enricher.clinvar import ClinVarReferenceError
from just_dna_enricher.locations import (
    PULL_RECORD_FILENAME,
    PULL_RECORD_REPLACING_KEY,
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_MANIFEST_FILENAME,
    SNAPSHOT_REPO_IDS,
    SNAPSHOT_ROOT_FILENAMES,
    SNAPSHOT_SIDECAR_DIRNAMES,
    STRCHIVE_CATALOGUE_FILENAME,
    SnapshotManifest,
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
    """

    release_label: Callable[[Path], str | None]
    repo: str | None = None
    local: str | None = None
    published: str | None = None
    outcome: str | None = None
    detail: str | None = None

    def note(self) -> str | None:
        """The line `cache pull` and `cache prepare` print beside the lane, naming both labels; `None` when quiet."""
        local = self.local or "no release label"
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


#: The pull-record key naming the sha256 of the `release.json` the pull placed, `None` when it placed
#: none (RM420). A builder pointed at a pulled cache leaves the old record behind and writes its own
#: `release.json`, so a record whose digest no longer matches is not this cache's origin any more. A
#: record without the key was written before RM420 and is read as a pull, which is what it was: only
#: the provisioner writes one.
_RELEASE_DIGEST_KEY = "release_sha256"


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _write_pull_record(cache_dir: Path, repo: str, files: list[str]) -> None:
    """The record of a pull that finished: its repo, its files, and the `release.json` it placed."""
    record = {"repo": repo, "files": files, _RELEASE_DIGEST_KEY: _file_sha256(cache_dir / RELEASE_FILENAME)}
    atomic_write_text(cache_dir / PULL_RECORD_FILENAME, json.dumps(record, indent=2) + "\n")


def _pulled_by_this_repo(cache_dir: Path, repo: str) -> bool:
    """Whether `cache_dir` came from a pull of `repo` and nothing has been built over it since (RM420).

    The pull record is the witness, because only the provisioner writes one: a builder never does. A
    record naming no repo is read as this repo's, as `locations.pulled_from` reads it.
    """
    try:
        payload = json.loads((cache_dir / PULL_RECORD_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or pulled_from(cache_dir, repo) is not None:
        return False
    if _RELEASE_DIGEST_KEY not in payload:
        return True
    return payload[_RELEASE_DIGEST_KEY] == _file_sha256(cache_dir / RELEASE_FILENAME)


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


def _refreshing(cache_dir: Path, label: str, follow: _FollowHub) -> None:
    follow.outcome = "refreshed"
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
    if _follow_hub is not None and (whole or unrecorded):
        differs = _compare_with_hub(cache_dir, repo_root, label, _follow_hub)
        if differs and whole and _pulled_by_this_repo(cache_dir, hf_repo_prefix):
            refreshing = True
            _refreshing(cache_dir, label, _follow_hub)
        elif differs and (whole or _follow_hub.local is not None):
            # Built here, or a builder's release over a stale record. An unrecorded cache stating no
            # release is no builder's (every builder writes one): it is RM339's case, completed below.
            return _left_alone(cache_dir, label, _follow_hub)
        elif whole:
            return cache_dir

    for p in corrupt:
        logger.warning("Corrupt/truncated %s parquet %s — removing for re-download", label, p.name)
        p.unlink()
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
    # Made only once there is something to put in it (RM395): a pull that found nothing published left
    # an empty `data/`, which `cache status` then called occupied and `cache prepare` refused to build
    # over.
    data_dir.mkdir(parents=True, exist_ok=True)

    # The release's manifest (RM372), fetched **first** and staged beside the cache rather than in it:
    # it is what a kept or a downloaded file is checked against, so it has to be in hand before the
    # first one; and it is renamed into place with the other root files at the end, so it never
    # describes bytes that have not arrived. A repo that publishes none (every lane but Ensembl) or
    # one that does not parse leaves the footer rule as it was.
    manifest_part = cache_dir / f"{SNAPSHOT_MANIFEST_FILENAME}.part"
    try:
        manifest = _stage_manifest(fs, f"{repo_root}/{SNAPSHOT_MANIFEST_FILENAME}", manifest_part, label)
    except OSError as exc:
        # Could not ask, which is not "publishes none": pulling on without it would accept every byte
        # unverified, so this pull stops here, and a cache nothing contradicts is served as it is.
        manifest_part.unlink(missing_ok=True)
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
    if manifest is not None:
        unnamed = sorted(
            name
            for name in (f.rsplit("/", 1)[-1] for f in remote_files)
            if manifest.entry(f"{SNAPSHOT_DATA_DIRNAME}/{name}") is None
        )
        if unnamed:
            manifest_part.unlink(missing_ok=True)
            raise error_cls(
                f"{hf_repo_prefix} publishes {len(unnamed)} file(s) its own {SNAPSHOT_MANIFEST_FILENAME} "
                f"does not attest ({', '.join(unnamed[:5])}); a cache holding them would be withheld, "
                f"so nothing was downloaded."
            )
        # Placed **now**, before the record and the first byte, unlike `release.json`. A manifest only
        # ever refuses: a reader withholds whatever it does not attest. So an interrupted pull leaves a
        # cache whose old files the new manifest disowns (withheld, re-pulled on the next call) rather
        # than one whose mixture nothing on disk can see.
        manifest_part.replace(cache_dir / SNAPSHOT_MANIFEST_FILENAME)
    else:
        # The repo answered that it publishes none: a manifest already here describes other bytes.
        (cache_dir / SNAPSHOT_MANIFEST_FILENAME).unlink(missing_ok=True)

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
    # A switch is recorded as under way until every file is the new repo's: `pull_record_repo` reads
    # `replacing` first, so an interrupted switch is still a cache of the old repo on the next call.
    record: dict[str, object] = {"repo": hf_repo_prefix, "files": planned}
    if switched_from is not None:
        record[PULL_RECORD_REPLACING_KEY] = switched_from
    atomic_write_text(cache_dir / PULL_RECORD_FILENAME, json.dumps(record, indent=2) + "\n")
    # A file this repo's own pull already placed was checked by sha256 on its way in; only a file of
    # unknown origin (no record, or another repo's) is hashed again. A file an older release's pull
    # placed is of unknown release, so a refresh hashes it too (RM420).
    placed_here = recorded_repo == hf_repo_prefix and not refreshing
    # A refresh replaces the release whole, as a switch does: nothing on disk says which release a whole
    # file without a manifest entry is.
    replacing = switched or refreshing
    if refreshing:
        # Withdrawn right before the first byte moves, and fetched last below, as a builder's record is
        # (`@snapshot-layout-locations`): a refresh cut short leaves a cache that states no release, which
        # the next pull reads as differing from the hub's and finishes, never old bytes beside new ones
        # described as the old release.
        (cache_dir / RELEASE_FILENAME).unlink(missing_ok=True)

    for remote_path in remote_files:
        filename = remote_path.rsplit("/", 1)[-1]
        local_path = data_dir / filename
        relative = f"{SNAPSHOT_DATA_DIRNAME}/{filename}"
        if _keep(local_path, relative, manifest, switched=replacing, placed_here=placed_here):
            continue
        _fetch_parquet(
            fs,
            remote_path,
            local_path,
            display=filename,
            label=label,
            error_cls=error_cls,
            manifest=manifest,
            relative=relative,
        )

    for sidecar, remote_path in remote_sidecars:
        filename = remote_path.rsplit("/", 1)[-1]
        target_dir = cache_dir / sidecar
        target_dir.mkdir(parents=True, exist_ok=True)
        local_path = target_dir / filename
        # After a switch or a refresh a whole sidecar may be the old release's, and no manifest names
        # `citations/`.
        if parquet_footer_ok(local_path) and not replacing:
            continue
        _fetch_parquet(
            fs, remote_path, local_path, display=f"{sidecar}/{filename}", label=label, error_cls=error_cls
        )

    # `release.json` too, when the repo has one: the publisher uploads it and this only ever fetched
    # parquet, so a *provisioned* snapshot could not say which release it was while a *built* one could.
    # That is the difference between a cache and a pinnable reference — `source_sha256` is what
    # `GenePanelSpec.reference_sha256` pins against (RM4), and it cannot pin a file that was never
    # fetched. It also describes the sidecars (the citations builder merges its own block in), which is
    # what keeps a two-release artifact from being silent about it. Absence is not an error: a repo
    # published before the builder wrote one is still usable.
    #
    # `LICENSE.txt` rides along for the same reason, one step further: a share-alike snapshot's terms
    # are pinned by `license_sha256`, and a consumer that holds the bytes must be able to read what
    # governs them without going back to the source archive. The publisher was dropping it; fetching it
    # here is the other half, so a *provisioned* snapshot is the same artifact a *built* one is.
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
    # hand-kept copy of itself is the defect shape, not the count (`@registry-completeness`).
    for optional in SNAPSHOT_ROOT_FILENAMES:
        target = cache_dir / optional
        tmp_path = target.with_suffix(target.suffix + ".part")
        if optional == SNAPSHOT_MANIFEST_FILENAME:
            continue  # asked for and placed before the data
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
                "No %s in the %s repo (%s); the cache carries data only.", optional, label, type(exc).__name__
            )
    # Rewritten now that every file is in place: a switch is no longer under way, and the record states
    # the `release.json` this pull placed, so a builder's release written over it later is not taken
    # for this pull (RM420, `_pulled_by_this_repo`).
    _write_pull_record(cache_dir, hf_repo_prefix, planned)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir


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


def ensure_snapshot(ensembl_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["ensembl"],
        label="Ensembl",
        error_cls=EnsemblReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["ensembl"],
        _follow_hub=_follow_hub,
    )


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


def _ensure_opentargets_snapshot(
    opentargets_cache: Path | None = None, *, _follow_hub: _FollowHub | None = None
) -> Path:
    """Provision the trimmed Open Targets Platform snapshot from HuggingFace Hub (RM408).

    The release is CC0-marked, so a deployment pulls ~5.5 GB instead of downloading ~22 GB of
    Platform parquet to cut it. A pulled copy is the release its `release.json` names; the lane pins
    one release, so currency is a new pin, never a re-pull.

    **Private on `main`.** It is reached through `CACHE_LANES` (`cache pull`, `cache prepare`) and a
    new public function is minor scope (RELEASE_CYCLE), so the next minor may give it its siblings'
    public name.
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
    refreshing = False
    if _json_parses(target):
        if _follow_hub is None or not _compare_with_hub(cache_dir, hf_repo, label, _follow_hub):
            return cache_dir
        if not _pulled_by_this_repo(cache_dir, hf_repo):
            return _left_alone(cache_dir, label, _follow_hub)
        refreshing = True
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
    if refreshing:
        # Withdrawn right before the payload moves, and fetched last below (`@snapshot-layout-locations`):
        # the old release's record may not describe the new catalogue for a moment, let alone after a crash.
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
    try:
        fs.get(f"{hf_repo}/{RELEASE_FILENAME}", str(release_tmp))
        release_tmp.replace(release_target)
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
    _write_pull_record(cache_dir, hf_repo, [])
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

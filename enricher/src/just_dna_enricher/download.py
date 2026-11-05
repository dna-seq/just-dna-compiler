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

import json
import logging
import os
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

#: Every pulled lane's HuggingFace dataset repository, by lane name: the **one** place a repo id is
#: spelled (RM384). Each lane's fsspec prefix (`SNAPSHOT_REPO_PREFIXES`), each publisher default
#: (`upload.DEFAULT_*_REPO_ID`) and each lane's `CacheLane.publish_repo` is derived from it. Before
#: RM384 every repo was written twice, as a repo id in `upload.py` and inside a prefix here, with
#: nothing tying the pair, and the Ensembl lane had only the private prefix, so a consumer pinning
#: `manifest.compilation.ensembl_reference` (`org/repo@<rev>`) took the `org/repo` half by stripping
#: `datasets/` and `/data` off it (S130). The keys equal the lanes in `caches.CACHE_LANES` with an
#: `ensure`, asserted by test, and an AST walk refuses a repo id written as a literal anywhere else.
#:
#: Ensembl's is the split release since RM372: prepare-annotations publishes dbSNP 157 / VEP 116 as a
#: **separate** repo, one row per ALT, left-aligned indels, with a `manifest.json` (release id,
#: per-file sha256) and no `release.json`. The old repo, `just-dna-seq/ensembl_variations`, is no
#: longer written and keeps the same file names, which is why a warm cache compares its pull record's
#: repo with this one. This tier pulls it and never publishes it.
SNAPSHOT_REPO_IDS: dict[str, str] = {
    "ensembl": "just-dna-seq/ensembl_variations_split",
    "clinvar": "just-dna-seq/clinvar",
    "constraint": "just-dna-seq/gnomad_constraint",
    "clinpgx": "just-dna-seq/clinpgx",
    "cpic": "just-dna-seq/cpic",
    "drug_labels": "just-dna-seq/clinpgx_drug_labels",
    "civic": "just-dna-seq/civic",
    "strchive": "just-dna-seq/strchive",
    "mitomap": "just-dna-seq/mitomap",
    "alphagenome_avi": "just-dna-seq/alphagenome_avi",
    "clinvar_gkm": "just-dna-seq/clinvar_gkm",
}


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
}


#: Where each lane in `SNAPSHOT_FILE_GLOBS` is pulled from, by lane name: the second half of what a
#: pull is (RM372). A cache whose pull record names another repo is not this lane's snapshot, however
#: complete, so `cache pull` sends it down the pull route; asserted equal in keys to the globs, so a
#: lane cannot gain one and not the other. Each is derived, `datasets/<repo id>/data`, from
#: `SNAPSHOT_REPO_IDS` (RM384): a prefix is where a repo keeps its parquet, never a second spelling of
#: which repo.
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
) -> Path:
    """Provision a parquet cache from HuggingFace Hub, returning the cache directory.

    **A cache is trusted without touching the network only when its pull record says the pull
    finished** (RM339): every file the record names is present and whole. Before the record, any
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
    if existing and not corrupt and missing == [] and not switched and (coverage is None or coverage.whole):
        return cache_dir
    # Nothing on disk says this cache is unfinished: the one state that may still serve, as it is,
    # when the published listing cannot be read. Since RM372 that includes a whole cache of another
    # repo (the resolver reads it as the older release it is): a network outage is not a reason to
    # take it away, and "nothing is published" would be false about it.
    servable = bool(existing) and not corrupt and missing in (None, [])
    unrecorded = missing is None and servable

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
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError as exc:  # the one guarded optional import (CLAUDE.md)
        if servable:
            return _unverified(cache_dir, label, "huggingface_hub is not installed")
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        ) from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    # A token is optional on the read side and doubles the per-IP rate allowance, so the `.env`
    # is read here for the same reason the publisher reads it (`@credential-where-read`):
    # anonymous traffic sleeping on a 429 looks exactly like a hung download. `env_value` reads the
    # one key and exports nothing else from the file (RM301).
    fs = HfFileSystem(token=env_value("HF_TOKEN") or get_token())
    try:
        listing = fs.ls(hf_repo_prefix, detail=False)
    except Exception as exc:
        if servable:
            return _unverified(
                cache_dir, label, f"the published listing could not be read ({type(exc).__name__})"
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
            return _unverified(cache_dir, label, f"{hf_repo_prefix} publishes no {filename_glob}")
        raise error_cls(
            f"no {filename_glob} in {hf_repo_prefix} — the published snapshot carries "
            f"{len(remote_parquet)} parquet file(s), none of them this snapshot's "
            f"({', '.join(ignored) or 'none at all'})"
        )
    logger.info("Found %d remote parquet files", len(remote_files))

    repo_root = hf_repo_prefix.rsplit("/", 1)[0]

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
                cache_dir, label, f"its {SNAPSHOT_MANIFEST_FILENAME} could not be fetched ({exc})"
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
    # unknown origin (no record, or another repo's) is hashed again.
    placed_here = recorded_repo == hf_repo_prefix

    for remote_path in remote_files:
        filename = remote_path.rsplit("/", 1)[-1]
        local_path = data_dir / filename
        relative = f"{SNAPSHOT_DATA_DIRNAME}/{filename}"
        if _keep(local_path, relative, manifest, switched=switched, placed_here=placed_here):
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
        # After a switch a whole sidecar may be the old repo's, and no manifest names `citations/`.
        if parquet_footer_ok(local_path) and not switched:
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
            if switched and target.is_file():
                # The old repo's file, describing (or licensing) bytes this pull replaced.
                target.unlink()
                logger.info(
                    "Removed %s: it came with %s, and %s has none.", optional, switched_from, hf_repo_prefix
                )
            logger.info(
                "No %s in the %s repo (%s); the cache carries data only.", optional, label, type(exc).__name__
            )
    if switched_from is not None:
        atomic_write_text(
            cache_dir / PULL_RECORD_FILENAME,
            json.dumps({"repo": hf_repo_prefix, "files": planned}, indent=2) + "\n",
        )
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


def _unverified(cache_dir: Path, label: str, why: str) -> Path:
    """Serve a cache nothing on disk calls unfinished, whose completeness could not be checked, and say so.

    The unknown arm of the three (RM339): neither trusted as complete, which is the defect, nor refused,
    which would take a working cache away from a machine with no network. The record is not written,
    so the next call that can reach the listing checks again.
    """
    logger.warning(
        "%s cache at %s carries no pull record, and %s, so whether it is complete is unknown. "
        "Using it as it is; a run that can reach HuggingFace checks it against the published listing.",
        label,
        cache_dir,
        why,
    )
    return cache_dir


def ensure_snapshot(ensembl_cache: Path | None = None) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["ensembl"],
        label="Ensembl",
        error_cls=EnsemblReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["ensembl"],
    )


def ensure_clinvar_snapshot(clinvar_cache: Path | None = None) -> Path:
    """Provision the ClinVar parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(clinvar_cache) if clinvar_cache is not None else default_clinvar_cache_dir()
    return _provision_snapshot(
        cache_dir,
        SNAPSHOT_REPO_PREFIXES["clinvar"],
        label="ClinVar",
        error_cls=ClinVarReferenceError,
        filename_glob=SNAPSHOT_FILE_GLOBS["clinvar"],
    )


def ensure_constraint_snapshot(constraint_cache: Path | None = None) -> Path:
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
    )


def ensure_clinpgx_snapshot(clinpgx_cache: Path | None = None) -> Path:
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
    )


def ensure_cpic_snapshot(cpic_cache: Path | None = None) -> Path:
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
    )


def ensure_civic_snapshot(civic_cache: Path | None = None) -> Path:
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
    )


def ensure_drug_labels_snapshot(drug_labels_cache: Path | None = None) -> Path:
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
    )


def ensure_mitomap_snapshot(mitomap_cache: Path | None = None) -> Path:
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
    )


def ensure_clinvar_gkm_snapshot(clinvar_gkm_cache: Path | None = None) -> Path:
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
    )


def ensure_alphagenome_avi_snapshot(alphagenome_avi_cache: Path | None = None) -> Path:
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
    )


def ensure_strchive_snapshot(strchive_cache: Path | None = None) -> Path:
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
    )


def _provision_root_file_snapshot(
    cache_dir: Path,
    hf_repo: str,
    *,
    payload: str,
    label: str,
    error_cls: type[Exception],
) -> Path:
    """Fetch a snapshot whose payload is one named file at the repo root, plus `release.json`.

    A present, parseable payload is trusted without touching the network — the whole cache, provenance
    included, as a parquet cache whose pull record says the pull finished is trusted whole. A snapshot that arrived without a
    `release.json` therefore stays without one until it is re-provisioned from scratch, which is the
    parquet lanes' behaviour too and is why it is not repaired here: a catalogue with no release label
    is honestly unlabelled, and the check says so rather than claiming a release it cannot name.
    """
    target = cache_dir / payload
    if _json_parses(target):
        return cache_dir

    logger.info("Provisioning the %s snapshot from HuggingFace Hub ...", label)
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError as exc:  # the one guarded optional import (CLAUDE.md)
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        ) from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    # A token is optional on the read side and doubles the per-IP rate allowance, so the `.env`
    # is read here for the same reason the publisher reads it (`@credential-where-read`):
    # anonymous traffic sleeping on a 429 looks exactly like a hung download. `env_value` reads the
    # one key and exports nothing else from the file (RM301).
    fs = HfFileSystem(token=env_value("HF_TOKEN") or get_token())
    tmp_path = target.with_suffix(target.suffix + ".part")
    try:
        fs.get(f"{hf_repo}/{payload}", str(tmp_path))
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
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

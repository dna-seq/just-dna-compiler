"""HuggingFace snapshot provisioning — the bulk-fetch side of the resolver chain.

Two reference snapshots share one download body: the Ensembl parquet slice (popular rsIDs) and the
ClinVar parquet slice (clinically-curated GRCh38 records). Neither is a *canonical* reference — each
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
from fnmatch import fnmatch
from pathlib import Path

from just_dna_enricher.clinvar import ClinVarReferenceError
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_LICENSE_FILENAME,
    SNAPSHOT_SIDECAR_DIRNAMES,
    STRCHIVE_CATALOGUE_FILENAME,
    default_civic_cache_dir,
    default_clinpgx_cache_dir,
    default_clinvar_cache_dir,
    default_constraint_cache_dir,
    default_cpic_cache_dir,
    default_drug_labels_cache_dir,
    default_ensembl_cache_dir,
    default_strchive_cache_dir,
    load_env,
)
from just_dna_enricher.resolver import EnsemblReferenceError

logger = logging.getLogger(__name__)

_PARQUET_MAGIC = b"PAR1"
_ENSEMBL_HF_PREFIX = "datasets/just-dna-seq/ensembl_variations/data"
_CLINVAR_HF_PREFIX = "datasets/just-dna-seq/clinvar/data"
_CONSTRAINT_HF_PREFIX = "datasets/just-dna-seq/gnomad_constraint/data"

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
_CLINVAR_FILES = "clinvar-*.parquet"          # deliberately excludes the flat `clinvar.parquet`
_CONSTRAINT_FILES = "gnomad_constraint.parquet"
# The two gated snapshots that may be published (RM38). Both are multi-table, so the glob is the whole
# directory rather than one name — `cpic_build` writes five parquets and `clinpgx_build` one, and both
# sets are this snapshot's own; nothing foreign has ever been published into either repo.
_CLINPGX_FILES = "*.parquet"
_CPIC_FILES = "*.parquet"

_CLINPGX_HF_PREFIX = "datasets/just-dna-seq/clinpgx/data"
_CPIC_HF_PREFIX = "datasets/just-dna-seq/cpic/data"

# The three lanes that had a builder and a licence permitting publication, and no way to fetch the
# result (RM176). CIViC's absent `ensure_*` was recorded in the cache roster as a *gap* rather than a
# refusal — CC0 grants redistribution outright — and STRchive's MIT and the drug labels' CC BY-SA say
# the same thing on their own terms. What was missing in all three cases was plumbing, not permission.
#
# The drug labels are a **second** ClinPGx archive with its own cadence, so they get their own repo
# rather than a table inside `clinpgx/`: `summaryAnnotations.zip` and `drugLabels.zip` do not refresh
# together, and one repo holding both would date the pair from whichever was published last.
_CIVIC_HF_PREFIX = "datasets/just-dna-seq/civic/data"
_DRUG_LABELS_HF_PREFIX = "datasets/just-dna-seq/clinpgx_drug_labels/data"
_CIVIC_FILES = "*.parquet"
_DRUG_LABELS_FILES = "*.parquet"

#: STRchive's repo root, not a `data/` prefix: this snapshot is the upstream catalogue verbatim beside
#: its provenance, and it holds no parquet at all.
_STRCHIVE_HF_REPO = "datasets/just-dna-seq/strchive"


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


def _parquet_footer_ok(path: Path) -> bool:
    """A complete parquet begins and ends with the `PAR1` magic. A truncated/interrupted download —
    the common cache-corruption mode — is missing its footer, which is what makes DuckDB blow up with
    "No magic bytes found at end of file". Reads only 4 bytes from each end."""
    if not path.is_file() or path.stat().st_size < 8:
        return False
    with path.open("rb") as fh:
        if fh.read(4) != _PARQUET_MAGIC:
            return False
        fh.seek(-4, 2)
        return fh.read(4) == _PARQUET_MAGIC


def _provision_snapshot(
    cache_dir: Path,
    hf_repo_prefix: str,
    *,
    label: str,
    error_cls: type[Exception],
    filename_glob: str,
) -> Path:
    """Provision a parquet cache from HuggingFace Hub, returning the cache directory.

    A non-empty cache with no truncated files is trusted without touching the network. Only an empty
    or corrupt cache (re-)downloads — a corrupt file left by an interrupted download is removed and
    refetched rather than skipped forever. The returned directory holds `data/*.parquet`, which the
    resolver reads directly (no prebuilt `.duckdb` required). Shared by all three snapshots; they
    differ only in `hf_repo_prefix`, `label`, `filename_glob`, and the error type raised.

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
            label, path.name, filename_glob,
        )
    corrupt = [p for p in existing if not _parquet_footer_ok(p)]
    if existing and not corrupt:
        return cache_dir

    for p in corrupt:
        logger.warning("Corrupt/truncated %s parquet %s — removing for re-download", label, p.name)
        p.unlink()

    logger.info("Provisioning %s parquet cache from HuggingFace Hub ...", label)
    try:
        from huggingface_hub import HfFileSystem, get_token
    except ImportError as exc:  # the one guarded optional import (CLAUDE.md)
        raise error_cls(
            f"huggingface_hub is required to download the {label} snapshot; install "
            f"just-dna-enricher (which depends on it) or point at a local cache"
        ) from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    # A token is optional on the read side and doubles the per-IP rate allowance, so the `.env`
    # is loaded here for the same reason the publisher loads it (`@credential-where-read`):
    # anonymous traffic sleeping on a 429 looks exactly like a hung download.
    load_env()
    fs = HfFileSystem(token=get_token())
    try:
        listing = fs.ls(hf_repo_prefix, detail=False)
    except Exception as exc:  # noqa: BLE001 - the transport's type is not this module's contract
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
            len(ignored), filename_glob, ", ".join(ignored),
        )
    if not remote_files:
        raise error_cls(
            f"no {filename_glob} in {hf_repo_prefix} — the published snapshot carries "
            f"{len(remote_parquet)} parquet file(s), none of them this snapshot's "
            f"({', '.join(ignored) or 'none at all'})"
        )
    logger.info("Found %d remote parquet files", len(remote_files))
    for remote_path in remote_files:
        filename = remote_path.rsplit("/", 1)[-1]
        local_path = data_dir / filename
        if _parquet_footer_ok(local_path):
            continue
        # Download to a temp path and rename only after the footer verifies, so an interrupted
        # download never leaves a truncated file under the real name.
        tmp_path = local_path.with_suffix(".part")
        logger.info("  Downloading %s ...", filename)
        fs.get(remote_path, str(tmp_path))
        if not _parquet_footer_ok(tmp_path):
            tmp_path.unlink(missing_ok=True)
            raise error_cls(f"Downloaded {filename} is incomplete (missing parquet footer magic)")
        tmp_path.replace(local_path)

    repo_root = hf_repo_prefix.rsplit("/", 1)[0]

    # The optional parquet **sidecars** beside `data/` — ClinVar's `citations/` today. Fetched here so a
    # provisioned snapshot is the same artifact a built one is: without the citations table a consumer has
    # no PMIDs, and `draft-panel` cannot produce a compilable module because `studies.csv` is mandatory.
    # They go in their own directory, never into `data/`, which is the whole reason the layout has a
    # sibling: the readers glob `data/*.parquet` and a two-column table there breaks every query.
    for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
        try:
            remote_sidecar = [
                f for f in fs.ls(f"{repo_root}/{sidecar}", detail=False) if f.endswith(".parquet")
            ]
        except Exception as exc:
            logger.debug("No %s/ in the %s repo (%s).", sidecar, label, type(exc).__name__)
            continue
        target_dir = cache_dir / sidecar
        target_dir.mkdir(parents=True, exist_ok=True)
        for remote_path in remote_sidecar:
            filename = remote_path.rsplit("/", 1)[-1]
            local_path = target_dir / filename
            if _parquet_footer_ok(local_path):
                continue
            tmp_path = local_path.with_suffix(".part")
            logger.info("  Downloading %s/%s ...", sidecar, filename)
            fs.get(remote_path, str(tmp_path))
            if not _parquet_footer_ok(tmp_path):
                tmp_path.unlink(missing_ok=True)
                raise error_cls(
                    f"Downloaded {sidecar}/{filename} is incomplete (missing parquet footer magic)"
                )
            tmp_path.replace(local_path)

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
    for optional in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
        try:
            fs.get(f"{repo_root}/{optional}", str(cache_dir / optional))
        except Exception as exc:
            logger.info("No %s in the %s repo (%s); the cache carries data only.",
                        optional, label, type(exc).__name__)
    logger.info("Download complete: %s", cache_dir)
    return cache_dir


def ensure_snapshot(ensembl_cache: Path | None = None) -> Path:
    """Provision the Ensembl parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(ensembl_cache) if ensembl_cache is not None else default_ensembl_cache_dir()
    return _provision_snapshot(
        cache_dir, _ENSEMBL_HF_PREFIX, label="Ensembl", error_cls=EnsemblReferenceError,
        filename_glob=_ENSEMBL_FILES,
    )


def ensure_clinvar_snapshot(clinvar_cache: Path | None = None) -> Path:
    """Provision the ClinVar parquet cache from HuggingFace Hub, returning the cache directory."""
    cache_dir = Path(clinvar_cache) if clinvar_cache is not None else default_clinvar_cache_dir()
    return _provision_snapshot(
        cache_dir, _CLINVAR_HF_PREFIX, label="ClinVar", error_cls=ClinVarReferenceError,
        filename_glob=_CLINVAR_FILES,
    )


def ensure_constraint_snapshot(constraint_cache: Path | None = None) -> Path:
    """Provision the gnomAD constraint parquet cache from HuggingFace Hub.

    The third caller of one download body — the plumbing generalized when ClinVar landed, so this is
    parameterization rather than new machinery.
    """
    cache_dir = (
        Path(constraint_cache) if constraint_cache is not None else default_constraint_cache_dir()
    )
    return _provision_snapshot(
        cache_dir, _CONSTRAINT_HF_PREFIX, label="gnomAD constraint",
        error_cls=ConstraintReferenceError, filename_glob=_CONSTRAINT_FILES,
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
        cache_dir, _CLINPGX_HF_PREFIX, label="ClinPGx", error_cls=GatedSnapshotError,
        filename_glob=_CLINPGX_FILES,
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
        cache_dir, _CPIC_HF_PREFIX, label="CPIC", error_cls=GatedSnapshotError,
        filename_glob=_CPIC_FILES,
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
        cache_dir, _CIVIC_HF_PREFIX, label="CIViC", error_cls=OpenSnapshotError,
        filename_glob=_CIVIC_FILES,
    )


def ensure_drug_labels_snapshot(drug_labels_cache: Path | None = None) -> Path:
    """Provision the regulator drug-label snapshot from HuggingFace Hub (RM176).

    Publishable on the annotation lane's grounds and gated on its terms — ClinPGx's CC BY-SA permits
    redistribution and forbids sale, which is why the error type is `GatedSnapshotError` and why
    `cache pull` puts this lane through `check_declared_use` before fetching. `LICENSE.txt` rides
    along with the parquet, because a share-alike snapshot whose terms did not travel pins nothing
    for whoever holds the bytes.
    """
    cache_dir = (
        Path(drug_labels_cache) if drug_labels_cache is not None else default_drug_labels_cache_dir()
    )
    return _provision_snapshot(
        cache_dir, _DRUG_LABELS_HF_PREFIX, label="ClinPGx drug labels",
        error_cls=GatedSnapshotError, filename_glob=_DRUG_LABELS_FILES,
    )


def ensure_strchive_snapshot(strchive_cache: Path | None = None) -> Path:
    """Provision the STRchive catalogue from HuggingFace Hub (RM176).

    **Not `_provision_snapshot`, and the difference is the snapshot rather than the plumbing.** That
    body is parquet all the way down — it globs `data/*.parquet`, trusts a populated directory, and
    re-fetches anything failing the `PAR1` footer check. This snapshot is one JSON catalogue at the
    repo root: there is no `data/`, no footer to check, and no way to tell a truncated JSON file from
    a short one without parsing it. So the catalogue is fetched to a `.part` path and parsed before it
    is renamed into place, which is the same guarantee the footer check gives the parquet lanes —
    an interrupted download never lands under the real name.
    """
    cache_dir = (
        Path(strchive_cache) if strchive_cache is not None else default_strchive_cache_dir()
    )
    return _provision_root_file_snapshot(
        cache_dir, _STRCHIVE_HF_REPO, payload=STRCHIVE_CATALOGUE_FILENAME, label="STRchive",
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
    included, exactly as a populated parquet cache is trusted whole. A snapshot that arrived without a
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
    # is loaded here for the same reason the publisher loads it (`@credential-where-read`):
    # anonymous traffic sleeping on a 429 looks exactly like a hung download.
    load_env()
    fs = HfFileSystem(token=get_token())
    tmp_path = target.with_suffix(target.suffix + ".part")
    try:
        fs.get(f"{hf_repo}/{payload}", str(tmp_path))
    except Exception as exc:  # noqa: BLE001 - the transport's type is not this caller's contract
        tmp_path.unlink(missing_ok=True)
        raise SnapshotNotPublished(
            f"no {payload} in {hf_repo} — nothing has been published there yet. Build your own with "
            f"`just-dna-enricher {label.lower()} build --out <dir>`."
        ) from exc
    if not _json_parses(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise error_cls(f"Downloaded {payload} is not readable JSON (interrupted download?)")
    tmp_path.replace(target)

    try:
        fs.get(f"{hf_repo}/{RELEASE_FILENAME}", str(cache_dir / RELEASE_FILENAME))
    except Exception as exc:  # noqa: BLE001 - absence is not an error; a nameless release is honest
        logger.info("No %s in the %s repo (%s); the snapshot carries no release label.",
                    RELEASE_FILENAME, label, type(exc).__name__)
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

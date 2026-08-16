"""HuggingFace upload — publisher surface of the network tier.

Two publish shapes share one create-or-update pathway (``ensure_repo``):

* **module** — a compiled module's artifacts (weights/annotations/studies.parquet + manifest.json,
  and a logo and readme if present) to ``datasets/<repo>/data/<name>/``, matching the layout
  just-dna-lite's discovery scans, **and** to ``data/<name>/v<version>/`` when the manifest states a
  version, so the discovery path can address a particular release rather than only "whatever is there
  now" (``upload_module``; RM84).
* **reference snapshot** — a built ClinVar (or Ensembl) parquet snapshot + ``release.json`` to the
  root of a dataset repo, matching the ``download.ensure_*_snapshot`` layout
  (``publish_reference_snapshot``).

Both require a HuggingFace token with write access (``hf auth login`` or ``HF_TOKEN``). This is the
**dev/publisher** half of the enricher's HuggingFace use: snapshot *download* is a runtime enrich
path (``download.ensure_snapshot``); *upload* is for authors republishing modules (e.g. the Gen-I
``v1-port`` recreation) or publishing a rebuilt reference. Install as ``just-dna-enricher[dev]``.

Extracted from ``just_dna_pipelines.v1_port.publish`` (just-dna-lite); ``create_repo`` was added here
(the origin assumed the repo pre-existed) so a brand-new dataset repo can be created on first push.
"""

import json
from pathlib import Path

from just_dna_format.identity import is_valid_version
from just_dna_format.manifest import README_CANDIDATES
from pydantic import BaseModel, Field

from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
    SNAPSHOT_SIDECAR_DIRNAMES,
)

# weights/annotations/studies are what discovery needs; manifest.json + logo + readme are additive.
_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")
# Named once because two things now have to agree about it: the allowlist that uploads the file, and
# the reader below that takes the module's version out of it.
_MANIFEST_FILENAME = "manifest.json"
# **A manifest field whose bytes nobody uploads is a field that does not travel** — the same gap as
# ClinVar's `citations/` and the ClinPGx `LICENSE.txt` below, and the reason `manifest.readme` (S25) is
# named here in the same commit that adds it. The candidate list is imported rather than spelled out:
# the compiler discovers a readme from `README_CANDIDATES` and this publisher must accept exactly the
# set the compiler can produce, or an author who wrote `README.rst` publishes a manifest attesting a
# file the repo does not carry. `logo.jpeg` is a pre-existing instance of that same skew, left alone
# here because widening it is not this item's decision.
_ALLOW_PATTERNS = [
    *_REQUIRED,
    _MANIFEST_FILENAME,
    "logo.png",
    "logo.jpg",
    *README_CANDIDATES,
]
# A reference snapshot is `data/*.parquet` + its optional parquet sidecars + `release.json` — the
# `ensure_*_snapshot` layout, defined once in `locations` so the publisher and the provisioner cannot
# disagree about it. **The sidecars were the gap this closes:** ClinVar's `citations/` was built and
# never published, so anyone who *downloaded* the snapshot instead of building it had no PMIDs — and a
# drafted gene panel cannot compile without them, because `studies.csv` is mandatory.
#
# **`LICENSE.txt` was the second gap, and it is worse than the sidecars were.** ClinPGx ships its terms
# *inside* the archive the data came from, and the builder extracts them precisely so a holder of the
# snapshot can read what governs the bytes without going back to the archive — the whole pinned-licence
# design (`license_sha256`) rests on that file travelling with them. It was not in these patterns, so
# publishing a share-alike snapshot dropped it silently. Absent is normal (only ClinPGx has one).
_SNAPSHOT_ALLOW_PATTERNS = [
    f"{SNAPSHOT_DATA_DIRNAME}/*.parquet",
    *(f"{name}/*.parquet" for name in SNAPSHOT_SIDECAR_DIRNAMES),
    RELEASE_FILENAME,
    SNAPSHOT_LICENSE_FILENAME,
]

DEFAULT_REPO_ID = "just-dna-seq/annotators"
DEFAULT_CLINVAR_REPO_ID = "just-dna-seq/clinvar"
DEFAULT_CONSTRAINT_REPO_ID = "just-dna-seq/gnomad_constraint"
# The two licence-gated snapshots that may be published (RM38): both record `redistribution=True`, and
# CC BY-SA grants sharing under share-alike plus attribution. **PharmVar has no entry here on purpose** —
# its bulk data is pulled under a personal, non-transferable key and no recorded axis covers passing
# that on, so an unestablished permission stays a refusal.
DEFAULT_CLINPGX_REPO_ID = "just-dna-seq/clinpgx"
DEFAULT_CPIC_REPO_ID = "just-dna-seq/cpic"


def _hf_api(repo_id: str, token: str | None = None):
    """Resolve a write token and return an authenticated ``HfApi``.

    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent
    (a guarded lazy import, so a download-only install that somehow lacks the wheel fails clearly).
    """
    try:
        from huggingface_hub import HfApi, get_token
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required to publish to HuggingFace; install just-dna-enricher "
            "(or just-dna-enricher[dev] for the publisher surface)"
        ) from exc
    resolved_token = token or get_token()
    if not resolved_token:
        raise PermissionError(
            "No HuggingFace token found. Authenticate first (e.g. `hf auth login`, or set HF_TOKEN) "
            f"with write access to {repo_id}."
        )
    return HfApi(token=resolved_token)


def ensure_repo(repo_id: str, token: str | None = None):
    """Create-or-update: ensure the dataset repo exists, returning the authenticated ``HfApi``.

    ``create_repo(..., exist_ok=True)`` is a no-op when the repo already exists, so create and update
    are one pathway. The returned api is reused by the caller's ``upload_folder`` so only one
    ``HfApi`` is constructed per publish.
    """
    api = _hf_api(repo_id, token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
    return api


class UploadPlan(BaseModel):
    """What an upload would send (also the dry-run result)."""

    module: str = Field(description="Module directory name under the collection")
    repo_id: str = Field(description="Target HuggingFace dataset repo (owner/name)")
    path_in_repo: str = Field(description="Path inside the dataset repo (data/<module>)")
    versioned_path_in_repo: str | None = Field(
        default=None,
        description="Second path, data/<module>/v<version>, or null when no version could be read",
    )
    version_unknown_reason: str | None = Field(
        default=None,
        description="Why no versioned path is planned; null when the version was read",
    )
    files: list[str] = Field(description="Basenames that will be uploaded")


def _module_version(module_dir: Path) -> tuple[str | None, str | None]:
    """Read ``identity.version`` out of the compiled manifest — ``(version, reason_it_is_unknown)``.

    Exactly one member is ever set, which is the point: a bare `None` version cannot say whether the
    manifest was missing, unparseable, silent about the version, or carrying something that is not a
    version, and those are four different things for an author to do something about.

    **The one field is read out of the JSON rather than through ``read_manifest``, deliberately.**
    Validating the whole ``ModuleManifest`` to reach one string means an unrelated defect — a hyphen in
    ``identity.name``, an ``icon_set`` outside the vocabulary — withholds a version that is right there
    and perfectly legible, and the resulting refusal names neither the field nor the value. The
    SemVer rule is not restated here either: ``is_valid_version`` is the same predicate
    ``Identity.version``'s own validator calls, and it is what keeps a stray ``/`` or ``..`` out of a
    path segment.

    Never raises: ``manifest.json`` is in ``_ALLOW_PATTERNS`` and **not** in ``_REQUIRED``, so this
    publisher has always accepted a module directory without one, and RM84 is not a licence to tighten
    what it accepts.
    """
    path = module_dir / _MANIFEST_FILENAME
    if not path.is_file():
        return None, f"no {_MANIFEST_FILENAME} in the module directory"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, f"{_MANIFEST_FILENAME} could not be read as JSON"
    identity = document.get("identity") if isinstance(document, dict) else None
    version = identity.get("version") if isinstance(identity, dict) else None
    if version is None:
        return None, f"{_MANIFEST_FILENAME} states no identity.version"
    if not isinstance(version, str) or not is_valid_version(version):
        return None, f"{_MANIFEST_FILENAME}'s identity.version is not MAJOR.MINOR.PATCH: {version!r}"
    return version, None


def plan_upload(
    module_dir: Path,
    name: str,
    repo_id: str | None = None,
) -> UploadPlan:
    """Resolve the upload plan and validate the compiled artifacts are present.

    Two destinations, both planned here (RM84): the flat `data/<name>/`, which is what the reference
    consumer's discovery scans and therefore has to keep working and keep meaning *latest*, and
    `data/<name>/v<version>/` **inside it** — nested rather than a sibling, because the flat path is
    the one deployed readers are pointed at — which is the only thing on that path that can name a
    particular release. A module with no readable version gets the flat path alone, never a `vNone`
    directory, and `version_unknown_reason` says which of the four reasons applies. The reason is a
    field rather than a log line for the reason every other withheld answer here is
    (`clin_sig_not_checked`, `skipped_offline`): a caller that has to parse prose to learn what
    happened has not been told.
    """
    resolved_repo = repo_id or DEFAULT_REPO_ID
    present = [f for f in _ALLOW_PATTERNS if (module_dir / f).exists()]
    missing = [f for f in _REQUIRED if f not in present]
    if missing:
        raise FileNotFoundError(
            f"{name}: missing compiled artifact(s) {missing} in {module_dir} — "
            f"compile the module first (e.g. `just-dna-enricher enrich-and-compile` "
            f"or `just-dna-compiler compile`)"
        )
    flat = f"data/{name}"
    version, reason = _module_version(module_dir)
    return UploadPlan(
        module=name,
        repo_id=resolved_repo,
        path_in_repo=flat,
        versioned_path_in_repo=None if version is None else f"{flat}/v{version}",
        version_unknown_reason=reason,
        files=present,
    )


def upload_module(
    module_dir: Path,
    name: str,
    repo_id: str | None = None,
    token: str | None = None,
    commit_message: str | None = None,
) -> UploadPlan:
    """Upload the compiled module to a HuggingFace dataset collection.

    Ensures the dataset repo exists (create-or-update), then writes the same files to the flat path
    and — when the manifest states a version — to the versioned subdirectory under it.

    **The two writes are two commits, not one.** `upload_folder` commits per call, so a reader can
    briefly see the flat path refreshed while the versioned copy is not there yet; the flat path goes
    first because it is the one anything reads today. Making it atomic means `create_commit` over an
    explicit operation list, which is a different shape from the allow-pattern plumbing every publish
    here uses, and it was not worth holding the fix for. If the second call fails the first has already
    landed — `data/<name>/` is the new release and the versioned copy is absent until a re-run, which
    is idempotent.

    **A versioned path is only as stable as the author's `version:` is.** Nothing here checks the
    remote, so re-publishing without bumping `module_spec.yaml`'s version overwrites
    `data/<name>/v<version>/` with different bytes — the same overwrite the flat path has always done,
    but under a name that invites caching. Refusing it needs a remote read and a policy (warn, refuse,
    `--force`), which is a decision rather than this item.

    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent.
    """
    plan = plan_upload(module_dir, name, repo_id)
    api = ensure_repo(plan.repo_id, token)
    api.upload_folder(
        folder_path=str(module_dir),
        path_in_repo=plan.path_in_repo,
        repo_id=plan.repo_id,
        repo_type="dataset",
        allow_patterns=_ALLOW_PATTERNS,
        commit_message=commit_message or f"Add {name} module",
    )
    if plan.versioned_path_in_repo is not None:
        segment = plan.versioned_path_in_repo.rsplit("/", 1)[-1]
        api.upload_folder(
            folder_path=str(module_dir),
            path_in_repo=plan.versioned_path_in_repo,
            repo_id=plan.repo_id,
            repo_type="dataset",
            allow_patterns=_ALLOW_PATTERNS,
            commit_message=commit_message or f"Add {name} module {segment}",
        )
    return plan


class SnapshotPlan(BaseModel):
    """What a reference-snapshot publish would send (also the dry-run result)."""

    repo_id: str = Field(description="Target HuggingFace dataset repo (owner/name)")
    files: list[str] = Field(description="Repo-relative paths that will be uploaded")


def plan_reference_snapshot(snapshot_dir: Path, repo_id: str | None = None) -> SnapshotPlan:
    """Resolve a snapshot publish plan and validate the built artifacts are present."""
    resolved_repo = repo_id or DEFAULT_CLINVAR_REPO_ID
    data_dir = snapshot_dir / SNAPSHOT_DATA_DIRNAME
    parquet = sorted(p.name for p in data_dir.glob("*.parquet")) if data_dir.is_dir() else []
    if not parquet:
        raise FileNotFoundError(
            f"no {SNAPSHOT_DATA_DIRNAME}/*.parquet in {snapshot_dir} — build the snapshot first "
            f"(e.g. `just-dna-enricher clinvar build`)"
        )
    files = [f"{SNAPSHOT_DATA_DIRNAME}/{name}" for name in parquet]
    # Sidecars, when the snapshot has them. Only ClinVar does, and only when `clinvar citations` was
    # run, so absence is normal rather than a reason to refuse.
    for sidecar in SNAPSHOT_SIDECAR_DIRNAMES:
        directory = snapshot_dir / sidecar
        if directory.is_dir():
            files.extend(f"{sidecar}/{p.name}" for p in sorted(directory.glob("*.parquet")))
    for name in (RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME):
        if (snapshot_dir / name).is_file():
            files.append(name)
    return SnapshotPlan(repo_id=resolved_repo, files=files)


def publish_reference_snapshot(
    snapshot_dir: Path,
    repo_id: str | None = None,
    token: str | None = None,
    commit_message: str | None = None,
) -> SnapshotPlan:
    """Create-or-update a dataset repo and upload a built reference snapshot to its root.

    Uploads ``data/*.parquet`` + any parquet sidecars (ClinVar's ``citations/``) + ``release.json``, so
    the tree matches ``download.ensure_*_snapshot`` and a provisioned snapshot is the same artifact a
    built one is — PMIDs included, which is what a drafted gene panel needs to compile.
    Raises PermissionError if no token is available and ImportError if huggingface_hub is absent.
    """
    plan = plan_reference_snapshot(snapshot_dir, repo_id)
    api = ensure_repo(plan.repo_id, token)
    api.upload_folder(
        folder_path=str(snapshot_dir),
        path_in_repo="",
        repo_id=plan.repo_id,
        repo_type="dataset",
        allow_patterns=_SNAPSHOT_ALLOW_PATTERNS,
        commit_message=commit_message or f"Publish reference snapshot ({len(plan.files)} files)",
    )
    return plan

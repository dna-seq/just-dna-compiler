"""HuggingFace upload — publisher surface of the network tier.

Two publish shapes share one create-or-update pathway (``ensure_repo``):

* **module** — a compiled module's artifacts (weights/annotations/studies.parquet + manifest.json,
  and a logo if present) to ``datasets/<repo>/data/<name>/``, matching the layout just-dna-lite's
  discovery scans (``upload_module``).
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

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# weights/annotations/studies are what discovery needs; manifest.json + logo are additive.
_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")
_ALLOW_PATTERNS = [*_REQUIRED, "manifest.json", "logo.png", "logo.jpg"]
# A reference snapshot is `data/*.parquet` + `release.json` (the ensure_*_snapshot layout).
_SNAPSHOT_ALLOW_PATTERNS = ["data/*.parquet", "release.json"]

DEFAULT_REPO_ID = "just-dna-seq/annotators"
DEFAULT_CLINVAR_REPO_ID = "just-dna-seq/clinvar"
DEFAULT_CONSTRAINT_REPO_ID = "just-dna-seq/gnomad_constraint"


def _hf_api(repo_id: str, token: Optional[str] = None):
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


def ensure_repo(repo_id: str, token: Optional[str] = None):
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
    files: list[str] = Field(description="Basenames that will be uploaded")


def plan_upload(
    module_dir: Path,
    name: str,
    repo_id: Optional[str] = None,
) -> UploadPlan:
    """Resolve the upload plan and validate the compiled artifacts are present."""
    resolved_repo = repo_id or DEFAULT_REPO_ID
    present = [f for f in _ALLOW_PATTERNS if (module_dir / f).exists()]
    missing = [f for f in _REQUIRED if f not in present]
    if missing:
        raise FileNotFoundError(
            f"{name}: missing compiled artifact(s) {missing} in {module_dir} — "
            f"compile the module first (e.g. `just-dna-enricher enrich-and-compile` "
            f"or `just-dna-compiler compile`)"
        )
    return UploadPlan(
        module=name,
        repo_id=resolved_repo,
        path_in_repo=f"data/{name}",
        files=present,
    )


def upload_module(
    module_dir: Path,
    name: str,
    repo_id: Optional[str] = None,
    token: Optional[str] = None,
    commit_message: Optional[str] = None,
) -> UploadPlan:
    """Upload the compiled module to a HuggingFace dataset collection.

    Ensures the dataset repo exists (create-or-update) then uploads in a single commit. Raises
    PermissionError if no token is available and ImportError if huggingface_hub is absent.
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
    return plan


class SnapshotPlan(BaseModel):
    """What a reference-snapshot publish would send (also the dry-run result)."""

    repo_id: str = Field(description="Target HuggingFace dataset repo (owner/name)")
    files: list[str] = Field(description="Repo-relative paths that will be uploaded")


def plan_reference_snapshot(snapshot_dir: Path, repo_id: Optional[str] = None) -> SnapshotPlan:
    """Resolve a snapshot publish plan and validate the built artifacts are present."""
    resolved_repo = repo_id or DEFAULT_CLINVAR_REPO_ID
    data_dir = snapshot_dir / "data"
    parquet = sorted(p.name for p in data_dir.glob("*.parquet")) if data_dir.is_dir() else []
    if not parquet:
        raise FileNotFoundError(
            f"no data/*.parquet in {snapshot_dir} — build the snapshot first "
            f"(e.g. `just-dna-enricher clinvar build`)"
        )
    files = [f"data/{name}" for name in parquet]
    if (snapshot_dir / "release.json").is_file():
        files.append("release.json")
    return SnapshotPlan(repo_id=resolved_repo, files=files)


def publish_reference_snapshot(
    snapshot_dir: Path,
    repo_id: Optional[str] = None,
    token: Optional[str] = None,
    commit_message: Optional[str] = None,
) -> SnapshotPlan:
    """Create-or-update a dataset repo and upload a built reference snapshot to its root.

    Uploads ``data/*.parquet`` + ``release.json`` so the tree matches ``download.ensure_*_snapshot``.
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

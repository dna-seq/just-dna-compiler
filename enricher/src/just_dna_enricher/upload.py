"""HuggingFace module upload — publisher surface of the network tier.

Uploads a compiled module's artifacts (weights/annotations/studies.parquet + manifest.json, and a
logo if present) to ``datasets/<repo>/data/<name>/`` in a single commit, matching the layout
just-dna-lite's discovery scans. Requires a HuggingFace token with write access
(``hf auth login`` or ``HF_TOKEN``).

This is the **dev/publisher** half of the enricher's HuggingFace use: snapshot *download* is a
runtime enrich path (``download.ensure_snapshot``); *upload* is for authors republishing modules
(e.g. the Gen-I ``v1-port`` recreation). Install the publisher surface as ``just-dna-enricher[dev]``.

Extracted from ``just_dna_pipelines.v1_port.publish`` (just-dna-lite).
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# weights/annotations/studies are what discovery needs; manifest.json + logo are additive.
_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")
_ALLOW_PATTERNS = [*_REQUIRED, "manifest.json", "logo.png", "logo.jpg"]

DEFAULT_REPO_ID = "just-dna-seq/annotators"


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

    Raises PermissionError if no token is available. huggingface_hub is imported lazily so a
    download-only install that somehow lacks the wheel still fails with a clear diagnosis.
    """
    plan = plan_upload(module_dir, name, repo_id)
    try:
        from huggingface_hub import HfApi, get_token
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required to upload modules; install just-dna-enricher "
            "(or just-dna-enricher[dev] for the publisher surface)"
        ) from exc

    resolved_token = token or get_token()
    if not resolved_token:
        raise PermissionError(
            "No HuggingFace token found. Authenticate first (e.g. `hf auth login`, or set HF_TOKEN) "
            f"with write access to {plan.repo_id}."
        )
    message = commit_message or f"Add {name} module"
    api = HfApi(token=resolved_token)
    api.upload_folder(
        folder_path=str(module_dir),
        path_in_repo=plan.path_in_repo,
        repo_id=plan.repo_id,
        repo_type="dataset",
        allow_patterns=_ALLOW_PATTERNS,
        commit_message=message,
    )
    return plan

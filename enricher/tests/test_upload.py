"""Unit tests for the HF module-upload publisher surface (no network)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from just_dna_enricher.upload import (
    DEFAULT_CLINVAR_REPO_ID,
    DEFAULT_REPO_ID,
    UploadPlan,
    plan_reference_snapshot,
    plan_upload,
    publish_reference_snapshot,
    upload_module,
)

_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")


def _compiled_module(d: Path, *, logo: bool = False) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED:
        (d / name).write_bytes(b"parquet-placeholder")
    (d / "manifest.json").write_text("{}", encoding="utf-8")
    if logo:
        (d / "logo.png").write_bytes(b"png")
    return d


def _snapshot(d: Path) -> Path:
    (d / "data").mkdir(parents=True, exist_ok=True)
    (d / "data" / "clinvar-chr1.parquet").write_bytes(b"PAR1payloadPAR1")
    (d / "release.json").write_text("{}", encoding="utf-8")
    return d


def test_plan_upload_lists_present_artifacts(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "coronary", logo=True)
    plan = plan_upload(module_dir, "coronary")
    assert plan == UploadPlan(
        module="coronary",
        repo_id=DEFAULT_REPO_ID,
        path_in_repo="data/coronary",
        files=[
            "weights.parquet",
            "annotations.parquet",
            "studies.parquet",
            "manifest.json",
            "logo.png",
        ],
    )


def test_plan_upload_rejects_missing_required(tmp_path: Path) -> None:
    module_dir = tmp_path / "half"
    module_dir.mkdir()
    (module_dir / "weights.parquet").write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="annotations.parquet"):
        plan_upload(module_dir, "half")


def test_plan_upload_honours_repo_override(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "vo2max")
    plan = plan_upload(module_dir, "vo2max", repo_id="org/custom")
    assert plan.repo_id == "org/custom"
    assert plan.path_in_repo == "data/vo2max"


def test_upload_module_calls_hf_api(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "lipidmetabolism")
    mock_api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=mock_api) as api_cls,
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        plan = upload_module(
            module_dir,
            "lipidmetabolism",
            commit_message="Port lipidmetabolism",
        )
    api_cls.assert_called_once_with(token="hf_test_token")
    # upload now routes through ensure_repo → create-or-update the repo, then upload in one commit.
    mock_api.create_repo.assert_called_once_with(
        repo_id=DEFAULT_REPO_ID, repo_type="dataset", exist_ok=True
    )
    mock_api.upload_folder.assert_called_once()
    kwargs: dict[str, Any] = mock_api.upload_folder.call_args.kwargs
    assert kwargs["folder_path"] == str(module_dir)
    assert kwargs["path_in_repo"] == "data/lipidmetabolism"
    assert kwargs["repo_id"] == DEFAULT_REPO_ID
    assert kwargs["repo_type"] == "dataset"
    assert kwargs["commit_message"] == "Port lipidmetabolism"
    assert plan.module == "lipidmetabolism"


def test_upload_module_requires_token(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "superhuman")
    with patch("huggingface_hub.get_token", return_value=None):
        with pytest.raises(PermissionError, match="No HuggingFace token"):
            upload_module(module_dir, "superhuman")


# ── reference-snapshot publish (ClinVar/Ensembl parquet + release.json) ─────────────────────────


def test_plan_reference_snapshot_lists_files(tmp_path: Path) -> None:
    plan = plan_reference_snapshot(_snapshot(tmp_path / "snap"))
    assert plan.repo_id == DEFAULT_CLINVAR_REPO_ID
    assert plan.files == ["data/clinvar-chr1.parquet", "release.json"]


def test_plan_reference_snapshot_carries_the_citations_sidecar(tmp_path: Path) -> None:
    """ClinVar's `citations/` was built and never published, so a consumer who downloaded the snapshot
    got no PMIDs — and a drafted gene panel cannot compile without them (`studies.csv` is mandatory).

    It rides in its own directory, never in `data/`: the readers glob `data/*.parquet`, so a two-column
    citations table there breaks every query.
    """
    snap = _snapshot(tmp_path / "snap")
    (snap / "citations").mkdir()
    (snap / "citations" / "citations.parquet").write_bytes(b"PAR1payloadPAR1")
    plan = plan_reference_snapshot(snap)
    assert plan.files == [
        "data/clinvar-chr1.parquet", "citations/citations.parquet", "release.json",
    ]


def test_a_snapshot_without_citations_publishes_as_before(tmp_path: Path) -> None:
    """Only ClinVar has a sidecar, and only after `clinvar citations` — absence is normal."""
    plan = plan_reference_snapshot(_snapshot(tmp_path / "plain"))
    assert plan.files == ["data/clinvar-chr1.parquet", "release.json"]


def test_plan_reference_snapshot_rejects_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="no data/\\*.parquet"):
        plan_reference_snapshot(empty)


def test_publish_reference_snapshot_creates_repo_then_uploads(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path / "snap")
    mock_api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=mock_api) as api_cls,
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        plan = publish_reference_snapshot(snap, "just-dna-seq/clinvar")
    api_cls.assert_called_once_with(token="hf_test_token")
    mock_api.create_repo.assert_called_once_with(
        repo_id="just-dna-seq/clinvar", repo_type="dataset", exist_ok=True
    )
    kwargs: dict[str, Any] = mock_api.upload_folder.call_args.kwargs
    assert kwargs["folder_path"] == str(snap)
    assert kwargs["path_in_repo"] == ""
    assert kwargs["repo_id"] == "just-dna-seq/clinvar"
    assert kwargs["repo_type"] == "dataset"
    assert kwargs["allow_patterns"] == ["data/*.parquet", "citations/*.parquet", "release.json"]
    assert plan.repo_id == "just-dna-seq/clinvar"


def test_publish_reference_snapshot_requires_token(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path / "snap")
    with patch("huggingface_hub.get_token", return_value=None):
        with pytest.raises(PermissionError, match="No HuggingFace token"):
            publish_reference_snapshot(snap)

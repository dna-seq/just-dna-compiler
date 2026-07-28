"""Unit tests for the HF module-upload publisher surface (no network)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from just_dna_enricher.upload import DEFAULT_REPO_ID, UploadPlan, plan_upload, upload_module

_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")


def _compiled_module(d: Path, *, logo: bool = False) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED:
        (d / name).write_bytes(b"parquet-placeholder")
    (d / "manifest.json").write_text("{}", encoding="utf-8")
    if logo:
        (d / "logo.png").write_bytes(b"png")
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

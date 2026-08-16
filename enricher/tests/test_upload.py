"""Unit tests for the HF module-upload publisher surface (no network)."""

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.cli import app
from just_dna_enricher.upload import (
    DEFAULT_CLINVAR_REPO_ID,
    DEFAULT_REPO_ID,
    UploadPlan,
    plan_reference_snapshot,
    plan_upload,
    publish_reference_snapshot,
    upload_module,
)
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.manifest import (
    README_CANDIDATES,
    Artifact,
    Display,
    Identity,
    ModuleManifest,
    read_manifest,
    write_manifest,
)
from typer.testing import CliRunner

_REQUIRED = ("weights.parquet", "annotations.parquet", "studies.parquet")
_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
# `plan_upload` requires the three SNP-core parquets, so the fixture has to be a module that carries
# `variants.csv` — which rules out both reference examples that state a `version:` today
# (`htt_repeat_expansion`, `pgx_slco1b1_simvastatin` are table-only). The version is therefore written
# into a copy of this spec, which is the same path an author takes: `module_spec.yaml`'s `version:` →
# the compiler's SemVer gate → `manifest.identity.version`.
_EXAMPLE = "hfe_hemochromatosis"
_AUTHORED_VERSION = "2.1.0"


def _manifest(name: str, version: str | None) -> ModuleManifest:
    """The smallest manifest that validates — identity, display, artifact."""
    return ModuleManifest(
        identity=Identity(name=name, version=version),
        display=Display(title=name, description=name, report_title=name),
        artifact=Artifact(digest="sha256:" + "0" * 64),
    )


def _compiled_module(
    d: Path, *, logo: bool = False, version: str | None = "1.2.3", manifest_bytes: str | None = None
) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED:
        (d / name).write_bytes(b"parquet-placeholder")
    if manifest_bytes is None:
        write_manifest(_manifest("test_module", version), d / "manifest.json")
    else:
        (d / "manifest.json").write_text(manifest_bytes, encoding="utf-8")
    if logo:
        (d / "logo.png").write_bytes(b"png")
    return d


def _compile_example(tmp_path: Path, *, version: str | None = None) -> Path:
    """Compile a real reference example, optionally authoring a `version:` first, and return the
    artifact directory."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / _EXAMPLE, spec)
    if version is not None:
        spec_file = spec / "module_spec.yaml"
        document = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        document["module"]["version"] = version
        spec_file.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        # The closure is bound to the authored bytes, and this rewrote one of them (RM73).
        (spec / VERIFICATION_JSON).unlink(missing_ok=True)
    out = tmp_path / "out"
    compile_module(spec, out)
    return out


def _snapshot(d: Path) -> Path:
    (d / "data").mkdir(parents=True, exist_ok=True)
    (d / "data" / "clinvar-chr1.parquet").write_bytes(b"PAR1payloadPAR1")
    (d / "release.json").write_text("{}", encoding="utf-8")
    return d


def test_plan_upload_lists_present_artifacts(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "coronary", logo=True, version="2.0.1")
    plan = plan_upload(module_dir, "coronary")
    assert plan == UploadPlan(
        module="coronary",
        repo_id=DEFAULT_REPO_ID,
        path_in_repo="data/coronary",
        versioned_path_in_repo="data/coronary/v2.0.1",
        version_unknown_reason=None,
        files=[
            "weights.parquet",
            "annotations.parquet",
            "studies.parquet",
            "manifest.json",
            "logo.png",
        ],
    )


def test_plan_upload_carries_the_readme_the_compiler_attests(tmp_path: Path) -> None:
    """A manifest field whose bytes nobody uploads is a field that does not travel (S25).

    `manifest.readme` would otherwise attest a file this publisher leaves behind — the same silent gap
    as ClinVar's unpublished `citations/` and ClinPGx's dropped `LICENSE.txt`. The allowlist is checked
    against the compiler's own discovery set rather than a copy of it, so a stem or extension the
    compiler can produce cannot fall out of what the publisher sends."""
    module_dir = _compiled_module(tmp_path / "candidates")
    (module_dir / "README.md").write_text("# candidate findings\n", encoding="utf-8")
    assert "README.md" in plan_upload(module_dir, "candidates").files

    # Every spelling the compiler will discover is a spelling the publisher accepts.
    for name in README_CANDIDATES:
        alt = _compiled_module(tmp_path / f"m-{name}")
        (alt / name).write_text("prose\n", encoding="utf-8")
        assert name in plan_upload(alt, "m").files, name


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


# ── the version segment (RM84) ──────────────────────────────────────────────────────────────────


def test_a_real_compiled_module_plans_both_paths(tmp_path: Path) -> None:
    """The flat path keeps meaning *latest*; the versioned one is the only thing on the discovery
    path that can name a release, so a republished module stops shadowing itself (RM84).

    Compiled from the real spec rather than a hand-written manifest, because the version has to come
    out of the same place a published module's does: `module_spec.yaml`'s `version:` → the compiler's
    SemVer gate → `manifest.identity.version`.
    """
    out = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    version = read_manifest(out / "manifest.json").identity.version
    assert version == _AUTHORED_VERSION, "the compiler must carry the authored SemVer through"

    plan = plan_upload(out, _EXAMPLE)
    assert plan.path_in_repo == f"data/{_EXAMPLE}"
    assert plan.versioned_path_in_repo == f"data/{_EXAMPLE}/v{version}"
    assert plan.version_unknown_reason is None
    # Verbatim, never a bare major segment: two patch releases of one module would otherwise collide
    # at one path, which is the defect being fixed rather than a smaller version of it.
    assert plan.versioned_path_in_repo.endswith(f"/v{version}")


def test_a_module_with_no_version_gets_the_flat_path_alone(tmp_path: Path) -> None:
    """`Identity.version` is null until the registry stamps one, so most compiled modules have none —
    and `data/<name>/vNone/` would be a path asserting a version that does not exist."""
    out = _compile_example(tmp_path)
    assert read_manifest(out / "manifest.json").identity.version is None

    plan = plan_upload(out, _EXAMPLE)
    assert plan.path_in_repo == f"data/{_EXAMPLE}"
    assert plan.versioned_path_in_repo is None
    assert plan.version_unknown_reason == "manifest.json states no identity.version"


def test_the_reasons_a_version_is_unknown_are_told_apart(tmp_path: Path) -> None:
    """A bare null cannot say whether the manifest was missing, unparseable, silent about the version,
    or carrying something that is not one — four different things for an author to do about it.

    None of them refuses: `manifest.json` is in `_ALLOW_PATTERNS` and **not** in `_REQUIRED`, so this
    publisher has always accepted a directory without one, and closing RM84 is not a licence to
    tighten what it accepts.
    """
    absent = _compiled_module(tmp_path / "absent")
    (absent / "manifest.json").unlink()
    unparseable = _compiled_module(tmp_path / "unparseable", manifest_bytes="{")
    silent = _compiled_module(tmp_path / "silent", version=None)
    freeform = _compiled_module(tmp_path / "freeform", manifest_bytes='{"identity": {"version": "v2"}}')
    dirs = (absent, unparseable, silent, freeform)

    assert {d.name: plan_upload(d, d.name).version_unknown_reason for d in dirs} == {
        "absent": "no manifest.json in the module directory",
        "unparseable": "manifest.json could not be read as JSON",
        "silent": "manifest.json states no identity.version",
        "freeform": "manifest.json's identity.version is not MAJOR.MINOR.PATCH: 'v2'",
    }
    for d in dirs:
        plan = plan_upload(d, d.name)
        assert plan.versioned_path_in_repo is None
        assert plan.files[:3] == list(_REQUIRED)


def test_an_unrelated_manifest_defect_does_not_withhold_a_legible_version(tmp_path: Path) -> None:
    """Reading the one field, rather than validating the whole `ModuleManifest` to reach it.

    A hyphen in `identity.name` or an `icon_set` outside the vocabulary fails `read_manifest` while
    saying nothing about the version, which is right there and canonical — and the refusal that follows
    would name neither the field nor the value. Demonstrated on the old behaviour by checking that the
    model really does reject this document.
    """
    module_dir = _compiled_module(
        tmp_path / "foreign",
        manifest_bytes=json.dumps({"identity": {"name": "not-a-legal-name", "version": "3.1.4"}}),
    )
    with pytest.raises(ValueError):
        read_manifest(module_dir / "manifest.json")

    plan = plan_upload(module_dir, "foreign")
    assert plan.versioned_path_in_repo == "data/foreign/v3.1.4"
    assert plan.version_unknown_reason is None


def test_upload_module_calls_hf_api(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "lipidmetabolism", version="0.4.0")
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
    # upload routes through ensure_repo → create-or-update the repo, then writes both paths.
    mock_api.create_repo.assert_called_once_with(
        repo_id=DEFAULT_REPO_ID, repo_type="dataset", exist_ok=True
    )
    # Two calls, flat first: `upload_folder` commits per call, so this is deliberately two commits and
    # the path everything reads today is the one refreshed first.
    assert [c.kwargs["path_in_repo"] for c in mock_api.upload_folder.call_args_list] == [
        "data/lipidmetabolism",
        "data/lipidmetabolism/v0.4.0",
    ]
    for call in mock_api.upload_folder.call_args_list:
        kwargs: dict[str, Any] = call.kwargs
        assert kwargs["folder_path"] == str(module_dir)
        assert kwargs["repo_id"] == DEFAULT_REPO_ID
        assert kwargs["repo_type"] == "dataset"
        # An explicit message is the caller's and is used verbatim for both commits.
        assert kwargs["commit_message"] == "Port lipidmetabolism"
    # The same allowlist both times — a versioned copy carrying a different file set would not be a
    # copy of the thing at the flat path.
    patterns = {tuple(c.kwargs["allow_patterns"]) for c in mock_api.upload_folder.call_args_list}
    assert len(patterns) == 1
    assert set(_REQUIRED) <= set(next(iter(patterns)))
    assert plan.module == "lipidmetabolism"
    assert plan.versioned_path_in_repo == "data/lipidmetabolism/v0.4.0"


def test_upload_module_writes_one_path_when_the_version_is_unknown(tmp_path: Path) -> None:
    """The dual write is the fix; a `vNone` directory would be the defect wearing a version."""
    module_dir = _compiled_module(tmp_path / "superhuman", version=None)
    mock_api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=mock_api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        plan = upload_module(module_dir, "superhuman")
    mock_api.upload_folder.assert_called_once()
    assert mock_api.upload_folder.call_args.kwargs["path_in_repo"] == "data/superhuman"
    assert plan.versioned_path_in_repo is None


def test_the_default_commit_messages_name_which_copy_they_are(tmp_path: Path) -> None:
    """Two commits land in one repo history; identical default messages would make the versioned copy
    unreadable as a separate act."""
    module_dir = _compiled_module(tmp_path / "coronary", version="1.0.0")
    mock_api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=mock_api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        upload_module(module_dir, "coronary")
    assert [c.kwargs["commit_message"] for c in mock_api.upload_folder.call_args_list] == [
        "Add coronary module",
        "Add coronary module v1.0.0",
    ]


def test_the_dry_run_names_both_destinations(tmp_path: Path) -> None:
    """`--dry-run` is what an author reads before publishing, so it has to show the second path — a
    destination nobody is told about is one nobody checks."""
    out = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    version = read_manifest(out / "manifest.json").identity.version
    result = CliRunner().invoke(app, ["upload", str(out), "--name", "hfe", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "data/hfe/" in result.output
    assert f"data/hfe/v{version}/" in result.output


def test_the_dry_run_says_why_there_is_no_versioned_copy(tmp_path: Path) -> None:
    out = _compile_example(tmp_path)
    result = CliRunner().invoke(app, ["upload", str(out), "--name", "hfe", "--dry-run"])
    assert result.exit_code == 0, result.output
    printed = result.output + (result.stderr if result.stderr_bytes else "")
    assert "data/hfe/" in printed
    assert "states no identity.version" in printed
    assert "/vNone" not in printed


def test_upload_module_requires_token(tmp_path: Path) -> None:
    module_dir = _compiled_module(tmp_path / "superhuman")
    with (
        patch("huggingface_hub.get_token", return_value=None),
        pytest.raises(PermissionError, match="No HuggingFace token"),
    ):
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
    assert kwargs["allow_patterns"] == [
        "data/*.parquet", "citations/*.parquet", "release.json", "LICENSE.txt",
    ]
    assert plan.repo_id == "just-dna-seq/clinvar"


def test_a_snapshots_licence_travels_with_its_bytes(tmp_path: Path) -> None:
    """A share-alike snapshot published without its `LICENSE.txt` is the pinned-licence design broken.

    ClinPGx bundles its terms inside the same archive as the data and the builder extracts them so a
    holder of the snapshot can read what governs the bytes — which `license_sha256` pins. The publisher
    was dropping the file: it was not in the allow-patterns and not in the plan. Demonstrated on the old
    behaviour by leaving it out, which is also the honest normal case (only ClinPGx has one).
    """
    without = _snapshot(tmp_path / "plain")
    assert plan_reference_snapshot(without).files == ["data/clinvar-chr1.parquet", "release.json"]

    with_licence = _snapshot(tmp_path / "clinpgx")
    (with_licence / "LICENSE.txt").write_text("CC BY-SA 4.0 …", encoding="utf-8")
    plan = plan_reference_snapshot(with_licence, "just-dna-seq/clinpgx")
    assert plan.files == ["data/clinvar-chr1.parquet", "release.json", "LICENSE.txt"]


def test_publish_reference_snapshot_requires_token(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path / "snap")
    with (
        patch("huggingface_hub.get_token", return_value=None),
        pytest.raises(PermissionError, match="No HuggingFace token"),
    ):
        publish_reference_snapshot(snap)

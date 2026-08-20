"""Unit tests for the HF module-upload publisher surface (no network)."""

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from just_dna_compiler.compiler import ARTIFACT_PARQUETS, compile_module
from just_dna_enricher.cli import app
from just_dna_enricher.upload import (
    _ALLOW_PATTERNS,
    DEFAULT_CLINVAR_REPO_ID,
    DEFAULT_REPO_ID,
    PublishCollisionError,
    UploadPlan,
    plan_reference_snapshot,
    plan_upload,
    publish_reference_snapshot,
    upload_module,
)
from just_dna_format.integrity import build_artifact
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    Artifact,
    Display,
    Identity,
    ModuleManifest,
    read_manifest,
    write_manifest,
)
from typer.testing import CliRunner

_SNP_CORE = ("weights.parquet", "annotations.parquet", "studies.parquet")
_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
# The RM84 fixtures write a SNP core because that is the commonest shape, not because the publisher
# demands one any more (RM89). The version is written into a copy of this spec, which is the same path
# an author takes: `module_spec.yaml`'s `version:` → the compiler's SemVer gate →
# `manifest.identity.version`.
_EXAMPLE = "hfe_hemochromatosis"
_AUTHORED_VERSION = "2.1.0"
# One real example per publishable shape, chosen to cover both halves of S35: a table-only module (no
# SNP core at all — the seven the old rule refused outright) and a weights-led one carrying a
# `sources.parquet` (the licence table the old allowlist dropped).
_SHAPES = ("pgx_slco1b1_simvastatin", "hfe_hemochromatosis")


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
    for name in _SNP_CORE:
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


def test_every_logo_the_compiler_can_ship_is_a_logo_the_publisher_uploads(tmp_path: Path) -> None:
    """RM105: the logo half of the allowlist was hand-spelled `logo.png`/`logo.jpg`.

    `manifest.LOGO_EXTENSIONS` is `{png, jpg, jpeg}` and `_collect_logo` takes the first in `sorted()`
    order, so **`jpeg` wins over `jpg` over `png`** — and `logo.jpeg` was the one spelling the
    publisher dropped. The manifest then attests, by name and sha256, bytes the published repo does not
    carry, which is exactly what deriving the readme half from `README_CANDIDATES` exists to prevent.
    `verify_manifest(check_logo=True)` does not catch it: an absent file is not a failure there.

    Set equality, not a floor — a floor passes on the pre-fix tree, since two of the three were
    already listed.
    """
    assert {p for p in _ALLOW_PATTERNS if p.startswith("logo.")} == {
        f"logo.{ext}" for ext in LOGO_EXTENSIONS
    }

    for ext in sorted(LOGO_EXTENSIONS):
        module_dir = _compiled_module(tmp_path / f"logo-{ext}")
        (module_dir / f"logo.{ext}").write_bytes(b"image-bytes")
        assert f"logo.{ext}" in plan_upload(module_dir, "m").files, ext

    # …and end to end through a real compile, which is where the skew was actually visible: the
    # winning spelling is the one the publisher used to drop.
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / _EXAMPLE, spec)
    (spec / "logo.jpeg").write_bytes(b"jpeg-bytes")
    out = tmp_path / "compiled"
    compile_module(spec, out)
    manifest = read_manifest(out / "manifest.json")
    assert manifest.logo is not None and manifest.logo.name == "logo.jpeg"
    assert manifest.logo.name in plan_upload(out, "hfe").files


def test_weights_parquet_never_travels_alone(tmp_path: Path) -> None:
    """A SNP core compiles to all three, so `weights.parquet` by itself is an interrupted compile.

    This is the one half of the old blanket rule that survives RM89, and it is scoped to the
    weights-led shape on purpose — the test below shows what the same demand did to every other shape.
    """
    module_dir = tmp_path / "half"
    module_dir.mkdir()
    (module_dir / "weights.parquet").write_bytes(b"x")
    with pytest.raises(FileNotFoundError, match="annotations.parquet"):
        plan_upload(module_dir, "half")


def test_a_directory_with_no_annotation_table_is_not_a_module(tmp_path: Path) -> None:
    """The failure a bare widening of the old rule would have produced, and it would have been silent.

    Dropping the required set without putting a positive rule in its place lets a directory publish as
    `manifest.json` + README with no data in it at all, which discovery then correctly ignores — worse
    than the refusal it replaced, because it leaves a directory behind and says nothing.
    """
    module_dir = tmp_path / "empty"
    module_dir.mkdir()
    write_manifest(_manifest("empty", "1.0.0"), module_dir / "manifest.json")
    (module_dir / "README.md").write_text("prose\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="no annotation table"):
        plan_upload(module_dir, "empty")


def test_a_module_may_carry_no_snp_core_at_all(tmp_path: Path) -> None:
    """RM2 made the SNP core optional four releases ago; `upload._REQUIRED` kept demanding it (S35).

    Measured on 2026-08-17 before the fix: seven of the sixteen reference examples raised here, which
    is every module whose lead table is a 0.4 family rather than `variants.csv`.
    """
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / "pgx_slco1b1_simvastatin", spec)
    out = tmp_path / "out"
    compile_module(spec, out)
    assert not (out / "weights.parquet").exists(), "the fixture must be a genuinely table-only module"

    plan = plan_upload(out, "slco1b1")
    assert "pharm_variants.parquet" in plan.files
    assert plan.path_in_repo == "data/slco1b1"


def test_the_plan_carries_every_file_the_artifact_attests(tmp_path: Path) -> None:
    """`manifest.artifact.files` names a parquet, its sha256 and its size, and `artifact.digest` is a
    Merkle root over exactly those — so a file attested and not uploaded makes the published manifest a
    false claim about bytes that are not there (S35).

    Measured before the fix over the same corpus: eight of the sixteen examples published a manifest
    whose digest the uploaded bytes could not reproduce, `sources.parquet` — the licence and
    attribution table — among the dropped ones every time it existed. Both assertions are computed at
    runtime from the manifest the compiler wrote, never from a copied list of filenames.
    """
    for example in _SHAPES:
        spec = tmp_path / example / "spec"
        shutil.copytree(_EXAMPLES / example, spec)
        out = tmp_path / example / "out"
        compile_module(spec, out)

        manifest = read_manifest(out / "manifest.json")
        attested = {entry.name for entry in manifest.artifact.files}
        assert attested, f"{example}: the fixture must attest at least one parquet"
        plan = plan_upload(out, example)
        assert attested <= set(plan.files), f"{example}: {attested - set(plan.files)} would be dropped"

        # And the consequence that makes it matter: a downloader holding only what was sent recomputes
        # the digest the manifest states.
        received = tmp_path / example / "received"
        received.mkdir()
        for name in plan.files:
            (received / name).write_bytes((out / name).read_bytes())
        assert build_artifact(received, list(ARTIFACT_PARQUETS)).digest == manifest.artifact.digest


def test_an_attested_file_missing_from_disk_refuses(tmp_path: Path) -> None:
    """The general guard, and it is a self-check as much as a module check: it fires whether the file
    was deleted from the directory or this publisher's allowlist fell behind the compiler's."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / _EXAMPLE, spec)
    out = tmp_path / "out"
    compile_module(spec, out)
    (out / "sources.parquet").unlink()

    with pytest.raises(FileNotFoundError, match="sources.parquet"):
        plan_upload(out, _EXAMPLE)


def test_an_unreadable_manifest_withholds_rather_than_refusing(tmp_path: Path) -> None:
    """Tri-state, the same as `version_unknown_reason` beside it: a manifest that cannot say what the
    artifact contains has said *unknown*, not *contains nothing*, and an unknown is never a finding.

    This is what keeps RM84's four reasons four reasons — a directory with no manifest at all is still
    publishable, exactly as it was before this guard existed.
    """
    absent = _compiled_module(tmp_path / "absent")
    (absent / "manifest.json").unlink()
    unparseable = _compiled_module(tmp_path / "unparseable", manifest_bytes="{")
    for module_dir in (absent, unparseable):
        assert set(_SNP_CORE) <= set(plan_upload(module_dir, module_dir.name).files)


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

    None of them refuses: `manifest.json` is in `_ALLOW_PATTERNS` and is not required, so this
    publisher has always accepted a directory without one, and neither RM84 nor RM89 is a licence to
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
        assert plan.files[:3] == list(_SNP_CORE)


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
    assert set(_SNP_CORE) <= set(next(iter(patterns)))
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


# ── RM88: the versioned path refuses to become a different release ────────────────────────────────

_LOCAL_DIGEST = "sha256:" + "0" * 64
_OTHER_DIGEST = "sha256:" + "1" * 64


def _remote(tmp_path: Path, digest: str | None) -> tuple[MagicMock, Path | None]:
    """A mock api whose versioned path holds a manifest with `digest`, or nothing when `digest` is
    None. Returns the api and the file `hf_hub_download` should hand back."""
    api = MagicMock()
    api.token = "hf_test_token"
    if digest is None:
        api.file_exists.return_value = False
        return api, None
    api.file_exists.return_value = True
    published = tmp_path / "published_manifest.json"
    published.write_text(json.dumps({"artifact": {"digest": digest}}), encoding="utf-8")
    return api, published


def _upload(module_dir: Path, api: MagicMock, published: Path | None, **kwargs):
    download = MagicMock(return_value=str(published) if published else "")
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
        patch("huggingface_hub.hf_hub_download", download),
    ):
        return upload_module(module_dir, "test_module", **kwargs)


def test_a_versioned_path_holding_a_different_artifact_refuses(tmp_path: Path) -> None:
    """RM88: republishing without bumping `version:` used to overwrite the versioned copy silently.

    The comparator is `artifact.digest` — a Merkle root over exactly the attested files — read off
    the published manifest, so the question asked is *are these the bytes that version names* rather
    than *is something there*.
    """
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _OTHER_DIGEST)

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    message = str(caught.value)
    assert "data/test_module/v1.2.3" in message
    assert "--force" in message
    assert "version:" in message                       # names the fix, not just the fault
    assert "newer compiler" in message                 # pre-answers "but I changed nothing"
    api.upload_folder.assert_not_called()              # refused BEFORE either write


def test_the_same_artifact_republished_is_not_a_collision(tmp_path: Path) -> None:
    """The case a naive existence check would break, and it is load-bearing rather than tidy.

    `upload_module` writes two commits and documents a re-run as the recovery when the second fails,
    so a gate keying on *presence* would refuse exactly the retry the design depends on. It compares
    digests instead, and identical bytes are not a collision.
    """
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _LOCAL_DIGEST)

    plan = _upload(module_dir, api, published)

    assert [c.kwargs["path_in_repo"] for c in api.upload_folder.call_args_list] == [
        "data/test_module",
        "data/test_module/v1.2.3",
    ]
    assert plan.versioned_path_in_repo == "data/test_module/v1.2.3"


def test_a_first_publish_of_a_version_is_never_a_collision(tmp_path: Path) -> None:
    """Nothing at the path is the normal case, and it costs one `file_exists`, not a download."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, None)

    _upload(module_dir, api, published)

    assert api.file_exists.call_args.kwargs["filename"] == "data/test_module/v1.2.3/manifest.json"
    assert len(api.upload_folder.call_args_list) == 2


def test_force_overwrites_and_does_not_even_ask(tmp_path: Path) -> None:
    """`--force` is the decision that overwriting is sometimes right, so it skips the read entirely —
    a curator re-cutting a draft release should not pay a round trip to be told what they already
    decided."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _OTHER_DIGEST)

    _upload(module_dir, api, published, force=True)

    api.file_exists.assert_not_called()
    assert len(api.upload_folder.call_args_list) == 2


def test_a_module_with_no_version_is_not_gated_at_all(tmp_path: Path) -> None:
    """There is no versioned path to collide with, so there is nothing to ask and nobody to ask."""
    module_dir = _compiled_module(tmp_path / "m", version=None)
    api, published = _remote(tmp_path, _OTHER_DIGEST)

    plan = _upload(module_dir, api, published)

    api.file_exists.assert_not_called()
    assert plan.versioned_path_in_repo is None
    api.upload_folder.assert_called_once()


def test_the_flat_path_is_deliberately_not_guarded(tmp_path: Path) -> None:
    """`data/<name>/` means *latest*, so overwriting it is what it is for — and the whole point of
    the versioned copy is that it is the one that does not move. A gate on both would make every
    republish need `--force`."""
    module_dir = _compiled_module(tmp_path / "m", version=None)
    api, published = _remote(tmp_path, None)

    _upload(module_dir, api, published)

    assert api.upload_folder.call_args.kwargs["path_in_repo"] == "data/test_module"


def test_an_unreadable_published_manifest_proceeds_with_a_warning(
    tmp_path: Path, caplog
) -> None:
    """**Fails open, deliberately.** Nothing established a collision, so nothing may assert one —
    the house algebra withholds on unknown. Failing closed would make a network flake demand
    `--force`, which trains an author to pass it by default and turns the gate into one people route
    around; that is the failure the policy was chosen to avoid, and it must not come back through the
    error path.
    """
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api = MagicMock()
    api.token = "hf_test_token"
    api.file_exists.side_effect = OSError("the hub is unwell")

    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
        caplog.at_level("WARNING"),
    ):
        plan = upload_module(module_dir, "test_module")

    assert len(api.upload_folder.call_args_list) == 2
    assert plan.versioned_path_in_repo == "data/test_module/v1.2.3"
    assert any("Nothing established a collision" in r.message for r in caplog.records)


def test_a_local_module_with_no_readable_digest_is_not_gated(tmp_path: Path) -> None:
    """Tri-state on this side too: an unreadable local manifest is an unknown digest, and an unknown
    cannot disagree with anything. It also cannot have produced a versioned path, which is why this
    is a belt-and-braces case rather than a reachable one."""
    module_dir = _compiled_module(tmp_path / "m", manifest_bytes="{ not json")
    api, published = _remote(tmp_path, _OTHER_DIGEST)

    _upload(module_dir, api, published)

    api.file_exists.assert_not_called()

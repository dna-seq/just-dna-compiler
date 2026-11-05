"""Unit tests for the HF module-upload publisher surface (no network)."""

import ast
import builtins
import io
import json
import shutil
import typing
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import huggingface_hub
import just_dna_compiler.compiler.manifest as compiler_manifest
import just_dna_enricher.upload as upload
import pytest
import yaml
from huggingface_hub.utils import filter_repo_objects
from just_dna_compiler.compiler import ARTIFACT_PARQUETS, compile_module
from just_dna_enricher.cli import app
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.upload import (
    _ALLOW_PATTERNS,
    DEFAULT_CLINVAR_REPO_ID,
    DEFAULT_REPO_ID,
    DEFAULT_STRCHIVE_REPO_ID,
    LayoutShift,
    PruneCandidate,
    PrunePlan,
    PublishCollisionError,
    ToolchainDiffersError,
    UploadPlan,
    _attested_parquets,
    _declared_files,
    plan_reference_snapshot,
    plan_upload,
    prune_repo,
    publish_reference_snapshot,
    upload_module,
)
from just_dna_format.integrity import build_artifact, file_entry, sha256_bytes, sha256_file
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    TOOLCHAIN_DIFFERS,
    Artifact,
    Compilation,
    Display,
    FileEntry,
    Identity,
    ModuleManifest,
    Provenance,
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


class _UnreachableHub:
    """An `HfApi` whose every call fails the way an unreachable hub does (RM368).

    Constructing one succeeds, as `HfApi(token=...)` does offline; any method raises. A test that
    means to talk to a hub patches `huggingface_hub.HfApi` itself, inside the test, and that patch
    sits on top of this one."""

    def __init__(self, *args: Any, token: str | None = None, **kwargs: Any) -> None:
        self.token = token

    def __getattr__(self, name: str) -> Any:
        def unreachable(*args: Any, **kwargs: Any) -> Any:
            raise ConnectionError(f"network blocked in tests: HfApi.{name}")

        return unreachable


def _unreachable_download(*args: Any, **kwargs: Any) -> Any:
    raise ConnectionError("network blocked in tests: hf_hub_download")


@pytest.fixture(autouse=True)
def _no_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test in this file reaches HuggingFace (RM368). The RM355 dry-run test ran a real `upload`
    and was offline only because the plan happened to refuse first; with the hub blocked here, a
    publish that gets further than its refusal fails loudly rather than reaching the network."""
    monkeypatch.setattr(huggingface_hub, "HfApi", _UnreachableHub)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", _unreachable_download)


def _manifest(name: str, version: str | None) -> ModuleManifest:
    """The smallest manifest that validates — identity, display, artifact."""
    return ModuleManifest(
        identity=Identity(name=name, version=version),
        display=Display(title=name, description=name, report_title=name),
        artifact=Artifact(digest="sha256:" + "0" * 64),
    )


def _compiled_module(
    d: Path,
    *,
    logo: str | None = None,
    readme: str | None = None,
    version: str | None = "1.2.3",
    manifest_bytes: str | None = None,
) -> Path:
    """A module directory whose manifest declares what it holds, as a compiled one does (RM353): the
    publisher sends what the manifest declares, so a fixture that wrote files its manifest does not
    name would be testing a directory no compiler produces."""
    d.mkdir(parents=True, exist_ok=True)
    for name in _SNP_CORE:
        (d / name).write_bytes(b"parquet-placeholder")
    if logo is not None:
        (d / logo).write_bytes(b"image-bytes")
    if readme is not None:
        (d / readme).write_text("prose\n", encoding="utf-8")
    if manifest_bytes is None:
        manifest = _manifest("test_module", version).model_copy(
            update={
                "artifact": build_artifact(d, list(_SNP_CORE)),
                "logo": file_entry(d, logo) if logo is not None else None,
                "readme": file_entry(d, readme) if readme is not None else None,
            }
        )
        write_manifest(manifest, d / "manifest.json")
    else:
        (d / "manifest.json").write_text(manifest_bytes, encoding="utf-8")
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
    module_dir = _compiled_module(tmp_path / "coronary", logo="logo.png", version="2.0.1")
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
        sha256={name: sha256_file(module_dir / name) for name in plan.files},
    )


def test_plan_upload_carries_the_readme_the_compiler_attests(tmp_path: Path) -> None:
    """A manifest field whose bytes nobody uploads is a field that does not travel (S25).

    `manifest.readme` would otherwise attest a file this publisher leaves behind — the same silent gap
    as ClinVar's unpublished `citations/` and ClinPGx's dropped `LICENSE.txt`. The allowlist is checked
    against the compiler's own discovery set rather than a copy of it, so a stem or extension the
    compiler can produce cannot fall out of what the publisher sends."""
    module_dir = _compiled_module(tmp_path / "candidates", readme="README.md")
    assert "README.md" in plan_upload(module_dir, "candidates").files

    # Every spelling the compiler will discover is a spelling the publisher accepts — declared, it is
    # sent (RM353), and with no readable manifest the fallback allowlist still covers it.
    for name in README_CANDIDATES:
        alt = _compiled_module(tmp_path / f"m-{name}", readme=name)
        assert name in plan_upload(alt, "m").files, name
        unknown = _compiled_module(tmp_path / f"u-{name}", readme=name, manifest_bytes="{")
        assert name in plan_upload(unknown, "m").files, name


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
    assert {p for p in _ALLOW_PATTERNS if p.startswith("logo.")} == {f"logo.{ext}" for ext in LOGO_EXTENSIONS}

    for ext in sorted(LOGO_EXTENSIONS):
        module_dir = _compiled_module(tmp_path / f"logo-{ext}", logo=f"logo.{ext}")
        assert f"logo.{ext}" in plan_upload(module_dir, "m").files, ext
        unknown = _compiled_module(tmp_path / f"u-logo-{ext}", logo=f"logo.{ext}", manifest_bytes="{")
        assert f"logo.{ext}" in plan_upload(unknown, "m").files, ext

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
    # Nothing is published at the versioned path. A bare MagicMock answers `file_exists` truthily, and
    # the collision check then called the real `hf_hub_download` with this fake token (RM372's fence).
    mock_api.file_exists.return_value = False
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
    mock_api.create_repo.assert_called_once_with(repo_id=DEFAULT_REPO_ID, repo_type="dataset", exist_ok=True)
    # Two commits, flat first: deliberately two, and the path everything reads today is the one
    # refreshed first.
    assert _destinations(mock_api) == ["data/lipidmetabolism", "data/lipidmetabolism/v0.4.0"]
    for call in mock_api.create_commit.call_args_list:
        kwargs: dict[str, Any] = call.kwargs
        assert kwargs["repo_id"] == DEFAULT_REPO_ID
        assert kwargs["repo_type"] == "dataset"
        # An explicit message is the caller's and is used verbatim for both commits.
        assert kwargs["commit_message"] == "Port lipidmetabolism"
    # The same files both times — a versioned copy carrying a different file set would not be a copy
    # of the thing at the flat path.
    contents = [
        {path.split("/", 2)[-1].removeprefix("v0.4.0/"): data for path, data in sent.items()}
        for _, sent in _commits(mock_api)
    ]
    assert contents[0] == contents[1]
    assert set(_SNP_CORE) <= set(contents[0])
    mock_api.upload_folder.assert_not_called()
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
    assert _destinations(mock_api) == ["data/superhuman"]
    assert plan.versioned_path_in_repo is None


def test_the_default_commit_messages_name_which_copy_they_are(tmp_path: Path) -> None:
    """Two commits land in one repo history; identical default messages would make the versioned copy
    unreadable as a separate act."""
    module_dir = _compiled_module(tmp_path / "coronary", version="1.0.0")
    mock_api = MagicMock()
    mock_api.file_exists.return_value = False  # see `test_upload_module_calls_hf_api`
    with (
        patch("huggingface_hub.HfApi", return_value=mock_api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        upload_module(module_dir, "coronary")
    assert [message for message, _ in _commits(mock_api)] == [
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
        "data/clinvar-chr1.parquet",
        "citations/citations.parquet",
        "release.json",
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


def _sent(hub) -> list[tuple[str, list[str]]]:
    """Each write a publish made, as `(method, the repo paths it sends in order)`: an `upload_folder`'s
    allowlist, a `create_commit`'s added paths."""
    sent = []
    for method, kwargs in hub.calls:
        if method == "upload_folder":
            sent.append((method, list(kwargs["allow_patterns"])))
        elif method == "create_commit":
            sent.append((method, [op.path_in_repo for op in kwargs["operations"]]))
    return sent


def test_publish_reference_snapshot_creates_repo_then_uploads(tmp_path: Path, fake_hub) -> None:
    snap = _snapshot(tmp_path / "snap")
    hub = fake_hub("just-dna-seq/clinvar")
    plan = publish_reference_snapshot(snap, "just-dna-seq/clinvar")
    # **Two commits, payload then description** (RM199). `release.json` is what a puller reads to
    # learn which release it holds, so it must not arrive before the bytes it describes. The payload
    # goes up through the hub's own uploader from the directory; the description is sent as the bytes
    # the publish read (RM386).
    (payload_call, payload), (description_call, description) = _sent(hub)
    assert (payload_call, description_call) == ("upload_folder", "create_commit")
    assert hub.calls[0][1]["folder_path"] == str(snap)
    assert hub.calls[0][1]["path_in_repo"] == ""
    assert RELEASE_FILENAME not in payload, "the description went out too early"
    assert description == [RELEASE_FILENAME]
    # The allowlist IS the plan's file list, not a parallel pattern list that has to agree with it
    # (`@publisher-allowlist-derived`). The two were separate statements of one thing, so a dry run
    # could print a file the upload then dropped — which is how `citations/` and `LICENSE.txt` each
    # went a release unpublished. Splitting the upload does not get to weaken that: the two calls
    # together must still send exactly what the plan promised, which is why this is a union rather
    # than a check on one call.
    assert payload + description == plan.files
    assert plan.repo_id == "just-dna-seq/clinvar"
    assert {name: hub.tree()[name] for name in plan.files} == {
        name: (snap / name).read_bytes() for name in plan.files
    }


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
    # `release.json` last: the plan's order IS the publish order since RM199, so the description
    # cannot be sent before the bytes it describes.
    assert plan.files == ["data/clinvar-chr1.parquet", "LICENSE.txt", "release.json"]


def test_publish_reference_snapshot_requires_token(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path / "snap")
    with (
        patch("huggingface_hub.get_token", return_value=None),
        pytest.raises(PermissionError, match="No HuggingFace token"),
    ):
        publish_reference_snapshot(snap)


# ── RM88: the versioned path refuses to become a different release ────────────────────────────────

_OTHER_DIGEST = "sha256:" + "1" * 64


def _published_as(module_dir: Path, *, digest: str | None = None) -> dict:
    """The module's own manifest as the versioned path would hold it, with `artifact.digest` replaced
    when `digest` is given — so "the same release" is the same document, declared files included."""
    document = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))
    if digest is not None:
        document["artifact"]["digest"] = digest
    return document


def _remote(tmp_path: Path, document: dict | None) -> tuple[MagicMock, Path | None]:
    """A mock api whose versioned path holds `document` as its manifest, or nothing when it is None.
    Returns the api and the file `hf_hub_download` should hand back."""
    api = MagicMock()
    api.token = "hf_test_token"
    if document is None:
        api.file_exists.return_value = False
        return api, None
    api.file_exists.return_value = True
    published = tmp_path / "published_manifest.json"
    published.write_text(json.dumps(document), encoding="utf-8")
    return api, published


def _upload(module_dir: Path, api: MagicMock, published: Path | None, **kwargs):
    download = MagicMock(return_value=str(published) if published else "")
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
        patch("huggingface_hub.hf_hub_download", download),
    ):
        return upload_module(module_dir, "test_module", **kwargs)


def _commits(api: MagicMock) -> list[tuple[str, dict[str, bytes]]]:
    """Each `create_commit` the module publish made, as `(commit message, {path in repo: bytes})`."""
    return [
        (
            call.kwargs["commit_message"],
            {op.path_in_repo: op.path_or_fileobj for op in call.kwargs["operations"]},
        )
        for call in api.create_commit.call_args_list
    ]


def _destinations(api: MagicMock) -> list[str]:
    """The directory each module commit wrote to, in commit order, read off where `manifest.json` went."""
    return [
        next(path for path in sent if path.endswith("/manifest.json")).removesuffix("/manifest.json")
        for _, sent in _commits(api)
    ]


def test_a_versioned_path_holding_a_different_artifact_refuses(tmp_path: Path) -> None:
    """RM88: republishing without bumping `version:` used to overwrite the versioned copy silently.

    The comparator is `artifact.digest` — a Merkle root over exactly the attested files — read off
    the published manifest, so the question asked is *are these the bytes that version names* rather
    than *is something there*.
    """
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _published_as(module_dir, digest=_OTHER_DIGEST))

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    message = str(caught.value)
    assert "data/test_module/v1.2.3" in message
    assert "--force" in message
    assert "version:" in message  # names the fix, not just the fault
    assert "newer compiler" in message  # pre-answers "but I changed nothing"
    api.create_commit.assert_not_called()  # refused BEFORE either write


def test_the_same_artifact_republished_is_not_a_collision(tmp_path: Path) -> None:
    """The case a naive existence check would break, and it is load-bearing rather than tidy.

    `upload_module` writes two commits and documents a re-run as the recovery when the second fails,
    so a gate keying on *presence* would refuse exactly the retry the design depends on. It compares
    digests instead, and identical bytes are not a collision.
    """
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _published_as(module_dir))

    plan = _upload(module_dir, api, published)

    assert _destinations(api) == [
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
    assert len(api.create_commit.call_args_list) == 2


def test_force_overwrites_and_does_not_even_ask(tmp_path: Path) -> None:
    """`--force` is the decision that overwriting is sometimes right, so it skips the read entirely —
    a curator re-cutting a draft release should not pay a round trip to be told what they already
    decided."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _published_as(module_dir, digest=_OTHER_DIGEST))

    _upload(module_dir, api, published, force=True)

    api.file_exists.assert_not_called()
    assert len(api.create_commit.call_args_list) == 2


def test_a_module_with_no_version_is_not_gated_at_all(tmp_path: Path) -> None:
    """There is no versioned path to collide with, so there is nothing to ask and nobody to ask."""
    module_dir = _compiled_module(tmp_path / "m", version=None)
    api, published = _remote(tmp_path, _published_as(module_dir, digest=_OTHER_DIGEST))

    plan = _upload(module_dir, api, published)

    api.file_exists.assert_not_called()
    assert plan.versioned_path_in_repo is None
    api.create_commit.assert_called_once()


def test_the_flat_path_is_deliberately_not_guarded(tmp_path: Path) -> None:
    """`data/<name>/` means *latest*, so overwriting it is what it is for — and the whole point of
    the versioned copy is that it is the one that does not move. A gate on both would make every
    republish need `--force`."""
    module_dir = _compiled_module(tmp_path / "m", version=None)
    api, published = _remote(tmp_path, None)

    _upload(module_dir, api, published)

    assert _destinations(api) == ["data/test_module"]


def test_an_unreadable_published_manifest_proceeds_with_a_warning(tmp_path: Path, caplog) -> None:
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

    assert len(api.create_commit.call_args_list) == 2
    assert plan.versioned_path_in_repo == "data/test_module/v1.2.3"
    assert any("Nothing established a collision" in r.message for r in caplog.records)


def test_a_local_module_with_no_readable_digest_is_not_gated(tmp_path: Path) -> None:
    """Tri-state on this side too: an unreadable local manifest is an unknown digest, and an unknown
    cannot disagree with anything. It also cannot have produced a versioned path, which is why this
    is a belt-and-braces case rather than a reachable one."""
    module_dir = _compiled_module(tmp_path / "m", manifest_bytes="{ not json")
    api, published = _remote(tmp_path, {"artifact": {"digest": _OTHER_DIGEST}})

    _upload(module_dir, api, published)

    api.file_exists.assert_not_called()


# ── RM342: a collision the two recorded toolchains explain names that reason ─────────────────────


def _published_like(
    module_dir: Path, tmp_path: Path, *, toolchain: dict[str, str] | None
) -> tuple[MagicMock, Path]:
    """A remote holding this module's own manifest with a different digest and the given toolchain.

    Built from the local manifest rather than typed, so the only things that differ between the two
    sides are the ones each test sets; `toolchain=None` removes the block, as a manifest compiled
    before 0.8 has none.
    """
    document = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))
    document["artifact"]["digest"] = _OTHER_DIGEST
    if toolchain is None:
        document["compilation"].pop("toolchain", None)
    else:
        document["compilation"]["toolchain"] = toolchain
    published = tmp_path / "published_manifest.json"
    published.write_text(json.dumps(document), encoding="utf-8")
    api = MagicMock()
    api.token = "hf_test_token"
    api.file_exists.return_value = True
    return api, published


def _local_toolchain(module_dir: Path) -> dict[str, str]:
    toolchain = read_manifest(module_dir / "manifest.json").compilation.toolchain
    assert toolchain, "the compile did not record a toolchain"
    return toolchain


def test_a_collision_under_a_different_polars_is_reported_as_toolchain_differs(tmp_path: Path) -> None:
    """The PT2 A1 test: different digests and different recorded polars are `toolchain_differs`,
    never the plain collision. The publish still refuses — the versioned path's bytes stay what they
    were cut as — but it says why the bytes moved, by type."""
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    local = _local_toolchain(module_dir)
    remote = {**local, "polars": "1.39.0"}
    api, published = _published_like(module_dir, tmp_path, toolchain=remote)

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    assert type(caught.value) is ToolchainDiffersError
    assert caught.value.reason == TOOLCHAIN_DIFFERS
    assert caught.value.published_toolchain == remote
    assert caught.value.local_toolchain == local
    assert caught.value.content_unchanged is True
    assert "1.39.0" in str(caught.value)
    api.create_commit.assert_not_called()


def test_a_content_change_under_a_different_polars_does_not_claim_the_content_is_unchanged(
    tmp_path: Path,
) -> None:
    """The reason names a co-occurring difference, never a proven cause. A content edit recompiled
    beside another polars still raises the subclass, and `content_unchanged` says the toolchain does
    not account for all of it, so nobody reads the refusal as licence to `--force` a content change."""
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    api, published = _published_like(
        module_dir, tmp_path, toolchain={**_local_toolchain(module_dir), "polars": "1.39.0"}
    )
    document = json.loads(published.read_text(encoding="utf-8"))
    document["content_signature"] = "sha256:" + "2" * 64
    published.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    assert type(caught.value) is ToolchainDiffersError
    assert caught.value.content_unchanged is False

    del document["content_signature"]
    published.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PublishCollisionError) as unknown:
        _upload(module_dir, api, published)
    assert unknown.value.content_unchanged is None


def test_a_published_manifest_with_no_toolchain_is_the_plain_collision(tmp_path: Path) -> None:
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    api, published = _published_like(module_dir, tmp_path, toolchain=None)

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    assert type(caught.value) is PublishCollisionError
    assert caught.value.reason is None


def test_a_local_manifest_with_no_toolchain_is_the_plain_collision(tmp_path: Path) -> None:
    """The other side's unknown arm: a module compiled before 0.8 records nothing to compare."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, published = _remote(tmp_path, _published_as(module_dir, digest=_OTHER_DIGEST))
    document = json.loads(published.read_text(encoding="utf-8"))
    document["compilation"] = {"toolchain": {"polars": "1.39.0", "python": "3.12.0"}}
    published.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    assert type(caught.value) is PublishCollisionError


def test_the_same_toolchain_and_a_different_digest_is_the_plain_collision(tmp_path: Path) -> None:
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    api, published = _published_like(module_dir, tmp_path, toolchain=_local_toolchain(module_dir))

    with pytest.raises(PublishCollisionError) as caught:
        _upload(module_dir, api, published)

    assert type(caught.value) is PublishCollisionError


def test_the_cli_says_toolchain_differs_rather_than_already_published(tmp_path: Path) -> None:
    """The CLI's branch for the subclass must sit before the collision's, or it never runs."""
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    remote = {**_local_toolchain(module_dir), "polars": "1.39.0"}
    api, published = _published_like(module_dir, tmp_path, toolchain=remote)
    download = MagicMock(return_value=str(published))

    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
        patch("huggingface_hub.hf_hub_download", download),
    ):
        result = CliRunner().invoke(app, ["upload", str(module_dir), "--name", "hfe"])

    assert result.exit_code == 1
    assert "TOOLCHAIN DIFFERS" in result.output
    assert "ALREADY PUBLISHED" not in result.output


def test_the_dry_run_promises_exactly_what_the_upload_sends(tmp_path: Path, fake_hub) -> None:
    """The property the derived allowlist buys, over a snapshot carrying every optional part.

    Pinned on a snapshot with a sidecar *and* a licence because that is where the two lists used to
    diverge: a pattern list covering `data/*.parquet` and `release.json` silently dropped the other
    two, and the dry run — which reads the plan — said otherwise.
    """
    snap = _snapshot(tmp_path / "everything")
    (snap / "citations").mkdir()
    (snap / "citations" / "citations.parquet").write_bytes(b"PAR1payloadPAR1")
    (snap / "LICENSE.txt").write_text("CC BY-SA 4.0", encoding="utf-8")
    promised = plan_reference_snapshot(snap, "just-dna-seq/clinpgx").files

    hub = fake_hub("just-dna-seq/clinpgx")
    publish_reference_snapshot(snap, "just-dna-seq/clinpgx")
    # Summed over both commits (RM199 split the upload), because the promise is about what *reaches*
    # the repo and not about how many commits carried it. A check on one call would have started
    # passing for the wrong reason the moment the publish was split.
    sent = [f for _, paths in _sent(hub) for f in paths]
    assert sent == promised
    assert set(promised) >= {"citations/citations.parquet", "LICENSE.txt"}
    assert sent[-1] == RELEASE_FILENAME, "the description must be the last thing sent"


# ── a snapshot whose payload is one root file (STRchive; ACMG is the shape's second member) ─────


def test_a_payload_snapshot_publishes_the_named_file_and_its_provenance(tmp_path: Path) -> None:
    """STRchive holds no parquet at all, so the publisher's `data/*.parquet` premise refused it."""
    snap = tmp_path / "strchive"
    snap.mkdir()
    (snap / "STRchive-loci.json").write_text("[]", encoding="utf-8")
    (snap / "release.json").write_text('{"dataset": "strchive_v2.26.0"}', encoding="utf-8")
    plan = plan_reference_snapshot(snap, DEFAULT_STRCHIVE_REPO_ID, payload="STRchive-loci.json")
    assert plan.repo_id == DEFAULT_STRCHIVE_REPO_ID
    assert plan.files == ["STRchive-loci.json", "release.json"]


def test_a_payload_snapshot_with_nothing_built_is_refused_like_an_empty_parquet_one(
    tmp_path: Path,
) -> None:
    """Same claim in both shapes: there is nothing built here to publish."""
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "release.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="no STRchive-loci.json"):
        plan_reference_snapshot(empty, DEFAULT_STRCHIVE_REPO_ID, payload="STRchive-loci.json")


# ── the publish path's shape (RM199) ─────────────────────────────────────────────────────────────


def test_a_publish_never_reaches_for_the_deprecated_large_uploader(tmp_path: Path, fake_hub) -> None:
    """`upload_large_folder` is deprecated in `huggingface_hub` 1.x and must not be called.

    It existed here because `upload_folder` used to be one non-resumable commit, which is the wrong
    shape for 32 GB. The Hub settled it the other way — `upload_folder` is multi-commit now — and
    said so with a `FutureWarning` in a real publish. This was asserted at 1 KiB and at a 6 GiB sparse
    snapshot, because the branch it replaced only fired above a 5 GB threshold. Since RM386 the publish
    reads every byte once to hash it, so the large arm cost two full reads of 6 GiB per run; the
    property is now asserted where it holds at every size by construction — the deprecated uploader is
    named nowhere in the package — and the payload goes up as one `upload_folder`.
    """
    named = [
        f"{path.name}:{node.lineno}"
        for path in sorted(_UPLOAD_SOURCE.parent.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Attribute) and node.attr == "upload_large_folder"
    ]
    assert named == []
    hub = fake_hub("just-dna-seq/alphagenome_avi")
    publish_reference_snapshot(_snapshot(tmp_path / "snap"), "just-dna-seq/alphagenome_avi")
    assert [method for method, _ in hub.calls] == ["upload_folder", "create_commit"], (
        "payload then description"
    )


def test_a_retirement_still_rides_the_payload_commit_at_any_size(tmp_path: Path, fake_hub) -> None:
    """RM186's guarantee survived the RM199 revision, and that is the point of recording it.

    The first cut of RM199 had to *refuse* a declared retirement above the threshold, because
    `upload_large_folder` takes no `delete_patterns`. Dropping that uploader dissolves the collision:
    the deletion rides the payload call again, at every size (there is no size branch left to take;
    see the test above for why this no longer builds a 6 GiB fixture).
    """
    hub = fake_hub("just-dna-seq/alphagenome_avi", {"data/clinvar.parquet": b"PAR1 retired PAR1"})
    with patch(
        "just_dna_enricher.upload.layout_shifts_to_apply",
        # `retires` is one name, never a glob (`LayoutShift`), and it reaches the hub as a literal.
        return_value=[SimpleNamespace(retires="data/clinvar.parquet", reason="a test")],
    ):
        publish_reference_snapshot(_snapshot(tmp_path / "snap"), "just-dna-seq/alphagenome_avi")

    (_, payload), (_, description) = hub.calls
    assert payload["delete_patterns"] == ["data/clinvar.parquet"]
    assert not any(
        isinstance(op, huggingface_hub.CommitOperationDelete) for op in description["operations"]
    ), "the description commit deletes nothing"
    assert "data/clinvar.parquet" not in hub.tree()


# ── the logs `manifest.logs` names travel with the module (RM347) ────────────────────────────────

_LOGS_EXAMPLE = "apoe_epsilon"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _compile_with_logs(tmp_path: Path) -> tuple[Path, list[str]]:
    """Compile a copy of a real example carrying a `.log`, a nested `.jsonl` and a `.png` under
    `logs/`, and return the artifact directory with the log names its manifest states.

    Real compile, so `manifest.logs` is what the compiler's own discovery wrote (RM338) rather than a
    list this test spelled."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / _LOGS_EXAMPLE, spec)
    (spec / "logs" / "trace").mkdir(parents=True)
    (spec / "logs" / "authoring.log").write_text("drafted from CPIC\n", encoding="utf-8")
    (spec / "logs" / "trace" / "a.jsonl").write_text('{"step": 1}\n{"step": 2}\n', encoding="utf-8")
    (spec / "logs" / "fig.png").write_bytes(_PNG_BYTES)
    # A glob metacharacter in a name the compiler ships: `upload_folder` matches with fnmatch.
    (spec / "logs" / "fig[1].png").write_bytes(_PNG_BYTES)
    # A hidden `*.log` ships from discovery as it always has (RM338 left it alone), so the publisher's
    # hidden-path refusal must not reach it.
    (spec / "logs" / ".session.log").write_text("hidden but a log\n", encoding="utf-8")
    out = tmp_path / "out"
    compile_module(spec, out)
    document = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    named = [entry["name"] for entry in document["logs"]]
    expected = {
        "logs/authoring.log",
        "logs/trace/a.jsonl",
        "logs/fig.png",
        "logs/fig[1].png",
        "logs/.session.log",
    }
    assert expected <= set(named), "the fixture must compile to a manifest naming every log it wrote"
    return out, named


def _files_under(module_dir: Path) -> list[str]:
    return sorted(p.relative_to(module_dir).as_posix() for p in module_dir.rglob("*") if p.is_file())


def test_every_log_the_manifest_names_is_planned(tmp_path: Path) -> None:
    """A manifest naming a log the published repo lacks is a field that does not travel — the gap
    `@publisher-allowlist-derived` closed for the parquets, the logo and the readme, left open here."""
    out, named = _compile_with_logs(tmp_path)
    files = plan_upload(out, _LOGS_EXAMPLE).files
    assert set(named) <= set(files)


def test_a_log_on_disk_the_manifest_does_not_name_stays_behind(tmp_path: Path) -> None:
    """The default RM347 left open: an unnamed file under `logs/` is not uploaded, because nothing the
    published manifest says covers it — and a published file is permanent."""
    out, named = _compile_with_logs(tmp_path)
    (out / "logs" / "scratch.log").write_text("not attested\n", encoding="utf-8")
    assert "logs/scratch.log" not in named
    assert "logs/scratch.log" not in plan_upload(out, _LOGS_EXAMPLE).files


def test_the_module_upload_sends_exactly_what_the_plan_promises(tmp_path: Path) -> None:
    """The dry run is a promise: what each commit carries is the plan, nothing more — so the unnamed
    log is not sent and every named one is. `logs/fig1.png` is the decoy an unescaped `logs/fig[1].png`
    pattern selected in its place while the send was an allowlist (RM347); since RM368 the commit
    carries the planned files themselves, and the decoy stays a decoy."""
    out, named = _compile_with_logs(tmp_path)
    (out / "logs" / "scratch.log").write_text("not attested\n", encoding="utf-8")
    (out / "logs" / "fig1.png").write_bytes(_PNG_BYTES)
    promised = plan_upload(out, _LOGS_EXAMPLE).files
    api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        upload_module(out, _LOGS_EXAMPLE, force=True)
    commits = _commits(api)
    assert commits, "the upload must have been attempted"
    for prefix, (_, sent) in zip(_destinations(api), commits, strict=True):
        names = {path.removeprefix(f"{prefix}/") for path in sent}
        assert names == set(promised)
        assert set(named) <= names
        assert "logs/fig1.png" not in names


def test_a_log_path_that_leaves_the_module_directory_is_never_planned(tmp_path: Path, caplog) -> None:
    """`manifest.logs` names paths relative to the module, and a hand-edited manifest can name one that
    is not: `..`, an absolute path, a symlink whose target is outside, or a hidden path inside it. None
    is uploaded, and the
    publish still goes ahead — a refused log is a logged reason, never a failed plan."""
    out, named = _compile_with_logs(tmp_path)
    outside = tmp_path / "outside.log"
    outside.write_text("secret\n", encoding="utf-8")
    (out / "logs" / "link.log").symlink_to(outside)
    # Inside the directory and on disk, but tool state: `.env`, and a `.git` path the hub's own
    # default ignore list would drop, so planning it would be a promise the upload breaks.
    (out / ".env").write_text("HF_TOKEN=hf_secret\n", encoding="utf-8")
    (out / "logs" / ".git").mkdir()
    (out / "logs" / ".git" / "run.log").write_text("tool state\n", encoding="utf-8")
    escaping = [
        "../outside.log",
        "logs/../../outside.log",
        str(outside),
        "logs/link.log",
        ".env",
        "logs/.git/run.log",
    ]
    # Not an escape but unresolvable: `Path.resolve` raises on a NUL, and the plan must not.
    unresolvable = "logs/nul\x00.log"
    manifest_path = out / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["logs"] += [
        {"name": name, "sha256": "sha256:" + "0" * 64, "size": 7} for name in [*escaping, unresolvable]
    ]
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    with caplog.at_level("WARNING", logger="just_dna_enricher.upload"):
        files = plan_upload(out, _LOGS_EXAMPLE).files
    assert not {*escaping, unresolvable} & set(files)
    assert set(named) <= set(files), "a refused log must not take the legitimate ones with it"
    for name in escaping:
        assert any(name in record.getMessage() for record in caplog.records), name
    assert any("cannot be resolved" in record.getMessage() for record in caplog.records)


# ── the publisher sends what the manifest declares, and guards it (RM353) ───────────────────────


def _declared(document: dict) -> dict[str, str]:
    """Every file the manifest declares, by name, with its sha256 — computed from the document the
    compiler wrote, the five kinds that sit in the module directory."""
    entries = [*document["artifact"]["files"], *document.get("logs", [])]
    entries += [document[key] for key in ("logo", "readme") if document.get(key)]
    declared = {entry["name"]: entry["sha256"] for entry in entries}
    if document.get("provenance"):
        declared[document["provenance"]["file"]] = document["provenance"]["sha256"]
    return declared


def _compile_with_everything(tmp_path: Path, *, version: str | None = None) -> Path:
    """A real compile of a copy of `apoe_epsilon` carrying every optional kind a manifest declares: a
    `provenance.json`, a logo, its README and a log."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / _LOGS_EXAMPLE, spec)
    (spec / "provenance.json").write_text(
        json.dumps({"generator": "a test", "items": [{"variant_key": "rs429358", "rationale": "why"}]}),
        encoding="utf-8",
    )
    (spec / "logo.png").write_bytes(_PNG_BYTES)
    (spec / "logs").mkdir()
    (spec / "logs" / "authoring.log").write_text("drafted\n", encoding="utf-8")
    if version is not None:
        spec_file = spec / "module_spec.yaml"
        document = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        document["module"]["version"] = version
        spec_file.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        (spec / VERIFICATION_JSON).unlink(missing_ok=True)
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success, result.errors
    return out


def test_every_file_the_manifest_declares_is_planned(tmp_path: Path) -> None:
    """`provenance.json` is named, with a sha256, in `manifest.provenance.file`, and no allowlist held
    it, so a published manifest pointed at a document the repository lacked. The plan is derived from
    every file entry the manifest declares — artifact files, logs, provenance, logo, readme — so a kind
    the compiler ships is a kind the publisher sends without a list to update."""
    out = _compile_with_everything(tmp_path)
    document = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    declared = _declared(document)
    assert "provenance.json" in declared, "the fixture must compile to a manifest naming its provenance"
    assert {"logo.png", "README.md", "logs/authoring.log"} <= set(declared)

    plan = plan_upload(out, _LOGS_EXAMPLE)
    assert set(plan.files) == {*declared, "manifest.json"}

    # What the commit carries is the plan, provenance included.
    api = MagicMock()
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        upload_module(out, _LOGS_EXAMPLE, force=True)
    (prefix,) = _destinations(api)
    sent = {path.removeprefix(f"{prefix}/") for path in _commits(api)[0][1]}
    assert sent == set(plan.files)


def test_a_file_on_disk_the_manifest_does_not_declare_stays_behind(tmp_path: Path) -> None:
    """The plan is the manifest's declarations, not whatever the allowlist finds on disk: a parquet a
    previous compile left in the directory, or a logo the current manifest does not name, would arrive
    unattested — and a stale parquet on the flat path reads to discovery as part of the module."""
    out = _compile_with_everything(tmp_path)
    assert not (out / "weights.parquet").exists(), "the fixture must be a table-only module"
    for stale in ("weights.parquet", "annotations.parquet", "studies.parquet"):
        (out / stale).write_bytes(b"left by an earlier compile")
    (out / "logo.jpeg").write_bytes(_PNG_BYTES)
    files = plan_upload(out, _LOGS_EXAMPLE).files
    assert not {"weights.parquet", "annotations.parquet", "studies.parquet", "logo.jpeg"} & set(files)


def test_a_declared_optional_file_that_leaves_the_module_is_never_planned(tmp_path: Path, caplog) -> None:
    """The path guard RM347 wrote for logs reads every declared name now, so a hand-edited
    `provenance.file` naming `../x` is skipped with a reason, like a log would be."""
    out = _compile_with_everything(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    manifest_path = out / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["provenance"]["file"] = "../outside.json"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with caplog.at_level("WARNING", logger="just_dna_enricher.upload"):
        files = plan_upload(out, _LOGS_EXAMPLE).files
    assert "../outside.json" not in files
    assert any("../outside.json" in record.getMessage() for record in caplog.records)


def test_a_snapshot_file_with_a_glob_metacharacter_selects_only_itself(tmp_path: Path, fake_hub) -> None:
    """`upload_folder` matches its allowlist with `fnmatch`, so an unescaped `data/chr[1].parquet` is a
    character class: it selects `data/chr1.parquet` and never itself. RM347 escaped the module
    publisher's patterns; the snapshot publisher's went through unescaped."""
    snap = _snapshot(tmp_path / "snap")
    (snap / "data" / "chr[1].parquet").write_bytes(b"PAR1payloadPAR1")
    (snap / "data" / "chr1.parquet").write_bytes(b"PAR1decoyPAR1")
    plan = plan_reference_snapshot(snap, "just-dna-seq/clinvar")
    assert "data/chr[1].parquet" in plan.files

    hub = fake_hub("just-dna-seq/clinvar")
    publish_reference_snapshot(snap, "just-dna-seq/clinvar")
    on_disk = _files_under(snap)
    (_, payload), _ = hub.calls
    patterns = payload["allow_patterns"]
    # One pattern per payload file, each selecting exactly that file and nothing else; the description
    # is a `create_commit` of its bytes since RM386, which no pattern reaches.
    assert len(patterns) == len(plan.files) - 1
    for name, pattern in zip(plan.files, patterns, strict=False):
        assert set(filter_repo_objects(on_disk, allow_patterns=[pattern])) == {name}, pattern
    assert hub.tree()["data/chr[1].parquet"] == b"PAR1payloadPAR1"


def test_a_declared_retirement_deletes_only_the_file_it_names(tmp_path: Path, fake_hub) -> None:
    """`LayoutShift.retires` is one name, never a glob, and `delete_patterns` is matched with
    `fnmatch` too — so a retired name carrying `[` would delete a different file, unescaped."""
    shift = LayoutShift(
        repo_id="just-dna-seq/clinvar",
        retires="data/old[1].parquet",
        introduces="data/clinvar-chr*.parquet",
        reason="a test",
    )
    remote = ["data/old[1].parquet", "data/old1.parquet"]
    hub = fake_hub("just-dna-seq/clinvar", dict.fromkeys(remote, b"PAR1 old PAR1"))
    with patch("just_dna_enricher.upload.layout_shifts_to_apply", return_value=[shift]):
        publish_reference_snapshot(_snapshot(tmp_path / "snap"), "just-dna-seq/clinvar")
    delete = hub.calls[0][1]["delete_patterns"]
    assert set(filter_repo_objects(remote, allow_patterns=delete)) == {"data/old[1].parquet"}
    assert "data/old1.parquet" in hub.tree() and "data/old[1].parquet" not in hub.tree()


def test_a_prune_deletes_only_the_files_its_plan_names(tmp_path: Path, fake_hub) -> None:
    """The prune plan lists remote paths and `delete_files` matched them with `fnmatch`: a candidate
    `data/x[1].parquet` unescaped would delete `data/x1.parquet`, a file nobody was shown. Since RM386
    the deletion is one delete operation per listed path, so no pattern exists to be misread."""
    hub = fake_hub("just-dna-seq/clinvar", {"data/x[1].parquet": b"PAR1", "data/x1.parquet": b"PAR1"})
    plan = PrunePlan(
        repo_id="just-dna-seq/clinvar",
        candidates=[PruneCandidate(path="data/x[1].parquet", reason="t")],
        revision=hub.head,
    )
    prune_repo(plan)
    assert set(hub.tree()) == {".gitattributes", "data/x1.parquet"}


def test_a_logs_only_change_at_the_versioned_path_refuses_without_force(tmp_path: Path) -> None:
    """`artifact.digest` excludes logs by design, so a guard comparing only the digest let a second
    publish of the same version replace its logs. The guard compares every declared file's hash: the
    compiled data is identical, a declared log is not, and the refusal says which."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(out)

    # The same release arriving twice is not a collision, declared files included.
    api, remote = _remote(tmp_path, published)
    _upload(out, api, remote)
    assert len(api.create_commit.call_args_list) == 2

    # Recompile with one log changed: same data, same digest (P7), a different declared log.
    (tmp_path / "spec" / "logs" / "authoring.log").write_text("drafted, then reviewed\n", encoding="utf-8")
    shutil.rmtree(out)
    assert compile_module(tmp_path / "spec", out).success
    local = _published_as(out)
    assert local["artifact"]["digest"] == published["artifact"]["digest"], "the data must not have moved"
    assert _declared(local)["logs/authoring.log"] != _declared(published)["logs/authoring.log"]

    api, remote = _remote(tmp_path, published)
    with pytest.raises(PublishCollisionError) as caught:
        _upload(out, api, remote)
    message = str(caught.value)
    assert f"data/test_module/v{_AUTHORED_VERSION}" in message
    assert "logs/authoring.log" in message
    assert "--force" in message
    api.create_commit.assert_not_called()

    api, remote = _remote(tmp_path, published)
    _upload(out, api, remote, force=True)
    assert len(api.create_commit.call_args_list) == 2


def test_a_declared_file_on_one_side_only_is_a_collision(tmp_path: Path) -> None:
    """A log the published version does not declare, added under the same version, changes what that
    version says it holds — the declared sets are compared, not only the hashes they share."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    published = _published_as(module_dir)
    published["logs"] = [{"name": "logs/run.log", "sha256": "sha256:" + "2" * 64, "size": 3}]
    api, remote = _remote(tmp_path, published)
    with pytest.raises(PublishCollisionError, match="logs/run.log"):
        _upload(module_dir, api, remote)
    api.create_commit.assert_not_called()


def test_a_declared_file_difference_under_another_toolchain_is_the_plain_collision(tmp_path: Path) -> None:
    """RM342 meets RM353: the recorded toolchain explains a moved `artifact.digest`, never a declared
    file. With the data identical and only a log differing, a different polars on the published side
    says nothing about why, so the refusal is the plain collision naming the log, not the subclass."""
    module_dir = _compile_example(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(module_dir)
    published["compilation"]["toolchain"] = {**_local_toolchain(module_dir), "polars": "1.39.0"}
    published["logs"] = [{"name": "logs/run.log", "sha256": "sha256:" + "2" * 64, "size": 3}]
    api, remote = _remote(tmp_path, published)

    with pytest.raises(PublishCollisionError, match="logs/run.log") as caught:
        _upload(module_dir, api, remote)

    assert type(caught.value) is PublishCollisionError
    assert caught.value.reason is None
    api.create_commit.assert_not_called()


def test_a_declaration_with_no_legible_hash_is_not_compared(tmp_path: Path) -> None:
    """An unknown cannot disagree: a published manifest whose `provenance` names the file but states
    no sha256 says nothing about its bytes, so it is no collision with a local one that does."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(out)
    published["provenance"]["sha256"] = None
    api, remote = _remote(tmp_path, published)
    _upload(out, api, remote)
    assert len(api.create_commit.call_args_list) == 2


def test_a_declared_file_edited_after_the_compile_refuses(tmp_path: Path) -> None:
    """The guard compares manifests, so the manifest has to be true of the bytes sent: a log appended
    to after the compile (a hand edit, an override recorded into the artifact directory) would arrive
    under a manifest stating its old sha256, and a republish of the same version would replace the
    published log with the guard comparing two identical manifests."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(out)
    with (out / "logs" / "authoring.log").open("a", encoding="utf-8") as handle:
        handle.write("an override, after the compile\n")
    with pytest.raises(FileNotFoundError, match="logs/authoring.log"):
        plan_upload(out, _LOGS_EXAMPLE)
    api, remote = _remote(tmp_path, published)
    with pytest.raises(FileNotFoundError, match="Re-compile"):
        _upload(out, api, remote)
    api.create_commit.assert_not_called()


# ── one manifest, one reader, one filter (RM355) ─────────────────────────────────────────────────


def test_a_dry_run_reports_a_refusal_exactly_as_the_real_run_does(tmp_path: Path) -> None:
    """`--dry-run` called `plan_upload` outside the `try` the real run sits in, so a refusal the real
    run prints as one line came out of the dry run as a traceback. The dry run is what an author reads
    first, so it is where a refusal has to be legible.

    An uncaught `FileNotFoundError` also exits 1 under `CliRunner`, so the exit code alone cannot tell
    the two apart: the test compares the dry run's stderr with the real run's, and asserts the
    exception that ended the run is the CLI's own exit rather than the refusal. The real run needs no
    hub — the plan refuses before `ensure_repo` is reached."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    with (out / "logs" / "authoring.log").open("a", encoding="utf-8") as handle:
        handle.write("an override, after the compile\n")

    dry = CliRunner().invoke(app, ["upload", str(out), "--name", "apoe", "--dry-run"])
    real = CliRunner().invoke(app, ["upload", str(out), "--name", "apoe"])

    for result in (dry, real):
        assert result.exit_code == 1, result.output
        assert isinstance(result.exception, SystemExit), repr(result.exception)
        assert "UPLOAD FAILED:" in result.stderr
        assert "logs/authoring.log" in result.stderr
        assert "Would upload" not in result.output
    assert dry.stderr == real.stderr


def test_the_plan_reads_the_manifest_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_module_version` opened and parsed `manifest.json` itself, beside `_manifest_document`, so the
    version and the file list of one plan came from two reads of one file. One reader now: a plan reads
    the manifest once, and a publish's plan and guard share that one read. The send reads it once
    more (RM368), to check its bytes still hash to the plan's and to send those very bytes — so a
    publish reads it twice, and never once per commit.

    Counted at `io.open` (and the builtin, the same function under another name), which every way of
    reading a file goes through — `Path.read_text`, `read_bytes`, `Path.open`, `open()` — so a second
    read cannot pass by choosing a different spelling."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    manifest_path = out / "manifest.json"
    reads: list[object] = []
    original = io.open

    def counting_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(file, (str, Path)) and Path(file) == manifest_path:
            reads.append(file)
        return original(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr(builtins, "open", counting_open)

    plan = plan_upload(out, "apoe")
    assert plan.versioned_path_in_repo == f"data/apoe/v{_AUTHORED_VERSION}"
    assert len(reads) == 1

    reads.clear()
    api, remote = _remote(tmp_path, None)
    _upload(out, api, remote)
    assert len(api.create_commit.call_args_list) == 2
    assert len(reads) == 2


def test_an_entry_naming_no_file_is_read_one_way_and_refused(tmp_path: Path) -> None:
    """`_named_entries` kept an `artifact.files` entry whose `name` is `""`, which `_declared_files`
    dropped, so one manifest gave the attested list and the declared list two answers about the same
    entry, and the plan refused with `attests ['']` and a hint to recompile "if the file is missing".

    One filter now: neither list carries the entry. The plan still refuses, because the attested list
    is what `artifact.digest` covers and an entry naming no file is a digest no upload can satisfy;
    dropping it quietly would publish that false claim. The refusal quotes the entry, as a malformed
    input's refusal does. An optional declaration naming no file (a `logo` with an empty name) is
    outside the digest and is dropped without a refusal, as before."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    baseline = plan_upload(module_dir, "test_module").files
    original = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))

    unnamed = {"name": "", "sha256": "sha256:" + "3" * 64, "size": 1}
    document = json.loads(json.dumps(original))
    document["artifact"]["files"].append(unnamed)
    (module_dir / "manifest.json").write_text(json.dumps(document), encoding="utf-8")

    attested = _attested_parquets(document)
    declared = [name for name, _ in _declared_files(document)]
    assert attested is not None
    assert "" not in attested
    assert "" not in declared
    assert set(attested) <= set(declared)
    with pytest.raises(FileNotFoundError) as caught:
        plan_upload(module_dir, "test_module")
    assert repr(unnamed) in str(caught.value)
    assert "attests ['']" not in str(caught.value)

    document = json.loads(json.dumps(original))
    document["logo"] = {"name": "", "sha256": "sha256:" + "4" * 64, "size": 1}
    (module_dir / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
    assert "" not in [name for name, _ in _declared_files(document)]
    assert plan_upload(module_dir, "test_module").files == baseline


# ── what the publisher plans, checks and sends is one reading of the disk (RM368) ───────────────


def test_the_plan_states_the_hash_of_every_file_it_sends(tmp_path: Path) -> None:
    """The plan is paths and the sha256 each one had when it was read, `manifest.json` among them, and
    each commit carries exactly those bytes under both paths."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    plan = plan_upload(out, "apoe")
    assert set(plan.sha256) == set(plan.files)
    assert "manifest.json" in plan.sha256
    assert plan.sha256 == {name: sha256_file(out / name) for name in plan.files}

    api, remote = _remote(tmp_path, None)
    _upload(out, api, remote)
    commits = _commits(api)
    prefixes = ["data/test_module", f"data/test_module/v{_AUTHORED_VERSION}"]
    assert len(commits) == len(prefixes)
    for prefix, (_, sent) in zip(prefixes, commits, strict=True):
        assert set(sent) == {f"{prefix}/{name}" for name in plan.files}
        assert {path.removeprefix(f"{prefix}/"): sha256_bytes(data) for path, data in sent.items()} == (
            plan.sha256
        )
    api.upload_folder.assert_not_called()


def test_a_file_that_changes_after_the_check_is_never_sent(tmp_path: Path) -> None:
    """The guard compared the in-memory manifest, and `upload_folder` then read the directory again,
    so a recompile landing between the two shipped bytes nothing had checked. The send now reads each
    planned file once more, refuses when its hash is not the plan's, and sends the bytes it hashed."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    api, remote = _remote(tmp_path, None)
    log = out / "logs" / "authoring.log"

    def a_recompile_in_the_window(**kwargs: Any) -> bool:
        log.write_text("written after the plan was checked\n", encoding="utf-8")
        return False

    api.file_exists.side_effect = a_recompile_in_the_window
    with pytest.raises(upload.PlanChangedError, match="logs/authoring.log") as caught:
        _upload(out, api, remote)
    assert isinstance(caught.value, upload.PublishRefused)
    api.create_commit.assert_not_called()
    api.upload_folder.assert_not_called()


def _rewrite(module_dir: Path, edit: typing.Callable[[dict], None]) -> None:
    path = module_dir / "manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    path.write_text(json.dumps(document), encoding="utf-8")


#: Each declared field written as a shape the compiler never writes. Present and unreadable is the
#: refusal (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`): reading it as
#: absent dropped a gate — the attestation check for `artifact.files`, the hash check for a `sha256`.
_MALFORMED: dict[str, typing.Callable[[dict], None]] = {
    "artifact": lambda d: d.__setitem__("artifact", "sha256:" + "0" * 64),
    "artifact.files": lambda d: d["artifact"].__setitem__("files", {"annotations.parquet": "x"}),
    "artifact.files[0].sha256": lambda d: d["artifact"]["files"][0].__setitem__("sha256", 123),
    "logs": lambda d: d.__setitem__("logs", "logs/authoring.log"),
    "logs[0].sha256": lambda d: d["logs"][0].__setitem__("sha256", ["sha256:" + "0" * 64]),
    "logo": lambda d: d.__setitem__("logo", "logo.png"),
    "logo.name": lambda d: d["logo"].__setitem__("name", ["logo.png"]),
    "provenance.file": lambda d: d["provenance"].__setitem__("file", 7),
    "readme": lambda d: d.__setitem__("readme", ["README.md"]),
    "provenance": lambda d: d.__setitem__("provenance", "provenance.json"),
    "provenance.sha256": lambda d: d["provenance"].__setitem__("sha256", 5),
}


def test_a_file_that_goes_missing_after_the_check_is_a_refusal_not_a_traceback(tmp_path: Path) -> None:
    """A planned file deleted between the check and the send (a recompile unlinking it) is the same
    `PlanChangedError`, never a bare `FileNotFoundError` the CLI no longer catches."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    api, remote = _remote(tmp_path, None)

    def a_recompile_unlinks_it(**kwargs: Any) -> bool:
        (out / "logs" / "authoring.log").unlink()
        return False

    api.file_exists.side_effect = a_recompile_unlinks_it
    with pytest.raises(upload.PlanChangedError, match=r"logs/authoring.log \(unreadable"):
        _upload(out, api, remote)
    api.create_commit.assert_not_called()


@pytest.mark.parametrize("field", sorted(_MALFORMED))
def test_a_malformed_declaration_refuses_rather_than_dropping_its_gate(tmp_path: Path, field: str) -> None:
    out = _compile_with_everything(tmp_path)
    _rewrite(out, _MALFORMED[field])
    with pytest.raises(upload.ModuleNotPublishable) as caught:
        plan_upload(out, "apoe")
    assert field in str(caught.value)
    assert isinstance(caught.value, upload.PublishRefused)


def test_every_declared_field_has_a_malformed_case() -> None:
    """The parametrization above walks the publisher's own registry of declared fields."""
    assert {field.split(".")[0].split("[")[0] for field in _MALFORMED} == set(upload.DECLARED_FILE_FIELDS)


def test_an_absent_file_list_still_withholds(tmp_path: Path) -> None:
    """The other arm of the same rule: `artifact.files` null or missing is unknown, and the plan falls
    back to the allowlist found on disk exactly as an unreadable manifest does."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    _rewrite(module_dir, lambda d: d["artifact"].__setitem__("files", None))
    assert set(_SNP_CORE) <= set(plan_upload(module_dir, "test_module").files)
    _rewrite(module_dir, lambda d: d["artifact"].pop("files"))
    assert set(_SNP_CORE) <= set(plan_upload(module_dir, "test_module").files)


def test_a_blank_name_names_no_file(tmp_path: Path) -> None:
    """`_named_entry` took a whitespace-only `name` for a file, so the attested refusal read `attests
    ['  ']` and asked for a recompile "if the file is missing". A blank name is no name: the attested
    entry is refused quoting it, and an optional one is dropped, as an empty name is."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    baseline = plan_upload(module_dir, "test_module").files
    blank = {"name": "  ", "sha256": "sha256:" + "3" * 64, "size": 1}
    _rewrite(module_dir, lambda d: d["artifact"]["files"].append(blank))
    with pytest.raises(upload.ModuleNotPublishable) as caught:
        plan_upload(module_dir, "test_module")
    assert repr(blank) in str(caught.value)
    assert "attests" not in str(caught.value)

    _rewrite(module_dir, lambda d: d["artifact"]["files"].remove(blank))
    _rewrite(module_dir, lambda d: d.__setitem__("logo", blank))
    assert plan_upload(module_dir, "test_module").files == baseline


def test_the_manifest_itself_is_compared_at_the_versioned_path(tmp_path: Path) -> None:
    """The guard compared the digest and each declared file, never `manifest.json`: the same data under
    a new title replaced the published manifest of that version without `--force`. The manifest is
    part of what the version names, so a field that differs is a collision, named by its path."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    published = _published_as(module_dir)
    published["display"]["title"] = "the title it was published under"
    api, remote = _remote(tmp_path, published)
    with pytest.raises(PublishCollisionError, match=r"display\.title") as caught:
        _upload(module_dir, api, remote)
    assert type(caught.value) is PublishCollisionError
    api.create_commit.assert_not_called()
    api.upload_folder.assert_not_called()


def test_a_non_file_key_inside_a_declared_field_is_compared(tmp_path: Path) -> None:
    """The manifest arm skips only the keys the other two arms compare (name, hash, size, digest), so
    `provenance.generator` differing under one version is a collision named by its path."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(out)
    published["provenance"]["generator"] = "another generator"
    api, remote = _remote(tmp_path, published)
    with pytest.raises(PublishCollisionError, match=r"provenance\.generator"):
        _upload(out, api, remote)
    api.create_commit.assert_not_called()


def test_the_dry_run_runs_the_versioned_path_check_and_writes_nothing(tmp_path: Path) -> None:
    """A rehearsal that skips the check the real run refuses on is a different operation (the snapshot
    dry runs' rule). The dry run now reads the published manifest, read-only, and refuses as the real
    run does; it creates no repo and commits nothing."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    api, remote = _remote(tmp_path, _published_as(module_dir, digest=_OTHER_DIGEST))
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.hf_hub_download", MagicMock(return_value=str(remote))),
    ):
        dry = CliRunner().invoke(app, ["upload", str(module_dir), "--name", "test_module", "--dry-run"])
    assert dry.exit_code == 1, dry.output
    assert "ALREADY PUBLISHED" in dry.output
    assert "Would upload" not in dry.output
    api.create_repo.assert_not_called()
    api.create_commit.assert_not_called()
    api.upload_folder.assert_not_called()


def test_an_unreachable_hub_leaves_the_dry_run_a_plan(tmp_path: Path, caplog) -> None:
    """The dry run's read fails open as the real run's does: unreachable is unknown, never a refusal."""
    module_dir = _compiled_module(tmp_path / "m", version="1.2.3")
    with caplog.at_level("WARNING", logger="just_dna_enricher.upload"):
        plan = upload.rehearse_upload(module_dir, "test_module")
    assert plan.versioned_path_in_repo == "data/test_module/v1.2.3"
    assert any("Nothing established a collision" in r.getMessage() for r in caplog.records)


def test_a_snapshot_refusal_is_a_publish_refusal(tmp_path: Path) -> None:
    """Typed in the publisher's own family, and still a `FileNotFoundError` within 0.8 so a caller's
    existing handler keeps catching it."""
    (tmp_path / "data").mkdir()
    with pytest.raises(upload.SnapshotNotPublishable) as caught:
        plan_reference_snapshot(tmp_path)
    assert isinstance(caught.value, upload.PublishRefused)
    assert isinstance(caught.value, FileNotFoundError)
    with pytest.raises(upload.SnapshotNotPublishable):
        plan_reference_snapshot(tmp_path, payload="STRchive-loci.json")


def test_a_module_refusal_is_a_publish_refusal(tmp_path: Path) -> None:
    d = tmp_path / "m"
    d.mkdir()
    (d / "README.md").write_text("no data\n", encoding="utf-8")
    with pytest.raises(upload.ModuleNotPublishable) as caught:
        plan_upload(d, "m")
    assert isinstance(caught.value, upload.PublishRefused)
    assert isinstance(caught.value, FileNotFoundError)


_UPLOAD_SOURCE = Path(upload.__file__)
_CLI_DIR = _UPLOAD_SOURCE.parent / "cli"
#: Raised by the publisher and outside its refusal family on purpose: neither says anything about what
#: would be sent. A missing write token is a credential, a missing `huggingface_hub` a dependency.
_NOT_REFUSALS = {"PermissionError", "ImportError"}


def _raised_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            names.add(target.id if isinstance(target, ast.Name) else ast.unparse(target))
    return names


def _subclasses(cls: type) -> set[type]:
    found = set(cls.__subclasses__())
    for sub in list(found):
        found |= _subclasses(sub)
    return found


def test_every_refusal_the_publisher_raises_is_in_its_family() -> None:
    """An AST walk over `upload.py`: what it raises is its refusal family plus the two non-refusals,
    and every member of the family is raised somewhere. A `FileNotFoundError` for "this module is not
    publishable" was the wrong type: a caller could not tell it from a missing directory."""
    family = {cls.__name__ for cls in _subclasses(upload.PublishRefused)}
    raised = _raised_names(ast.parse(_UPLOAD_SOURCE.read_text(encoding="utf-8")))
    assert raised == family | _NOT_REFUSALS


#: Functions in `upload` a command reaches the publisher through.
_PUBLISH_ENTRIES = {
    "upload_module",
    "rehearse_upload",
    "plan_upload",
    "publish_reference_snapshot",
    "rehearse_reference_snapshot",
    "plan_reference_snapshot",
    "check_publish_orphans_no_sidecar",
    "prune_repo",
}
#: The one command calling a bare plan, and why that is not a dry run: `civic reproduce` asserts the
#: plan's file list offline as one of its reproduction checks, and publishes nothing.
_BARE_PLAN_CALLERS = {("civic_commands.py", "plan_reference_snapshot")}


def _calls(node: ast.AST) -> set[str]:
    return {
        n.func.id
        for n in ast.walk(node)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _PUBLISH_ENTRIES
    }


def test_every_publish_command_catches_the_refusal_family() -> None:
    """Every `try` in the CLI that calls into the publisher has a handler naming `PublishRefused`, so a
    refusal reads as one line from every command, whichever member raised it."""
    missing: list[str] = []
    for path in sorted(_CLI_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Try) or not any(_calls(stmt) for stmt in node.body):
                continue
            handled = {
                n.id
                for handler in node.handlers
                if handler.type is not None
                for n in ast.walk(handler.type)
                if isinstance(n, ast.Name)
            }
            if "PublishRefused" not in handled:
                missing.append(f"{path.name}:{node.lineno}")
    assert missing == []


def test_every_publisher_call_in_the_cli_sits_inside_a_refusal_handler() -> None:
    """The test above reads the `try` blocks that exist, so a call outside any `try` went unseen:
    `cache prune --yes` called `prune_repo` bare, and a prune refused because the repo moved after its
    plan (RM386) would have been a traceback. Every call to an entry is inside a `try` whose handlers
    name `PublishRefused`, but the allowlisted bare plan."""
    bare: list[str] = []
    for path in sorted(_CLI_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = {
            id(call)
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and "PublishRefused"
            in {
                n.id
                for h in node.handlers
                if h.type is not None
                for n in ast.walk(h.type)
                if isinstance(n, ast.Name)
            }
            for stmt in node.body
            for call in ast.walk(stmt)
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            unguarded = node.func.id in _PUBLISH_ENTRIES and id(node) not in guarded
            if unguarded and (path.name, node.func.id) not in _BARE_PLAN_CALLERS:
                bare.append(f"{path.name}:{node.lineno} {node.func.id}")
    assert bare == []


def test_every_dry_run_is_a_rehearsal() -> None:
    """A dry run calls the rehearsal, which runs every check the real publish runs; a bare plan in the
    CLI is the one allowlisted caller. Equality, so the allowlist cannot outlive its reason."""
    bare = {
        (path.name, name)
        for path in sorted(_CLI_DIR.glob("*.py"))
        for name in _calls(ast.parse(path.read_text(encoding="utf-8")))
        & {"plan_upload", "plan_reference_snapshot", "check_publish_orphans_no_sidecar"}
    }
    assert bare == _BARE_PLAN_CALLERS


def _file_models(annotation: Any) -> set[type]:
    """The pydantic models an annotation reaches, through unions, lists and nested models."""
    found: set[type] = set()
    stack = [annotation]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        stack.extend(typing.get_args(current))
        if isinstance(current, type) and hasattr(current, "model_fields"):
            found.add(current)
            stack.extend(field.annotation for field in current.model_fields.values())
    return found


def test_the_publisher_reads_every_field_that_names_a_file() -> None:
    """`ModuleManifest`'s fields that reach a `FileEntry` or a `Provenance` are exactly the publisher's
    declared fields plus the spec-side ones it states a reason for skipping — so a field the compiler
    starts writing a file into goes red here until the publisher decides whether it travels."""
    naming = {
        name
        for name, field in ModuleManifest.model_fields.items()
        if _file_models(field.annotation) & {FileEntry, Provenance}
    }
    assert naming == set(upload.DECLARED_FILE_FIELDS) | set(upload.SPEC_SIDE_FILE_FIELDS)
    assert not set(upload.DECLARED_FILE_FIELDS) & set(upload.SPEC_SIDE_FILE_FIELDS)


# ── a republish of an unchanged spec stays idempotent (RM368, lead review) ──────────────────────


def test_a_recompile_of_an_unchanged_spec_republishes_as_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Comparing every manifest field made a recompile of the same spec at the same version a
    collision only because `compiled_at` moved. The stamps of the act of compiling are not what the
    version names; the digest, the declared files and the toolchain still are."""
    out = _compile_with_everything(tmp_path, version=_AUTHORED_VERSION)
    published = _published_as(out)

    # The same spec compiled again, later, by someone else: only the act's stamps move.
    monkeypatch.setattr(compiler_manifest, "_now_iso", lambda: "2031-01-01T00:00:00Z")
    shutil.rmtree(out)
    assert compile_module(tmp_path / "spec", out, compiled_by="another-host").success
    local = _published_as(out)
    assert local["compilation"]["compiled_at"] != published["compilation"]["compiled_at"]
    assert local["artifact"]["digest"] == published["artifact"]["digest"], "the data must not have moved"

    api, remote = _remote(tmp_path, published)
    _upload(out, api, remote)
    assert len(api.create_commit.call_args_list) == 2

    # A changed log is still a different release of that version.
    (tmp_path / "spec" / "logs" / "authoring.log").write_text("drafted, then reviewed\n", encoding="utf-8")
    shutil.rmtree(out)
    assert compile_module(tmp_path / "spec", out).success
    api, remote = _remote(tmp_path, published)
    with pytest.raises(PublishCollisionError, match="logs/authoring.log"):
        _upload(out, api, remote)
    api.create_commit.assert_not_called()


def test_every_compilation_field_is_classified_for_the_versioned_path() -> None:
    """Each `Compilation` field either describes the module (compared at the versioned path) or
    stamps the act of compiling (excluded, with its reason): a new field goes red here until it is
    classified, so a new stamp cannot turn every republish into a collision, and a new fact about the
    module cannot slip out of the comparison."""
    stamps = set(upload.COMPILATION_STAMPS)
    compared = set(upload.COMPILATION_COMPARED)
    assert not stamps & compared
    assert stamps | compared == set(Compilation.model_fields)
    assert "toolchain" in compared, "RM342's toolchain-differs refusal reads it"
    assert all(reason.strip() for reason in upload.COMPILATION_STAMPS.values())

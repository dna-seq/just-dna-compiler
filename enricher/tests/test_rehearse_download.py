"""`cache rebuild --dry-run --publish --rehearse-download`: the download and the build are real, the upload is not (RM412).

RM411 made `--dry-run` take nothing, so a rehearsal of a publish that wants the source's real bytes (does
the download still work, does the build still parse it, would the upload be refused) had no command.
The flag is that rehearsal, asked for by name. It is refused without `--dry-run` (it would then upload)
and without `--publish` (there is then no upload to rehearse), before anything runs.

Every outside host is fenced (the root conftest) and the hub is faked; the one download a test lets
happen is STRchive's catalogue, monkeypatched to write the checked-in slice.
"""

import shutil
from pathlib import Path

import huggingface_hub
import pytest
import typer
from just_dna_enricher import strchive_build
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.cli import app, cache_commands
from just_dna_enricher.cli.cache_commands import REHEARSE_DOWNLOAD_REFUSAL
from just_dna_enricher.locations import STRCHIVE_CATALOGUE_FILENAME
from just_dna_enricher.upload import plan_reference_snapshot
from just_dna_format.snapshot import release_label
from typer.testing import CliRunner

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "strchive_loci_slice.json"


class _Hub:
    """`HfFileSystem.get` for the repo-root `release.json`: the repo has published nothing yet."""

    def get(self, remote: str, local: str) -> None:
        raise FileNotFoundError(remote)


class _Api:
    """`HfApi` for the orphan check (the repo holds `held`), and an upload that fails the test if reached."""

    held: list[str] = []

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def list_repo_files(self, repo_id: str, repo_type: str | None = None, revision: str | None = None):
        return list(self.held)

    def create_repo(self, *args, **kwargs):
        raise AssertionError("a rehearsal created a repo")

    def upload_folder(self, *args, **kwargs):
        raise AssertionError("a rehearsal uploaded")

    def create_commit(self, *args, **kwargs):
        raise AssertionError("a rehearsal committed")


@pytest.fixture
def fake_hub(monkeypatch: pytest.MonkeyPatch) -> type[_Api]:
    _Api.held = []
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: _Hub())
    monkeypatch.setattr(huggingface_hub, "HfApi", _Api)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    return _Api


def _strchive_from_the_slice(monkeypatch: pytest.MonkeyPatch, fetched: list[str]) -> None:
    """STRchive's download, answered with the checked-in slice: the one download these tests let happen."""

    def fake_download(dest: Path, url: str = strchive_build.DEFAULT_STRCHIVE_URL) -> tuple[Path, str]:
        fetched.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_SLICE, dest)
        return dest, ""

    monkeypatch.setattr(strchive_build, "download_catalogue", fake_download)


_REHEARSE = ["--dry-run", "--publish", "--rehearse-download"]


@pytest.mark.parametrize(
    ("flags", "missing"),
    [
        ([], "--dry-run, --publish"),
        (["--dry-run"], "--publish"),
        (["--publish"], "--dry-run"),
    ],
)
def test_the_flag_without_both_partners_is_refused_before_anything_runs(
    flags: list[str], missing: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--publish --rehearse-download` without `--dry-run` must never reach an upload, or a build."""

    def explode(*args, **kwargs):
        raise AssertionError("the refused run reached a lane")

    monkeypatch.setattr(cache_commands, "rebuild_lane", explode)
    monkeypatch.setattr(cache_commands, "_dry_run", explode)
    monkeypatch.setattr(cache_commands, "_publish_rebuilt", explode)
    out = tmp_path / "caches"

    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(out), "--only", "strchive", "--rehearse-download", *flags]
    )

    assert result.exit_code == 2, result.output
    assert REHEARSE_DOWNLOAD_REFUSAL in result.output
    assert f"Missing: {missing}." in result.output
    assert not out.exists()


def test_the_rehearsal_downloads_and_builds_for_real_and_uploads_nothing(
    fake_hub: type[_Api], no_ambient_caches: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The inverse of RM411: the adapter's own download is taken, the snapshot is built into `<out>/<lane>`."""
    fetched: list[str] = []
    _strchive_from_the_slice(monkeypatch, fetched)
    out = tmp_path / "caches"
    built = out / "strchive"
    repo = LANES_BY_NAME["strchive"].publish_repo

    result = CliRunner().invoke(
        app,
        ["cache", "rebuild", "--out", str(out), "--only", "strchive", "--pin", "strchive=v2.0.0", *_REHEARSE],
    )

    assert result.exit_code == 0, result.output
    assert fetched == [strchive_build.catalogue_url("v2.0.0")]
    assert (built / STRCHIVE_CATALOGUE_FILENAME).is_file()
    label = release_label(built)
    assert label is not None
    files = plan_reference_snapshot(built, repo, payload=STRCHIVE_CATALOGUE_FILENAME).files
    assert f"strchive      rehearsing: v2.0.0, downloading it, into {built}" in result.output
    assert "this machine: absent" in result.output
    assert f"published at {repo}: nothing published" in result.output
    assert (
        f"would upload {len(files)} file(s) from the snapshot just built at {built} ({label}) to {repo}"
        in result.output
    )
    assert "rehearsal: rebuilt 1, failed 0, not run 0 of 1 lane(s)" in result.output
    assert "nothing was uploaded" in result.output


def test_a_build_that_fails_exits_1_as_the_real_run_does_and_rehearses_no_upload(
    fake_hub: type[_Api], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def broken_download(dest: Path, url: str = strchive_build.DEFAULT_STRCHIVE_URL) -> tuple[Path, str]:
        raise OSError("connection reset")

    monkeypatch.setattr(strchive_build, "download_catalogue", broken_download)

    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(tmp_path / "c"), "--only", "strchive", *_REHEARSE]
    )

    assert result.exit_code == 1, result.output
    assert "connection reset" in result.output
    assert "would upload" not in result.output
    assert "rehearsal: rebuilt 0, failed 1, not run 0 of 1 lane(s)" in result.output


def test_an_upload_the_publisher_would_refuse_is_named_after_the_real_build(
    fake_hub: type[_Api], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A repo holding a sidecar the new snapshot does not carry: the orphan check refuses, and the rehearsal says so."""
    _strchive_from_the_slice(monkeypatch, [])
    fake_hub.held = ["STRchive-loci.json", "citations/stale.parquet", "release.json"]

    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(tmp_path / "c"), "--only", "strchive", *_REHEARSE]
    )

    # Exit 0, as the real run's refused publish leaves it: the exit code counts builds only (RM412's
    # rehearsal is the real run with the upload rehearsed, so it does not grow a second exit rule).
    assert result.exit_code == 0, result.output
    assert "strchive      built" in result.output
    assert "WOULD BE REFUSED" in result.output
    assert "would upload" not in result.output


def test_a_local_source_is_named_as_the_origin_and_read_without_a_download(
    fake_hub: type[_Api], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_download(*args, **kwargs):
        raise AssertionError("a --source build downloaded")

    monkeypatch.setattr(strchive_build, "download_catalogue", no_download)
    out = tmp_path / "caches"

    result = CliRunner().invoke(
        app,
        [
            "cache",
            "rebuild",
            "--out",
            str(out),
            "--only",
            "strchive",
            "--source",
            f"strchive={_SLICE}",
            *_REHEARSE,
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"rehearsing: the lane's own release, from {_SLICE}, into {out / 'strchive'}" in result.output
    assert "would upload 2 file(s) from the snapshot just built at" in result.output


def test_a_lane_that_cannot_run_is_reported_in_the_real_runs_words(
    fake_hub: type[_Api], no_ambient_caches: Path, tmp_path: Path
) -> None:
    """A derived lane with no parents on disk: the rehearsal says what the real run says, and builds nothing."""
    argv = ["cache", "rebuild", "--out", str(tmp_path / "c"), "--only", "mitomap_miss"]

    def lane_line(extra: list[str]) -> str:
        result = CliRunner().invoke(app, [*argv, *extra])
        return next(line for line in result.output.splitlines() if line.lstrip().startswith("mitomap_miss"))

    assert lane_line(_REHEARSE) == lane_line([])
    assert not (tmp_path / "c" / "mitomap_miss").exists()


def test_the_dry_run_alone_still_takes_nothing(
    fake_hub: type[_Api], no_ambient_caches: Path, tmp_path: Path
) -> None:
    """The flag is opt-in: without it RM411's dry run is unchanged, and the strchive download is never asked."""
    out = tmp_path / "caches"
    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(out), "--only", "strchive", "--publish", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert not out.exists()
    assert "nothing was downloaded, built or uploaded" in result.output


def test_the_flags_help_states_that_the_prediction_is_only_as_wide_as_the_dry_runs() -> None:
    """RM412's residual (d): an adapter refusing on its own inputs is predicted to run, so the help says so."""
    command = typer.main.get_command(app)
    rebuild = command.commands["cache"].commands["rebuild"]
    (option,) = [p for p in rebuild.params if p.name == "rehearse_download"]

    assert (
        "The prediction is the dry run's and no wider: an adapter that refuses on its own inputs (ACMG "
        "with no workbook, PharmVar with no key) prints `rehearsing:` and then `not run`."
    ) in option.help

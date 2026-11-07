"""`cache rebuild --dry-run` reads and never writes: no download, no build, no upload (RM411).

The dry run ran the whole rebuild and skipped only the upload, so the maintainer's rehearsal of
`--only opentargets --publish` began downloading 22 GB into `<out>/opentargets/source/`. These tests
run the dry run with every outside host fenced (the root conftest) and the hub faked, so a dry run
that reached for a source fails the test rather than a disk.
"""

import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher.cli import app
from just_dna_enricher.locations import RELEASE_FILENAME
from typer.testing import CliRunner


class _Hub:
    """`HfFileSystem.get` for one repo-root `release.json`: a label, absent, or a failure to ask."""

    def __init__(self, releases: dict[str, str | None], failure: Exception | None = None) -> None:
        self.releases = releases  # repo id -> release.json body, or None for "not there"
        self.failure = failure
        self.asked: list[str] = []

    def get(self, remote: str, local: str) -> None:
        self.asked.append(remote)
        if self.failure is not None:
            raise self.failure
        repo = remote.removeprefix("datasets/").rsplit("/", 1)[0]
        body = self.releases.get(repo)
        if body is None:
            raise FileNotFoundError(remote)
        Path(local).write_text(body, encoding="utf-8")


class _Api:
    """`HfApi.list_repo_files` for the rehearsal's orphan check: the repo holds nothing yet."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def list_repo_files(self, repo_id: str, repo_type: str | None = None, revision: str | None = None):
        return []


def _install(monkeypatch: pytest.MonkeyPatch, hub: _Hub) -> None:
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: hub)
    monkeypatch.setattr(huggingface_hub, "HfApi", _Api)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)


def _tree(root: Path) -> dict[str, float]:
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")} if root.exists() else {}


def test_a_dry_run_of_a_downloading_lane_downloads_nothing_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, tmp_path: Path
) -> None:
    """The maintainer's case: on the previous `main` this reached EBI, which the fence refuses."""
    _install(monkeypatch, _Hub({"just-dna-seq/opentargets": json.dumps({"dataset": "opentargets_26.09"})}))
    out = tmp_path / "caches"

    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(out), "--only", "opentargets", "--publish", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert not out.exists(), sorted(_tree(out))
    assert "published at just-dna-seq/opentargets: opentargets_26.09" in result.output
    assert "this machine: absent" in result.output
    assert "nothing was downloaded, built or uploaded" in result.output


def test_nothing_published_and_could_not_ask_are_different_answers(
    monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, tmp_path: Path
) -> None:
    """`@unreachable-not-absent`: a hub that failed to answer is never reported as an empty repo."""
    argv = [
        "cache",
        "rebuild",
        "--out",
        str(tmp_path / "c"),
        "--only",
        "clinvar_gkm",
        "--publish",
        "--dry-run",
    ]

    _install(monkeypatch, _Hub({}))
    absent = CliRunner().invoke(app, argv)
    _install(monkeypatch, _Hub({}, failure=OSError("read timed out")))
    unreachable = CliRunner().invoke(app, argv)

    assert "published at just-dna-seq/clinvar_gkm: nothing published" in absent.output, absent.output
    assert "could not ask (OSError)" in unreachable.output, unreachable.output
    assert "nothing published" not in unreachable.output


def test_a_snapshot_already_built_is_rehearsed_and_left_as_it_was(
    monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, tmp_path: Path
) -> None:
    """The arm that keeps a rebuild-route lane rehearsable: build first, then dry-run the upload."""
    _install(monkeypatch, _Hub({}))
    out = tmp_path / "caches"
    built = out / "clinvar_gkm"
    (built / "data").mkdir(parents=True)
    pl.DataFrame({"vrs_id": ["ga4gh:VA.x"]}).write_parquet(built / "data" / "clinvar_gkm-indels.parquet")
    (built / RELEASE_FILENAME).write_text(json.dumps({"dataset": "clinvar_gkm_2026-10-24"}), encoding="utf-8")
    before = _tree(out)

    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(out), "--only", "clinvar_gkm", "--publish", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert (
        f"would upload 2 file(s) from the snapshot already at {built} (clinvar_gkm_2026-10-24)"
        in result.output
    )
    assert _tree(out) == before


def test_a_gated_lane_says_in_the_dry_run_what_the_real_run_says(
    monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, tmp_path: Path
) -> None:
    """The prediction is the real run's own words: CPIC under an unstated use is skipped before any bytes.

    The real run is safe to run here because the gate refuses before the adapter fetches anything,
    and the fence would fail this test if it did not.
    """
    _install(monkeypatch, _Hub({}))

    def lane_line(argv: list[str]) -> str:
        result = CliRunner().invoke(
            app, ["cache", "rebuild", "--out", str(tmp_path / "c"), "--only", "cpic", *argv]
        )
        return next(line for line in result.output.splitlines() if line.lstrip().startswith("cpic"))

    assert lane_line(["--dry-run"]) == lane_line([])

"""`opentargets publish` and `clinvar-gkm publish`: a snapshot already built, published without a rebuild (RM412).

Both lanes published only through `cache rebuild --publish` in the 0.8 line, so an operator who had
built a snapshot with the lane's own `build` command had no command to send it. The two commands take
a built directory, as their siblings do, and send it where the lane's registry entry says, through the
same publisher call the rebuild route makes. Every outside host is fenced (the root conftest) and the
hub is faked, so a command that reached for the network fails the test.
"""

import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.cli import app
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.upload import plan_reference_snapshot
from typer.testing import CliRunner

#: The CLI group that carries each lane's standalone publish.
_GROUPS = {"opentargets": "opentargets", "clinvar_gkm": "clinvar-gkm"}


class _Api:
    """`HfApi` for the rehearsal's orphan check: the repo holds `held`, and a real upload is a failure."""

    held: list[str] = []

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def list_repo_files(self, repo_id: str, repo_type: str | None = None, revision: str | None = None):
        return list(self.held)

    def create_repo(self, *args, **kwargs):
        raise AssertionError("a dry run created a repo")

    def upload_folder(self, *args, **kwargs):
        raise AssertionError("a dry run uploaded")


@pytest.fixture
def fake_hub(monkeypatch: pytest.MonkeyPatch) -> type[_Api]:
    _Api.held = []
    monkeypatch.setattr(huggingface_hub, "HfApi", _Api)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    return _Api


def _built(root: Path, lane: str) -> Path:
    """A minimal built snapshot for `lane`: one parquet under `data/` and a labelled `release.json`."""
    snapshot = root / lane
    (snapshot / "data").mkdir(parents=True)
    pl.DataFrame({"key": ["x"]}).write_parquet(snapshot / "data" / f"{lane}-part.parquet")
    (snapshot / RELEASE_FILENAME).write_text(json.dumps({"dataset": f"{lane}_fixture"}), encoding="utf-8")
    return snapshot


@pytest.mark.parametrize("lane", sorted(_GROUPS))
def test_the_command_exists_and_can_be_rehearsed(lane: str) -> None:
    result = CliRunner().invoke(app, [_GROUPS[lane], "publish", "--help"])
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.output


@pytest.mark.parametrize("lane", sorted(_GROUPS))
def test_the_dry_run_names_the_lanes_repo_and_the_files_the_rebuild_route_would_send(
    lane: str, fake_hub: type[_Api], tmp_path: Path
) -> None:
    """Parity with the rebuild route: the lane's own `publish_repo`, and the plan the publisher makes of the dir."""
    snapshot = _built(tmp_path, lane)
    repo = LANES_BY_NAME[lane].publish_repo
    assert repo is not None
    expected = plan_reference_snapshot(snapshot, repo)

    result = CliRunner().invoke(app, [_GROUPS[lane], "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert f"would upload {len(expected.files)} file(s) to {repo}: {expected.files}" in result.output


@pytest.mark.parametrize("lane", sorted(_GROUPS))
def test_a_directory_with_nothing_built_is_refused_in_the_dry_run_as_in_the_real_run(
    lane: str, fake_hub: type[_Api], tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    runner = CliRunner()

    rehearsed = runner.invoke(app, [_GROUPS[lane], "publish", str(empty), "--dry-run"])
    real = runner.invoke(app, [_GROUPS[lane], "publish", str(empty)])

    assert rehearsed.exit_code == 1 and real.exit_code == 1
    assert "WOULD BE REFUSED: no data/*.parquet" in rehearsed.output
    assert "PUBLISH FAILED: no data/*.parquet" in real.output


def test_the_rehearsal_runs_the_orphan_check_the_real_publish_refuses_on(
    fake_hub: type[_Api], tmp_path: Path
) -> None:
    """A repo holding a sidecar this snapshot does not carry: the publish would orphan it, so the dry run says so."""
    snapshot = _built(tmp_path, "clinvar_gkm")
    fake_hub.held = ["data/clinvar_gkm-part.parquet", "citations/stale.parquet", RELEASE_FILENAME]

    result = CliRunner().invoke(app, ["clinvar-gkm", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 1, result.output
    assert "WOULD BE REFUSED" in result.output

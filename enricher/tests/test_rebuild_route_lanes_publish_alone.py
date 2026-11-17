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


# ── a partial build is refused, and an unlabelled one is warned about (RM412's follow-up) ─────────────


def _with_release(root: Path, lane: str, release: dict) -> Path:
    """`_built`, with `release.json` replaced by `release`."""
    snapshot = _built(root, lane)
    (snapshot / RELEASE_FILENAME).write_text(json.dumps(release), encoding="utf-8")
    return snapshot


#: A `--parts 2` test build's counts: one dataset read short, one (`study`, always read whole) not.
_PARTS_READ = {"credible_set": 2, "study": 1}
_PARTS_TOTAL = {"credible_set": 40, "study": 1}


def _partial_refusal(snapshot: Path, read: dict[str, int], total: dict[str, int]) -> str:
    """The refusal's text, computed from the fixture's numbers: every dataset read short, sorted by name."""
    short = ", ".join(
        f"{name} {read[name]} of {total[name]} parts"
        for name in sorted(set(read) & set(total))
        if read[name] < total[name]
    )
    return (
        f"{snapshot} is a partial build: its {RELEASE_FILENAME} records {short} read, so whoever pulls it "
        f"would take a row missing from a part nobody read for an answer. Publish a whole build (for Open "
        f"Targets, one `opentargets build` made without --parts)."
    )


@pytest.mark.parametrize("lane", sorted(_GROUPS))
def test_a_partial_build_is_refused_in_the_dry_run_and_before_the_real_run_touches_the_repo(
    lane: str, fake_hub: type[_Api], tmp_path: Path
) -> None:
    """A `--parts`-limited test build may not reach the public repo: refused with both numbers, before `create_repo`."""
    snapshot = _with_release(
        tmp_path,
        lane,
        {"dataset": f"{lane}_fixture", "parts_read": _PARTS_READ, "parts_total": _PARTS_TOTAL},
    )
    expected = _partial_refusal(snapshot, _PARTS_READ, _PARTS_TOTAL)
    runner = CliRunner()

    rehearsed = runner.invoke(app, [_GROUPS[lane], "publish", str(snapshot), "--dry-run"])
    real = runner.invoke(app, [_GROUPS[lane], "publish", str(snapshot)])

    assert rehearsed.exit_code == 1, rehearsed.output
    assert f"WOULD BE REFUSED: {expected}" in " ".join(rehearsed.output.split())
    # The fake hub's `create_repo` raises: a refusal that came after it would surface as that error.
    assert isinstance(real.exception, SystemExit), real.exception
    assert real.exit_code == 1, real.output
    assert f"PUBLISH FAILED: {expected}" in " ".join(real.output.split())


@pytest.mark.parametrize(
    "release",
    [
        {"dataset": "fixture"},
        {"dataset": "fixture", "parts_total": _PARTS_TOTAL},
        {"dataset": "fixture", "parts_read": _PARTS_READ},
        {"dataset": "fixture", "parts_read": {"credible_set": 40}, "parts_total": {"credible_set": 40}},
        {"dataset": "fixture", "parts_read": {"credible_set": 2}, "parts_total": {"l2g": 40}},
    ],
    ids=["no-keys", "total-only", "read-only", "whole", "no-dataset-in-both"],
)
def test_a_record_that_does_not_state_a_short_read_is_not_refused_by_this_check(
    release: dict, fake_hub: type[_Api], tmp_path: Path
) -> None:
    """Only a dataset whose record states both counts, read below total, refuses; an unstated count is not partial."""
    snapshot = _with_release(tmp_path, "opentargets", release)

    result = CliRunner().invoke(app, ["opentargets", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "would upload" in result.output
    assert "partial build" not in result.output


#: The source each lane's warning names.
_SOURCE_NAMES = {"opentargets": "Open Targets", "clinvar_gkm": "ClinVar-GKM"}

#: The opening the two new commands share with `mitomap publish` and `strchive publish`.
_UNLABELLED = "this snapshot carries no release label, so everyone who pulls it inherits"


@pytest.mark.parametrize("lane", sorted(_GROUPS))
@pytest.mark.parametrize(
    "release", [{}, {"dataset": "  "}, None], ids=["no-dataset", "blank", "no-release-json"]
)
def test_an_unlabelled_snapshot_is_warned_about_as_its_siblings_do_and_still_rehearsed(
    lane: str, release: dict | None, fake_hub: type[_Api], tmp_path: Path
) -> None:
    snapshot = _built(tmp_path, lane)
    if release is None:
        (snapshot / RELEASE_FILENAME).unlink()
    else:
        (snapshot / RELEASE_FILENAME).write_text(json.dumps(release), encoding="utf-8")

    result = CliRunner().invoke(app, [_GROUPS[lane], "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    said = " ".join(result.output.split())
    assert (
        f"{_UNLABELLED} a snapshot that cannot name its own {_SOURCE_NAMES[lane]} release. "
        f"Rebuild it with `{_GROUPS[lane]} build`." in said
    )
    assert "would upload" in said


@pytest.mark.parametrize("lane", sorted(_GROUPS))
def test_a_labelled_whole_snapshot_draws_neither_the_warning_nor_the_refusal(
    lane: str, fake_hub: type[_Api], tmp_path: Path
) -> None:
    snapshot = _built(tmp_path, lane)

    result = CliRunner().invoke(app, [_GROUPS[lane], "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "carries no release label" not in result.output
    assert "partial build" not in result.output


def test_an_unlabelled_partial_build_is_warned_about_first_and_then_refused(
    fake_hub: type[_Api], tmp_path: Path
) -> None:
    snapshot = _with_release(
        tmp_path, "opentargets", {"parts_read": _PARTS_READ, "parts_total": _PARTS_TOTAL}
    )

    result = CliRunner().invoke(app, ["opentargets", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 1, result.output
    said = " ".join(result.output.split())
    assert said.index(_UNLABELLED) < said.index("WOULD BE REFUSED")

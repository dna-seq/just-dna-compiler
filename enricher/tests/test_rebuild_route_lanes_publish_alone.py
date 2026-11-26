"""`opentargets publish` and `clinvar-gkm publish`: a snapshot already built, published without a rebuild (RM412).

Both lanes published only through `cache rebuild --publish` in the 0.8 line, so an operator who had
built a snapshot with the lane's own `build` command had no command to send it. The two commands take
a built directory, as their siblings do, and send it where the lane's registry entry says, through the
same publisher call the rebuild route makes. Every outside host is fenced (the root conftest) and the
hub is faked, so a command that reached for the network fails the test.
"""

import json
import os
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.cli import app
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.upload import SnapshotNotPublishable, plan_reference_snapshot
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


@pytest.mark.parametrize("command", [*_GROUPS.values(), "strchive", "mitomap"])
def test_a_directory_with_nothing_built_is_refused_in_the_dry_run_as_in_the_real_run(
    command: str, fake_hub: type[_Api], tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    runner = CliRunner()

    rehearsed = runner.invoke(app, [command, "publish", str(empty), "--dry-run"])
    real = runner.invoke(app, [command, "publish", str(empty)])

    assert rehearsed.exit_code == 0 and real.exit_code == 1
    missing = "STRchive-loci.json" if command == "strchive" else "data/*.parquet"
    assert f"WOULD BE REFUSED: no {missing}" in rehearsed.output
    assert f"PUBLISH FAILED: no {missing}" in real.output


def test_the_rehearsal_runs_the_orphan_check_the_real_publish_refuses_on(
    fake_hub: type[_Api], tmp_path: Path
) -> None:
    """A repo holding a sidecar this snapshot does not carry: the publish would orphan it, so the dry run says so."""
    snapshot = _built(tmp_path, "clinvar_gkm")
    fake_hub.held = ["data/clinvar_gkm-part.parquet", "citations/stale.parquet", RELEASE_FILENAME]

    result = CliRunner().invoke(app, ["clinvar-gkm", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
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

    assert rehearsed.exit_code == 0, rehearsed.output
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

    assert result.exit_code == 0, result.output
    said = " ".join(result.output.split())
    assert said.index(_UNLABELLED) < said.index("WOULD BE REFUSED")


# ── an unreadable record is refused, an absent one is not (RM412's second follow-up) ──────────────────


def _with_release_bytes(root: Path, lane: str, raw: bytes) -> Path:
    """`_built`, with `release.json` replaced by `raw`, byte for byte."""
    snapshot = _built(root, lane)
    (snapshot / RELEASE_FILENAME).write_bytes(raw)
    return snapshot


def _decode_problem(raw: bytes) -> str:
    """What the standard library says is wrong with `raw` as JSON: the error the refusal must quote."""
    try:
        json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        return str(exc)
    raise AssertionError(f"{raw!r} parses")


def _unreadable_refusal(snapshot: Path, problem: str) -> str:
    return (
        f"{snapshot / RELEASE_FILENAME} cannot be read ({problem}), so nothing can say whether this snapshot "
        f"was built whole. Rebuild the snapshot before publishing."
    )


def _miscounted_refusal(snapshot: Path, items: list[str]) -> str:
    return (
        f"{snapshot / RELEASE_FILENAME} records {'; '.join(items)}, so nothing can say whether this snapshot "
        f"was built whole. Rebuild the snapshot before publishing."
    )


#: Bytes that are not a JSON document at all: truncated, not JSON, not UTF-8.
_UNPARSABLE = {
    "truncated": b'{"dataset": "fixture", "parts_read": {"l2g": 1',
    "not-json": b"dataset=fixture\n",
    "empty": b"",
    "not-utf8": b'{"dataset": "\xff"}',
}


def _assert_refused_in_both_runs(lane: str, snapshot: Path, expected: str) -> None:
    """Refused in the rehearsal and in the real run, and the real run never reached `create_repo`."""
    runner = CliRunner()
    rehearsed = runner.invoke(app, [_GROUPS[lane], "publish", str(snapshot), "--dry-run"])
    real = runner.invoke(app, [_GROUPS[lane], "publish", str(snapshot)])

    assert rehearsed.exit_code == 0, rehearsed.output
    assert f"WOULD BE REFUSED: {expected}" in " ".join(rehearsed.output.split())
    # The fake hub's `create_repo` raises: a refusal that came after it would surface as that error.
    assert isinstance(real.exception, SystemExit), real.exception
    assert real.exit_code == 1, real.output
    assert f"PUBLISH FAILED: {expected}" in " ".join(real.output.split())


@pytest.mark.parametrize("lane", sorted(_GROUPS))
@pytest.mark.parametrize("raw", list(_UNPARSABLE.values()), ids=list(_UNPARSABLE))
def test_a_release_record_that_does_not_parse_is_refused_before_the_repo_is_touched(
    lane: str, raw: bytes, fake_hub: type[_Api], tmp_path: Path
) -> None:
    """Present and unreadable is the refusal: the record that would say whether the build is whole says nothing."""
    snapshot = _with_release_bytes(tmp_path, lane, raw)

    _assert_refused_in_both_runs(lane, snapshot, _unreadable_refusal(snapshot, _decode_problem(raw)))


def test_a_release_record_that_cannot_be_read_off_the_disk_is_refused(
    fake_hub: type[_Api], tmp_path: Path
) -> None:
    """Present and unreadable on disk is the same refusal: the record is there and says nothing."""
    snapshot = _built(tmp_path, "opentargets")
    record = snapshot / RELEASE_FILENAME
    record.chmod(0)
    try:
        if os.access(record, os.R_OK):
            pytest.skip("this user, or this filesystem, reads a file whatever its mode")
        with pytest.raises(OSError) as denied:
            record.read_bytes()
        _assert_refused_in_both_runs(
            "opentargets", snapshot, _unreadable_refusal(snapshot, str(denied.value))
        )
    finally:
        record.chmod(0o644)


@pytest.mark.parametrize("lane", sorted(_GROUPS))
@pytest.mark.parametrize("document", [[], ["fixture"], "fixture", 3, None], ids=repr)
def test_a_release_record_that_is_not_a_json_object_is_refused(
    lane: str, document: object, fake_hub: type[_Api], tmp_path: Path
) -> None:
    snapshot = _with_release_bytes(tmp_path, lane, json.dumps(document).encode())

    _assert_refused_in_both_runs(lane, snapshot, _unreadable_refusal(snapshot, "not a JSON object"))


#: A count present and not a whole number, and what the refusal says about it. A parts map that is not
#: a map at all is the same claim one level up.
_MISCOUNTED = {
    "read-is-a-string": (
        {"parts_read": "1", "parts_total": {"l2g": 12}},
        ['parts_read is "1", not a map of datasets to part counts'],
    ),
    "total-is-a-number": (
        {"parts_read": {"l2g": 1}, "parts_total": 12},
        ["parts_total is 12, not a map of datasets to part counts"],
    ),
    "total-is-a-list": (
        {"parts_read": {"l2g": 1}, "parts_total": [12]},
        ["parts_total is [12], not a map of datasets to part counts"],
    ),
    "count-is-a-string": (
        {"parts_read": {"l2g": "1"}, "parts_total": {"l2g": 12}},
        ['parts_read["l2g"] is "1", not a whole number'],
    ),
    "count-is-a-fraction": (
        {"parts_read": {"l2g": 1.5}, "parts_total": {"l2g": 12}},
        ['parts_read["l2g"] is 1.5, not a whole number'],
    ),
    "count-is-a-float": (
        {"parts_read": {"l2g": 12}, "parts_total": {"l2g": 12.0}},
        ['parts_total["l2g"] is 12.0, not a whole number'],
    ),
    "count-is-a-boolean": (
        {"parts_read": {"l2g": True}, "parts_total": {"l2g": 1}},
        ['parts_read["l2g"] is true, not a whole number'],
    ),
    "count-is-a-map": (
        {"parts_read": {"l2g": {"n": 1}}, "parts_total": {"l2g": 1}},
        ['parts_read["l2g"] is {"n": 1}, not a whole number'],
    ),
    "a-name-outside-ascii": (
        {"parts_read": {"étude": "1"}, "parts_total": {"étude": 1}},
        ['parts_read["étude"] is "1", not a whole number'],
    ),
    "count-is-null": (
        # No builder writes a `null` count, and the lenient read drops the whole map over one, which
        # let `l2g` at 1 of 12 past the partial-build check.
        {"parts_read": {"l2g": 1, "study": None}, "parts_total": {"l2g": 12, "study": 1}},
        ['parts_read["study"] is null, not a whole number'],
    ),
    "total-count-is-null": (
        {"parts_read": {"l2g": 1}, "parts_total": {"l2g": None}},
        ['parts_total["l2g"] is null, not a whole number'],
    ),
    "read-below-zero": (
        {"parts_read": {"l2g": -1}, "parts_total": {"l2g": 12}},
        ['parts_read["l2g"] is -1, below zero'],
    ),
    "total-below-zero": (
        {"parts_read": {"l2g": 1}, "parts_total": {"l2g": -12}},
        ['parts_total["l2g"] is -12, below zero'],
    ),
    "total-is-zero": (
        {"parts_read": {"l2g": 0}, "parts_total": {"l2g": 0}},
        ['parts_total["l2g"] is 0, and a dataset has at least one part'],
    ),
    "several": (
        {"parts_read": {"study": "1", "l2g": "1"}, "parts_total": {"l2g": 1.0, "study": 1}},
        [
            'parts_read["l2g"] is "1", not a whole number',
            'parts_read["study"] is "1", not a whole number',
            'parts_total["l2g"] is 1.0, not a whole number',
        ],
    ),
}


@pytest.mark.parametrize("lane", sorted(_GROUPS))
@pytest.mark.parametrize("case", list(_MISCOUNTED.values()), ids=list(_MISCOUNTED))
def test_a_parts_count_present_and_not_a_whole_number_is_refused_quoting_it(
    lane: str, case: tuple[dict, list[str]], fake_hub: type[_Api], tmp_path: Path
) -> None:
    """`"1"` and `12.0` are coerced into counts by the lenient read, and `true` into 1; the gate reads them as written."""
    release, items = case
    snapshot = _with_release(tmp_path, lane, {"dataset": f"{lane}_fixture", **release})

    _assert_refused_in_both_runs(lane, snapshot, _miscounted_refusal(snapshot, items))


@pytest.mark.parametrize(
    "release",
    [
        {"dataset": "fixture", "parts_read": None, "parts_total": None},
        {"dataset": "fixture", "parts_read": {"l2g": 12}, "parts_total": {"l2g": 12}, "row_count": "7"},
    ],
    ids=["stated-unknown", "an-unrelated-key-miscounted"],
)
def test_a_stated_unknown_and_other_keys_are_not_this_checks_refusal(
    release: dict, fake_hub: type[_Api], tmp_path: Path
) -> None:
    """A recorded `null` map is the model's stated unknown, and the gate reads only the parts counts strictly."""
    snapshot = _with_release(tmp_path, "opentargets", release)

    result = CliRunner().invoke(app, ["opentargets", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "would upload" in result.output
    assert "Rebuild the snapshot before publishing" not in result.output


def test_a_read_of_zero_parts_is_not_this_checks_refusal(fake_hub: type[_Api], tmp_path: Path) -> None:
    """Zero parts read is a whole number the partial-build check reads: short of any total, never unreadable."""
    snapshot = _with_release(
        tmp_path, "opentargets", {"dataset": "fixture", "parts_read": {"l2g": 0}, "parts_total": {"l2g": 12}}
    )

    result = CliRunner().invoke(app, ["opentargets", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Rebuild the snapshot before publishing" not in result.output
    assert "is a partial build" in result.output and "l2g 0 of 12 parts" in result.output


def test_a_snapshot_with_no_release_record_is_not_refused_by_this_check(
    fake_hub: type[_Api], tmp_path: Path
) -> None:
    snapshot = _built(tmp_path, "opentargets")
    (snapshot / RELEASE_FILENAME).unlink()

    result = CliRunner().invoke(app, ["opentargets", "publish", str(snapshot), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "would upload" in result.output


@pytest.mark.parametrize("payload", [None, "STRchive-loci.json"])
def test_the_planner_itself_refuses_so_every_snapshot_publish_inherits_it(
    payload: str | None, tmp_path: Path
) -> None:
    """`plan_reference_snapshot`, with and without a root payload: the check runs before either branch."""
    snapshot = _with_release_bytes(tmp_path, "opentargets", b"{")
    if payload is not None:
        (snapshot / payload).write_text("[]", encoding="utf-8")
    miscounted = _with_release(tmp_path / "other", "opentargets", {"parts_read": "1"})
    if payload is not None:
        (miscounted / payload).write_text("[]", encoding="utf-8")

    with pytest.raises(SnapshotNotPublishable) as unreadable:
        plan_reference_snapshot(snapshot, "o/r", payload=payload)
    with pytest.raises(SnapshotNotPublishable) as counted:
        plan_reference_snapshot(miscounted, "o/r", payload=payload)

    assert str(unreadable.value) == _unreadable_refusal(snapshot, _decode_problem(b"{"))
    assert str(counted.value) == _miscounted_refusal(
        miscounted, ['parts_read is "1", not a map of datasets to part counts']
    )


def test_the_four_refusals_say_four_different_things(tmp_path: Path) -> None:
    """Unparsable, not an object, miscounted and partial are four instructions; no two messages may coincide."""
    snapshots = {
        "unparsable": _with_release_bytes(tmp_path / "a", "opentargets", b"{"),
        "not-an-object": _with_release_bytes(tmp_path / "b", "opentargets", b"[]"),
        "miscounted": _with_release(tmp_path / "c", "opentargets", {"parts_read": {"l2g": "1"}}),
        "partial": _with_release(
            tmp_path / "d", "opentargets", {"parts_read": _PARTS_READ, "parts_total": _PARTS_TOTAL}
        ),
    }
    said = {}
    for name, snapshot in snapshots.items():
        with pytest.raises(SnapshotNotPublishable) as refused:
            plan_reference_snapshot(snapshot, "o/r")
        said[name] = str(refused.value).replace(str(snapshot), "<dir>")

    assert len(set(said.values())) == len(said), said


def test_the_publish_gate_refuses_more_parts_read_than_exist(tmp_path: Path) -> None:
    total = _PARTS_TOTAL["study"]
    read = total + 1
    snapshot = _with_release(
        tmp_path, "opentargets", {"parts_read": {"study": read}, "parts_total": {"study": total}}
    )
    with pytest.raises(SnapshotNotPublishable) as refused:
        plan_reference_snapshot(snapshot)
    assert str(refused.value) == _miscounted_refusal(
        snapshot, [f'parts_read["study"] is {read}, above parts_total {total}']
    )


def test_planning_still_warns_about_an_unrelated_mistyped_field(tmp_path: Path, caplog) -> None:
    snapshot = _with_release(tmp_path, "opentargets", {"dataset": "labelled", "row_count": []})
    assert RELEASE_FILENAME in plan_reference_snapshot(snapshot).files
    assert (
        f"{snapshot / RELEASE_FILENAME}: row_count do not fit the snapshot record; read as unstated."
        in caplog.messages
    )

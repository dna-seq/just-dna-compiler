"""Deletion on a published repo is declared or asked for, never swept (RM185, RM186).

The policy these tests pin, decided with the maintainer on 2026-09-03 after the audit that found a
159 MB single-file `clinvar.parquet` still sitting beside the per-chromosome layout that replaced it:

* **A publish may delete exactly one thing: a retirement the code declares.** A change that retires a
  published file and introduces another carries a `LayoutShift`, whose predicate is over the *remote* —
  new absent and old present — so it fires once per repo and is a no-op forever after.
* **Everything else goes through `cache prune`**, which reads, prints, and stops unless told `--yes`.
* **A publish refuses to orphan a sidecar**: replacing a `release.json` that describes bytes this
  publish is not carrying is what left the published ClinVar snapshot mixed-vintage and silent.

No sockets: `huggingface_hub.HfApi` is a `MagicMock`, the same way `test_upload.py` fakes it.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from just_dna_enricher.caches import CACHE_LANES
from just_dna_enricher.download import SNAPSHOT_FILE_GLOBS
from just_dna_enricher.upload import (
    DEFAULT_CLINVAR_REPO_ID,
    LAYOUT_SHIFTS,
    OrphanedSidecarError,
    SnapshotPlan,
    check_publish_orphans_no_sidecar,
    layout_shifts_to_apply,
    plan_prune,
    prune_repo,
    publish_reference_snapshot,
)

_OLD = "data/clinvar.parquet"
_NEW = "data/clinvar-chr1.parquet"


def _tree(*paths_and_sizes):
    """`list_repo_tree(expand=True)` entries, as objects with `path` and `size`."""
    return [MagicMock(path=path, size=size) for path, size in paths_and_sizes]


# ── the predicate: fires once, on the state it names ────────────────────────────────────────────


def test_a_declared_shift_fires_only_on_a_repo_that_has_not_moved() -> None:
    """New absent and old present. Every other state is somebody else's business."""
    fires = layout_shifts_to_apply([_OLD, "release.json"], DEFAULT_CLINVAR_REPO_ID)
    assert [s.retires for s in fires] == [_OLD]

    # already moved but never cleaned — today's repo. The migration is NOT the tool for this; prune is.
    assert layout_shifts_to_apply([_OLD, _NEW, "release.json"], DEFAULT_CLINVAR_REPO_ID) == []
    # moved and clean: nothing to do, forever
    assert layout_shifts_to_apply([_NEW, "release.json"], DEFAULT_CLINVAR_REPO_ID) == []
    # a fresh repo
    assert layout_shifts_to_apply([], DEFAULT_CLINVAR_REPO_ID) == []


def test_a_shift_is_scoped_to_its_own_repo() -> None:
    """A file name is not a global fact: another repo's `data/clinvar.parquet` is not this one's."""
    assert layout_shifts_to_apply([_OLD], "just-dna-seq/cpic") == []


def test_applying_a_shift_makes_its_own_predicate_false() -> None:
    """The fires-once property, asserted as the property rather than as a count of calls.

    After the migration commits, the repo holds the new file and not the old — which is exactly the
    state the predicate excludes, so a second publish deletes nothing.
    """
    before = [_OLD, "release.json"]
    (shift,) = layout_shifts_to_apply(before, DEFAULT_CLINVAR_REPO_ID)
    after = [p for p in before if p != shift.retires] + [_NEW]
    assert layout_shifts_to_apply(after, DEFAULT_CLINVAR_REPO_ID) == []


def test_every_declared_shift_names_a_repo_this_tier_publishes_to() -> None:
    """A retirement against a repo no lane publishes could never fire and would never be noticed."""
    published = {lane.publish_repo for lane in CACHE_LANES if lane.publish_repo}
    assert {shift.repo_id for shift in LAYOUT_SHIFTS} <= published


def test_every_published_lane_with_a_data_directory_has_a_glob() -> None:
    """Walked, because `cache prune` asks the registry by lane name (`@registry-completeness`).

    STRchive is the one exclusion and it is a shape, not an omission: its snapshot is a single JSON at
    the repo root, so there is no `data/` for a file to be outside of.
    """
    publishable = {lane.name for lane in CACHE_LANES if lane.publish_repo is not None}
    assert publishable - set(SNAPSHOT_FILE_GLOBS) == {"strchive"}


# ── the publish: one declared delete, in the same commit ────────────────────────────────────────


@pytest.fixture
def hf(tmp_path: Path):
    """A snapshot directory and a `MagicMock` HfApi whose remote file list the test chooses."""
    snapshot = tmp_path / "clinvar"
    (snapshot / "data").mkdir(parents=True)
    (snapshot / "data" / "clinvar-chr1.parquet").write_bytes(b"PAR1PAR1")
    (snapshot / "release.json").write_text('{"clinvar_file_date": "2026-08-29"}')

    def install(remote: list[str]):
        api = MagicMock()
        api.list_repo_files.return_value = remote
        patcher = patch("huggingface_hub.HfApi", return_value=api)
        patcher.start()
        token = patch("huggingface_hub.get_token", return_value="hf_test_token")
        token.start()
        return api, snapshot

    yield install
    patch.stopall()


def test_a_publish_onto_an_unmigrated_repo_deletes_the_retired_file_in_the_same_commit(hf) -> None:
    """One commit, not two: the window in which the repo has both or neither is what this avoids."""
    api, snapshot = hf([_OLD, "release.json"])
    publish_reference_snapshot(snapshot, DEFAULT_CLINVAR_REPO_ID)

    kwargs = api.upload_folder.call_args.kwargs
    assert kwargs["delete_patterns"] == [_OLD]
    assert _OLD in kwargs["commit_message"], "the operator reads the deletion in the commit message"
    api.delete_files.assert_not_called()      # the deletion rides the upload; it is not a second write


def test_a_publish_onto_a_repo_that_has_moved_deletes_nothing(hf) -> None:
    """Today's ClinVar repo: both files present, so the declaration is spent and prune owns it."""
    api, snapshot = hf([_OLD, _NEW, "release.json"])
    publish_reference_snapshot(snapshot, DEFAULT_CLINVAR_REPO_ID)
    assert api.upload_folder.call_args.kwargs["delete_patterns"] is None


def test_a_publish_to_a_repo_with_no_declaration_deletes_nothing(hf) -> None:
    api, snapshot = hf(["data/anything.parquet"])
    publish_reference_snapshot(snapshot, "just-dna-seq/cpic")
    assert api.upload_folder.call_args.kwargs["delete_patterns"] is None


# ── the refusal: a publish may not orphan a sidecar ─────────────────────────────────────────────


def test_a_publish_that_would_leave_the_citations_undescribed_is_refused() -> None:
    """The 2026-09-02 publish, refused. The message names the file so the fix is the next command."""
    api = MagicMock()
    api.list_repo_files.return_value = [
        "data/clinvar-chr1.parquet", "citations/citations.parquet", "release.json",
    ]
    plan = SnapshotPlan(repo_id=DEFAULT_CLINVAR_REPO_ID,
                        files=["data/clinvar-chr1.parquet", "release.json"])
    with pytest.raises(OrphanedSidecarError, match="citations/citations.parquet"):
        check_publish_orphans_no_sidecar(plan, api)


def test_carrying_the_sidecar_passes() -> None:
    api = MagicMock()
    api.list_repo_files.return_value = ["citations/citations.parquet", "release.json"]
    plan = SnapshotPlan(
        repo_id=DEFAULT_CLINVAR_REPO_ID,
        files=["data/clinvar-chr1.parquet", "citations/citations.parquet", "release.json"],
    )
    check_publish_orphans_no_sidecar(plan, api)


def test_a_publish_carrying_no_release_json_overwrites_no_provenance() -> None:
    """The refusal is about replacing the description, so a publish that replaces none is not it."""
    api = MagicMock()
    api.list_repo_files.return_value = ["citations/citations.parquet"]
    plan = SnapshotPlan(repo_id=DEFAULT_CLINVAR_REPO_ID, files=["data/clinvar-chr1.parquet"])
    check_publish_orphans_no_sidecar(plan, api)


def test_a_repo_nobody_has_published_to_is_a_first_publish_not_an_orphan() -> None:
    api = MagicMock()
    api.list_repo_files.side_effect = FileNotFoundError("no such repo")
    plan = SnapshotPlan(repo_id=DEFAULT_CLINVAR_REPO_ID, files=["release.json"])
    check_publish_orphans_no_sidecar(plan, api)


def test_the_guard_reads_the_tree_and_not_the_release_block() -> None:
    """The state it was found in: the sidecar present, its block already gone from `release.json`.

    A guard that asked the remote `release.json` whether it described a sidecar would have said no —
    and passed the second bad publish exactly as the first one passed.
    """
    api = MagicMock()
    api.list_repo_files.return_value = ["citations/citations.parquet"]   # no block anywhere
    plan = SnapshotPlan(repo_id=DEFAULT_CLINVAR_REPO_ID, files=["release.json"])
    with pytest.raises(OrphanedSidecarError):
        check_publish_orphans_no_sidecar(plan, api)


# ── prune: names two kinds of file and nothing else ─────────────────────────────────────────────


def test_prune_names_the_glob_excluded_and_the_declared_and_leaves_the_rest() -> None:
    api = MagicMock()
    api.list_repo_tree.return_value = _tree(
        (_NEW, 7_000_000),                       # this snapshot
        (_OLD, 159_000_000),                     # declared retired
        ("data/stray-export.parquet", 12),       # outside the glob
        ("citations/citations.parquet", 13_000), # a sidecar: never a candidate
        ("release.json", 300),
        ("LICENSE.txt", 1_000),
        ("README.md", 2_000),
        (".gitattributes", 100),
    )
    plan = plan_prune(DEFAULT_CLINVAR_REPO_ID, SNAPSHOT_FILE_GLOBS["clinvar"], api)

    assert [c.path for c in plan.candidates] == [_OLD, "data/stray-export.parquet"]
    assert plan.total_bytes == 159_000_012
    reasons = {c.path: c.reason for c in plan.candidates}
    assert "declared retired" in reasons[_OLD], "a declaration says when and why; a glob does not"
    assert "outside this snapshot" in reasons["data/stray-export.parquet"]


def test_a_lane_whose_glob_is_everything_can_still_name_a_declared_retirement() -> None:
    """For clinpgx/cpic/civic/drug_labels the glob excludes nothing, so declaration is the only name.

    Asserted against the real registry entry rather than a literal `*.parquet`, so the day one of
    those lanes narrows its glob this test is about that lane rather than about a string.
    """
    assert SNAPSHOT_FILE_GLOBS["cpic"] == "*.parquet"
    api = MagicMock()
    api.list_repo_tree.return_value = _tree(("data/genes.parquet", 5), ("data/old.parquet", 5))
    assert plan_prune("just-dna-seq/cpic", SNAPSHOT_FILE_GLOBS["cpic"], api).candidates == []


def test_prune_deletes_exactly_what_it_listed() -> None:
    api = MagicMock()
    api.list_repo_tree.return_value = _tree((_NEW, 1), (_OLD, 159_000_000))
    plan = plan_prune(DEFAULT_CLINVAR_REPO_ID, SNAPSHOT_FILE_GLOBS["clinvar"], api)
    with (
        patch("huggingface_hub.HfApi", return_value=api),
        patch("huggingface_hub.get_token", return_value="hf_test_token"),
    ):
        deleted = prune_repo(plan)
    assert deleted == 1
    assert api.delete_files.call_args.kwargs["delete_patterns"] == [_OLD]


def test_an_empty_plan_touches_nothing() -> None:
    """`@empty-work-is-a-path`: the run with nothing to do must not open a write."""
    api = MagicMock()
    api.list_repo_tree.return_value = _tree((_NEW, 1))
    plan = plan_prune(DEFAULT_CLINVAR_REPO_ID, SNAPSHOT_FILE_GLOBS["clinvar"], api)
    with patch("huggingface_hub.HfApi", return_value=api):
        assert prune_repo(plan) == 0
    api.delete_files.assert_not_called()

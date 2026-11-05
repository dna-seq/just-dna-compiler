"""A publish is tied to the bytes it read and to the revision it read them at (RM386).

The class (audit 2, class 1): a publish plan named paths, and what was sent was whatever those paths
held when the hub got round to reading them; and it read the remote at one moment and committed at
another, with nothing pinning the commit to the state it had read. Each defect needs a concurrent
writer to bite, so every test here arranges one against `FakeHub` (conftest), a repository with a
head, parents and a hub-side refusal of a stale `parent_commit` — never a recorder of calls.

The mechanism is one helper, `upload._commit`, that every hub write goes through and that always
passes the revision the plan read as `parent_commit`; every remote read the publisher makes names
that revision; and a snapshot's payload is checked on the hub against the hashes of the one local
read before anything describes it. The two AST guards at the bottom hold the first two to the code.
"""

import ast
import hashlib
import inspect
import json
from pathlib import Path

import just_dna_enricher
import just_dna_enricher.upload as upload
import pytest
from huggingface_hub import HfApi
from just_dna_enricher.cli import app
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.upload import (
    DEFAULT_CLINVAR_REPO_ID,
    PlanChangedError,
    PruneCandidate,
    PrunePlan,
    plan_prune,
    prune_repo,
    publish_reference_snapshot,
    upload_module,
)
from just_dna_format.integrity import build_artifact
from just_dna_format.manifest import Artifact, Display, Identity, ModuleManifest, write_manifest
from typer.testing import CliRunner

_REPO = "just-dna-seq/clinvar"
_MODULE_REPO = "just-dna-seq/annotators"


def _build(snapshot: Path, release: str) -> dict[str, bytes]:
    """Build (or rebuild) a snapshot of `release` in place: a payload parquet and its description."""
    files = {
        "data/clinvar-chr1.parquet": f"PAR1 chr1 rows of {release} PAR1".encode(),
        "data/clinvar-chr2.parquet": f"PAR1 chr2 rows of {release} PAR1".encode(),
        "LICENSE.txt": f"terms of {release}\n".encode(),
        RELEASE_FILENAME: json.dumps({"clinvar": {"release": release}}).encode(),
    }
    for name, data in files.items():
        (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
        (snapshot / name).write_bytes(data)
    return files


def _published(hub, files: dict[str, bytes]) -> dict[str, bytes]:
    tree = hub.tree()
    return {name: tree.get(name) for name in files}


# ── the snapshot publish: the bytes ───────────────────────────────────────────────────────────────


def test_a_rebuild_after_the_payload_lands_never_reaches_its_description(tmp_path: Path, fake_hub) -> None:
    """The audit's scenario: R1's payload is sent, the snapshot is rebuilt as R2, and the second
    upload read `release.json` off the disk again — so the hub held R1's rows under R2's description.
    The description is now the plan's bytes, read once with the rest, so it describes what was sent."""
    snapshot = tmp_path / "snap"
    r1 = _build(snapshot, "2026-10")
    hub = fake_hub(_REPO)
    hub.before_write[1] = lambda: _build(snapshot, "2026-11")
    publish_reference_snapshot(snapshot, _REPO)
    assert _published(hub, r1) == r1


def test_a_rebuild_while_the_payload_is_read_withholds_the_description(tmp_path: Path, fake_hub) -> None:
    """The hub reads the folder after the plan did. A rebuild landing in between sends bytes the plan
    never read; the payload commit has landed by the time anyone could know, so what is refused is the
    description — the previous release's `release.json` stays, as after any failed second commit."""
    snapshot = tmp_path / "snap"
    _build(snapshot, "2026-10")
    old_description = b'{"clinvar": {"release": "2026-09"}}'
    hub = fake_hub(_REPO, {RELEASE_FILENAME: old_description})
    hub.while_sending = lambda: _build(snapshot, "2026-11")
    with pytest.raises(PlanChangedError, match="clinvar-chr1.parquet"):
        publish_reference_snapshot(snapshot, _REPO)
    assert hub.tree()[RELEASE_FILENAME] == old_description


def test_a_publish_states_the_hash_of_every_file_it_sent(tmp_path: Path, fake_hub) -> None:
    snapshot = tmp_path / "snap"
    files = _build(snapshot, "2026-10")
    fake_hub(_REPO)
    plan = publish_reference_snapshot(snapshot, _REPO)
    assert plan.sha256 == {name: "sha256:" + hashlib.sha256(data).hexdigest() for name, data in files.items()}


# ── the snapshot publish: the revision ────────────────────────────────────────────────────────────


def test_a_commit_landing_after_the_plan_read_refuses_the_publish(tmp_path: Path, fake_hub) -> None:
    """The orphan check and the retirement listing read the repo at one moment and the upload committed
    at another. Another publisher's commit in between was overwritten unseen; now the hub refuses."""
    snapshot = tmp_path / "snap"
    _build(snapshot, "2026-10")
    hub = fake_hub(_REPO)
    hub.before_write[0] = lambda: hub.foreign_commit({"citations/citations.parquet": b"PAR1 cites PAR1"})
    with pytest.raises(upload.RemoteMovedError, match="moved"):
        publish_reference_snapshot(snapshot, _REPO)
    assert set(hub.tree()) == {".gitattributes", "citations/citations.parquet"}


def test_a_commit_landing_between_payload_and_description_refuses_the_description(
    tmp_path: Path, fake_hub
) -> None:
    snapshot = tmp_path / "snap"
    _build(snapshot, "2026-10")
    hub = fake_hub(_REPO)
    hub.before_write[1] = lambda: hub.foreign_commit({"data/clinvar-chr1.parquet": b"PAR1 another PAR1"})
    with pytest.raises(upload.RemoteMovedError):
        publish_reference_snapshot(snapshot, _REPO)
    assert RELEASE_FILENAME not in hub.tree()


def test_every_read_a_snapshot_publish_makes_is_at_the_revision_it_commits_on(
    tmp_path: Path, fake_hub
) -> None:
    snapshot = tmp_path / "snap"
    _build(snapshot, "2026-10")
    hub = fake_hub(_REPO)
    read_at = hub.head
    publish_reference_snapshot(snapshot, _REPO)
    payload, description = hub.history[-2:]
    assert hub.parents[payload] == read_at
    assert hub.parents[description] == payload
    # One read of the head (the pin itself); every other read names a revision: the plan's, or the
    # payload commit's when the payload is checked on the hub; and each write's history walk starts at
    # the commit it made.
    assert hub.reads[0] == ("repo_info", None)
    assert {revision for method, revision in hub.reads[1:] if method != "list_repo_commits"} == {
        read_at,
        payload,
    }
    assert [revision for method, revision in hub.reads if method == "list_repo_commits"] == [
        payload,
        description,
    ]


def test_an_unchanged_payload_does_not_hide_a_commit_that_landed_first(tmp_path: Path, fake_hub) -> None:
    """The hub skips a write that changes nothing and answers with the current head, checking no
    precondition: a republish whose payload is byte-identical got another writer's head back as its
    own, and the description, pinned on it, went over a sidecar that writer had just added."""
    snapshot = tmp_path / "snap"
    r1 = _build(snapshot, "2026-10")
    hub = fake_hub(_REPO, {name: data for name, data in r1.items() if name != RELEASE_FILENAME})
    hub.before_write[0] = lambda: hub.foreign_commit({"citations/citations.parquet": b"PAR1 cites PAR1"})
    with pytest.raises(upload.RemoteMovedError, match="1 commit"):
        publish_reference_snapshot(snapshot, _REPO)
    assert RELEASE_FILENAME not in hub.tree()


def test_a_commit_between_the_uploaders_own_parts_withholds_the_description(tmp_path: Path, fake_hub) -> None:
    """The hub's multi-commit uploader pins its first part only, so a commit landing between two parts
    was built on silently, and the description went over it."""
    snapshot = tmp_path / "snap"
    _build(snapshot, "2026-10")
    theirs = b'{"theirs": true}'
    hub = fake_hub(_REPO)
    hub.between_parts = lambda: hub.foreign_commit({RELEASE_FILENAME: theirs})
    with pytest.raises(upload.RemoteMovedError, match="beside 2 of this write's own"):
        publish_reference_snapshot(snapshot, _REPO)
    assert hub.tree()[RELEASE_FILENAME] == theirs


# ── prune ─────────────────────────────────────────────────────────────────────────────────────────


def test_a_prune_refuses_when_the_repo_moved_after_its_plan(fake_hub) -> None:
    """The plan listed the repo and was shown to a person; the deletion happened later, by path, on
    whatever the repo had become. A republished file under a listed name was deleted unseen."""
    hub = fake_hub(_REPO, {"data/clinvar.parquet": b"PAR1 old PAR1", "data/clinvar-chr1.parquet": b"PAR1"})
    plan = plan_prune(_REPO, "clinvar-chr*.parquet")
    assert [c.path for c in plan.candidates] == ["data/clinvar.parquet"]
    hub.foreign_commit({"data/clinvar.parquet": b"PAR1 republished PAR1"})
    with pytest.raises(upload.RemoteMovedError):
        prune_repo(plan)
    assert hub.tree()["data/clinvar.parquet"] == b"PAR1 republished PAR1"


def test_a_prune_deletes_exactly_what_its_plan_listed_at_that_revision(fake_hub) -> None:
    files = {
        "data/x[1].parquet": b"PAR1 a PAR1",
        "data/x1.parquet": b"PAR1 b PAR1",
        "data/keep-1.parquet": b"P",
    }
    hub = fake_hub(_REPO, files)
    plan = plan_prune(_REPO, "keep-*.parquet")
    assert plan.revision == hub.head
    assert prune_repo(plan) == 2
    assert hub.parents[hub.head] == plan.revision
    assert set(hub.tree()) == {".gitattributes", "data/keep-1.parquet"}


def test_a_prune_plan_that_read_no_revision_deletes_nothing(fake_hub) -> None:
    hub = fake_hub(_REPO, {"data/old.parquet": b"PAR1"})
    plan = PrunePlan(repo_id=_REPO, candidates=[PruneCandidate(path="data/old.parquet", reason="t")])
    with pytest.raises(upload.RemoteMovedError, match="read no revision"):
        prune_repo(plan)
    assert "data/old.parquet" in hub.tree()


# ── the module publish ────────────────────────────────────────────────────────────────────────────


def _module(d: Path, version: str = "1.2.3") -> Path:
    d.mkdir(parents=True)
    for name in ("weights.parquet", "annotations.parquet", "studies.parquet"):
        (d / name).write_bytes(f"PAR1 {name} PAR1".encode())
    manifest = ModuleManifest(
        identity=Identity(name="test_module", version=version),
        display=Display(title="t", description="t", report_title="t"),
        artifact=Artifact(digest="sha256:" + "0" * 64),
    ).model_copy(
        update={"artifact": build_artifact(d, ["weights.parquet", "annotations.parquet", "studies.parquet"])}
    )
    write_manifest(manifest, d / "manifest.json")
    return d


def test_a_version_published_after_the_collision_check_is_not_overwritten(tmp_path: Path, fake_hub) -> None:
    """RM368's collision check read the versioned path, found nothing, and the commits followed. A
    second publisher landing that version in between was overwritten without `--force`."""
    module_dir = _module(tmp_path / "m")
    theirs = b'{"identity": {"name": "test_module", "version": "1.2.3"}, "theirs": true}'
    hub = fake_hub(_MODULE_REPO)
    hub.before_write[0] = lambda: hub.foreign_commit({"data/test_module/v1.2.3/manifest.json": theirs})
    with pytest.raises(upload.RemoteMovedError):
        upload_module(module_dir, "test_module")
    assert hub.tree()["data/test_module/v1.2.3/manifest.json"] == theirs


def test_a_refused_versioned_copy_says_the_flat_path_already_landed(tmp_path: Path, fake_hub) -> None:
    module_dir = _module(tmp_path / "m")
    hub = fake_hub(_MODULE_REPO)
    hub.before_write[1] = lambda: hub.foreign_commit({"README.md": b"someone else"})
    with pytest.raises(upload.RemoteMovedError, match="the flat path data/test_module/ at"):
        upload_module(module_dir, "test_module")
    assert "data/test_module/manifest.json" in hub.tree()
    assert "data/test_module/v1.2.3/manifest.json" not in hub.tree()


def test_every_read_a_module_publish_makes_is_at_the_revision_it_commits_on(tmp_path: Path, fake_hub) -> None:
    module_dir = _module(tmp_path / "m")
    hub = fake_hub(
        _MODULE_REPO, {"data/test_module/v1.2.3/manifest.json": (module_dir / "manifest.json").read_bytes()}
    )
    read_at = hub.head
    upload_module(module_dir, "test_module")
    flat, versioned = hub.history[-2:]
    assert (hub.parents[flat], hub.parents[versioned]) == (read_at, flat)
    assert hub.reads[0] == ("repo_info", None)
    assert {revision for method, revision in hub.reads[1:] if method != "list_repo_commits"} == {read_at}
    assert [revision for method, revision in hub.reads if method == "list_repo_commits"] == [flat, versioned]


# ── the guards ────────────────────────────────────────────────────────────────────────────────────

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_UPLOAD = Path(upload.__file__).resolve()

#: Every `HfApi` method that makes a commit, read off the library: the ones that take a precondition.
_HUB_WRITES = frozenset(
    name
    for name, function in inspect.getmembers(HfApi, inspect.isfunction)
    if "parent_commit" in inspect.signature(function).parameters
)
#: Every `HfApi` method that reads a repo at a revision, the writes aside, and the download function.
_HUB_READS = frozenset(
    name
    for name, function in inspect.getmembers(HfApi, inspect.isfunction)
    if "revision" in inspect.signature(function).parameters and name not in _HUB_WRITES
) | {"hf_hub_download"}
#: The one function that writes, and the one read that is not pinned because it is the pin.
_THE_WRITER = "_commit"
_THE_PIN = "_head"


def _calls_by_function(path: Path, names: frozenset[str]) -> list[tuple[str, ast.Call]]:
    """Every call to one of `names` in `path` (as `x.name(...)` or `name(...)`), with the enclosing
    top-level function's name."""
    found = []
    for top in ast.parse(path.read_text(encoding="utf-8")).body:
        owner = top.name if isinstance(top, ast.FunctionDef | ast.ClassDef) else "<module>"
        for node in ast.walk(top):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if name in names:
                found.append((owner, node))
    return found


def test_the_rosters_are_read_off_the_library() -> None:
    assert {"create_commit", "upload_folder", "delete_files"} <= _HUB_WRITES
    assert {"list_repo_files", "list_repo_tree", "file_exists", "repo_info"} <= _HUB_READS


def test_every_hub_write_goes_through_the_one_pinned_helper() -> None:
    """A hub write outside `_commit`, or one inside it without `parent_commit=`, is a commit on
    whatever the repo has become rather than on what the plan read."""
    calls = [
        (path, owner, call)
        for path in sorted(_PACKAGE.rglob("*.py"))
        for owner, call in _calls_by_function(path, _HUB_WRITES)
    ]
    assert calls, "the guard found no hub write at all"
    outside = [
        f"{path.name}:{call.lineno} in {owner}"
        for path, owner, call in calls
        if (path, owner) != (_UPLOAD, _THE_WRITER)
    ]
    assert outside == []
    unpinned = [call.lineno for _, _, call in calls if "parent_commit" not in {k.arg for k in call.keywords}]
    assert unpinned == []


def test_every_remote_read_in_the_publisher_names_its_revision() -> None:
    calls = _calls_by_function(_UPLOAD, _HUB_READS)
    assert calls, "the guard found no hub read at all"
    unnamed = [
        f"{owner}:{call.lineno}"
        for owner, call in calls
        if owner != _THE_PIN and "revision" not in {k.arg for k in call.keywords}
    ]
    assert unnamed == []
    assert [owner for owner, _ in calls if owner == _THE_PIN], "the head is read somewhere other than the pin"


def test_cache_prune_says_a_moved_repo_refused_rather_than_tracebacking(fake_hub, cli_text) -> None:
    """`cache prune --yes` called `prune_repo` outside any handler, so the refusal above would have
    ended the command in a traceback mid-loop."""
    hub = fake_hub(
        DEFAULT_CLINVAR_REPO_ID, {"data/clinvar.parquet": b"PAR1 old PAR1", "data/clinvar-chr1.parquet": b"P"}
    )
    hub.before_write[0] = lambda: hub.foreign_commit({"data/clinvar.parquet": b"PAR1 republished PAR1"})
    result = CliRunner().invoke(app, ["cache", "prune", "--only", "clinvar", "--yes"])
    assert result.exception is None, result.exception
    assert "PRUNE REFUSED" in cli_text(result)
    assert hub.tree()["data/clinvar.parquet"] == b"PAR1 republished PAR1"

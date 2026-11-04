"""Every builder writes `release.json` through `SnapshotRelease`, and every snapshot here reads (RM303).

Fourteen builders wrote `release.json` by hand at fifteen sites and the keys drifted: `rows` beside
`row_count`, `licence` beside `license`, and a ClinVar builder that wrote no `dataset`, which reached
`cache status` as a blank label. The model in `just_dna_format.snapshot` fixes the spellings; the
guard here is what keeps a sixteenth site from writing a dict by hand again (`@registry-completeness`).

**The guard's rule is about the name, not the dict.** `write_release(out_dir, release)` builds the
path itself, so a builder has no reason to spell `release.json` at all, as the constant or as the
literal, except to delete a stale one. A hand-built writer has to spell it. So the walk refuses every
spelling outside an import and an `.unlink`, and asserts the set of builders calling `write_release`
**equals** the set of builders, so a builder that stops writing a release is as visible as one that
writes it by hand.

The second half reads the snapshots actually provisioned on this machine, because the published ones
carry the old spellings and are the case the model's input side exists for. It skips where nothing is
provisioned.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import just_dna_enricher
import pytest
from just_dna_enricher.caches import LANES_BY_NAME, lane_status
from just_dna_enricher.cli import app
from just_dna_enricher.mitomap_miss_build import stale_parents
from just_dna_format.snapshot import (
    RELEASE_FILENAME,
    SnapshotRelease,
    clinvar_release_label,
    read_release,
    write_release,
)
from typer.testing import CliRunner

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_BUILDERS = sorted(_PACKAGE.glob("*_build.py"))
_WRITER = "write_release"


def _spellings_outside_an_unlink(tree: ast.AST) -> list[str]:
    """Every expression naming `release.json` that is not an import and not a file being deleted."""
    deleted: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "unlink":
            deleted.update(id(sub) for sub in ast.walk(node.func.value))
    found = []
    for node in ast.walk(tree):
        names_it = (isinstance(node, ast.Name) and node.id == "RELEASE_FILENAME") or (
            isinstance(node, ast.Constant) and node.value == RELEASE_FILENAME
        )
        if names_it and id(node) not in deleted:
            found.append(f"line {node.lineno}: {ast.unparse(node)}")
    return found


def _calls_the_writer(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == _WRITER)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == _WRITER)
        )
        for node in ast.walk(tree)
    )


def _tree(path: Path) -> ast.Module:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Docstrings are constants too, and prose may name the file freely.
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0] = ast.Pass()
    # Imports name it legitimately; a module-level import is how a builder used to get the constant.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            node.names = [alias for alias in node.names if alias.name != "RELEASE_FILENAME"]
    return tree


def test_the_walk_found_the_builders() -> None:
    """A glob that matches nothing passes every assertion below; the walk has to have found something."""
    assert len(_BUILDERS) >= 2, _BUILDERS


@pytest.mark.parametrize("builder", _BUILDERS, ids=lambda p: p.stem)
def test_no_builder_spells_the_release_path(builder: Path) -> None:
    found = _spellings_outside_an_unlink(_tree(builder))
    assert not found, (
        f"{builder.name} names release.json outside an import or an unlink: {found}. Write it with "
        f"`just_dna_format.snapshot.write_release(out_dir, SnapshotRelease(...))`, never by hand."
    )


def test_every_builder_writes_through_the_model() -> None:
    """An equality: the builders that call `write_release` are exactly the builders."""
    writing = {path.stem for path in _BUILDERS if _calls_the_writer(_tree(path))}
    assert writing == {path.stem for path in _BUILDERS}


@pytest.mark.parametrize(
    "planted",
    [
        'path = out_dir / RELEASE_FILENAME\natomic_write_text(path, json.dumps({"dataset": d}) + "\\n")\n',
        '(out_dir / "release.json").write_text(json.dumps(release))\n',
        'with open(out_dir / RELEASE_FILENAME, "w") as fh:\n    json.dump(release, fh)\n',
    ],
)
def test_the_guard_refuses_a_hand_built_release(planted: str) -> None:
    """The guard is a detector, so it is shown detecting: each of these is how a builder used to write."""
    assert _spellings_outside_an_unlink(ast.parse(planted))
    assert not _calls_the_writer(ast.parse(planted))


def test_the_guard_allows_deleting_a_stale_release() -> None:
    allowed = "(out_dir / RELEASE_FILENAME).unlink(missing_ok=True)\nwrite_release(out_dir, release)\n"
    assert _spellings_outside_an_unlink(ast.parse(allowed)) == []
    assert _calls_the_writer(ast.parse(allowed))


# ── the snapshots on this machine ───────────────────────────────────────────────────────────────


def _provisioned() -> list[tuple[str, Path]]:
    return [
        (status.lane.name, status.path)
        for status in lane_status()
        if status.path is not None and status.path.is_dir() and (status.path / RELEASE_FILENAME).is_file()
    ]


def test_every_provisioned_snapshot_reads_into_the_model() -> None:
    """The published spellings are the input side's whole case; read what this machine actually holds.

    Expected values come from the raw file at run time: every raw key is either a field the model
    typed, a key it carried in extra, or one of the old spellings it maps; and a `dataset` the file
    states is the label the model reads.
    """
    provisioned = _provisioned()
    if not provisioned:
        pytest.skip("no snapshot with a release.json is provisioned on this machine")
    old_spellings = {"rows", "licence"}
    for name, path in provisioned:
        raw = json.loads((path / RELEASE_FILENAME).read_text(encoding="utf-8"))
        release = read_release(path)
        assert release is not None, name
        carried = set(release.model_fields_set) | set(release.model_extra or {})
        assert set(raw) - old_spellings <= carried, (name, set(raw) - carried)
        assert not (old_spellings & set(release.model_extra or {})), name
        if "dataset" in raw:
            assert release.dataset == raw["dataset"], name
        if name == "clinvar" and "dataset" not in raw:
            assert release.dataset == clinvar_release_label(
                raw.get("clinvar_file_date"), raw.get("source_sha256")
            )
            assert release.dataset is not None
        # A rewrite through the model carries the canonical spellings and loses no key.
        rewritten = json.loads(release.to_json())
        assert not (old_spellings & set(rewritten)), name
        assert SnapshotRelease.model_validate(rewritten) == release, name


def test_an_old_clinvar_snapshot_still_prints_its_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The per-lane reader is gone; a ClinVar snapshot built before RM303 must still name its release."""
    directory = tmp_path / "clinvar"
    (directory / "data").mkdir(parents=True)
    (directory / "data" / "chr1.parquet").write_bytes(b"PAR1PAR1")
    (directory / RELEASE_FILENAME).write_text(
        json.dumps({"clinvar_file_date": "2026-08-29", "record_count": 4460499, "source_sha256": "ab"}),
        encoding="utf-8",
    )
    monkeypatch.setenv(LANES_BY_NAME["clinvar"].env_var, str(directory))
    assert LANES_BY_NAME["clinvar"].release_label(directory) == "clinvar_2026-08-29"
    result = CliRunner().invoke(app, ["cache", "status"])
    assert result.exit_code == 0, result.output
    line = next(ln for ln in result.output.splitlines() if ln.strip().startswith("clinvar "))
    assert "present" in line and "clinvar_2026-08-29" in line


def test_a_pin_recorded_in_an_old_spelling_is_not_a_parent_that_moved(tmp_path: Path) -> None:
    """`mitomap_miss` pins its parents' keys; a parent rebuilt through the model spells them canonically.

    A child built before RM303 recorded MITOMAP's `rows` and no ClinVar `dataset`. Its parents,
    rebuilt since, say `row_counts` and carry `dataset`. Read on one side only, every such child
    would report both parents moved. Both sides go through the model, so only a real move shows.
    """
    mitomap, clinvar, child = tmp_path / "mitomap", tmp_path / "clinvar", tmp_path / "miss"
    for directory in (mitomap, clinvar, child):
        directory.mkdir()
    write_release(mitomap, SnapshotRelease(dataset="mitomap_2026-08-21", source_sha256="16f0", rows={"a": 2}))
    write_release(
        clinvar,
        SnapshotRelease(
            dataset=clinvar_release_label("2026-06-27", "20f5"),
            clinvar_file_date="2026-06-27",
            source_sha256="20f5",
            record_count=4431781,
        ),
    )
    old_pins = {
        "mitomap": {
            "dataset": "mitomap_2026-08-21",
            "source_sha256": "16f0",
            "rows": {"a": 2},
            "path": str(mitomap),
        },
        "clinvar": {
            "clinvar_file_date": "2026-06-27",
            "source_sha256": "20f5",
            "record_count": 4431781,
            "path": str(clinvar),
        },
    }
    (child / RELEASE_FILENAME).write_text(json.dumps({"parents": old_pins}), encoding="utf-8")
    assert stale_parents(child) == {}

    write_release(
        mitomap, SnapshotRelease(dataset="mitomap_2026-11-01", source_sha256="99aa", row_counts={"a": 3})
    )
    assert set(stale_parents(child)) == {"mitomap"}

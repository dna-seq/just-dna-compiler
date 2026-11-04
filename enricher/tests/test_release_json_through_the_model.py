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

**Since RM369 the route is the write handle, never `write_release` itself.** A builder used to swap
its payload in and then write the record, so a crash between the two left new bytes described by the
old `release.json`. `begin_snapshot_write(out_dir)` withdraws the record and returns the only thing
that can write the next one, so a builder that describes its snapshot has necessarily withdrawn the
old description first. The walk asserts that no builder names `write_release` and that the builders
opening a write are exactly the builders; `test_a_build_withdraws_its_description_first.py` runs them.

The reader half walks every source module: a key read off a release in logic is a typed field
(RM369), because `SnapshotRelease` keeps every other key in `extra`, where a typo or a wrong type
passes silently.

The last half reads the snapshots actually provisioned on this machine, because the published ones
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
from just_dna_enricher.mitomap_miss_build import PIN_KEYS, stale_parents
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
#: The two ways a builder may open a write: the whole record, or one block of it (ClinVar's citations).
_OPENERS = frozenset({"begin_snapshot_write", "begin_block_write"})
_SOURCE_ROOTS = tuple(
    Path(__file__).resolve().parents[2] / tier / "src" for tier in ("schema", "compiler", "enricher")
)


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


def _calls(tree: ast.AST, names: frozenset[str] | set[str]) -> bool:
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in names)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in names)
        )
        for node in ast.walk(tree)
    )


def _names_the_writer(tree: ast.AST) -> list[str]:
    """Every mention of `write_release` outside an import: a call, a reference, an alias."""
    return [
        f"line {node.lineno}: {ast.unparse(node)}"
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == _WRITER)
        or (isinstance(node, ast.Attribute) and node.attr == _WRITER)
    ]


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


def test_every_builder_opens_a_write_and_none_writes_the_record_itself() -> None:
    """Two equalities (RM369): the builders opening a write are the builders, and none names the writer.

    `write_release` called by a builder is a description written without the old one withdrawn, the
    shape every builder had before RM369. The handle `begin_snapshot_write` returns is the only route.
    """
    opening = {path.stem for path in _BUILDERS if _calls(_tree(path), _OPENERS)}
    assert opening == {path.stem for path in _BUILDERS}
    naming = {path.stem: found for path in _BUILDERS if (found := _names_the_writer(_tree(path)))}
    assert naming == {}, (
        f"{sorted(naming)} name `write_release`: {naming}. Open the write with "
        f"`begin_snapshot_write(out_dir)` right before the payload moves and describe it with its "
        f"`commit(release)`, so the old record is withdrawn before the bytes it describes change."
    )


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
    assert not _calls(ast.parse(planted), _OPENERS)


def test_the_guard_allows_deleting_a_stale_release() -> None:
    allowed = "(out_dir / RELEASE_FILENAME).unlink(missing_ok=True)\n"
    assert _spellings_outside_an_unlink(ast.parse(allowed)) == []


@pytest.mark.parametrize(
    "planted",
    [
        "write_release(out_dir, SnapshotRelease(dataset=d))\n",
        "snapshot.write_release(out_dir, release)\n",
        "describe = write_release\ndescribe(out_dir, release)\n",
    ],
)
def test_the_guard_refuses_a_builder_writing_the_record_itself(planted: str) -> None:
    """Every builder wrote this way before RM369: payload first, then `write_release`, no withdrawal."""
    assert _names_the_writer(ast.parse(planted))


def test_the_guard_allows_the_write_handle() -> None:
    allowed = "snapshot = begin_snapshot_write(out_dir)\nframe.write_parquet(p)\nsnapshot.commit(release)\n"
    assert _names_the_writer(ast.parse(allowed)) == []
    assert _calls(ast.parse(allowed), _OPENERS)


# ── the readers: a key acted on is a typed field (RM369) ────────────────────────────────────────

#: Calls whose result is a `SnapshotRelease`.
_RELEASE_CALLS = frozenset({"read_release", "read_miss_release", "_release_payload", "SnapshotRelease"})
#: Model methods a reader may call; any other attribute must be a typed field.
_MODEL_SURFACE = frozenset({"model_dump", "model_fields_set", "to_json", "model_copy", "model_dump_json"})
_TYPED = frozenset(SnapshotRelease.model_fields)


def _is_release_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _RELEASE_CALLS
    # `SnapshotRelease.model_validate(...)`, `snapshot.read_release(...)`.
    return isinstance(func, ast.Attribute) and (
        func.attr in _RELEASE_CALLS
        or (isinstance(func.value, ast.Name) and func.value.id == "SnapshotRelease")
    )


def _yields(node: ast.AST | None, leaf) -> bool:
    """Whether every branch of `node` is a `leaf` or `None`, and at least one is a `leaf`."""
    if node is None:
        return False
    if isinstance(node, ast.BoolOp):
        return any(_yields(v, leaf) for v in node.values) and all(
            _yields(v, leaf) or _blank(v) for v in node.values
        )
    if isinstance(node, ast.IfExp):
        return (_yields(node.body, leaf) or _yields(node.orelse, leaf)) and all(
            _yields(v, leaf) or _blank(v) for v in (node.body, node.orelse)
        )
    return leaf(node)


def _blank(node: ast.AST) -> bool:
    """`None`, `{}` or an empty `SnapshotRelease()`: the fallbacks a reader writes beside the read."""
    return (isinstance(node, ast.Constant) and node.value is None) or (
        isinstance(node, ast.Dict) and not node.keys
    )


def _annotated_release(annotation: ast.AST | None) -> bool:
    return annotation is not None and "SnapshotRelease" in ast.unparse(annotation)


def _key(node: ast.AST) -> str:
    return f"{node.value!r}" if isinstance(node, ast.Constant) else "<computed>"


def _untyped_reads(tree: ast.AST) -> list[str]:
    """Every read of a release key that does not go through a typed field.

    Tracks, per module, the names bound to a release (a call to a reader or the model, a parameter or
    attribute annotated `SnapshotRelease`) and the names bound to its `model_dump()`. On a release it
    refuses `getattr`/`hasattr`, `.get`, subscripts, `model_extra` and any attribute that is neither a
    typed field nor the model's own surface; on a dump it refuses a key that is not a typed field, and
    a computed key, which no walk can check. Names are tracked per module, not per scope, so the walk
    errs toward refusing: a plain dict sharing a name with a release elsewhere in the module is read
    as one.
    """
    models: set[str] = set()
    dumps: set[str] = set()
    attributes: set[str] = set()
    fields = {
        id(item)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.AnnAssign)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and _annotated_release(node.annotation):
            models.add(node.arg)
        if isinstance(node, ast.AnnAssign) and id(node) in fields and _annotated_release(node.annotation):
            # A class field (a dataclass's `release: SnapshotRelease`) is read as `self.release`.
            if isinstance(node.target, ast.Name):
                attributes.add(node.target.id)
        elif isinstance(node, ast.AnnAssign) and _annotated_release(node.annotation):
            if isinstance(node.target, ast.Name):
                models.add(node.target.id)
            elif isinstance(node.target, ast.Attribute):
                attributes.add(node.target.attr)
    # Two passes: a dump is of a name the first pass found.
    for _ in range(2):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign | ast.AnnAssign) or node.value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if _yields(node.value, _is_release_call):
                models.update(names)
                attributes.update(t.attr for t in targets if isinstance(t, ast.Attribute))
            elif _yields(node.value, lambda v: _is_dump(v, models, attributes)):
                dumps.update(names)

    def is_model(node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in models) or (
            isinstance(node, ast.Attribute)
            and node.attr in attributes
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        )

    found: list[str] = []
    for node in ast.walk(tree):
        where = f"line {getattr(node, 'lineno', '?')}: {ast.unparse(node)}"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr"}
        ):
            if node.args and is_model(node.args[0]):
                found.append(where)
        elif isinstance(node, ast.Attribute) and is_model(node.value):
            if node.attr not in _TYPED and node.attr not in _MODEL_SURFACE:
                found.append(where)
        elif isinstance(node, ast.Subscript) and is_model(node.value):
            found.append(where)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in dumps:
            if _key(node.slice) not in {repr(k) for k in _TYPED}:
                found.append(where)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in dumps
            and (not node.args or _key(node.args[0]) not in {repr(k) for k in _TYPED})
        ):
            found.append(where)
    return found


def _is_dump(node: ast.AST, models: set[str], attributes: set[str]) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "model_dump"
        and (
            (isinstance(node.func.value, ast.Name) and node.func.value.id in models)
            or (isinstance(node.func.value, ast.Attribute) and node.func.value.attr in attributes)
        )
    )


def _source_modules() -> list[Path]:
    modules = sorted(path for root in _SOURCE_ROOTS for path in root.rglob("*.py"))
    # The model's own module defines the fields; every other module reads them.
    return [path for path in modules if path.name != "snapshot.py"]


def test_the_reader_walk_found_the_readers() -> None:
    """The walk is only as good as its bindings: it must see the readers it exists for."""
    readers = [path for path in _source_modules() if "read_release(" in path.read_text(encoding="utf-8")]
    assert {path.stem for path in readers} >= {"opentargets", "clinvar_gkm", "acmg", "clinvar"}


@pytest.mark.parametrize("module", _source_modules(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_no_reader_acts_on_an_untyped_release_key(module: Path) -> None:
    found = _untyped_reads(ast.parse(module.read_text(encoding="utf-8")))
    assert not found, (
        f"{module.name} reads a release key that is not a typed `SnapshotRelease` field: {found}. "
        f"Type the key on the model (an optional field, `None` when unstated) and read the attribute."
    )


@pytest.mark.parametrize(
    "planted",
    [
        'release = read_release(path) or SnapshotRelease()\nv = getattr(release, "vrs_version", None)\n',
        "record = read_release(path)\nrelease = record.model_dump() if record is not None else {}\n"
        'total = release.get("parts_totl") or {}\n',
        "release = read_release(path)\nextra = release.model_extra\n",
        "release = read_release(path)\nv = release.parts_totl\n",
        "def f(release: SnapshotRelease) -> None:\n    stated = release.model_dump()\n    v = stated[key]\n",
        "class W:\n    release: SnapshotRelease\n    def v(self):\n        return getattr(self.release, 'x', None)\n",
    ],
)
def test_the_reader_guard_refuses_an_untyped_read(planted: str) -> None:
    """The first two are the shapes 0.8 shipped in `clinvar_gkm.py` and `opentargets.py` (the second
    read `parts_total`, typed since; a misspelt key is the same shape)."""
    assert _untyped_reads(ast.parse(planted))


def test_the_reader_guard_allows_typed_reads() -> None:
    allowed = (
        "record = read_release(path)\n"
        "release = record.model_dump() if record is not None else {}\n"
        'label = release.get("dataset")\n'
        "other = read_release(path) or SnapshotRelease()\n"
        "total = other.parts_total or {}\n"
        '"dataset" in other.model_fields_set\n'
    )
    assert _untyped_reads(ast.parse(allowed)) == []


def test_a_parent_pin_is_typed_keys_only() -> None:
    """`mitomap_miss` compares its parents on `PIN_KEYS`; a pin on an extra key would compare untyped."""
    assert set(PIN_KEYS) <= _TYPED


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

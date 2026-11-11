"""Every authored column says which release it appeared in (RM146).

A module authored on 0.6.6 was sent to a registry deployment running 0.6.1, which runs `validate_spec`
server-side and reports its findings verbatim. It said:

    studies.csv line 2 [curator]: Extra inputs are not permitted

`StudyRow.curator` is ours, added in 0.6.5. A genuine typo produces the byte-identical shape —
`[curatr]` — and the two want **opposite actions** from an author: upgrade the reader, or fix the cell.
The finding is pydantic's under `extra="forbid"`, so it cannot be reworded into carrying the
distinction: the information was not in the model at all.

**Declared on the field rather than in a roster**, because a hand-kept list beside a model is a second
statement of one fact and it is the copy that goes stale (`@fieldnames-from-model`). The guard below is
therefore the load-bearing half: an **equality over the walked registry**, so the next column added
cannot omit one. A floor or a count is satisfied by exactly the state that produced the report.

**The backfill was measured, not recalled** — parsed out of each release tag's own sources, per
`(model, field)`. `curator` is why that matters and is asserted below.
"""

import ast
import importlib
import inspect
import pkgutil
import re
import subprocess
import tomllib
import typing
from pathlib import Path

import just_dna_format
import pytest
from just_dna_format.base import AuthoredModel, field_first_seen, since
from just_dna_format.manifest import ModuleManifest, ProvenanceDoc, VerificationDoc
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.release_records import ReleaseRecord
from just_dna_format.snapshot import SnapshotRelease
from just_dna_format.spec import StudyRow, VariantRow
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parents[2]

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

#: Releases that exist, plus the uncut one this work lands in. A field may not claim a version that
#: was never published — the commonest way a hand-edited marker goes wrong is a typo'd number, and
#: nothing else in the model would catch it.
_RELEASES: frozenset[str] = frozenset(
    {
        "0.2.0",
        "0.3.0",
        "0.4.0",
        "0.5.0",
        "0.5.1",
        "0.5.2",
        "0.5.3",
        "0.5.4",
        "0.6.0",
        "0.6.1",
        "0.6.2",
        "0.6.3",
        "0.6.4",
        "0.6.5",
        "0.6.6",
        "0.7.0",
        # The 0.7 patch line, tagged on `main` and merged into `0.8`. Missing here until RM365, which
        # is what a hand-kept list does; `test_the_release_list_is_the_tags_and_the_uncut_one` now
        # holds it equal to the tags.
        "0.7.1",
        "0.7.2",
        "0.7.3",
        # Uncut, on the `0.8` branch: the release the PT1 round lands in (RM258 is the first field).
        "0.8.0",
        # The 0.8 patch line, tagged on `main`. 0.8.1 moved the enricher only, but the tag is the
        # release, and the guard below holds this list equal to the tags.
        "0.8.1",
        "0.8.2",
        "0.8.3",
        # Uncut until its tag: the release `_UNCUT` names while the 0.8.4 cut is on `main`.
        "0.8.4",
    }
)

#: The release a field in no tag lands in: the format package's own version, read from its
#: `pyproject.toml` (where versions live) rather than restated or taken from an installed distribution's
#: metadata, which lags a bump until the next sync. The cut that bumps it moves this answer with it.
_UNCUT = tomllib.loads((_ROOT / "schema" / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]


# ── the guard ───────────────────────────────────────────────────────────────────────────────────


def test_every_field_of_every_authored_model_declares_a_first_seen() -> None:
    """An **equality over the walked set**, which is the only shape that catches the next omission.

    `>= 400 fields` or `len(...) > 0` would both pass on the tree that shipped the report this item is
    about. The set difference names the offenders, so a failure says which field to fix rather than
    that some field is wrong (`@registry-completeness`).
    """
    missing: list[str] = []
    for model in _ALL_MODELS.values():
        declared = set(field_first_seen(model))
        missing.extend(f"{model.__name__}.{f}" for f in set(model.model_fields) - declared)

    assert missing == [], f"fields with no first_seen: {sorted(missing)}"


#: The documents the compiler, the enricher and the release machinery WRITE. A model reachable from
#: one of these through its fields' annotations is part of a written record, not an authored table,
#: so it sits outside `_ALL_MODELS` by construction — unless an author also writes it (the `module:`
#: block's `Display`/`Contribution`/`Weighting`/`GenePanelSpec`, and `VerificationRecord`), in which
#: case the registry holds it and the reachability does not matter.
_WRITTEN_DOCUMENTS: tuple[type[BaseModel], ...] = (
    ModuleManifest,
    VerificationDoc,
    ProvenanceDoc,
    SnapshotRelease,
    ReleaseRecord,
)

#: Models defined in the package that are neither a table nor part of a written document, each with
#: why. Each is a base: it carries no row of its own and every concrete model built on it is
#: walked in its own right.
_ABSTRACT_BASES: dict[str, str] = {
    "AuthoredModel": "the base every authored row inherits; it declares no field",
    "CitationPair": "the `pmid`/`doi` mixin (RM336); every model with `pmid` inherits it and is walked",
    "PairedFields": "the `_PAIRED_FIELDS` validator mixin (RM366); it declares no field, and every model "
    "inheriting it is walked",
}


def _every_model_the_package_defines() -> set[type[BaseModel]]:
    """Every pydantic model whose home module is in `just_dna_format`, found by importing the package
    rather than by reading any registry — the independent side of the equality below."""
    found: set[type[BaseModel]] = set()
    for info in pkgutil.walk_packages(just_dna_format.__path__, "just_dna_format."):
        module = importlib.import_module(info.name)
        found.update(
            obj
            for obj in vars(module).values()
            if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == module.__name__
        )
    return found


def _models_in(annotation: object) -> set[type[BaseModel]]:
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return {annotation}
    return {model for arg in typing.get_args(annotation) for model in _models_in(arg)}


def _reachable(roots: tuple[type[BaseModel], ...]) -> set[type[BaseModel]]:
    seen: set[type[BaseModel]] = set()
    pending = list(roots)
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for field in model.model_fields.values():
            pending.extend(_models_in(field.annotation))
    return seen


def test_the_registry_really_covers_the_authored_surface() -> None:
    """The guard above is only as complete as the registry it walks, so the registry is checked too.

    `GeneMetricsRow` sat outside `_ALL_MODELS` once and its unenforced vocabulary went unnoticed for
    exactly that reason (RM96). A guard over an incomplete registry reports a clean bill about the
    models it happens to know.

    **An equality, since RM365.** This asserted `len(_ALL_MODELS) >= 31` and `>= 414` fields — floors,
    which a new row model left out of the registry satisfies forever, and which the registry had
    already outgrown by seven models and a hundred fields. Now every model the package defines is
    accounted for exactly once: in the registry, inside a document the tooling writes, or a named
    abstract base.
    """
    defined = _every_model_the_package_defines()
    registry = set(_ALL_MODELS.values())
    written = _reachable(_WRITTEN_DOCUMENTS)
    bases = {model for model in defined if model.__name__ in _ABSTRACT_BASES}
    assert {model.__name__ for model in bases} == set(_ABSTRACT_BASES), "a named base no longer exists"
    unaccounted = defined - registry - written - bases
    assert not unaccounted, (
        f"models in neither `_ALL_MODELS`, a written document, nor the named bases: "
        f"{sorted(m.__name__ for m in unaccounted)} — add a table model to the registry"
    )
    assert registry <= defined, "the registry holds a model the package does not define"
    # An authored row inherits `AuthoredModel`, so being reachable from a written document is no
    # exemption for one: a new row model the manifest also embeds must still be registered.
    authored = {model for model in defined if issubclass(model, AuthoredModel)} - bases
    assert authored <= registry, sorted(m.__name__ for m in authored - registry)
    assert not (bases & (registry | written)), "a named base is also a table or a record"


# ── the measurement: each declaration against the release tags (RM365) ──────────────────────────


def _git(*args: str) -> str | None:
    """`git <args>` at the repository root, or `None` where git cannot answer (or is not installed)."""
    try:
        done = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return done.stdout if done.returncode == 0 else None


def _release_tags() -> list[str]:
    """`vX.Y.Z` tags in SemVer order — empty where this checkout cannot be measured: no git, no tags,
    or a shallow clone (CI's default), whose tags, if any, are a partial history that would measure an
    old field as new."""
    if (_git("rev-parse", "--is-shallow-repository") or "").strip() != "false":
        return []
    listing = _git("tag", "--list", "v*") or ""
    tags = [tag for tag in listing.split() if _SEMVER.match(tag[1:])]
    return sorted(tags, key=lambda tag: tuple(int(part) for part in tag[1:].split(".")))


def _fields_by_class_at(tag: str) -> dict[str, set[str]]:
    """`{class name: field names}` for every class in the format package as `tag` has it, read from
    the tag's own sources. A field is an annotated class attribute that is not private, not
    `model_config` and not a `ClassVar`; inherited fields come from bases defined at the same tag,
    which is how `CitationPair` gives `doi` to every model carrying `pmid`."""
    listing = _git("ls-tree", "-r", "--name-only", tag, "--", "schema/src/just_dna_format/") or ""
    classes: dict[str, tuple[list[str], set[str]]] = {}
    for path in listing.split():
        if not path.endswith(".py"):
            continue
        for node in ast.walk(ast.parse(_git("show", f"{tag}:{path}") or "")):
            if not isinstance(node, ast.ClassDef):
                continue
            own = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and not statement.target.id.startswith("_")
                and statement.target.id != "model_config"
                and "ClassVar" not in ast.unparse(statement.annotation)
            }
            bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
            classes[node.name] = (bases, own)

    def fields(name: str, seen: frozenset[str]) -> set[str]:
        if name not in classes or name in seen:
            return set()
        bases, own = classes[name]
        return own.union(*(fields(base, seen | {name}) for base in bases))

    return {name: fields(name, frozenset()) for name in classes}


def test_the_release_list_is_the_tags_and_the_uncut_one() -> None:
    """`_RELEASES` is a list, so it is held equal to what it lists: it was three patch tags short."""
    tags = _release_tags()
    if not tags:
        pytest.skip("no full history with release tags here (shallow clone or no git); nothing to measure")
    assert _RELEASES == {tag[1:] for tag in tags} | {_UNCUT}


def test_every_field_declares_the_first_release_whose_model_carries_it() -> None:
    """**The measurement the module docstring says the backfill was, as a test (RM365).** Each
    `since()` must equal the first release tag whose model has that field, and a field no tag has
    must declare the uncut release. Nothing else checked a declaration's *value* — a typo'd version
    was caught, a plausible wrong one was not — so `ResolutionRow.vrs_spec`'s `0.5.0` could be
    disputed by two builders' prose and settled by nobody. It measures `0.5.0`, which is right: the
    "0.8" in that dispute is the parquet that began carrying the column (RM270), not the column.

    The same walk enforces Principle 3 from the other side: a field some release published on a model
    that still exists under its name, and that the model no longer has, is a removal, which is
    major-only. A model removed or renamed outright is outside this walk — the tags hold no registry to
    say which of their classes were authored ones.
    """
    tags = _release_tags()
    if not tags:
        pytest.skip("no full history with release tags here (shallow clone or no git); nothing to measure")
    first: dict[tuple[str, str], str] = {}
    for tag in tags:
        at_tag = _fields_by_class_at(tag)
        for model in _ALL_MODELS.values():
            for field in at_tag.get(model.__name__, set()):
                first.setdefault((model.__name__, field), tag[1:])

    wrong = sorted(
        f"{model.__name__}.{field}: declares {declared!r}, measured {first.get((model.__name__, field), _UNCUT)!r}"
        for model in _ALL_MODELS.values()
        for field, declared in field_first_seen(model).items()
        if declared != first.get((model.__name__, field), _UNCUT)
    )
    assert wrong == [], f"first-seen declarations the release tags contradict: {wrong}"

    current = {(model.__name__, field) for model in _ALL_MODELS.values() for field in model.model_fields}
    removed = sorted(
        f"{model}.{field} (since {release})"
        for (model, field), release in first.items()
        if (model, field) not in current
    )
    assert removed == [], f"fields a release published that the model no longer has: {removed}"


@pytest.mark.parametrize("label", sorted(_ALL_MODELS))
def test_every_declared_version_is_a_release_that_exists(label: str) -> None:
    """A typo'd version is the one error the model itself cannot catch, so it is caught here."""
    for field, version in field_first_seen(_ALL_MODELS[label]).items():
        assert _SEMVER.match(version), f"{label}.{field} = {version!r} is not a SemVer"
        assert version in _RELEASES, f"{label}.{field} claims {version!r}, which was never published"


# ── the worked example, which is why the answer is per (model, field) ───────────────────────────


def test_curator_answers_differently_on_the_two_models_that_carry_it() -> None:
    """**The case that decides the shape.** `curator` is on `VariantRow` from the 0.2 line and gains
    its `StudyRow` twin only in 0.6.5, so a roster keyed by *column name* would give one answer for
    two facts — and the wrong one for the module in the report.
    """
    assert field_first_seen(VariantRow)["curator"] == "0.2.0"
    assert field_first_seen(StudyRow)["curator"] == "0.6.5"


def test_a_field_added_in_this_release_says_so() -> None:
    """The uncut release is a legal answer: a column that exists in no tag ships in 0.7.0."""
    from just_dna_format.pgx import PharmVariantRow

    assert field_first_seen(PharmVariantRow)["pmid"] == "0.7.0"


# ── the marker's own contract ───────────────────────────────────────────────────────────────────


def test_the_marker_composes_with_the_vocabulary_one() -> None:
    """Both ride in one `json_schema_extra` dict, so a field may carry either or both.

    Asserted over the real models rather than a toy: a field that is both vocabulary-bound and
    versioned must answer both questions, and an implementation that replaced the dict rather than
    merging into it would silently drop the older marker.
    """
    from just_dna_format.base import field_vocabularies

    both = [
        (m.__name__, f)
        for m in _ALL_MODELS.values()
        for f in set(field_vocabularies(m)) & set(field_first_seen(m))
    ]
    assert both, "no field carries both markers, so this test is not measuring anything"
    for label, field in both:
        model = next(m for m in _ALL_MODELS.values() if m.__name__ == label)
        assert field_vocabularies(model)[field]["options"]
        assert field_first_seen(model)[field] in _RELEASES


def test_the_reader_returns_nothing_for_a_model_that_declares_nothing() -> None:
    """Absence is an empty map, never a guess. A consumer asking about an unmarked model gets `{}`
    and can say *this reader cannot tell you*, rather than being handed a fabricated version."""
    from pydantic import BaseModel

    class Bare(BaseModel):
        x: str | None = None

    assert field_first_seen(Bare) == {}


def test_the_marker_is_a_plain_dict_a_consumer_can_read_offline() -> None:
    """The point of the ask: any tool rendering our findings answers *when did this column appear*
    without importing our validators or parsing `model_fields` itself."""
    assert since("0.6.5") == {"first_seen": "0.6.5"}

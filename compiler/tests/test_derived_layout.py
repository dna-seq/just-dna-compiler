"""A spec may keep its machine-written sidecars under `derived/`, and compile where it sits (RM49).

Nothing in a flat listing says which files a human wrote and which `just-dna-enricher` produced. A
registry gave its publishers a `derived/` tree, then found a downloaded module does not recompile
where it lands, so the layout stays transport-only — flatten on upload, re-split on download. They
asked for a *tolerated* input location, not a required one, and that is what this is.

Three properties hold it together, and each has a test below:

* the split tree compiles to **exactly** the flat tree's identity, so the layout is presentation;
* two copies of one table is an **error naming both**, never a merge — these tables are fact-hashed
  and hand-editable, so two copies are two claims;
* the near-miss guard follows into `derived/`, so tolerating the layout does not re-open the hole that
  guard was written to close.

Only the machine-written tables move. `variants.csv` has one legal home, and the asymmetry is the
point: two legal homes for an authored table means a module can carry two and the ignored copy is
invisible.
"""

import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.layout import (
    DERIVED_SUBDIR,
    SidecarCollision,
    resolve_sidecar,
    sidecar_write_path,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
#: Exactly what may move — `resolution.csv` plus the fact sidecars. Named here rather than imported
#: from the compiler's private tuple so the test states the contract instead of echoing it.
_MOVABLE = ("resolution.csv", "frequencies.csv", "gene_metrics.csv", "literature.csv", "sources.csv")


def _flat(tmp_path: Path, name: str = "flat") -> Path:
    """A real module with a resolution table, copied so a test may rearrange it."""
    for candidate in sorted(_EXAMPLES.iterdir()):
        if (candidate / "resolution.csv").is_file() and (candidate / "variants.csv").is_file():
            spec_dir = tmp_path / name
            shutil.copytree(candidate, spec_dir)
            return spec_dir
    pytest.skip("no reference example carries both variants.csv and resolution.csv")


def _split(spec_dir: Path) -> Path:
    """Move every movable sidecar into `derived/`, leaving the authored tables where they are."""
    derived = spec_dir / DERIVED_SUBDIR
    derived.mkdir(exist_ok=True)
    moved = 0
    for name in _MOVABLE:
        source = spec_dir / name
        if source.is_file():
            source.rename(derived / name)
            moved += 1
    assert moved, "the fixture must actually have something to move"
    return spec_dir


def _manifest(spec_dir: Path, out: Path) -> dict:
    result = compile_module(spec_dir, out, resolve_with_ensembl=True)
    assert result.success, result.errors
    return json.loads((out / "manifest.json").read_text())


def test_the_split_tree_compiles_to_the_same_identity(tmp_path: Path) -> None:
    """The layout is presentation, and this is the assertion that makes that true rather than claimed.

    Every signature, not just the digest: `content_signature` is over authored rows and
    `resolution_signature` over the injected facts, so a layout that moved either would mean the
    location had leaked into identity.
    """
    flat = _manifest(_flat(tmp_path, "flat"), tmp_path / "out_flat")
    split = _manifest(_split(_flat(tmp_path, "split")), tmp_path / "out_split")

    assert flat["artifact"]["digest"] == split["artifact"]["digest"]
    assert flat["content_signature"] == split["content_signature"]
    assert flat["compilation"]["resolution_signature"] == split["compilation"]["resolution_signature"]
    assert flat["compilation"]["fully_resolved"] == split["compilation"]["fully_resolved"]


def test_a_split_module_resolves_its_variants_at_all(tmp_path: Path) -> None:
    """Guard the premise: identical digests would also follow from both compiles ignoring the table.

    Without this the test above passes just as happily on a compiler that never found `derived/` —
    which is the exact bug being fixed, and it would look like a success.
    """
    split = _manifest(_split(_flat(tmp_path, "split")), tmp_path / "out")
    assert split["compilation"]["resolution_signature"] is not None
    assert split["compilation"]["resolution_sources"]


def test_the_manifest_records_where_the_file_actually_was(tmp_path: Path) -> None:
    """`manifest.derived` is what a registry re-splitting a download reads, so it carries the path.

    Transport-only by design (outside `artifact.digest`), which is precisely why it may carry a
    location where nothing else may.
    """
    split = _manifest(_split(_flat(tmp_path, "split")), tmp_path / "out")
    names = {entry["name"] for entry in split["derived"]}

    assert names, "the fixture carries sidecars, so the block cannot be empty"
    assert all(name.startswith(f"{DERIVED_SUBDIR}/") for name in names), names


def test_the_same_table_in_both_places_is_refused_naming_both(tmp_path: Path) -> None:
    """The collision `enrich`-on-a-downloaded-module would otherwise create, refused before any write.

    Neither copy may be preferred: the tables are fact-hashed *and* human-overridable, so picking one
    silently discards a curator's override. That is why this is an error and not a warning.
    """
    spec_dir = _flat(tmp_path)
    derived = spec_dir / DERIVED_SUBDIR
    derived.mkdir()
    shutil.copy(spec_dir / "resolution.csv", derived / "resolution.csv")

    with pytest.raises(SidecarCollision) as caught:
        resolve_sidecar(spec_dir, "resolution.csv")
    message = str(caught.value)
    assert "resolution.csv" in message and DERIVED_SUBDIR in message

    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert not result.success
    assert any(DERIVED_SUBDIR in e for e in result.errors), result.errors


def test_a_pass_writes_beside_the_copy_it_read(tmp_path: Path) -> None:
    """Follow the module's layout, or the next run produces the collision above.

    This is the rule that makes the tolerance coherent: tolerating a location on *input* while always
    writing to the root breaks on first use, which is what kept this item a design round rather than a
    one-line fallback.
    """
    spec_dir = _split(_flat(tmp_path))
    assert sidecar_write_path(spec_dir, "resolution.csv") == spec_dir / DERIVED_SUBDIR / "resolution.csv"

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    assert sidecar_write_path(fresh, "resolution.csv") == fresh / "resolution.csv"


def test_an_authored_table_does_not_get_a_second_home(tmp_path: Path) -> None:
    """`variants.csv` under `derived/` is not read — and the module is refused, not silently thinned.

    The asymmetry is deliberate. Two legal homes for an authored table means a module can carry two
    copies with the ignored one invisible, which is the silent-success shape. Demonstrated on the
    behaviour rather than asserted: move the only authored table and the compile must not succeed with
    a quietly empty module.
    """
    spec_dir = _flat(tmp_path)
    derived = spec_dir / DERIVED_SUBDIR
    derived.mkdir()
    (spec_dir / "variants.csv").rename(derived / "variants.csv")

    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert not result.success, "an authored table in derived/ must not read as a module without one"


def test_the_near_miss_guard_follows_into_the_subdirectory(tmp_path: Path) -> None:
    """Tolerating a second location must not put a typo where the guard cannot see it.

    A mistyped table name is the one case where "unknown files are ignored" is the wrong answer, and
    the guard exists for exactly that. Extending the layout without extending the guard would have
    bought a convenience by re-opening a closed hole.
    """
    spec_dir = _split(_flat(tmp_path))
    (spec_dir / DERIVED_SUBDIR / "resolutoin.csv").write_text("variant_key\n")

    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert any("resolutoin.csv" in w and "one small edit" in w for w in result.warnings), result.warnings


def test_a_tolerated_stray_file_in_the_subdirectory_stays_quiet(tmp_path: Path) -> None:
    """High precision, or the guard undoes the tolerance it sits beside.

    Warning about every unrecognised file would fire on the notes and receipts the contract exists to
    permit, which is why the check is keyed on a near miss rather than on "unknown csv".
    """
    spec_dir = _split(_flat(tmp_path))
    (spec_dir / DERIVED_SUBDIR / "curation-notes.csv").write_text("note\n")

    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert not any("curation-notes.csv" in w for w in result.warnings), result.warnings


def test_validate_sees_the_split_layout_too(tmp_path: Path) -> None:
    """Pre-flight has to agree with compile, or a green `validate` precedes a refusal."""
    spec_dir = _split(_flat(tmp_path))
    validation = validate_spec(spec_dir)
    assert validation.valid, validation.errors

"""`licensing.csv` is a second accepted spelling of `sources.csv`, landed in a minor (RM51).

The name was always wrong — the file records licence *terms*, and its own `source` column collides
with the `source` column four other tables carry — but a rename landing only at 1.0 would have to
**add** a spelling at the major and then remove one at the next. Landing the alias in 0.6 inverts
that: every module drafted from here on carries the new name, so 1.0 only removes.

What these tests hold down is that the alias is a *spelling* and nothing more — same rows, same fact
hash, same parquet, same manifest key — and that two spellings present at once is refused rather than
silently resolved. Signatures are compared against the same module under the other name, computed in
the test, never against a recorded constant.
"""

import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.draft import DRAFTABLE, blank_template
from just_dna_format.layout import (
    DERIVED_SUBDIR,
    LICENSING_CSV,
    SOURCES_CSV,
    SidecarCollision,
    preferred_spelling,
    resolve_sidecar,
    sidecar_write_path,
)
from just_dna_format.sources import SourceRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _with_sources(tmp_path: Path, name: str) -> Path:
    """A copy of a real module that carries a `sources.csv`, under the requested spelling."""
    for candidate in sorted(_EXAMPLES.iterdir()):
        if (candidate / SOURCES_CSV).is_file():
            source_module = candidate
            break
    else:  # pragma: no cover - the corpus is expected to carry one
        pytest.skip("no reference example carries a sources.csv")

    spec_dir = tmp_path / f"{source_module.name}__{name}"
    shutil.copytree(source_module, spec_dir)
    if name != SOURCES_CSV:
        (spec_dir / SOURCES_CSV).rename(spec_dir / name)
    return spec_dir


def _compile(spec_dir: Path, out: Path) -> dict:
    result = compile_module(spec_dir, out, resolve_with_ensembl=True)
    assert result.success, result.errors
    return json.loads((out / "manifest.json").read_text())


# ── the resolver itself ────────────────────────────────────────────────────────────────────────


def test_the_preferred_spelling_is_the_new_one(tmp_path: Path) -> None:
    """A module with neither file gets the current name, which is what makes 1.0 a removal."""
    assert preferred_spelling(SOURCES_CSV) == LICENSING_CSV
    assert sidecar_write_path(tmp_path, SOURCES_CSV).name == LICENSING_CSV


@pytest.mark.parametrize("name", [SOURCES_CSV, LICENSING_CSV])
def test_a_pass_writes_to_the_file_the_module_already_has(tmp_path: Path, name: str) -> None:
    """Write to the file you read — otherwise a re-enrich leaves two copies behind.

    That is the collision below, reached by following the documented workflow rather than by
    misusing it, which is why this rule is the load-bearing half of the alias.
    """
    (tmp_path / name).write_text("source,layer\n")
    assert sidecar_write_path(tmp_path, SOURCES_CSV) == tmp_path / name
    assert resolve_sidecar(tmp_path, SOURCES_CSV) == tmp_path / name


def test_both_spellings_present_is_refused_and_names_both_paths(tmp_path: Path) -> None:
    """Two copies are two claims: the table is fact-hashed *and* hand-editable, so neither wins.

    A merge or a newest-wins would discard a curator's override without saying so, which is the one
    outcome this codebase treats as worse than a refusal.
    """
    (tmp_path / SOURCES_CSV).write_text("source,layer\n")
    (tmp_path / LICENSING_CSV).write_text("source,layer\n")

    with pytest.raises(SidecarCollision) as caught:
        resolve_sidecar(tmp_path, SOURCES_CSV)

    message = str(caught.value)
    assert SOURCES_CSV in message and LICENSING_CSV in message


# ── the compiler reads both, identically ───────────────────────────────────────────────────────


def test_the_alias_changes_no_identity(tmp_path: Path) -> None:
    """Same module, two filenames, everything a consumer keys on unchanged.

    This is the claim that made the item minor-legal: the fact sidecars are outside `_INPUT_FILES`,
    so the filename enters no identity. Asserted by compiling the same bytes twice rather than by
    quoting the reasoning.
    """
    old = _compile(_with_sources(tmp_path, SOURCES_CSV), tmp_path / "out_old")
    new = _compile(_with_sources(tmp_path, LICENSING_CSV), tmp_path / "out_new")

    assert old["artifact"]["digest"] == new["artifact"]["digest"]
    assert old["content_signature"] == new["content_signature"]
    assert old["sources"] == new["sources"]
    assert old["compilation"]["resolution_signature"] == new["compilation"]["resolution_signature"]


def test_the_output_names_do_not_move(tmp_path: Path) -> None:
    """`sources.parquet` and `manifest.sources` keep their names — both are major-only renames.

    The 0.x tail therefore reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a
    real legibility cost and it is taken knowingly; pinning it here stops a well-meaning follow-up
    from "finishing" the rename into a published key.
    """
    spec_dir = _with_sources(tmp_path, LICENSING_CSV)
    out = tmp_path / "out"
    manifest = _compile(spec_dir, out)

    assert (out / "sources.parquet").is_file()
    assert not (out / "licensing.parquet").exists()
    assert manifest["sources"]["signature"] is not None


def test_the_licence_gate_still_refuses_under_the_new_spelling(tmp_path: Path) -> None:
    """The gate reads this file and nothing else, so an alias it could not see would disarm it.

    Demonstrated on the *failing* behaviour rather than asserted: strip `declared_use` from a
    no-sale source and the compile must refuse under either name.
    """
    refused: dict[str, bool] = {}
    for name in (SOURCES_CSV, LICENSING_CSV):
        spec_dir = _with_sources(tmp_path, name)
        rows = (spec_dir / name).read_text().splitlines()
        header = rows[0].split(",")
        # A commercial-use-forbidding annotation row with no declaration is the gate's trigger.
        row = dict.fromkeys(header, "")
        row.update(
            {"source": "cpic", "layer": "annotation", "commercial_use": "false", "declared_use": "commercial"}
        )
        (spec_dir / name).write_text(
            "\n".join(rows + [",".join(row[field] for field in header)]) + "\n"
        )
        result = compile_module(spec_dir, tmp_path / f"gate_{name}", resolve_with_ensembl=True)
        refused[name] = not result.success

    assert refused[SOURCES_CSV] == refused[LICENSING_CSV]
    assert refused[LICENSING_CSV], "the gate must still fire under the new spelling"


def test_the_deprecated_spelling_warns_but_still_compiles(tmp_path: Path) -> None:
    """Deprecate in a minor means warn-only: the file reads exactly as before.

    A deprecation that refused anything would be a breaking change wearing a notice, and the 0.6
    amendment's *actionable* scope is met here — the replacement exists and the migration is a rename.
    """
    spec_dir = _with_sources(tmp_path, SOURCES_CSV)
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)

    assert result.success, result.errors
    assert any(SOURCES_CSV in w and LICENSING_CSV in w for w in result.warnings)

    fresh = _with_sources(tmp_path, LICENSING_CSV)
    quiet = compile_module(fresh, tmp_path / "out_new", resolve_with_ensembl=True)
    assert quiet.success, quiet.errors
    assert not any("deprecated spelling" in w for w in quiet.warnings)


def test_validate_and_compile_agree_about_both_spellings(tmp_path: Path) -> None:
    """Pre-flight has to see what the compile sees, or a green `validate` precedes a refusal.

    `validate_spec` runs the licence gate and loads the fact tables from its own loop, so an alias
    wired into only one of the two is the exact shape that sent an author hunting a change they had
    not made.
    """
    for name in (SOURCES_CSV, LICENSING_CSV):
        spec_dir = _with_sources(tmp_path, name)
        validation = validate_spec(spec_dir)
        assert validation.valid, validation.errors


def test_the_near_miss_guard_does_not_flag_the_new_name(tmp_path: Path) -> None:
    """A file the compiler reads must never also be reported as a probable typo.

    `licensing.csv` is one small edit from nothing the guard knows *except* by being unknown to it,
    which is why the known-file set is built from the spellings rather than from the registries.
    """
    spec_dir = _with_sources(tmp_path, LICENSING_CSV)
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert not any(LICENSING_CSV in w and "one small edit" in w for w in result.warnings)


# ── reverse ────────────────────────────────────────────────────────────────────────────────────


def test_reverse_emits_the_preferred_spelling(tmp_path: Path) -> None:
    """`reverse` regenerates a spec, so the spelling it writes is the one 1.0 will keep.

    It used to join `_FACT_TABLES`' name on by hand, and that tuple names the licence table by its
    *deprecated* spelling because the parquet and the manifest key keep it — so a module compiled
    clean, reversed, and recompiled deprecation-warned on the second pass. `manifest.compilation.
    warnings` is a published field a catalog reindexes from (RM44), so the module and its own round
    trip disagreed about it.
    """
    spec_dir = _with_sources(tmp_path, LICENSING_CSV)
    out = tmp_path / "out"
    _compile(spec_dir, out)

    reversed_spec = tmp_path / "reversed"
    reverse_module(out, reversed_spec)

    assert (reversed_spec / LICENSING_CSV).is_file()
    assert not (reversed_spec / SOURCES_CSV).exists()

    again = compile_module(reversed_spec, tmp_path / "out_again", resolve_with_ensembl=True)
    assert again.success, again.errors
    assert not any("deprecated spelling" in w for w in again.warnings), again.warnings


def test_the_round_trip_moves_no_identity_when_the_name_changes(tmp_path: Path) -> None:
    """A module on the old name reverses onto the new one, and every signature is unchanged.

    This is what makes the previous test a fix rather than a trade: the fact sidecars are outside
    `_INPUT_FILES` and hashed by their facts, so the filename enters nothing a consumer keys on.
    Measured across all four — the artifact digest, the authored content signature, the resolution
    signature and the whole `manifest.sources` block — rather than argued from that.
    """
    spec_dir = _with_sources(tmp_path, SOURCES_CSV)
    out = tmp_path / "out"
    before = _compile(spec_dir, out)

    reversed_spec = tmp_path / "reversed"
    reverse_module(out, reversed_spec)
    assert (reversed_spec / LICENSING_CSV).is_file(), "reverse migrates the name"
    after = _compile(reversed_spec, tmp_path / "out_again")

    assert before["artifact"]["digest"] == after["artifact"]["digest"]
    assert before["content_signature"] == after["content_signature"]
    assert before["sources"] == after["sources"]
    assert before["compilation"]["resolution_signature"] == after["compilation"]["resolution_signature"]


@pytest.mark.parametrize("subdir", ["", DERIVED_SUBDIR])
def test_reverse_writes_to_the_copy_the_output_directory_already_has(
    tmp_path: Path, subdir: str
) -> None:
    """Write to the file you read, in `reverse` too — or it leaves the collision behind it.

    Reversing over a tree that already carries the deprecated name (or a `derived/` split) and always
    creating the preferred one at the root would produce two copies of one hand-editable table, which
    the next compile refuses naming both. Following the existing copy is the same rule every other
    writer obeys; a *fresh* directory has nothing to follow, which is why the test above sees the
    preferred spelling instead.
    """
    spec_dir = _with_sources(tmp_path, LICENSING_CSV)
    out = tmp_path / "out"
    _compile(spec_dir, out)

    reversed_spec = tmp_path / "reversed"
    stale = reversed_spec / subdir / SOURCES_CSV
    stale.parent.mkdir(parents=True)
    stale.write_text("source,layer\n")

    reverse_module(out, reversed_spec)

    present = sorted(
        path.relative_to(reversed_spec).as_posix()
        for path in reversed_spec.rglob("*")
        if path.name in (SOURCES_CSV, LICENSING_CSV)
    )
    assert present == [stale.relative_to(reversed_spec).as_posix()]
    assert resolve_sidecar(reversed_spec, SOURCES_CSV) == stale
    assert stale.read_text() != "source,layer\n", "the stale placeholder must have been rewritten"


def test_reverse_refuses_a_colliding_output_directory_before_writing_anything(
    tmp_path: Path,
) -> None:
    """Resolving the destinations first is what keeps the refusal from leaving a half-rebuilt spec.

    Following the module's existing copy gives `reverse` a way to fail that joining a name on did not
    have. Raised late — at the fact-table loop, which runs last — it would land after
    `module_spec.yaml` and the authored CSVs had already been rewritten, so a directory that could not
    be finished would still have been damaged. Resolved up front, a collision costs nothing.
    """
    spec_dir = _with_sources(tmp_path, LICENSING_CSV)
    out = tmp_path / "out"
    _compile(spec_dir, out)

    colliding = tmp_path / "colliding"
    colliding.mkdir()
    (colliding / SOURCES_CSV).write_text("source,layer\n")
    (colliding / LICENSING_CSV).write_text("source,layer\n")

    with pytest.raises(SidecarCollision) as caught:
        reverse_module(out, colliding)

    assert SOURCES_CSV in str(caught.value) and LICENSING_CSV in str(caught.value)
    assert sorted(path.name for path in colliding.iterdir()) == [LICENSING_CSV, SOURCES_CSV]


# ── drafting ───────────────────────────────────────────────────────────────────────────────────


def test_both_spellings_are_draftable_onto_the_same_model() -> None:
    """The surface an author reaches for instead of reading our models must know the new name.

    Excluding it would make `blank_template("licensing.csv")` deny that a table the compiler reads is
    a table of this format — the same false claim excluding `sources.csv` used to make (S21).
    """
    assert DRAFTABLE[SOURCES_CSV] is SourceRow
    assert DRAFTABLE[LICENSING_CSV] is SourceRow
    assert blank_template(LICENSING_CSV) == blank_template(SOURCES_CSV)


def test_drafting_writes_the_spelling_the_module_already_carries(tmp_path: Path) -> None:
    """Two accepted spellings made the *writer* able to create the collision the reader refuses.

    `DRAFTABLE` takes both names as keys, so a caller may legitimately ask for `licensing.csv` on a
    module that carries `sources.csv` — and the literal `spec_dir / csv_name` join then left two
    files behind, which `compile_module` refuses by design. That is the collision arrived at by
    following the documented surface rather than by misusing it, which is exactly the failure
    `layout.sidecar_write_path` exists to prevent. **Write to the file you read.**

    Watched failing before the fix: the append created a second file and the recompile refused with
    "…are the same table in two places".
    """
    from just_dna_compiler.draft import append_rows

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / SOURCES_CSV).write_text(
        "source,layer,license,license_url,license_sha256,attribution,notice,share_alike,"
        "commercial_use,redistribution,declared_use,dataset,fetched_at\n"
        "ensembl,resolution,Apache-2.0,,,Ensembl,,false,true,true,unstated,,\n",
        encoding="utf-8",
    )
    append_rows(spec, LICENSING_CSV, [SourceRow(source="clinvar", layer="clinical_assertion")])

    assert not (spec / LICENSING_CSV).exists(), "a second copy of the same table was created"
    assert {r["source"] for r in _rows(spec / SOURCES_CSV)} == {"ensembl", "clinvar"}


def test_drafting_honours_the_name_asked_for_when_the_module_carries_neither(tmp_path: Path) -> None:
    """The other half, and the reason the fix is narrower than `sidecar_write_path`.

    Here the filename is the caller's own argument, not a fixed name a pass writes under, so an absent
    file is created as asked. Redirecting `draft sources.csv` to `licensing.csv` would answer a
    different question than the one put — only the two-copies collision is repaired.
    """
    from just_dna_compiler.draft import append_rows

    for name in (SOURCES_CSV, LICENSING_CSV):
        spec = tmp_path / f"spec_{name}"
        spec.mkdir()
        append_rows(spec, name, [SourceRow(source="clinvar", layer="annotation")])
        assert (spec / name).exists()
        assert len(list(spec.glob("*.csv"))) == 1


def test_drafting_onto_a_module_that_already_carries_both_refuses(tmp_path: Path) -> None:
    """Appending to an already-broken module would make a third claim about one table."""
    from just_dna_compiler.draft import DraftError, append_rows

    spec = tmp_path / "spec"
    spec.mkdir()
    header = (
        "source,layer,license,license_url,license_sha256,attribution,notice,share_alike,"
        "commercial_use,redistribution,declared_use,dataset,fetched_at\n"
    )
    (spec / SOURCES_CSV).write_text(header, encoding="utf-8")
    (spec / LICENSING_CSV).write_text(header, encoding="utf-8")
    with pytest.raises(DraftError, match="same table in two places"):
        append_rows(spec, LICENSING_CSV, [SourceRow(source="clinvar", layer="annotation")])


def _rows(path: Path) -> list[dict]:
    import csv

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

"""Every module in `reference_examples/` is a Principle 7 fixed point. Discovered, never listed.

The reference examples are this repo's real corpus — eleven modules spanning the SNP core, all three
PGx tables, every binning kind, the fact sidecars, a pseudoautosomal locus and a non-GRCh38 build — and
each one's README asserts the round trip holds. Nothing checked it. Individual tests cover individual
shapes with inline fixtures, so an invariant could break for a whole class of real module while the
suite stayed green: that is exactly how `reverse_module` came to hardcode `genome_build: "GRCh38"`. On
the ten GRCh38 examples the hardcoded value is indistinguishable from reading the real one, so the bug
was invisible until a GRCh37 module existed — and *then* only if something round-tripped it.

Discovery rather than a list, because a listed sweep is a second hand-kept inventory: an example added
without being added here is an example nobody checks, and adding one is precisely when a new shape
arrives.

Three signatures, because they answer different questions and only one of them is order-independent:

* `content_signature` — the authored bytes before resolution. Must survive because reverse re-emits the
  *authored shape* (`authored_ident`), not whatever resolution filled in.
* `resolution_signature` — the injected facts, hashed by fact rather than by byte, so a reverse-emitted
  table with different provenance still hashes equal.
* `artifact.digest` — the parquet bytes, hence row order and column types. The strictest of the three.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    _DERIVED_FILES,
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_compiler.compiler.reverse import REVERSE_MANIFEST_EXCLUDED, reconstructed_projection
from just_dna_format.layout import VERIFICATION_JSON, resolve_sidecar, sidecar_relative_names

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _specs() -> list[Path]:
    found = sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())
    assert found, f"no reference examples discovered under {_EXAMPLES}"
    return found


def _signatures(result) -> tuple[str, str]:
    """The two that must hold from the very first lap. `resolution_signature` is handled apart."""
    manifest = result.manifest
    return (manifest.artifact.digest, manifest.content_signature)


def _carried_files_come_back(manifest, reversed_dir: Path) -> None:
    """Every file the compile hashed from the spec directory is in the reversed spec (RM364).

    `manifest.inputs[]` names the authored files and `manifest.derived[]` the sidecars, each under the
    spelling the module carried; a reversed sidecar is looked up under any legal spelling, since reverse
    writes the preferred one. The attestation is the one exclusion, for the reason the registry gives.
    """
    assert "derived" in REVERSE_MANIFEST_EXCLUDED and "verification" in REVERSE_MANIFEST_EXCLUDED
    for entry in manifest.inputs:
        assert (reversed_dir / entry.name).is_file(), f"reverse lost the authored file {entry.name}"
    for entry in manifest.derived:
        tables = [csv for csv in _DERIVED_FILES if entry.name in sidecar_relative_names(csv)]
        assert len(tables) == 1, f"manifest.derived names {entry.name}, which {len(tables)} sidecar(s) accept"
        (table,) = tables
        if table == VERIFICATION_JSON:
            continue
        assert resolve_sidecar(reversed_dir, table) is not None, f"reverse lost the sidecar {entry.name}"


def _resolution_signature(result) -> str | None:
    """**On `manifest.compilation`, not on the manifest root — and that is why this is a function.**

    This sweep used to read it as `getattr(manifest, "resolution_signature", None)`, and the manifest
    has no such attribute: the field lives inside the `compilation` block beside `resolution_mode`
    and `fully_resolved`. So the third element of every comparison was `None` on both sides, for
    every example, for the whole of 0.6 — the docstring above devotes a bullet to why this signature
    matters and nothing ever compared one.

    A defaulted `getattr` on a name that does not exist is indistinguishable from a name whose value
    is legitimately `None`, which is exactly the case this sweep has to be able to see (a module
    carrying no `resolution.csv` has no signature). Reading the attribute directly is what makes a
    rename fail here instead of quietly disabling the check.
    """
    return result.manifest.compilation.resolution_signature


@pytest.mark.parametrize("spec", _specs(), ids=lambda p: p.name)
def test_reference_example_round_trips_to_a_fixed_point(spec: Path, tmp_path: Path) -> None:
    """compile → reverse → compile → reverse → compile, and every signature holds from the first."""
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    assert content_signature(spec) == first.manifest.content_signature

    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    reversed_check = validate_spec(tmp_path / "rev1")
    assert reversed_check.valid, reversed_check.errors

    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    assert second.success, second.errors
    assert _signatures(first) == _signatures(second)
    _carried_files_come_back(first.manifest, tmp_path / "rev1")
    # Every manifest field the registry says a round trip gives back (RM364), `resolution_signature`
    # among them, from the FIRST lap: see the note at the end of this test for why that is now
    # unconditional.
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)

    # A second lap, because "reverse produces something that recompiles" and "reverse is a fixed
    # point" are different claims — a transform can be stable from the second iteration onward while
    # the first lap already lost something.
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors
    assert _signatures(second) == _signatures(third)
    assert reconstructed_projection(second.manifest) == reconstructed_projection(third.manifest)
    assert _resolution_signature(second) == _resolution_signature(third)

    # `resolution_signature` on the FIRST lap used to carry an exception, and the corpus held three
    # shapes: unchanged; `None` → a value, where reverse rebuilt a `resolution.csv` the module never had
    # from its authored cells (`grch37_build`, `mt_heteroplasmy`, `cyp2d6_structural`); and a value →
    # a different value on `cyp2c9_warfarin_grch37`, whose `pharm_variants.csv` the GRCh37 fill skips, so
    # no parquet held what the table said about those rows. RM364 closed both: reverse writes no table
    # for a module that read none, and every positional parquet carries the loci its table filed under
    # each row's key. So the exemption, derived from the declared build, is gone, and the projection
    # above compares the signature from the first lap on every example.
    assert _resolution_signature(first) == _resolution_signature(second)


@pytest.mark.parametrize("spec", _specs(), ids=lambda p: p.name)
def test_reference_example_compiles_idempotently(spec: Path, tmp_path: Path) -> None:
    """Principle 7's other half: the same spec in a fixed environment gives the same digest."""
    once = compile_module(spec, tmp_path / "once")
    twice = compile_module(spec, tmp_path / "twice")
    assert once.success and twice.success
    assert _signatures(once) == _signatures(twice)


@pytest.mark.parametrize("spec", _specs(), ids=lambda p: p.name)
def test_reference_example_declared_build_survives(spec: Path, tmp_path: Path) -> None:
    """The build a module declares is still the build its artifact records after a round trip.

    Stated separately from the digest check because it is the *reason* the digest moved, and because it
    fails more legibly: a mismatch here names the assembly, while the digest only says "different".
    """
    declared = validate_spec(spec)
    assert declared.valid, declared.errors

    first = compile_module(spec, tmp_path / "a1")
    build = first.manifest.genome_build
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert f"genome_build: {build}" in (tmp_path / "rev" / "module_spec.yaml").read_text()
    assert compile_module(tmp_path / "rev", tmp_path / "a2").manifest.genome_build == build


@pytest.mark.parametrize("spec", _specs(), ids=lambda p: p.name)
def test_reference_example_compiles_under_strict(spec: Path, tmp_path: Path) -> None:
    """The mode the READMEs and the authoring skill's step 6 actually tell an author to use.

    Every check above runs in `best_effort`, which is the default and therefore the one an inline
    fixture reaches for — and that is how a whole release's worth of examples came to fail the command
    their own documentation prints. `reference_examples/pathogenic_clinvar/README.md` says "it compiles
    under `--strict`, which is the point" and gives the line twice; regenerating its `resolution.csv`
    online added 185 enricher-minted indel identities, `_verify_vrs_ids` escalated every one of them
    under `strict`, and nothing noticed because no test in the suite passed `strict=True` over the
    corpus. `shox_par1` went the same way, for two alleles.

    So this is not a duplicate of the idempotency sweep with a flag flipped. It is the assertion that
    the corpus still satisfies the *documented* contract, and it is the one that fails when a severity
    decision quietly makes the strictest mode unreachable for real modules.

    `validate` is asserted alongside, in the same mode, because the skill puts it immediately before
    the compile as a pre-flight — a green pre-flight that precedes a refusal is its own defect.
    """
    pre_flight = validate_spec(spec, strict=True)
    assert pre_flight.valid, pre_flight.errors

    result = compile_module(spec, tmp_path / "strict", strict=True)
    assert result.success, result.errors


def test_the_corpus_covers_more_than_one_build() -> None:
    """The sweep above only has teeth if the corpus is not uniform.

    This is the assertion that would have made the hardcoded build fail. Ten GRCh38 examples cannot
    distinguish "reads the module's build" from "writes GRCh38", so the guard is that at least two
    builds are represented — and it fails if `reference_examples/grch37_build/` is ever removed without
    a replacement.
    """
    builds = set()
    for spec in _specs():
        for line in (spec / "module_spec.yaml").read_text().splitlines():
            if line.startswith("genome_build:"):
                builds.add(line.split(":", 1)[1].strip())
    assert len(builds) > 1, f"every example declares the same build: {builds}"

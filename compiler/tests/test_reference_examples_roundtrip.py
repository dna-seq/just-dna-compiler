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
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _specs() -> list[Path]:
    found = sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())
    assert found, f"no reference examples discovered under {_EXAMPLES}"
    return found


def _signatures(result) -> tuple[str, str, str | None]:
    manifest = result.manifest
    return (
        manifest.artifact.digest,
        manifest.content_signature,
        getattr(manifest, "resolution_signature", None),
    )


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

    # A second lap, because "reverse produces something that recompiles" and "reverse is a fixed
    # point" are different claims — a transform can be stable from the second iteration onward while
    # the first lap already lost something.
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors
    assert _signatures(second) == _signatures(third)


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

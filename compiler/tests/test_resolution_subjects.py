"""`fully_resolved` is `all(...)` over `variants.csv`, so it needs its denominator (RM44).

A module with no `variants.csv` makes that flag `all()` over an empty list — **vacuously true** — and
the field's own documented trust rule (`resolution_mode == "strict" or fully_resolved`) then grants a
verdict to a module that resolves nothing. A registry followed that comment and badged two modules as
`trusted`, then repaired it by substring-matching a warning's prose.

`Compilation.resolution_subjects` is the count the flag quantifies over, so the vacuous case is
`fully_resolved=true, resolution_subjects=0` and needs no prose to read.

Every expectation here is counted off the authored CSV or read off another manifest field at runtime;
nothing is a number copied from a data dump. The corpus is the parameter, deliberately — the defect is
one that a module *with* variants cannot exhibit, so a single hand-picked fixture would prove nothing.
"""

import csv
import io
import json
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _example_dirs() -> list[Path]:
    return sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())


def _authored_variant_rows(spec_dir: Path) -> int:
    """Rows in the module's `variants.csv`, counted off the file the author wrote."""
    path = spec_dir / "variants.csv"
    if not path.is_file():
        return 0
    return len(list(csv.DictReader(io.StringIO(path.read_text()))))


@pytest.mark.parametrize("spec_dir", _example_dirs(), ids=lambda d: d.name)
def test_the_count_brackets_the_authored_rows(spec_dir: Path, tmp_path: Path) -> None:
    """Never fewer than the author wrote, and zero exactly when they wrote no variants table.

    An inequality rather than an equality because resolution *expands*: one rsID naming several loci
    becomes several subjects, and `fully_resolved` iterates the expanded list. Asserting equality would
    mean re-implementing the expansion in the test, which is the transform under test.
    """
    result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None
    subjects = result.manifest.compilation.resolution_subjects
    authored = _authored_variant_rows(spec_dir)

    assert subjects >= authored
    assert (subjects == 0) == (authored == 0)


def test_expansion_is_what_lifts_the_count_above_the_authored_rows(tmp_path: Path) -> None:
    """The denominator is the *resolved* set, and one real module proves the two differ.

    `pathogenic_clinvar` carries rsIDs that resolve to more than one locus, so its subject count is
    strictly greater than its authored row count. Without this the bracketing test above would pass
    just as happily on a count that was never expanded at all.
    """
    spec_dir = _EXAMPLES / "pathogenic_clinvar"
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None

    assert result.manifest.compilation.resolution_subjects > _authored_variant_rows(spec_dir)


def test_the_vacuous_modules_are_exactly_the_ones_with_no_variants_table(tmp_path: Path) -> None:
    """`fully_resolved` alone cannot separate these two sets; with the count, it can.

    Set equality rather than counts: the point is *which* modules the flag is vacuous for, and the
    corpus answers it — several of the examples carry no `variants.csv` at all, and every one of them
    reports `fully_resolved=True`.
    """
    vacuous: set[str] = set()
    table_only: set[str] = set()
    for spec_dir in _example_dirs():
        result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
        assert result.success, result.errors
        assert result.manifest is not None
        compilation = result.manifest.compilation
        if compilation.fully_resolved and compilation.resolution_subjects == 0:
            vacuous.add(spec_dir.name)
        if not (spec_dir / "variants.csv").is_file():
            table_only.add(spec_dir.name)

    assert vacuous == table_only
    # Guard the premise: an empty set would make the assertion above vacuous in its own turn.
    assert table_only, "the corpus must keep at least one table-only module or this proves nothing"


def test_the_count_agrees_with_the_weights_table_height(tmp_path: Path) -> None:
    """The one number this restates, pinned so a divergence is a decision rather than a drift.

    `Stats.weights_rows` is equal to the subject count on every module today, because the materializer
    emits one weights row per in-scope variant row. It is nonetheless the wrong field to key trust on:
    `Stats` is documented as card/detail display facets and promises no such relationship, while a
    denominator belongs beside the flag it qualifies. Both claims are asserted here, so if the
    materializer ever stops emitting one-for-one, this fails and someone chooses.
    """
    for spec_dir in _example_dirs():
        result = compile_module(spec_dir, tmp_path / spec_dir.name, resolve_with_ensembl=True)
        assert result.success, result.errors
        assert result.manifest is not None
        assert result.manifest.compilation.resolution_subjects == result.manifest.stats.weights_rows


def test_the_count_survives_into_manifest_json(tmp_path: Path) -> None:
    """It is a *published* field or it is nothing — a reindexing catalog has only the written file.

    This is the whole point of the item: the registry's workaround existed because the only record
    that survived a publish was prose inside `compilation.warnings`.
    """
    spec_dir = _EXAMPLES / "pathogenic_clinvar"
    out = tmp_path / "out"
    result = compile_module(spec_dir, out, resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None

    written = json.loads((out / "manifest.json").read_text())
    assert written["compilation"]["resolution_subjects"] == result.manifest.compilation.resolution_subjects
    assert written["compilation"]["resolution_subjects"] > 0
    assert written["compilation"]["fully_resolved"] is True


def test_a_table_only_module_reads_as_vacuous_rather_than_trusted(tmp_path: Path) -> None:
    """The motivating case, spelled as the consumer's own rule.

    `pgx_slco1b1_simvastatin` joins to no VCF. The documented trust rule says `trusted`; the rule plus
    the denominator says the flag covered nothing. Both statements are made here, so the regression to
    catch is the *pair* coming apart rather than one field's value moving.
    """
    spec_dir = _EXAMPLES / "pgx_slco1b1_simvastatin"
    result = compile_module(spec_dir, tmp_path / "out", resolve_with_ensembl=True)
    assert result.success, result.errors
    assert result.manifest is not None
    compilation = result.manifest.compilation

    trusted_by_the_documented_rule = compilation.resolution_mode == "strict" or compilation.fully_resolved
    assert trusted_by_the_documented_rule
    assert compilation.resolution_subjects == 0

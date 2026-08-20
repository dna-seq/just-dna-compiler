"""`manifest.stats` describes the module, not `variants.csv` (0.6, RM121 — motivating case S57).

`Stats` is documented as *"card/detail stats derived from the spec"*, and `variant_stats` derived the
gene facets from one table of that spec. Eight of the nine authored row models carry a `gene` column
and seven of those eight make it **required**, so a module whose lead table is `diplotypes.csv` or
`allele_function.csv` knows its genes exactly and published `gene_count: 0, genes: []` — and a
registry's gene index is fed from that field, so the module could not be found by a gene search.

The tests below run the real `compile_module` on real files and read the emitted `manifest.json`; the
expected gene sets are computed from the CSVs at run time, never transcribed, so a fixture edit cannot
leave a test agreeing with a stale number.
"""

import csv
import json
from pathlib import Path
from typing import Any

from just_dna_compiler.compiler import (
    _GENE_BEARING_TABLE_KINDS,
    _TABLE_KINDS,
    compile_module,
    module_stats,
    variant_stats,
)
from just_dna_format.manifest import read_manifest

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: stats\n"
    "  title: Stats\n"
    "  description: what manifest.stats describes\n"
    "  report_title: Stats\n"
    "genome_build: GRCh38\n"
)


def _genes_in_csv(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as handle:
        reader = csv.DictReader(handle)
        if "gene" not in (reader.fieldnames or []):
            return set()
        return {row["gene"] for row in reader if row.get("gene")}


def _stats(out: Path) -> dict[str, Any]:
    return json.loads((out / "manifest.json").read_text())["stats"]


# ── the registry is derived, not listed ──────────────────────────────────────────────────────────


def test_every_gene_bearing_table_kind_is_in_the_registry_and_nothing_else_is() -> None:
    """Equality over the walked set, not a floor: a kind added to `_TABLE_KINDS` with a `gene` column
    must enter this registry by construction, because the defect S57 reported *is* a hand-kept list of
    which tables count."""
    walked = {csv_name for csv_name, _p, model in _TABLE_KINDS if "gene" in model.model_fields}
    assert {csv_name for csv_name, _model in _GENE_BEARING_TABLE_KINDS} == walked
    # It is not vacuous, and it is not everything — both halves matter.
    assert walked and walked < {csv_name for csv_name, _p, _m in _TABLE_KINDS}


# ── the reported case, on the module it was reported against ─────────────────────────────────────


def test_a_star_allele_module_publishes_its_gene(tmp_path: Path) -> None:
    """The measurement in S57: `cyp2c19_star_alleles` has no `variants.csv` at all, and every one of
    its rows names `CYP2C19`."""
    spec = _EXAMPLES / "cyp2c19_star_alleles"
    expected = set().union(*(_genes_in_csv(spec / name) for name, _p, _m in _TABLE_KINDS))
    assert expected, "the fixture stopped carrying genes; the test below would pass vacuously"
    assert not (spec / "variants.csv").exists()

    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    stats = _stats(tmp_path / "out")
    assert set(stats["genes"]) == expected
    assert stats["gene_count"] == len(expected)


def test_the_gene_facets_are_a_union_over_every_authored_kind(tmp_path: Path) -> None:
    """Across the whole corpus, and computed per module rather than asserted as a total."""
    for spec in sorted(p for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").exists()):
        expected = _genes_in_csv(spec / "variants.csv")
        for name, _parquet, _model in _TABLE_KINDS:
            expected |= _genes_in_csv(spec / name)
        result = compile_module(spec, tmp_path / spec.name)
        if not result.success:
            continue  # the licence gate and strict-only examples are not this test's subject
        stats = _stats(tmp_path / spec.name)
        assert set(stats["genes"]) == expected, spec.name
        assert stats["gene_count"] == len(expected), spec.name


def test_at_least_one_example_was_publishing_an_empty_gene_list(tmp_path: Path) -> None:
    """The regression is only interesting if the corpus actually contains the shape. Counted here so
    that a corpus which stops containing it fails loudly rather than passing quietly."""
    table_only_with_genes = [
        spec
        for spec in sorted(p for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").exists())
        if not (spec / "variants.csv").exists()
        and any(_genes_in_csv(spec / name) for name, _p, _m in _TABLE_KINDS)
    ]
    assert table_only_with_genes, "no table-only module carries a gene; S57's case is gone"
    for spec in table_only_with_genes:
        result = compile_module(spec, tmp_path / spec.name)
        if result.success:
            assert _stats(tmp_path / spec.name)["genes"]


# ── what the union must NOT reach ────────────────────────────────────────────────────────────────


def test_a_derived_sidecars_gene_is_not_a_gene_the_module_claims(tmp_path: Path) -> None:
    """`gene_metrics.csv` is a machine-written fact table: a gene reaches it because a pass looked it
    up, not because the author said the module is about it. `_GENE_BEARING_TABLE_KINDS` derives from
    `_TABLE_KINDS`, which excludes the fact sidecars, so the exclusion is structural — this test pins
    that it stays so."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_SPEC_YAML)
    (spec / "allele_function.csv").write_text(
        "gene,allele,function_status\nCYP2C19,*2,no_function\n"
    )
    (spec / "gene_metrics.csv").write_text(
        "gene,dataset,status\nBRCA1,gnomad_v4.1_constraint,resolved\n"
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _stats(tmp_path / "out")["genes"] == ["CYP2C19"]


# ── a drop has to move the number, wherever the dropped row lived ────────────────────────────────


def test_dropping_the_last_row_naming_a_gene_removes_it_from_the_manifest(tmp_path: Path) -> None:
    """`pharm_variants.csv` is the one gene-bearing kind whose rows a `best_effort` compile may drop
    (a lengthless symbolic allele, RM5). The re-derive after that drop sat inside the loop's
    `variants.csv` branch, so before RM121 it could not have seen a kind table shrink — which is the
    RM44 class of defect that branch was itself written against.

    Two rows, because a table every row of which would be dropped is refused outright: the MSH2 one
    goes, the GLI2 one stays, so the assertion is about *which* gene left rather than about the table
    disappearing. Both are real ClinVar GRCh38 records — `rs2104016493` a 913 bp MSH2 deletion whose
    length this row deliberately omits, `rs2469808710` an ordinary spelled GLI2 insertion.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_SPEC_YAML)
    (spec / "allele_function.csv").write_text(
        "gene,allele,function_status\nCYP2C19,*2,no_function\n"
    )
    header = "rsid,chrom,start,ref,genotype,gene,drug,conclusion\n"
    kept_row = "rs2469808710,2,120926480,A,A/AT,GLI2,warfarin,a spelled insertion\n"
    (spec / "pharm_variants.csv").write_text(
        header
        + "rs2104016493,2,47410090,T,<DEL>/T,MSH2,warfarin,a deletion with no stated length\n"
        + kept_row
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert any("DROPPED" in w for w in result.warnings), result.warnings
    assert _stats(tmp_path / "out")["genes"] == ["CYP2C19", "GLI2"], "MSH2's only row was dropped"

    # Give the same deletion its published length and the row survives — so does its gene.
    (spec / "pharm_variants.csv").write_text(
        header
        + "rs2104016493,2,47410090,T,<DEL:913>/T,MSH2,warfarin,a 913 bp MSH2 deletion\n"
        + kept_row
    )
    kept = compile_module(spec, tmp_path / "kept")
    assert kept.success, kept.errors
    assert _stats(tmp_path / "kept")["genes"] == ["CYP2C19", "GLI2", "MSH2"]


# ── identity is untouched, which is what makes this a patch ──────────────────────────────────────


def test_stats_sits_outside_both_identities(tmp_path: Path) -> None:
    """`manifest.json` is not one of the hashed artifact files, so no `stats` value can move
    `artifact.digest`; `content_signature` is over authored rows and never read `stats` at all. Pinned
    because "does this move a published identity" is the question that sizes the release."""
    spec = _EXAMPLES / "cyp2c19_star_alleles"
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    manifest = read_manifest(tmp_path / "out" / "manifest.json")
    assert "manifest.json" not in {f.name for f in manifest.artifact.files}
    assert manifest.stats.genes, "the module under test must actually publish a gene"


# ── the two functions differ in exactly two keys ─────────────────────────────────────────────────


def test_module_stats_is_variant_stats_plus_the_gene_facets() -> None:
    """`variant_stats` keeps its name and its meaning — renaming it would be a major (S14's rule), so
    the wider answer arrived beside it rather than inside it."""
    narrow = variant_stats([])
    wide = module_stats([], {})
    assert narrow == wide
    assert {"gene_count", "genes"} <= set(narrow)

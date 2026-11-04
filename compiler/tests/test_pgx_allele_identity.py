"""RM351: a named allele's identity in the cross-table PGx checks is `(gene, allele)`, never the bare name.

Two defects of one class. The checks collected allele names into sets keyed on the bare string, so (a)
two genes sharing a name (`*2`) were one allele — one gene's definition silenced the other's missing
one, and in the phase check one gene's defining variants leaked into the other's signature — and (b) an
allele that is *typed* rather than defined by variants (an HLA allele, RM334) was reported as "can never
match", which is false: a typer calls it, and no `haplotypes.csv` row could ever define it.

A `haplotypes.csv` row with no `gene` is the unknown arm: it defines its name for every gene, because
nothing can say which gene it is not. That is exactly the pre-RM351 behaviour, so a gene-less module
is unchanged.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    _cross_validate_haplotype_definitions,
    _cross_validate_phase_ambiguity,
    load_csv_rows,
    validate_spec,
)
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, HaplotypeRow, is_hla_gene

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_UNDEFINED = "used but not defined in haplotypes.csv"


def _undefined_warnings(warnings: list) -> list[str]:
    return [str(w) for w in warnings if _UNDEFINED in str(w)]


def _apoe_with(tmp_path: Path, allele_function: str) -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / "apoe_epsilon", spec)
    (spec / "allele_function.csv").write_text(allele_function, encoding="utf-8")
    return spec


def test_an_hla_allele_beside_an_apoe_haplotype_table_is_not_undefined(tmp_path: Path) -> None:
    """The motivating case (the RM334 builder's e2e): an HLA allele has no defining variants by design,
    so a haplotypes.csv for another gene must not make it "never match"."""
    spec = _apoe_with(tmp_path, "gene,allele,function_status\nHLA-DRB1,*15:01,\n")
    result = validate_spec(spec)
    assert result.valid, result.errors
    assert _undefined_warnings(result.warnings) == []


def test_two_genes_sharing_a_name_are_two_alleles(tmp_path: Path) -> None:
    """CYP2C19 defines `*2`; CYP2C9 uses `*2` and defines nothing. Keyed on the bare name, CYP2C19's
    definition silenced CYP2C9's gap. The warning now names the gene."""
    spec = _apoe_with(
        tmp_path,
        "gene,allele,function_status\nCYP2C19,*2,no_function\nCYP2C9,*2,decreased_function\n",
    )
    with (spec / "haplotypes.csv").open("a", encoding="utf-8") as handle:
        handle.write("*2,rs4244285,10,94781859,G,A,CYP2C19\n")
    result = validate_spec(spec)
    assert result.valid, result.errors
    (warning,) = _undefined_warnings(result.warnings)
    assert "CYP2C9 *2" in warning
    assert "CYP2C19 *2" not in warning
    # The pinned phrases are kept word for word (`@warning-text-is-api`).
    assert "A consumer's caller cannot emit an allele nothing defines" in warning
    assert "can never match" in warning


def test_the_exempted_genes_are_named_when_the_warning_fires() -> None:
    """An exemption is stated, never silent: the HLA gene that was not checked rides along on the
    warning the real gap raises."""
    haplotypes = [HaplotypeRow(haplotype_name="e4", rsid="rs429358", allele="C", gene="APOE")]
    functions = [
        AlleleFunctionRow(gene="HLA-B", allele="*57:01"),
        AlleleFunctionRow(gene="APOE", allele="e7"),
    ]
    (warning,) = _cross_validate_haplotype_definitions(haplotypes, functions, [])
    assert "APOE e7" in warning
    assert "HLA-B" in warning and "typed" in warning
    assert "*57:01" not in warning.split("Not checked")[0]


def test_only_exempt_alleles_undefined_means_no_warning() -> None:
    """Nothing was wrong, so there is nothing to report (`@tautology-zero`)."""
    haplotypes = [HaplotypeRow(haplotype_name="e4", rsid="rs429358", allele="C", gene="APOE")]
    functions = [AlleleFunctionRow(gene="HLA-A", allele="*31:01")]
    diplotypes = [DiplotypeRow(gene="HLA-A", haplotype_a="*31:01", haplotype_b="*31:01", conclusion="x")]
    assert _cross_validate_haplotype_definitions(haplotypes, functions, diplotypes) == []


def test_a_gene_less_definition_defines_its_name_for_every_gene() -> None:
    """The unknown arm: `HaplotypeRow.gene` is optional, and a row naming no gene cannot be said to
    define some other gene's allele and not this one. Withheld, exactly as before RM351."""
    haplotypes = [HaplotypeRow(haplotype_name="*2", rsid="rs4244285", allele="A")]
    functions = [
        AlleleFunctionRow(gene="CYP2C19", allele="*2"),
        AlleleFunctionRow(gene="CYP2C9", allele="*2"),
    ]
    assert _cross_validate_haplotype_definitions(haplotypes, functions, []) == []


def test_a_gene_spelled_in_another_case_is_one_gene() -> None:
    """The bare-name key ignored the gene, so `Cyp2c19` in haplotypes.csv against `CYP2C19` elsewhere
    passed. Keying on the gene must not turn that spelling into a finding about every allele."""
    haplotypes = [HaplotypeRow(haplotype_name="*2", rsid="rs4244285", allele="A", gene="Cyp2c19 ")]
    functions = [AlleleFunctionRow(gene="CYP2C19", allele="*2")]
    diplotypes = [DiplotypeRow(gene="CYP2C19", haplotype_a="*2", haplotype_b="*2", conclusion="PM")]
    assert _cross_validate_haplotype_definitions(haplotypes, functions, diplotypes) == []


def test_an_hla_gene_the_module_defines_by_variants_is_checked() -> None:
    """The exemption is for a TYPED gene. A module that defines HLA-B *57:01 by a tag SNP has chosen
    definitions for HLA-B, so an HLA-B allele it uses and never defines is a real gap."""
    haplotypes = [HaplotypeRow(haplotype_name="*57:01", rsid="rs2395029", allele="G", gene="HLA-B")]
    functions = [
        AlleleFunctionRow(gene="HLA-B", allele="*57:01"),
        AlleleFunctionRow(gene="HLA-B", allele="*58:01"),
    ]
    (warning,) = _cross_validate_haplotype_definitions(haplotypes, functions, [])
    assert "By gene: HLA-B *58:01." in warning and "Not checked" not in warning


def test_the_gaps_are_grouped_per_gene() -> None:
    """One clause per gene, the aggregation the neighbouring PGx warnings use."""
    haplotypes = [HaplotypeRow(haplotype_name="*2", rsid="rs4244285", allele="A", gene="CYP2C19")]
    functions = [
        AlleleFunctionRow(gene="CYP2D6", allele="*36"),
        AlleleFunctionRow(gene="CYP2D6", allele="*37"),
        AlleleFunctionRow(gene="CYP2C9", allele="*2"),
    ]
    (warning,) = _cross_validate_haplotype_definitions(haplotypes, functions, [])
    assert "By gene: CYP2C9 *2; CYP2D6 *36, *37." in warning


def test_is_hla_gene_is_the_prefix_the_grammar_reads() -> None:
    """One predicate: the compiler's exemption and the model's grammar answer the same question."""
    assert is_hla_gene("HLA-DRB1") and is_hla_gene("HLA-B")
    assert not is_hla_gene("CYP2D6") and not is_hla_gene("hla-b")


def _one_variant_hap(name: str, gene: str, rsid: str, allele: str) -> HaplotypeRow:
    return HaplotypeRow(haplotype_name=name, rsid=rsid, allele=allele, gene=gene)


def test_one_genes_definition_does_not_leak_into_anothers_phase_signature() -> None:
    """GENE_A's `*2` and `*3` are defined identically and their rows disagree: a finding. GENE_B also
    defines a `*2`, at a different variant. Keyed on the bare name, GENE_B's variant was merged into
    GENE_A's `*2`, the two GENE_A haplotypes stopped looking identical, and the finding went silent."""
    haplotypes = [
        _one_variant_hap("*2", "GENE_A", "rs1", "T"),
        _one_variant_hap("*3", "GENE_A", "rs1", "T"),
        _one_variant_hap("*2", "GENE_B", "rs2", "G"),
    ]
    diplotypes = [
        DiplotypeRow(gene="GENE_A", haplotype_a="*2", haplotype_b="*2", conclusion="poor"),
        DiplotypeRow(gene="GENE_A", haplotype_a="*3", haplotype_b="*3", conclusion="normal"),
    ]
    warnings = _cross_validate_phase_ambiguity(haplotypes, diplotypes)
    identical = [w for w in warnings if "defines identically" in str(w)]
    assert len(identical) == 1 and str(identical[0]).startswith("GENE_A:"), warnings


def test_a_gene_less_definition_still_reaches_the_phase_check() -> None:
    """Same unknown arm on the phase side: an HFE table authored without `gene` behaves as before."""
    rows = [
        ("wt", "G", "C"),
        ("C282Y", "A", "C"),
        ("H63D", "G", "G"),
        ("C282Y-H63D", "A", "G"),
    ]
    haplotypes = [
        HaplotypeRow(haplotype_name=name, rsid=rsid, allele=allele)
        for name, c282y, h63d in rows
        for rsid, allele in (("rs1800562", c282y), ("rs1799945", h63d))
    ]
    diplotypes = [
        DiplotypeRow(gene="HFE", haplotype_a="C282Y", haplotype_b="H63D", conclusion="trans"),
        DiplotypeRow(gene="HFE", haplotype_a="C282Y-H63D", haplotype_b="wt", conclusion="cis"),
    ]
    (warning,) = _cross_validate_phase_ambiguity(haplotypes, diplotypes)
    assert "indistinguishable without phase" in str(warning)


def _without_genes(rows: list) -> list:
    return [row.model_copy(update={"gene": None}) for row in rows]


def _bare_name_gaps(haplotypes: list, functions: list, diplotypes: list) -> list[str]:
    """The pre-RM351 rule, as it read: every used name no `haplotypes.csv` row names, gene ignored,
    `*1` exempt. Kept here as the oracle the regression test compares against, never in the compiler."""
    if not haplotypes:
        return []
    defined = {row.haplotype_name for row in haplotypes}
    used = {row.allele for row in functions} | {
        name for row in diplotypes for name in (row.haplotype_a, row.haplotype_b)
    }
    return sorted(name for name in used if name not in defined and name != "*1")


@pytest.mark.parametrize(
    "example",
    [
        "apoe_epsilon",
        "cyp2c19_star_alleles",
        "cyp2c9_warfarin_grch37",
        "cyp2d6_structural",
        "hfe_compound_het",
        "pgx_slco1b1_simvastatin",
    ],
)
def test_the_reference_examples_warn_as_they_did_under_the_bare_name(example: str) -> None:
    """On every PGx reference example, keying on `(gene, allele)` reports the same gaps the bare-name
    rule did. `star_allele_undefined` is compared with the old rule restated above; the phase check is
    compared with itself run on a `haplotypes.csv` whose genes are blanked, which puts every definition
    under the one gene-blind key the bare name gave."""
    root = _EXAMPLES / example
    result = validate_spec(root)
    assert result.valid, result.errors
    haplotypes = _load(root / "haplotypes.csv", HaplotypeRow)
    functions = _load(root / "allele_function.csv", AlleleFunctionRow)
    diplotypes = _load(root / "diplotypes.csv", DiplotypeRow)
    reported = {str(w) for w in result.warnings}

    gaps = _bare_name_gaps(haplotypes, functions, diplotypes)
    undefined = [str(w) for w in _cross_validate_haplotype_definitions(haplotypes, functions, diplotypes)]
    if gaps:
        (warning,) = undefined
        assert f"haplotypes.csv: {gaps}." in warning and warning in reported
    else:
        assert undefined == [] and not _undefined_warnings(result.warnings)

    keyed = [str(w) for w in _cross_validate_phase_ambiguity(haplotypes, diplotypes)]
    blind = [str(w) for w in _cross_validate_phase_ambiguity(_without_genes(haplotypes), diplotypes)]
    assert keyed == blind
    assert set(keyed) <= reported


def _load(path: Path, model: type) -> list:
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, model, path.name)
    assert not errors, errors
    return rows

"""The phase-ambiguity cross-check (0.5.1) — RM28's cis/trans motivation, closed as a check.

Compound heterozygosity was the case that most justified a predicate language. Building it proved it
needs none: `haplotypes.csv` is same-strand conjunction and a *diplotype* is a statement about two
homologs, so cis and trans are already two rows. What no table can say is that a consumer without
phase cannot tell those two rows apart — and that turns out to be derivable from the tables
themselves, which makes it a compiler check rather than a schema change.

The fixture is `reference_examples/hfe_compound_het/` in miniature: two real HFE alleles, and the two
diplotypes that share an unphased genotype while disagreeing about what it means.
"""

from pathlib import Path

import pytest

from just_dna_compiler.compiler import (
    _cross_validate_phase_ambiguity,
    compile_module,
    validate_spec,
)
from just_dna_format.pgx import DiplotypeRow, HaplotypeRow

_C282Y = ("rs1800562", "6", 26092913, "G")
_H63D = ("rs1799945", "6", 26090951, "C")


def _hap(name: str, c282y: str, h63d: str) -> list[HaplotypeRow]:
    return [
        HaplotypeRow(haplotype_name=name, rsid=r, chrom=c, start=s, ref=f, allele=a, gene="HFE")
        for (r, c, s, f), a in ((_C282Y, c282y), (_H63D, h63d))
    ]


#: The four HFE haplotypes, written densely (every haplotype names an allele at every variant).
_HAPLOTYPES = [
    *_hap("wt", "G", "C"),
    *_hap("C282Y", "A", "C"),
    *_hap("H63D", "G", "G"),
    *_hap("C282Y-H63D", "A", "G"),
]


def _dip(a: str, b: str, conclusion: str, **kwargs) -> DiplotypeRow:
    return DiplotypeRow(gene="HFE", haplotype_a=a, haplotype_b=b, conclusion=conclusion, **kwargs)


def test_the_trans_and_cis_rows_are_flagged_because_they_disagree() -> None:
    """The whole point: same two variants, opposite finding, one observable genotype."""
    diplotypes = [
        _dip("C282Y", "H63D", "compound heterozygous — no wild-type protein on either chromosome"),
        _dip("C282Y-H63D", "wt", "both variants in cis — one intact copy remains, a carrier"),
    ]
    (warning,) = _cross_validate_phase_ambiguity(_HAPLOTYPES, diplotypes)
    assert "C282Y-H63D/wt" in warning and "C282Y/H63D" in warning
    assert "must withhold" in warning


def test_every_other_hfe_diplotype_is_unambiguous() -> None:
    """No false positives on the rest of the same real table."""
    diplotypes = [
        _dip("C282Y", "C282Y", "homozygous"),
        _dip("C282Y", "wt", "carrier"),
        _dip("H63D", "H63D", "H63D homozygous"),
        _dip("H63D", "wt", "H63D carrier"),
        _dip("C282Y-H63D", "C282Y", "functionally the C282Y homozygote"),
        _dip("wt", "wt", "neither allele"),
    ]
    assert _cross_validate_phase_ambiguity(_HAPLOTYPES, diplotypes) == []


def test_two_indistinguishable_rows_that_agree_are_not_a_finding() -> None:
    """A consumer reporting either is right, so there is nothing to warn about."""
    same = "both HFE variants present"
    diplotypes = [_dip("C282Y", "H63D", same), _dip("C282Y-H63D", "wt", same)]
    assert _cross_validate_phase_ambiguity(_HAPLOTYPES, diplotypes) == []


def test_one_pair_with_many_rows_is_not_a_phase_ambiguity() -> None:
    """The false positive the first implementation shipped, kept as a regression.

    The dedup key is (gene, a, b, trait_efo_id, drug, clinical_context), so one pair legitimately
    carries a row per drug and per clinical context. Those share a signature *by construction* and
    differ in conclusion *by design*. Grouping on rows rather than on distinct pairs reported 595
    ambiguities in the real CYP2C19 example, naming the same pair twice in every message.
    """
    diplotypes = [
        _dip("C282Y", "H63D", "avoid X", drug="drug-x", clinical_context="adults"),
        _dip("C282Y", "H63D", "consider Y", drug="drug-x", clinical_context="pediatrics"),
        _dip("C282Y", "H63D", "unrelated finding", trait_efo_id="MONDO:0004975"),
    ]
    assert _cross_validate_phase_ambiguity(_HAPLOTYPES, diplotypes) == []


def test_identically_defined_haplotypes_are_not_called_a_phase_problem() -> None:
    """Found by compiling a real 16,290-row CYP2D6 draft, and it was a defect in *this* check.

    CPIC's core definitions give `*10`, `*100`, `*101` and `*147` the identical three defining
    variants, so `*10/*8` and `*100/*8` present the same genotype **phased or not**. Telling the
    author "a phased consumer resolves it" would send them to buy phasing that cannot help. The two
    cases are separated by grouping on the *phase-preserving* signature: same multiset of haplotype
    definitions → nothing distinguishes them; different → phase does.
    """
    same = [
        HaplotypeRow(haplotype_name=name, rsid="rs1065852", start=42130692, allele="A", gene="CYP2D6")
        for name in ("*10", "*100")
    ]
    other = HaplotypeRow(
        haplotype_name="*8", rsid="rs5030865", start=42129084, allele="A", gene="CYP2D6"
    )
    diplotypes = [
        DiplotypeRow(gene="CYP2D6", haplotype_a="*10", haplotype_b="*8", conclusion="IM"),
        DiplotypeRow(gene="CYP2D6", haplotype_a="*100", haplotype_b="*8", conclusion="Indeterminate"),
    ]
    (warning,) = _cross_validate_phase_ambiguity([*same, other], diplotypes)
    assert "defines identically" in warning
    assert "phase does not help" in warning
    assert "indistinguishable without phase" not in warning


def test_findings_aggregate_per_gene_with_the_count_stated() -> None:
    """398 lines on the real CYP2D6 draft buried every other finding. One line per gene per class,
    examples plus a count, so nothing is silently capped."""
    haplotypes = [
        HaplotypeRow(haplotype_name=f"*{i}", rsid="rs1065852", start=42130692, allele="A",
                     gene="CYP2D6")
        for i in range(1, 10)
    ]
    haplotypes.append(
        HaplotypeRow(haplotype_name="*8", rsid="rs5030865", start=42129084, allele="A", gene="CYP2D6")
    )
    diplotypes = [
        DiplotypeRow(gene="CYP2D6", haplotype_a=f"*{i}", haplotype_b="*8", conclusion=f"c{i}")
        for i in range(1, 10)
    ]
    (warning,) = _cross_validate_phase_ambiguity(haplotypes, diplotypes)
    assert "1 group(s)" in warning
    assert warning.count(";") <= 3  # examples are bounded


def test_sparse_star_allele_definitions_do_not_collide() -> None:
    """CPIC publishes only the variants an allele carries, and no `ref` at all.

    An unmentioned variant reads as the implied reference — which needs no reference *sequence*, only
    that "unmentioned" means one thing everywhere. On such a table the check correctly finds nothing.
    """
    sparse = [
        HaplotypeRow(haplotype_name="*2", rsid="rs4244285", start=94781859, allele="A", gene="CYP2C19"),
        HaplotypeRow(haplotype_name="*17", rsid="rs12248560", start=94761900, allele="T", gene="CYP2C19"),
    ]
    diplotypes = [
        DiplotypeRow(gene="CYP2C19", haplotype_a="*2", haplotype_b="*2", conclusion="PM"),
        DiplotypeRow(gene="CYP2C19", haplotype_a="*17", haplotype_b="*2", conclusion="IM"),
        DiplotypeRow(gene="CYP2C19", haplotype_a="*17", haplotype_b="*17", conclusion="UM"),
    ]
    assert _cross_validate_phase_ambiguity(sparse, diplotypes) == []


def test_an_explicit_reference_allele_and_an_omitted_one_mean_the_same_thing() -> None:
    """`wt` written densely (`allele == ref`) must collide with a haplotype that omits the variant —
    otherwise the check would depend on authoring style rather than on meaning."""
    mixed = [
        *_hap("C282Y", "A", "C"),
        *_hap("H63D", "G", "G"),
        *_hap("C282Y-H63D", "A", "G"),
        # `wt` written sparsely: it names nothing at all.
        HaplotypeRow(haplotype_name="wt", rsid="rs1800562", chrom="6", start=26092913, ref="G",
                     allele="G", gene="HFE"),
    ]
    diplotypes = [
        _dip("C282Y", "H63D", "compound heterozygous"),
        _dip("C282Y-H63D", "wt", "in cis, a carrier"),
    ]
    assert len(_cross_validate_phase_ambiguity(mixed, diplotypes)) == 1


def test_a_pair_naming_an_undefined_haplotype_is_skipped_not_guessed() -> None:
    """Reading an undefined haplotype as all-reference would be a claim, not a computation. The
    neighbouring "used but not defined" warning is what covers that case."""
    diplotypes = [
        _dip("C282Y", "H63D", "compound heterozygous"),
        _dip("C282Y-H63D", "wt", "in cis"),
        _dip("H63D", "unknown-allele", "?"),
    ]
    warnings = _cross_validate_phase_ambiguity(_HAPLOTYPES, diplotypes)
    assert len(warnings) == 1 and "unknown-allele" not in warnings[0]


def test_no_haplotype_table_means_no_check() -> None:
    """Same stance as the used-but-not-defined check: a module may lean on a caller's definitions."""
    assert _cross_validate_phase_ambiguity([], [_dip("C282Y", "H63D", "x")]) == []


def test_it_fires_on_the_real_reference_example_and_never_blocks() -> None:
    root = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_compound_het"
    assert validate_spec(root).valid, validate_spec(root).errors

    import tempfile

    with tempfile.TemporaryDirectory() as out:
        result = compile_module(root, Path(out) / "artifact", resolve_with_ensembl=False)
        assert result.success, result.errors
        phase = [w for w in result.warnings if "indistinguishable without phase" in w]
        assert len(phase) == 1, result.warnings
        assert "C282Y/H63D" in phase[0]


@pytest.mark.parametrize("example", ["apoe_epsilon", "cyp2c19_star_alleles"])
def test_the_other_pgx_examples_stay_quiet(example: str) -> None:
    """APOE is the standing illustration of the closed-world boundary: ε2/ε4 vs ε1/ε3 is the textbook
    unphased collision, and the module carries no ε1, so there is nothing in it to collide."""
    import tempfile

    root = Path(__file__).resolve().parents[2] / "reference_examples" / example
    with tempfile.TemporaryDirectory() as out:
        result = compile_module(root, Path(out) / "artifact", resolve_with_ensembl=False)
        assert result.success, result.errors
        assert not [w for w in result.warnings if "indistinguishable without phase" in w]

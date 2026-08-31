"""The strand predicate behind S85's diagnosis: `reverse_complement` / `strand_flip_explains`.

A paper's supplementary published against hg19 routinely spells the submitted strand, so its `G/A`
meets GRCh38's `C/T`. `hosting_verdict` is right to call that a contradiction — on the strand it is
written on it *is* one — and the point of these is that the **reason** can be established rather
than guessed at.
"""

import pytest
from just_dna_format.alleles import reverse_complement, strand_flip_explains


@pytest.mark.parametrize(
    ("allele", "expected"),
    [
        ("A", "T"), ("T", "A"), ("C", "G"), ("G", "C"),
        ("AG", "CT"),            # reversed as well as complemented
        ("CAG", "CTG"),
        ("acgt", "ACGT"),        # case-folded to the stored spelling
    ],
)
def test_a_nucleotide_string_complements(allele: str, expected: str) -> None:
    assert reverse_complement(allele) == expected


@pytest.mark.parametrize("allele", ["", None, "N", "R", "<DEL:1500>", "*", "A?"])
def test_anything_that_is_not_four_bases_withholds(allele: str | None) -> None:
    """The house algebra. A degenerate code states an uncertainty, and complementing it would assert
    a definite base the source declined to name — the defect `non_nucleotide_reason` keeps apart."""
    assert reverse_complement(allele) is None


def test_reverse_complement_is_an_involution_on_what_it_accepts() -> None:
    """Applying it twice returns the original — the property that makes it a strand reading rather
    than a transformation, and the one a caller relies on when it says "reading it the other way"."""
    for allele in ("A", "AG", "CAGT", "TTTT"):
        assert reverse_complement(reverse_complement(allele)) == allele


def test_the_reported_case_is_established_as_a_flip() -> None:
    """rs61849494: `G/A` in the paper, `C>T` on GRCh38. Authored sorted, as the models require."""
    assert strand_flip_explains("A/G", "C", "T") is True


@pytest.mark.parametrize(
    ("genotype", "ref", "alts"),
    [
        ("C/T", "C", "T"),      # already fits — nothing to explain
        ("A/G", "A", "G"),
        ("A/T", "T", "A"),      # palindromic, and it already fits: never reported as a flip
    ],
)
def test_a_genotype_the_locus_already_hosts_is_never_a_flip(
    genotype: str, ref: str, alts: str
) -> None:
    """`called <= locus` is tested first. A palindromic SNV satisfies both readings, so without this
    the predicate would report a flip for a genotype that needed no explaining at all."""
    assert strand_flip_explains(genotype, ref, alts) is False


@pytest.mark.parametrize(
    ("genotype", "ref", "alts"),
    [
        ("A/G", "C", "G"),          # G matches, A's complement T is not offered
        ("A/G", "C", "N"),          # a degenerate locus allele: cannot be complemented, so withhold
        ("A/G", "C", "<DEL:5>"),    # symbolic: no sequence to complement
        ("G/GT", "AGAG", "AG"),     # RM31's indel pair — reconciled by parsimony, not by strand
    ],
)
def test_what_is_not_established_is_reported_as_not_established(
    genotype: str, ref: str, alts: str
) -> None:
    """`False` means *not established*, never *established otherwise*. A caller's message must not
    invert it, which is why the fallback reason says what it did not establish."""
    assert strand_flip_explains(genotype, ref, alts) is False


def test_a_locus_with_no_recorded_alleles_explains_nothing() -> None:
    """Nothing is known, so nothing can be established — the first rung of `hosting_verdict`'s own
    ladder, mirrored so the two cannot disagree about an empty locus."""
    assert strand_flip_explains("A/G", None, None) is False
    assert strand_flip_explains("A/G", "C", None) is False

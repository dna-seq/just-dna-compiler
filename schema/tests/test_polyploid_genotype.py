"""The genotype grammar caps at two alleles, and the refusal has to say that is a decision (RM67).

VCF 4.4 §7.2 permits any ploidy and adds *partial* phasing on top of it (`GT |0|0/1/2`, the first
phasing indicator optional), so a triploid call is spellable there and is not spellable here. That
divergence is deliberate — the format's ceiling is diploid, with the narrower haploid/hemizygous cases
carried by the single-allele arm — and it is recorded as RM67 rather than queued as work.

What was wrong is what the refusal *said*. A duplicated CYP2D6 carrying SNVs is the polyploid example
the standard itself reaches for, and it is the module where an author meets the cap; the message they
got was a bare restatement of the grammar, which reads as "you typed it wrong" for a call that is
perfectly real. Every other deliberate refusal in this codebase names its own limit in-line — the
lengthless-symbolic message says the grammar could widen, the ploidy check names its contigs, the VRS
warnings name RM15 — so this one was the odd one out.

Three refusals reach an author holding a polyploid call, and before this they were three different
sentences, none of which mentioned ploidy:

* `C/T/T` — three slash-separated alleles, the plain unphased triploid.
* `T|T|C` — three pipe-separated alleles, the fully phased one.
* `T|T/C` — VCF's partial phasing, which used to be reported as the *allele* `'T/C'` being unspellable.

The locus is real: `22:42127941 C>T` is the CYP2D6 row `reference_examples/cyp2d6_structural/`
already carries, on the gene whose duplication motivates the whole case.
"""

import pytest
from just_dna_format.spec import VariantRow

#: The CYP2D6 splice variant the reference example carries, on the duplicated gene.
_CHROM, _START, _REF, _ALT = "22", 42127941, "C", "T"


def _variant(genotype: str) -> VariantRow:
    """A real CYP2D6 locus, so the only thing under test is the genotype cell."""
    return VariantRow(
        chrom=_CHROM, start=_START, ref=_REF, alts=_ALT,
        genotype=genotype, state="risk", gene="CYP2D6",
        conclusion="a duplicated CYP2D6 carrying the *4 splice variant on more than one copy",
    )


@pytest.mark.parametrize(
    "genotype",
    [
        f"{_REF}/{_ALT}/{_ALT}",   # unphased triploid, sorted the way the two-allele arm asks
        f"{_ALT}|{_ALT}|{_REF}",   # fully phased triploid
        f"{_ALT}|{_ALT}/{_REF}",   # VCF 4.4 §7.2 partial phasing — the first two phased with each other
    ],
)
def test_a_polyploid_genotype_is_refused_as_a_decision_not_as_a_typo(genotype: str) -> None:
    """All three spellings must name the cap, the standard that permits more, and the item.

    Fails on the pre-fix code by construction: `C/T/T` and `T|T|C` restated the grammar and stopped,
    and `T|T/C` blamed the allele `'T/C'` for not being a nucleotide — three sentences, none of which
    said that two alleles is where this format stops on purpose.
    """
    with pytest.raises(ValueError) as caught:
        _variant(genotype)
    message = str(caught.value)
    assert "RM67" in message
    assert "7.2" in message, "the message must cite the section of VCF that permits higher ploidy"
    assert genotype in message, "the refusal must quote the cell it is about"


def test_the_partially_phased_spelling_is_diagnosed_as_partial_phasing() -> None:
    """Mixing the separators is a *notation*, and saying so is the whole repair for this arm.

    `T|T/C` has two pipe-separated parts, the second of which is `'T/C'` — not a spellable allele, so
    the old message was true and useless. No legal genotype member can contain either separator
    (`ALLELE_PATTERN` is `^[ACGT]+$`, a symbolic token is bracketed and colon-separated, `*` is one
    character), so a cell carrying both is always this notation and never a typo'd allele.
    """
    with pytest.raises(ValueError, match="partial") as caught:
        _variant(f"{_ALT}|{_ALT}/{_REF}")
    message = str(caught.value)
    assert "nucleotides" not in message, (
        "the cell is a partial-phasing notation, not an unspellable allele — the old message said "
        "the second half was not a nucleotide, which sends the author looking at the wrong thing"
    )


def test_partial_phasing_is_named_at_any_ploidy_not_only_at_one_pipe() -> None:
    """`A|A|C/G` is VCF's `0|0/1/2` at ploidy 4 — the notation the branch exists to name.

    It only reaches that diagnosis because the mixed-separator check sits above the arity check. With
    the two the other way round it was counted (`phased genotype must be two pipe-separated alleles`)
    and the notation was recognised at exactly one pipe and nowhere else.
    """
    with pytest.raises(ValueError, match="partial-phasing"):
        _variant(f"{_ALT}|{_ALT}|{_REF}/{_ALT}")


def test_a_slash_inside_an_illegal_token_is_an_allele_defect_not_partial_phasing() -> None:
    """`<DEL/INS>` is a slash-for-colon slip, and the separator in it is not a separator.

    The mixed-separator diagnosis fires only when every member is a spellable allele, for exactly this
    case: a token that is malformed *and* happens to contain `/` is an allele defect, and the message
    that names the token is the one that helps.
    """
    with pytest.raises(ValueError, match="genotype alleles must be") as caught:
        _variant(f"{_ALT}|<DEL/INS>")
    assert "'<DEL/INS>'" in str(caught.value)


def test_an_unspellable_allele_in_the_phased_arm_still_gets_the_allele_message() -> None:
    """The mixed-separator branch must fire on mixed cells only, and steal nothing next to it.

    `T|X` is a phased pair whose second member is simply not an allele. That is a different finding
    with a different fix, and it keeps the ordinary grammar message — which nothing pinned either.
    """
    with pytest.raises(ValueError, match="genotype alleles must be") as caught:
        _variant(f"{_ALT}|X")
    message = str(caught.value)
    assert "'X'" in message, "the allele message names the member it could not spell"
    assert "RM67" not in message, "a bad allele is not the ploidy divergence"


def test_the_two_allele_arms_are_untouched() -> None:
    """The cap is at two, so the two-allele and single-allele spellings of this locus still load."""
    for genotype in (f"{_REF}/{_ALT}", f"{_ALT}|{_REF}", _ALT):
        assert _variant(genotype).genotype == genotype

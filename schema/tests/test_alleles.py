"""Reference-free allele reduction (RM31), on the real pairs that motivated it.

Every case here is a spelling a real source publishes — ClinVar's and Ensembl's renderings of one SHOX
deletion, the three HBB records dbSNP files under `rs281864532`, the reciprocal insertion/deletion pair
under `rs1554917888`. No invented alleles: the whole question is what two *published* spellings of one
event have in common, and a fabricated pair would answer a different question.
"""

from just_dna_format.alleles import event_profile, parsimony_reduce


def test_the_two_published_spellings_of_the_shox_deletion_reduce_alike() -> None:
    """The case that produced RM31. ClinVar: `X:634689 CAG>C`. Ensembl: `X:634690 AGAG>AG`.

    One 2 bp AG deletion, anchored one base apart, with different amounts of flank carried. Comparing
    the strings said "different variant" and `rs1569493663` resolved to `not_found`.
    """
    clinvar = parsimony_reduce(["C", "CAG"])
    ensembl = parsimony_reduce(["AGAG", "AG"])
    assert clinvar == ensembl == frozenset({"", "AG"})


def test_a_substitution_is_left_exactly_as_written() -> None:
    """Nothing to strip, so nothing is stripped — reduction must not touch the common case."""
    assert parsimony_reduce(["C", "T"]) == frozenset({"C", "T"})
    assert parsimony_reduce(["A", "C", "T"]) == frozenset({"A", "C", "T"})


def test_the_shortest_allele_bounds_the_trim() -> None:
    """An allele consumed to `""` is the honest rendering of "the absence of what the others carry"."""
    assert parsimony_reduce(["G", "GT"]) == frozenset({"", "T"})
    assert parsimony_reduce(["GTT", "G"]) == frozenset({"", "TT"})


def test_a_multiallelic_indel_site_reduces_every_allele_against_the_shared_flank() -> None:
    """Real shape: one site offering the reference, a 2 bp deletion and a 2 bp insertion."""
    assert parsimony_reduce(["CAG", "C", "CAGAG"]) == frozenset({"", "AG", "AGAG"})


def test_a_single_allele_has_no_frame_and_is_returned_unchanged() -> None:
    """A lone string has nothing to be relative to, so there is no flank to identify — and saying
    otherwise would let a homozygous indel genotype be "reduced" to nothing at all."""
    assert parsimony_reduce(["C"]) == frozenset({"C"})
    assert parsimony_reduce(["CAG", "CAG"]) == frozenset({"CAG"})
    assert event_profile(["C"]) is None
    assert event_profile([]) is None


def test_the_event_profile_is_what_re_anchoring_cannot_change() -> None:
    """Sliding an indel inside a repeat moves it and can rotate its content; the size is the event."""
    assert event_profile(["C", "CAG"]) == event_profile(["AGAG", "AG"]) == frozenset({0, 2})
    # `rs281864532` really does file a 1 bp insertion and a 2 bp deletion under one rsID, and no
    # re-anchoring turns one into the other.
    assert event_profile(["G", "GT"]) == frozenset({0, 1})
    assert event_profile(["GTT", "G"]) == frozenset({0, 2})
    assert event_profile(["G", "GT"]) != event_profile(["GTT", "G"])


def test_the_reciprocal_pair_reduces_to_one_event_and_that_is_correct() -> None:
    """`rs1554917888` is filed as both `T>TA` and `TA>T` at one position in ClinVar.

    As *observed alleles* those two records offer the same two sequences — which of them is the
    reference is what differs, and a genotype cannot say. So reduction collapsing them is not a loss:
    the string comparison already accepted both for a `T/TA` genotype, and the honest reading is that a
    genotype naming both alleles fits either record.
    """
    assert parsimony_reduce(["T", "TA"]) == parsimony_reduce(["TA", "T"]) == frozenset({"", "A"})


def test_case_and_whitespace_do_not_decide_anything() -> None:
    assert parsimony_reduce([" c ", "cag"]) == frozenset({"", "AG"})

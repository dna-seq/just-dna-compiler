"""`contradiction_reason` — why `hosting_verdict` said a confident `False` (S85).

Its twin `undecided_reason` exists because `None` has five causes and one message asserted one of
them. `False` has two, and the enricher's message asserted the *event-length* one for both: an
authored `A/G` at a `C>T` locus is two 1 bp substitutions whose sizes are identical, so *"the event
sizes differ, which re-anchoring cannot change"* was a false claim that sent the author hunting a
second variant sharing the rsID instead of looking at the strand.
"""

import pytest
from just_dna_compiler.resolution import contradiction_reason, hosting_verdict


def test_a_strand_flip_is_named_where_it_is_established() -> None:
    """The reported case. The remedy is a column the old sentence never mentioned."""
    reason = contradiction_reason("A/G", "C", "T")
    assert "reverse complement" in reason and "strand" in reason
    # It must contradict the `not_found` reading the row carries, not merely describe the alleles.
    assert "HAS this variant" in reason


def test_a_substitution_that_is_not_a_flip_says_what_it_did_not_establish() -> None:
    """`A/G` at `C>G`: G is offered, A's complement T is not. Same-length alleles, so the old
    "event sizes differ" line was false here too — and there is no flip to name either."""
    reason = contradiction_reason("A/G", "C", "G")
    assert "no shared flank" in reason
    assert "event sizes differ" not in reason
    # It offers the two readings that remain, rather than asserting one.
    assert "different variant sharing the rsID" in reason


def test_the_event_length_arm_keeps_its_own_reason() -> None:
    """The one case the original sentence was always right about, which must not be lost: a 1 bp
    insertion cannot be a 2 bp deletion however it is spelled."""
    assert hosting_verdict("G/GT", "GTT", "G") is False
    assert "event sizes differ" in contradiction_reason("G/GT", "GTT", "G")


def test_every_false_shape_gets_a_reason_and_no_two_arms_share_one() -> None:
    """The `@registry-completeness` shape, applied to a set of *branches* rather than a registry.

    A reason function drifts by a later arm silently inheriting an earlier one's sentence — which is
    exactly the defect being repaired here. So this walks one shape per `False`-producing arm,
    asserts each really is `False`, and asserts the reasons are pairwise distinct. Adding a third arm
    without a reason of its own fails this rather than shipping a plausible-sounding wrong cause.
    """
    shapes = {
        "strand flip":   ("A/G", "C", "T"),
        "substitution":  ("A/G", "C", "G"),
        "event length":  ("G/GT", "GTT", "G"),
    }
    for label, (genotype, ref, alts) in shapes.items():
        assert hosting_verdict(genotype, ref, alts) is False, label
    reasons = {label: contradiction_reason(*args) for label, args in shapes.items()}
    assert len(set(reasons.values())) == len(shapes), reasons
    assert all(text.strip() for text in reasons.values())


@pytest.mark.parametrize(
    ("genotype", "ref", "alts"),
    [("C/T", "C", "T"), ("C/CAG", "AGAG", "AG"), ("A/G", None, None)],
)
def test_it_is_only_ever_asked_after_a_false_verdict(genotype, ref, alts) -> None:
    """A guard on the contract rather than on the function: these shapes are not `False`, so nothing
    calls it for them. Pinned because a caller reaching for it unconditionally would print a
    contradiction for a locus that was kept — `C/CAG` against `AGAG>AG` is RM31's reconciling pair,
    the SHOX 2 bp deletion that string comparison used to reject."""
    assert hosting_verdict(genotype, ref, alts) is not False

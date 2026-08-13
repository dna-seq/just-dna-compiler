"""`gene_validity.csv` (RM24) — the shape, the vocabularies, and what the fact hash covers.

Every expectation here is computed from the model or the vocabulary rather than transcribed, so a
member added to either is covered without editing a list — the rule these tests exist to keep.
"""

import pytest
from just_dna_format.gene_validity import GENE_VALIDITY_FACT_FIELDS, GeneValidityRow
from just_dna_format.integrity import gene_validity_signature
from just_dna_format.vocab import (
    ORDERED_GENE_VALIDITY,
    VALID_GENE_VALIDITY,
    VALID_INHERITANCE_MODE,
)
from pydantic import ValidationError


def _row(**kw) -> GeneValidityRow:
    return GeneValidityRow(
        **{
            "gene": "RYR1",
            "disease_id": "MONDO:0007783",
            "moi": "autosomal_dominant",
            "classification": "definitive",
            "dataset": "clingen_gene_validity_2026-08-13",
            **kw,
        }
    )


def test_every_declared_classification_is_accepted_and_nothing_else_is() -> None:
    """Membership by construction, not by a transcribed list."""
    for member in sorted(VALID_GENE_VALIDITY):
        assert _row(classification=member).classification == member
    with pytest.raises(ValidationError):
        _row(classification="probably")


def test_every_declared_inheritance_mode_is_accepted_and_nothing_else_is() -> None:
    for member in sorted(VALID_INHERITANCE_MODE):
        assert _row(moi=member).moi == member
    with pytest.raises(ValidationError):
        _row(moi="dominant-ish")


def test_a_separator_slip_canonicalizes_like_every_other_vocabulary() -> None:
    """The 0.6 `match_vocab` rule reaches these two for free, because `check_vocab` runs it.

    Worth pinning rather than assuming: a hand-written cell is exactly where the slip happens, and
    the value *stored* must be the declared member so nothing is ever fact-hashed two ways.
    """
    assert _row(classification="no-known-disease-relationship").classification == (
        "no_known_disease_relationship"
    )
    assert _row(moi="autosomal-recessive").moi == "autosomal_recessive"


def test_the_published_ladder_is_a_subset_of_the_vocabulary_and_strictly_ordered() -> None:
    """`ORDERED_GENE_VALIDITY` must name real members, in one direction, with no repeats.

    It exists so a consumer does not hardcode the ladder; a ladder naming a member the vocabulary
    does not have would be worse than none.
    """
    assert set(ORDERED_GENE_VALIDITY) <= VALID_GENE_VALIDITY
    assert len(set(ORDERED_GENE_VALIDITY)) == len(ORDERED_GENE_VALIDITY)
    # The three negative verdicts and the ungraded one are deliberately off the ladder: putting
    # `refuted` at position zero would read as "the weakest evidence for".
    assert set(ORDERED_GENE_VALIDITY).isdisjoint(
        {"disputed", "refuted", "no_known_disease_relationship", "supportive", "animal_model_only"}
    )


def test_an_ungraded_assertion_is_legal_and_is_not_a_negative_verdict() -> None:
    """A submitter may assert an association without grading it; that is an empty cell, not a verdict."""
    ungraded = _row(classification=None)
    against = _row(classification="no_known_disease_relationship")
    assert ungraded.classification is None
    assert gene_validity_signature([ungraded]) != gene_validity_signature([against])


def test_the_two_curation_date_spellings_canonicalize_to_one_fact() -> None:
    """ClinGen writes millisecond precision with a Z; GenCC writes a space and no zone at all.

    Two spellings of one instant in a fact column would hash as two facts, which is the whole reason
    `fetched_at` is canonicalized on load — the curation date needs it more, being inside the hash.
    """
    clingen_spelling = _row(classification_date="2024-03-14T16:00:00.000Z")
    gencc_spelling = _row(classification_date="2024-03-14 16:00:00")
    assert clingen_spelling.classification_date == gencc_spelling.classification_date
    assert gene_validity_signature([clingen_spelling]) == gene_validity_signature([gencc_spelling])


def test_the_fact_set_is_exactly_the_model_minus_provenance_and_the_report_link() -> None:
    """Derived from `model_fields`, so a new column has to be placed in or out on purpose."""
    excluded = {"report_url", "source", "status", "fetched_at"}
    assert set(GENE_VALIDITY_FACT_FIELDS) == set(GeneValidityRow.model_fields) - excluded


def test_provenance_is_outside_the_hash_and_the_assertion_is_inside() -> None:
    """The producer-independence every fact table buys, proved both ways on one row."""
    base = _row()
    assert gene_validity_signature([base]) == gene_validity_signature(
        [_row(source="gencc", status="resolved", fetched_at="2026-08-13T00:00:00Z",
              report_url="https://example.invalid/whatever")]
    )
    for changed in (
        {"classification": "limited"},
        {"moi": "autosomal_recessive"},
        {"submitter": "Ambry Genetics"},
        {"disease_id": "MONDO:0000001"},
        {"dataset": "gencc_submissions_2026-08-13"},
        {"assertion_id": "CGGV:assertion_deadbeef"},
    ):
        assert gene_validity_signature([base]) != gene_validity_signature([_row(**changed)]), changed


def test_the_hash_is_order_independent() -> None:
    """Row order is an authoring artefact; the facts are a set (every sibling signature agrees)."""
    a, b = _row(gene="RYR1"), _row(gene="CACNA1S")
    assert gene_validity_signature([a, b]) == gene_validity_signature([b, a])


def test_a_typo_column_is_rejected_rather_than_dropped() -> None:
    with pytest.raises(ValidationError):
        _row(classifcation="definitive")


def test_a_row_must_name_its_gene_and_its_release() -> None:
    """Both are the row's identity: an assertion about no gene, or from no stated release, is not one."""
    with pytest.raises(ValidationError):
        _row(gene="   ")
    with pytest.raises(ValidationError):
        _row(dataset="")

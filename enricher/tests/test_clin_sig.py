"""One clinical-significance normalizer, and the defect that was invisible from either source alone.

`_normalize_clin_sig` lived inside `clinvar_build` with exactly one caller, and its map keys are
underscored because that is how ClinVar spells `CLNSIG`. PubMind spells the same concepts with
spaces, so `Uncertain significance` and `Conflicting` both fell through to `other` — while ClinVar's
`Uncertain_significance` and `Conflicting_classifications_of_pathogenicity` mapped correctly. Two
sources that agree, reported as disagreeing, on the largest disagreeing class in the corpus join.

**Nothing here would fail with either source's tokens alone**, which is why the central test below
runs both through the one function and compares. A ClinVar-only suite is green on the broken code and
a PubMind-only suite would have justified a second map, which is the repair this change rejects.
"""

import pytest
from just_dna_enricher.clin_sig import (
    CLIN_SIG_MAP,
    CLIN_SIG_SEVERITY,
    _tokenize,
    normalize_clin_sig,
)
from just_dna_format.vocab import VALID_CLIN_SIG

#: ClinVar's `CLNSIG` spelling of a concept, beside PubMind's `pathogenicity_sum` spelling of the
#: same one, and the single member both must land on. The middle two rows are the fix: before the
#: whitespace pre-step and the bare `conflicting` key, the right-hand column of each was `other`.
SAME_CONCEPT_BOTH_SPELLINGS: list[tuple[str, str, str]] = [
    ("Pathogenic", "Pathogenic", "pathogenic"),
    ("Uncertain_significance", "Uncertain significance", "uncertain_significance"),
    ("Conflicting_classifications_of_pathogenicity", "Conflicting", "conflicting"),
    ("Benign", "Benign", "benign"),
    ("Pathogenic/Likely_pathogenic", "Pathogenic/Likely pathogenic", "pathogenic"),
    # Not a special case and deliberately not `benign`: the severity order resolves a composite the
    # same way for both spellings, which is what one normalizer *means*. The assessment document
    # wrote this one as `benign` before the single-map decision; teaching PubMind's spelling a
    # different answer from ClinVar's would reintroduce exactly the drift being removed here.
    ("Benign/Likely_benign", "Benign/Likely benign", "likely_benign"),
]

#: The six values `PubMindDB_pathogenicity_sum` actually takes, read off the 2026-08-24 ANNOVAR file.
PUBMIND_TOKENS: tuple[str, ...] = (
    "Pathogenic",
    "Pathogenic/Likely pathogenic",
    "Benign",
    "Benign/Likely benign",
    "Uncertain significance",
    "Conflicting",
)


@pytest.mark.parametrize(
    "clinvar_spelling,pubmind_spelling,member", SAME_CONCEPT_BOTH_SPELLINGS,
    ids=[c[2] + "-" + c[1].replace(" ", "_") for c in SAME_CONCEPT_BOTH_SPELLINGS],
)
def test_both_sources_spellings_of_one_concept_reach_one_member(
    clinvar_spelling: str, pubmind_spelling: str, member: str
) -> None:
    """The central test of this unit, and it needs both columns to say anything.

    The member is named rather than only compared pairwise: two spellings both landing on `other`
    would satisfy an equality assertion while being precisely the defect.
    """
    assert normalize_clin_sig(clinvar_spelling) == member
    assert normalize_clin_sig(pubmind_spelling) == member
    assert member != "other"


def test_every_pubmind_token_reaches_a_member_and_none_falls_through() -> None:
    """Totality over the source's whole observed vocabulary, not over the two that were broken."""
    mapped = {token: normalize_clin_sig(token) for token in PUBMIND_TOKENS}
    assert set(mapped.values()) <= VALID_CLIN_SIG
    assert "other" not in mapped.values(), mapped
    assert "not_provided" not in mapped.values(), mapped


def test_the_whitespace_prestep_is_an_identity_on_every_clinvar_key() -> None:
    """The no-op claim, asserted as an equality over the walked map rather than spot-checked.

    Every key is already underscored, so the fold added for PubMind cannot change a single ClinVar
    answer. Asserting it over the whole registry is what keeps a later key with a space in it from
    silently acquiring a second spelling (`@registry-completeness`).
    """
    assert {_tokenize(key) for key in CLIN_SIG_MAP} == set(CLIN_SIG_MAP)
    assert {key: normalize_clin_sig(key) for key in CLIN_SIG_MAP} == dict(CLIN_SIG_MAP)


def test_the_map_and_the_severity_order_both_cover_the_vocabulary_exactly() -> None:
    """Both registries, both as equalities — the `conflicting` addition had to keep both true.

    `CLIN_SIG_SEVERITY` must cover `VALID_CLIN_SIG` or a mapped token has no rank to be picked by;
    `CLIN_SIG_MAP`'s *range* must be `VALID_CLIN_SIG` or a key writes a cell the vocabulary rejects.
    A member no key reaches is a member no source can produce, which is why this is equality.
    """
    assert set(CLIN_SIG_SEVERITY) == VALID_CLIN_SIG
    assert set(CLIN_SIG_MAP.values()) == VALID_CLIN_SIG
    assert len(CLIN_SIG_SEVERITY) == len(set(CLIN_SIG_SEVERITY))


def test_a_composite_resolves_by_severity_and_is_order_independent() -> None:
    """The winner is the most consequential member present, whichever side of the slash it is on."""
    assert normalize_clin_sig("Likely_pathogenic|Pathogenic") == "pathogenic"
    assert normalize_clin_sig("Pathogenic|Likely_pathogenic") == "pathogenic"
    assert normalize_clin_sig("Benign,Pathogenic") == "pathogenic"
    assert normalize_clin_sig("drug_response/Benign") == "drug_response"


def test_absence_and_an_unmodelled_token_are_different_answers() -> None:
    """`not_provided` is "the source states no classification"; `other` is "it stated something else".

    Collapsing them would lose the distinction a concordance check turns on: a source that said
    nothing has not disagreed with anybody.
    """
    assert normalize_clin_sig(None) == "not_provided"
    assert normalize_clin_sig("") == "not_provided"
    assert normalize_clin_sig("   ") == "not_provided"
    assert normalize_clin_sig("a wording nobody models") == "other"


def test_the_clinvar_builder_calls_the_shared_normalizer_and_holds_no_map_of_its_own() -> None:
    """The extraction, asserted structurally: a second map is the thing this unit exists to prevent.

    A copy left behind in `clinvar_build` would keep every test above green while reintroducing the
    two-maps-one-vocabulary drift, so the assertion is about the module rather than about a value.
    """
    from just_dna_enricher import clinvar_build

    assert clinvar_build.normalize_clin_sig is normalize_clin_sig
    leftover = {
        name
        for name, obj in vars(clinvar_build).items()
        if isinstance(obj, dict | tuple | set | frozenset)
        and VALID_CLIN_SIG & _hashable_members(obj)
    }
    assert leftover == set(), sorted(leftover)


def _hashable_members(obj: dict | tuple | set | frozenset) -> set:
    """Every hashable key and value in a container, for the structural check above.

    `vars(module)` carries dunders holding unhashable objects (`__spec__`, `__builtins__`), so the
    membership test has to survive them rather than assume every constant is a string collection.
    """
    parts = list(obj) + (list(obj.values()) if isinstance(obj, dict) else [])
    return {p for p in parts if isinstance(p, str)}

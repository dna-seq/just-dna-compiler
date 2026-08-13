"""`clinical_assertions.csv` (RM25) — the shape, and the distinctions the table exists to keep.

The table is worth having only if it preserves what a bare `clin_sig` throws away: how much review
sits behind a call, and which archive record it came from. Each of those is pinned here as a
*difference* the fact hash can see, not as a field that merely exists.
"""

import pytest
from just_dna_format.assertions import CLINICAL_ASSERTION_FACT_FIELDS, ClinicalAssertionRow
from just_dna_format.integrity import clinical_assertion_signature
from just_dna_format.vocab import VALID_CLIN_SIG
from pydantic import ValidationError


def _row(**kw) -> ClinicalAssertionRow:
    return ClinicalAssertionRow(
        **{
            "variant_key": "1:230710048:A",
            "chrom": "1",
            "start": 230710048,
            "ref": "A",
            "alt": "G",
            "clin_sig": "pathogenic",
            "review_status": "criteria_provided,_multiple_submitters,_no_conflicts",
            "review_stars": 2,
            "variation_id": "12345",
            "dataset": "clinvar_2026-06-27",
            **kw,
        }
    )


def test_every_declared_clinical_significance_is_accepted_and_nothing_else_is() -> None:
    for member in sorted(VALID_CLIN_SIG):
        assert _row(clin_sig=member).clin_sig == member
    with pytest.raises(ValidationError):
        _row(clin_sig="probably_bad")


def test_the_star_rating_is_bounded_to_clinvars_own_scale() -> None:
    """0 to 4 inclusive. A 5 is not a stronger claim, it is a corrupt one."""
    for stars in range(5):
        assert _row(review_stars=stars).review_stars == stars
    with pytest.raises(ValidationError):
        _row(review_stars=5)
    with pytest.raises(ValidationError):
        _row(review_stars=-1)


def test_an_unrated_record_is_not_a_zero_star_record() -> None:
    """The distinction the whole table is for, pinned where it can be broken.

    `0` is the rating ClinVar gives a submission with no assertion criteria; `None` means the record
    states no review status at all. Collapsing the second into the first would report an unread
    record as the weakest evidence available, which is a claim nobody made.
    """
    unrated = _row(review_stars=None, review_status=None)
    zero_star = _row(review_stars=0, review_status="no_assertion_criteria_provided")
    assert unrated.review_stars is None
    assert clinical_assertion_signature([unrated]) != clinical_assertion_signature([zero_star])


def test_the_review_tier_moves_the_hash_although_the_call_is_identical() -> None:
    """A one-star single submission and a four-star practice guideline are not the same claim.

    Before RM25 both compiled to the same `clin_sig` and nothing downstream could tell them apart.
    """
    single = _row(review_status="criteria_provided,_single_submitter", review_stars=1)
    guideline = _row(review_status="practice_guideline", review_stars=4)
    assert single.clin_sig == guideline.clin_sig
    assert clinical_assertion_signature([single]) != clinical_assertion_signature([guideline])


def test_the_fact_set_is_exactly_the_model_minus_provenance_and_the_rsid() -> None:
    """Derived from `model_fields`, so a new column has to be placed in or out on purpose."""
    excluded = {"rsid", "source", "status", "fetched_at"}
    assert set(CLINICAL_ASSERTION_FACT_FIELDS) == set(ClinicalAssertionRow.model_fields) - excluded


def test_the_rsid_does_not_move_the_hash_because_it_is_not_the_archives() -> None:
    """The tuple's stated property, proved on the column most likely to break it.

    The archive lookup is allele-exact on `(chrom, start, ref, alt)` and returns no rsID at all — the
    column is filled from the module's own `resolution.csv`. Inside the fact set it would make two
    modules holding *the same ClinVar records* hash differently according to whether their resolver
    happened to attach an rsID, which is exactly the producer-dependence this hash exists to exclude.

    `FREQUENCY_FACT_FIELDS` keeps `rsid` and is right to: there it arrives in gnomAD's own payload, so
    it is part of what the source said. The precedent does not transfer, and this pins that it did not.
    """
    resolved = _row(rsid="rs334")
    unresolved = _row(rsid=None)
    assert clinical_assertion_signature([resolved]) == clinical_assertion_signature([unresolved])
    # ...while the allele the row is actually keyed on still moves it (`alt` defaults to G here).
    assert clinical_assertion_signature([resolved]) != clinical_assertion_signature(
        [_row(alt="T")]
    )


def test_provenance_is_outside_the_hash_and_the_record_is_inside() -> None:
    base = _row()
    assert clinical_assertion_signature([base]) == clinical_assertion_signature(
        [_row(source="clinvar", status="resolved", fetched_at="2026-08-13T00:00:00Z")]
    )
    for changed in (
        {"clin_sig": "benign"},
        {"clin_sig_raw": "Benign/Likely_benign"},
        {"condition": "Long QT syndrome"},
        {"variation_id": "99999"},
        {"dataset": "clinvar_2026-08-01"},
        {"genome_build": "GRCh37"},
    ):
        assert clinical_assertion_signature([base]) != clinical_assertion_signature(
            [_row(**changed)]
        ), changed


def test_the_hash_is_order_independent() -> None:
    a, b = _row(variation_id="1"), _row(variation_id="2")
    assert clinical_assertion_signature([a, b]) == clinical_assertion_signature([b, a])


def test_the_build_is_a_fact_because_the_lookup_key_carries_none() -> None:
    """Two rows with identical coordinates on two assemblies describe different places.

    The ClinVar lookup key is (chrom, start, ref, alt) and states no assembly, so this column is the
    only thing that says which frame the numbers are in — the fourth build confusion in this codebase.
    """
    assert clinical_assertion_signature([_row()]) != clinical_assertion_signature(
        [_row(genome_build="GRCh37")]
    )


def test_a_typo_column_is_rejected_rather_than_dropped() -> None:
    with pytest.raises(ValidationError):
        _row(review_star=2)


def test_a_row_must_name_the_allele_and_the_release() -> None:
    with pytest.raises(ValidationError):
        _row(variant_key="  ")
    with pytest.raises(ValidationError):
        _row(dataset="")

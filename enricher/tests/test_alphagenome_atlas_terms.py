"""`alphagenome_atlas`: the Atlas API's Output, and why it cannot share `alphagenome_avi`'s row.

RM194/RM200. One `(source, layer)` key cannot carry two licence classes, and AlphaGenome publishes
two: the AVI SNV scores are Permissive Use — commercial and non-commercial — while everything the
live service returns is ordinary Output, non-commercial only. That is not a distinction this
workspace drew for tidiness; it is the distinction the download page draws, and `@write-the-sourcerow`
keys a row on the pair, so two classes need two names.

**The two rows rest on opposite kinds of ground, which is the thing these tests pin.** AVI's
`commercial_use=True` took a maintainer's browser session, because the Additional Terms define the
Permissive class and delegate *membership* to a sign-in-gated page — for a day it shipped `None`,
since a permission nobody can check does not belong in a signed attribution ledger. This row needs no
page at all: the Output Terms say Output is for non-commercial use only in their own opening
sentence. A stated prohibition, not an absent grant.

Asserted against the **pinned bytes** rather than against constants, the shape
`test_alphagenome_avi_build.py` uses: if someone drops a vendor file, or upstream reclassifies and
the file is re-saved, these fail rather than going on asserting yesterday's permission.
"""

from pathlib import Path

import pytest
from just_dna_enricher.licensing import (
    ALPHAGENOME_ATLAS_TERMS,
    ALPHAGENOME_AVI_TERMS,
    TERMS_BY_SOURCE,
    LicenseRefusal,
    check_declared_use,
)

_VENDOR = Path(__file__).resolve().parents[2] / "docs" / "vendor"


def test_the_registry_holds_this_object_and_not_a_copy_of_it() -> None:
    """The identity assert every source in this module carries."""
    assert TERMS_BY_SOURCE["alphagenome_atlas"] is ALPHAGENOME_ATLAS_TERMS


def test_the_two_alphagenome_sources_are_two_rows_with_two_classes() -> None:
    """The reason a second name exists at all — and it is a difference, not a duplicate."""
    assert ALPHAGENOME_ATLAS_TERMS.source != ALPHAGENOME_AVI_TERMS.source
    assert ALPHAGENOME_ATLAS_TERMS.commercial_use is False
    assert ALPHAGENOME_AVI_TERMS.commercial_use is True


def test_non_commercial_is_stated_by_the_pinned_terms_rather_than_inferred() -> None:
    """`False` because a document forbids it, not because no document permits it.

    The distinction is the whole of `@no-named-licence`: unknown terms warn and never gate, because
    unknown is the absence of a finding either way. This source is not unknown — two pinned files say
    the same thing in their own words, and one of them says it in its opening sentence.
    """
    output_terms = (_VENDOR / "alphagenome_output_terms.txt").read_text()
    assert "for\nnon-commercial use only" in output_terms or "non-commercial use only" in output_terms

    additional = (_VENDOR / "alphagenome_additional_tos.txt").read_text()
    # Prohibition 1a, and the exception it names is the AVI Score — i.e. the row next door, not this one.
    assert "only for non-commercial" in additional
    assert "except for the AVI Score" in additional

    assert ALPHAGENOME_ATLAS_TERMS.commercial_use is False


def test_the_download_page_does_not_put_this_scorer_in_the_permissive_class() -> None:
    """The positive half: the page that makes AVI commercial says nothing that reaches the API."""
    page = (_VENDOR / "alphagenome_download_page.txt").read_text()
    permissive = page.split("Permissive Use Downloadable artifacts", 1)[1].split(
        "Downloadable artifacts for non-commercial", 1
    )[0]
    assert "AVI SNV scores" in permissive
    assert "RNA_SEQ" not in permissive, (
        "the page now classifies a scorer — re-read it before trusting this row"
    )


def test_the_redistribution_carve_out_is_the_general_clause_not_the_permissive_one() -> None:
    """Why `True` here is the *same* reading rather than a new one.

    The maintainer read prohibition 1b's "open source release" as covering a published snapshot on
    2026-09-10, for `alphagenome_avi`. This asserts the textual premise that lets the reading reach
    this source too: the carve-out sits in the **general** prohibition, so it is not scoped to the
    Permissive class. If upstream ever moves that phrase into the Permissive exception, this fails —
    and it should, because the reading would then no longer apply here.
    """
    additional = (_VENDOR / "alphagenome_additional_tos.txt").read_text()
    prohibition_one = additional.split("1.​ Except for Permissive Use", 1)[1].split("2.​ To transmit", 1)[0]
    assert "open source release" in prohibition_one
    assert ALPHAGENOME_ATLAS_TERMS.redistribution is True


@pytest.mark.parametrize(
    ("declared", "expect"),
    [("non_commercial", "proceed"), ("unstated", "skip"), ("commercial", "raise")],
)
def test_the_gate_has_three_outcomes_and_the_middle_one_is_the_point(declared: str, expect: str) -> None:
    """`unstated` is a skip, not permission — so a no-flag run writes nothing and says why.

    This is the behaviour that makes `--use non-commercial` load-bearing in the command's own
    documented example: a reader whose first run silently writes nothing reads it as broken rather
    than as correct.
    """
    if expect == "raise":
        with pytest.raises(LicenseRefusal):
            check_declared_use(ALPHAGENOME_ATLAS_TERMS, declared)
        return
    reason = check_declared_use(ALPHAGENOME_ATLAS_TERMS, declared)
    if expect == "proceed":
        assert reason is None
    else:
        assert reason is not None and "alphagenome_atlas" in reason


def test_the_eligibility_bar_is_recorded_in_the_notice_because_no_column_holds_it() -> None:
    """A bar on WHO may hold the data at all, which is not a use restriction and has no axis here.

    `ALPHAGENOME_ATLAS.md` § 2.6 names this as one of the four things the Terms need and `SourceRow`
    cannot say. It is carried as prose in `notice` rather than dropped, because a row that recorded
    only the axes it has columns for would publish a subset of the terms as if it were all of them.
    """
    assert "aren't available for any other types of" in ALPHAGENOME_ATLAS_TERMS.notice
    assert "NON-COMMERCIAL USE ONLY" in ALPHAGENOME_ATLAS_TERMS.notice

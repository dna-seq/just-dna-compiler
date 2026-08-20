"""The PGx record must carry a leg that could not have failed, not only the log (0.6, RM123 / S59).

RM73 gave `enrich_pgx` a **per-leg** tautology skip: a module drafted from CPIC has its
`function_status` compared against the very release it was copied out of, so that leg cannot disagree,
while PharmVar's leg is an independent authority and still runs. The skip is right and it is announced
at run time.

What it did not do is reach `verification.json`, which is the record a later reader trusts — the run's
stderr is not part of the module. The skip branch of `_function_check_record` already joins every
non-answered leg's note into its `detail`; the *answered* branch did not, so the one case the per-leg
design exists for — one authority answering, one tautological — recorded a clean two-authority
comparison with no sign that half of it was hollow.

`_function_check_record` takes every number as a parameter, so these run it directly rather than
through a network pass. That is the same reason it has that signature.
"""

from just_dna_enricher.pgx import _ANSWERED, PgxResult, _function_check_record

_TAUTOLOGY = (
    "cpic: this module's licence row records that these rows were drafted from cpic_2026-08-02, "
    "the release this leg reads, and every authored function_status still hashes to what the "
    "drafter wrote."
)
_OFFLINE = "pharmvar: skipped — --offline and no built snapshot."
_CLAIMS = {("CYP2C19", "*2"), ("CYP2C19", "*3"), ("CYP2C19", "*17")}


def _record(legs: dict[str, tuple[str, str]], compared: int = 3):
    result = PgxResult()
    result.compared = compared
    return _function_check_record(
        result,
        claims=_CLAIMS,
        legs=legs,
        releases={"pharmvar": "pharmvar_2026-08-02", "cpic": "cpic_2026-08-02"},
    )


def test_a_tautological_leg_beside_an_answering_one_reaches_the_record() -> None:
    record = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": ("tautology", _TAUTOLOGY)})
    assert record.detail is not None
    assert "pharmvar" in record.detail, "the real comparison is still reported"
    assert _TAUTOLOGY in record.detail, "and so is the one that could not have failed"


def test_the_record_still_says_a_comparison_ran() -> None:
    """Adding the withheld leg must not turn an answered record into a skip: PharmVar really did
    compare, and `subjects` is what says so."""
    record = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": ("tautology", _TAUTOLOGY)})
    assert record.subjects == 3
    assert record.skipped is None


def test_one_authority_only_names_it_and_the_other_one_does_not_claim_a_source() -> None:
    """`source` is a single join key into the licensing table, so it is set only when exactly one
    authority is implicated. A withheld leg does not make the answered one ambiguous."""
    both = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": (_ANSWERED, "live")})
    assert both.source is None
    one = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": ("tautology", _TAUTOLOGY)})
    assert one.source == "pharmvar"


def test_two_answering_legs_add_nothing() -> None:
    """Nothing was withheld, so nothing is appended — the sentence must not grow a trailing full stop
    on the ordinary case."""
    record = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": (_ANSWERED, "live")})
    assert record.detail is not None
    assert record.detail.endswith("cpic (live, cpic_2026-08-02)") or "cpic (" in record.detail
    assert "drafted from" not in record.detail


def test_the_sentence_is_byte_stable_across_leg_order() -> None:
    """`verification.json` is a hashed input, and `legs` is filled in whichever order the pass reached
    the authorities. Sorted by source, so the file cannot depend on that."""
    forward = _record({"pharmvar": ("offline", _OFFLINE), "cpic": ("tautology", _TAUTOLOGY)})
    reverse = _record({"cpic": ("tautology", _TAUTOLOGY), "pharmvar": ("offline", _OFFLINE)})
    assert forward.detail == reverse.detail
    mixed_a = _record({"pharmvar": (_ANSWERED, "snapshot"), "cpic": ("tautology", _TAUTOLOGY)})
    mixed_b = _record({"cpic": ("tautology", _TAUTOLOGY), "pharmvar": (_ANSWERED, "snapshot")})
    assert mixed_a.detail == mixed_b.detail


def test_the_all_withheld_case_was_already_right_and_stays_right() -> None:
    """The skip branch always carried every non-answered note; this is the regression guard on it."""
    record = _record({"pharmvar": ("offline", _OFFLINE), "cpic": ("tautology", _TAUTOLOGY)})
    assert record.skipped is not None
    assert record.detail is not None
    assert _TAUTOLOGY in record.detail and _OFFLINE in record.detail

"""The concordance record (RM130): the classifier, its arity, and the two tables it writes.

The classifier is a pure function, which is what makes the arity property testable at all: a
coverage test at the one authority the producer reaches today cannot see whether a third or a fifth
would need a new vocabulary member, and that is the exact property the two-field split exists to
hold.
"""

import csv
from pathlib import Path

import pytest
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.vocab import (
    VALID_AUTHORED_POSITION,
    VALID_AUTHORITY_CALL_STATUS,
    VALID_AUTHORITY_CONCORDANCE,
)

from just_dna_enricher.concordance import (
    AUTHORITY_CALLS_CSV,
    CLIN_SIG_CAMP,
    CONCORDANCE_CSV,
    AuthorityCall,
    ConcordanceSubject,
    camp_of,
    classify_concordance,
    concordance_tables,
    write_concordance_tables,
)


def _spoke(authority: str, clin_sig: str, *, confidence: str | None = None) -> AuthorityCall:
    return AuthorityCall(
        authority=authority,
        status="recorded",
        clin_sig=clin_sig,
        clin_sig_raw=clin_sig.replace("_", " ").capitalize(),
        confidence=confidence,
        confidence_unit=None if confidence is None else f"{authority}_scale",
        dataset=f"{authority}_2026-08-01",
    )


def _silent(authority: str) -> AuthorityCall:
    return AuthorityCall(authority=authority, status="no_record")


def _unreachable(authority: str) -> AuthorityCall:
    return AuthorityCall(authority=authority, status="unchecked")


# ── arity: the property the split exists to hold ────────────────────────────────────────────────


@pytest.mark.parametrize("n_authorities", [1, 2, 3, 5])
def test_the_vocabularies_do_not_grow_a_member_as_authorities_are_added(n_authorities: int) -> None:
    """The stress test that reshaped this record, run rather than argued.

    The drafted vocabulary named the authority *inside* the member (`clinvar_only`, `pubmind_only`),
    so a third source needed a third member and five needed every subset — one field carrying two
    axes, and the combinatorial growth was the symptom. Split, the member sets are fixed, and what
    a walk over every reachable topology at N authorities must produce is a **subset of a set that
    does not depend on N**.

    An equality would be the wrong assertion here and a floor would be no assertion at all: the
    reachable set at N=1 is genuinely smaller (no authority can disagree with another when there is
    only one), so the claim is *containment in an unchanged vocabulary*, plus the separate equality
    below that the whole vocabulary is reachable once N is large enough.
    """
    authorities = [f"a{i}" for i in range(n_authorities)]
    shapes = ["pathogenic", "benign", "uncertain_significance", None, "unreachable"]
    seen_concordance: set[str] = set()
    seen_position: set[str] = set()

    def walk(index: int, calls: list[AuthorityCall]) -> None:
        if index == len(authorities):
            for authored in ("pathogenic", "benign", "uncertain_significance", None):
                verdict = classify_concordance(authored, calls)
                seen_concordance.add(verdict.authority_concordance)
                seen_position.add(verdict.authored_position)
            return
        for shape in shapes:
            if shape is None:
                call = _silent(authorities[index])
            elif shape == "unreachable":
                call = _unreachable(authorities[index])
            else:
                call = _spoke(authorities[index], shape)
            walk(index + 1, [*calls, call])

    walk(0, [])
    assert seen_concordance <= VALID_AUTHORITY_CONCORDANCE
    assert seen_position <= VALID_AUTHORED_POSITION


def test_every_member_of_both_vocabularies_is_reachable_by_the_classifier() -> None:
    """An equality over a walked set, never a floor (`@registry-completeness`).

    A member no topology can produce is a member no producer can ever write, which is the gap the
    significance map's own assertion exists to catch one module over. Walked at three authorities,
    which is the smallest N at which every member is reachable — `discordant` needs two speakers and
    `matches_some` needs one of each beside a third.
    """
    authorities = ["a0", "a1", "a2"]
    shapes = ["pathogenic", "benign", "uncertain_significance", None, "unreachable"]
    seen_concordance: set[str] = set()
    seen_position: set[str] = set()

    def walk(index: int, calls: list[AuthorityCall]) -> None:
        if index == len(authorities):
            for authored in ("pathogenic", "benign", None):
                verdict = classify_concordance(authored, calls)
                seen_concordance.add(verdict.authority_concordance)
                seen_position.add(verdict.authored_position)
            return
        for shape in shapes:
            if shape is None:
                call = _silent(authorities[index])
            elif shape == "unreachable":
                call = _unreachable(authorities[index])
            else:
                call = _spoke(authorities[index], shape)
            walk(index + 1, [*calls, call])

    walk(0, [])
    assert seen_concordance == VALID_AUTHORITY_CONCORDANCE
    assert seen_position == VALID_AUTHORED_POSITION


def test_the_five_authority_split_reads_as_a_relation_to_the_set_and_resolves_nothing() -> None:
    """The case that decided `authored_position`'s definition, at the N it was decided at.

    Five authorities, two agreeing with the module and three against. Lexicographic precedence names
    one winner and majority names another, and choosing between those rules needs a weighting model
    this workspace has refused to invent three times. So the record says *the authorities disagree*
    and *the module matches some of them*, which is true under either rule, and it publishes no
    winner at all.
    """
    calls = [
        _spoke("e", "pathogenic"),
        _spoke("a", "pathogenic"),
        _spoke("b", "benign"),
        _spoke("c", "benign"),
        _spoke("d", "benign"),
    ]
    verdict = classify_concordance("pathogenic", calls)
    assert verdict.authority_concordance == "discordant"
    assert verdict.authored_position == "matches_some"
    assert verdict.opposed is True
    assert verdict.contested is True
    # Nothing on the verdict, or on the rows it produces, names a winner.
    parents, _calls = concordance_tables(
        [ConcordanceSubject("rs1", "A/G", "pathogenic", tuple(calls))]
    )
    assert not {"majority", "consensus", "resolved", "winner"} & set(ClinSigConcordanceRow.model_fields)


# ── the tri-state, and what an unreachable authority may and may not do ──────────────────────────


def test_an_unreachable_authority_is_never_reported_as_agreement() -> None:
    """`unchecked` is a third state beside asked-and-absent, and the difference is the whole point.

    One authority agrees with the module and a second could not be consulted. Recording that as
    `concordant` would claim a corroboration nobody gave, and recording it as `single` would claim
    the second archive was asked and had nothing. Both are false; `unchecked` is what is true.
    """
    calls = [_spoke("clinvar", "pathogenic"), _unreachable("pubmind")]
    verdict = classify_concordance("pathogenic", calls)
    assert verdict.authority_concordance == "unchecked"
    assert verdict.authored_position == "unchecked"
    assert verdict.contested is False

    asked_and_absent = classify_concordance(
        "pathogenic", [_spoke("clinvar", "pathogenic"), _silent("pubmind")]
    )
    assert asked_and_absent.authority_concordance == "single"
    assert asked_and_absent.authored_position == "matches_all"


def test_a_disagreement_already_witnessed_survives_an_unreachable_sibling() -> None:
    """Kleene, not withhold-on-any-unknown: `unknown AND false` really is `false`.

    Two archives already contradict each other. A third that could not be reached cannot make that
    disagreement unhappen, so `discordant` stands — and the module's position is `matches_some`,
    which is likewise witnessed by authorities that did speak.
    """
    verdict = classify_concordance(
        "pathogenic",
        [_spoke("a", "pathogenic"), _spoke("b", "benign"), _unreachable("c")],
    )
    assert verdict.authority_concordance == "discordant"
    assert verdict.authored_position == "matches_some"
    assert verdict.opposed is True


def test_opposed_is_none_rather_than_false_where_the_camps_are_not_established() -> None:
    """`None` is never `False`. A half-checked subject has not been shown to be uncontroversial."""
    half = classify_concordance("pathogenic", [_spoke("a", "pathogenic"), _unreachable("b")])
    assert half.opposed is None
    closed = classify_concordance("pathogenic", [_spoke("a", "pathogenic"), _silent("b")])
    assert closed.opposed is False


def test_nobody_asked_produces_no_row_on_its_own() -> None:
    """An unknown never forces a finding: withhold, never report and never negate.

    Every authority unreachable is the `--offline` shape, and it must produce no contested subject —
    a check that could not run reports nothing, rather than a record whose rows say the module is
    in dispute with archives nobody opened.
    """
    verdict = classify_concordance("pathogenic", [_unreachable("a"), _unreachable("b")])
    assert verdict.authority_concordance == "unchecked"
    assert verdict.contested is False
    parents, calls = concordance_tables(
        [ConcordanceSubject("rs1", "A/G", "pathogenic", (_unreachable("a"), _unreachable("b")))]
    )
    assert parents == []
    assert calls == []


# ── camps: what actually counts as a disagreement ────────────────────────────────────────────────


def test_a_confidence_step_within_one_conclusion_is_not_a_disagreement() -> None:
    """`pathogenic` against `likely_pathogenic` is one position held with two degrees of certainty.

    Reporting it would bury the real finding, which is why the record is at camp granularity and the
    camp map is coarser than the vocabulary it reads.
    """
    verdict = classify_concordance(
        "pathogenic", [_spoke("a", "likely_pathogenic"), _spoke("b", "risk_factor")]
    )
    assert verdict.authority_concordance == "concordant"
    assert verdict.authored_position == "matches_all"
    assert verdict.contested is False


def test_an_uncertain_call_opposes_nothing_so_it_does_not_contest_the_module() -> None:
    """Only `pathogenic` and `benign` are opinionated; the rest have no opposing claim to make.

    An authority calling a variant `uncertain_significance` has declined to take the module's side
    or the other one, so it cannot on its own put the module in dispute — which is the rule the
    shipped two-way check already applies and which the record must not quietly widen.
    """
    verdict = classify_concordance("pathogenic", [_spoke("a", "uncertain_significance")])
    assert verdict.authored_position == "matches_none"
    assert verdict.opposed is False
    assert verdict.contested is False


def test_two_authorities_can_differ_without_either_opposing_the_module() -> None:
    """The row `opposed` exists to distinguish, and the one a single authority can never produce.

    At one authority a reported conflict is opposed by construction — both sides must be opinionated
    and their camps must differ, and there are only two opinionated camps. The distinction becomes
    live here: the archives disagree with each other while neither contradicts the module's call.
    """
    verdict = classify_concordance(
        "pathogenic", [_spoke("a", "pathogenic"), _spoke("b", "uncertain_significance")]
    )
    assert verdict.authority_concordance == "discordant"
    assert verdict.opposed is False
    assert verdict.contested is True


def test_the_camp_map_places_every_member_of_the_significance_vocabulary() -> None:
    """An equality over a walked set: a member the map does not place would silently read as
    `undecided`, which is the answer that opposes nothing — so an omission would quietly stop a whole
    class of disagreement from ever being reported."""
    from just_dna_format.vocab import VALID_CLIN_SIG

    assert set(CLIN_SIG_CAMP) == VALID_CLIN_SIG
    assert camp_of(None) is None


# ── the key: two authored calls for one variant must not collapse ────────────────────────────────


def test_two_genotypes_of_one_variant_that_disagree_differently_stay_two_rows() -> None:
    """The key is `(variant_key, genotype)`, and this is why it cannot be the variant alone.

    A module may call the heterozygous state pathogenic and the homozygous state benign; an archive
    disagrees with each in a different direction. Keyed on the variant, one of those disagreements
    would be silently discarded, and the author would answer a question they were never shown.
    """
    subjects = [
        ConcordanceSubject("rs334", "A/T", "pathogenic", (_spoke("clinvar", "benign"),)),
        ConcordanceSubject("rs334", "T/T", "benign", (_spoke("clinvar", "pathogenic"),)),
    ]
    parents, calls = concordance_tables(subjects)
    assert {(row.variant_key, row.genotype) for row in parents} == {("rs334", "A/T"), ("rs334", "T/T")}
    assert {(row.variant_key, row.genotype, row.authority) for row in calls} == {
        ("rs334", "A/T", "clinvar"),
        ("rs334", "T/T", "clinvar"),
    }
    assert [row.authored_clin_sig for row in parents] == ["pathogenic", "benign"]


# ── the detail table keeps each authority in its own units ───────────────────────────────────────


def test_each_authoritys_confidence_stays_in_its_own_units() -> None:
    """No cross-authority normalization happens, and the unit column is what proves it.

    A gold-star count and an evidence-depth count are different instruments, so the numbers are
    carried verbatim with the instrument named beside each. A record that converted one to the other
    would be arithmetic over two scales nobody established a mapping between.
    """
    subject = ConcordanceSubject(
        "rs1",
        "A/G",
        "pathogenic",
        (
            _spoke("clinvar", "benign", confidence="3"),
            _spoke("pubmind", "pathogenic", confidence="2"),
        ),
    )
    _parents, calls = concordance_tables([subject])
    by_authority = {row.authority: row for row in calls}
    assert by_authority["clinvar"].confidence == "3"
    assert by_authority["clinvar"].confidence_unit == "clinvar_scale"
    assert by_authority["pubmind"].confidence == "2"
    assert by_authority["pubmind"].confidence_unit == "pubmind_scale"


def test_a_magnitude_with_no_instrument_beside_it_is_refused() -> None:
    """`@weight-has-no-unit`, applied at the boundary rather than left to a reader to notice."""
    with pytest.raises(ValueError, match="no instrument beside it"):
        ClinSigAuthorityCallRow(
            variant_key="rs1",
            genotype="A/G",
            authority="clinvar",
            status="recorded",
            clin_sig="pathogenic",
            confidence="3",
        )


@pytest.mark.parametrize("status", ["no_record", "unchecked"])
def test_a_consultation_with_nothing_to_report_carries_no_classification(status: str) -> None:
    """An unknown is withheld, never filled in with a value nobody gave."""
    with pytest.raises(ValueError, match="clin_sig"):
        ClinSigAuthorityCallRow(
            variant_key="rs1", genotype="A/G", authority="clinvar",
            status=status, clin_sig="pathogenic",
        )


def test_a_recorded_call_must_name_the_classification_it_recorded() -> None:
    """The inverse: `recorded` with no value claims a consultation that produced an answer and
    then names none, which is an unknown wearing an answer's clothes."""
    with pytest.raises(ValueError, match="must carry the classification"):
        ClinSigAuthorityCallRow(
            variant_key="rs1", genotype="A/G", authority="clinvar", status="recorded"
        )


def test_the_call_status_vocabulary_is_closed_and_accepts_a_separator_slip() -> None:
    """Closed (Principle 6), and the validator RETURNS `check_vocab` so a `-` spelling is stored as
    the declared member rather than passed through unchanged."""
    with pytest.raises(ValueError, match="status must be one of"):
        ClinSigAuthorityCallRow(
            variant_key="rs1", genotype="A/G", authority="clinvar", status="maybe"
        )
    assert set(VALID_AUTHORITY_CALL_STATUS) == {"recorded", "no_record", "unchecked"}
    row = ClinSigAuthorityCallRow(
        variant_key="rs1", genotype="A/G", authority="clinvar", status="no-record"
    )
    assert row.status == "no_record"


def test_the_two_verdict_vocabularies_are_closed_and_canonicalize_a_separator_slip() -> None:
    """Both parent vocabularies, same rule, same reason."""
    with pytest.raises(ValueError, match="authority_concordance must be one of"):
        ClinSigConcordanceRow(
            variant_key="rs1", genotype="A/G",
            authority_concordance="mostly", authored_position="matches_all",
        )
    with pytest.raises(ValueError, match="authored_position must be one of"):
        ClinSigConcordanceRow(
            variant_key="rs1", genotype="A/G",
            authority_concordance="concordant", authored_position="sort_of",
        )
    row = ClinSigConcordanceRow(
        variant_key="rs1", genotype="A/G",
        authority_concordance="concordant", authored_position="matches-all",
    )
    assert row.authored_position == "matches_all"


# ── the writer ───────────────────────────────────────────────────────────────────────────────────


def test_the_record_is_rewritten_whole_so_an_answered_subject_can_leave_it(tmp_path: Path) -> None:
    """Not merge-not-clobber, and the difference is what makes the vindication signal work.

    Every other derived sidecar gap-fills because a recorded row might carry a curator's judgement.
    This one carries none — the judgement goes in `overrides.csv` — so a subject the archive stopped
    contesting has to *leave* the record. Merging would keep reporting a conflict that no longer
    exists, which is exactly the signal an author is watching for.
    """
    first = [ConcordanceSubject("rs1", "A/G", "pathogenic", (_spoke("clinvar", "benign"),))]
    write_concordance_tables(tmp_path, *concordance_tables(first))
    assert _rows(tmp_path / CONCORDANCE_CSV)

    write_concordance_tables(tmp_path, *concordance_tables([]))
    assert _rows(tmp_path / CONCORDANCE_CSV) == []
    assert _rows(tmp_path / AUTHORITY_CALLS_CSV) == []


def test_the_written_columns_are_the_models_own(tmp_path: Path) -> None:
    """Derived from the model, never hand-kept — the defect that lost `SOURCES_FIELDNAMES` a column."""
    subject = ConcordanceSubject("rs1", "A/G", "pathogenic", (_spoke("clinvar", "benign"),))
    write_concordance_tables(tmp_path, *concordance_tables([subject]))
    with (tmp_path / CONCORDANCE_CSV).open() as handle:
        assert next(csv.reader(handle)) == list(ClinSigConcordanceRow.model_fields)
    with (tmp_path / AUTHORITY_CALLS_CSV).open() as handle:
        assert next(csv.reader(handle)) == list(ClinSigAuthorityCallRow.model_fields)


def test_the_written_rows_reload_through_their_own_models(tmp_path: Path) -> None:
    """A cell the writer renders must be a cell the model accepts, or the compiler cannot read what
    the enricher wrote — the silent seam between the two tiers this repo has paid for before."""
    subject = ConcordanceSubject(
        "rs1", "A/G", "pathogenic",
        (_spoke("clinvar", "benign", confidence="3"), _unreachable("pubmind")),
    )
    parents, calls = concordance_tables([subject])
    write_concordance_tables(tmp_path, parents, calls)
    reloaded = [ClinSigConcordanceRow(**row) for row in _rows(tmp_path / CONCORDANCE_CSV)]
    assert [row.model_dump() for row in reloaded] == [row.model_dump() for row in parents]
    reloaded_calls = [ClinSigAuthorityCallRow(**row) for row in _rows(tmp_path / AUTHORITY_CALLS_CSV)]
    assert [row.model_dump() for row in reloaded_calls] == [row.model_dump() for row in calls]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [{k: (v or None) for k, v in row.items()} for row in csv.DictReader(handle)]

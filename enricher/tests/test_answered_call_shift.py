"""RM151 — an answer written about a value the archive has since changed, and nothing said so.

RM117 shipped one of two signals: an answered subject that has *left* the concordance record, which
is computable offline because the record holds contested subjects only and is rewritten whole. This
is the other one, and it is the harder half — it needs the archive's value **now** against its value
**at record time**, and the only baseline this format keeps is the previous run's
`clin_sig_authority_calls.csv`.

Two properties are load-bearing and both are pinned here. The comparison **withholds** rather than
negating wherever either side is unknown, which is the house algebra and the one way this check
could do real harm — telling an author their reasoning stands when nobody actually asked. And the
wording **observes rather than adjudicates**: the disagreement changed is a statement about the
record, *your answer was wrong* is a verdict, and this format does not put a verdict under a check
that cannot see the reasoning.
"""

import csv
import re
from pathlib import Path

import pytest
from just_dna_enricher.clinical import answered_call_shift
from just_dna_enricher.concordance import (
    AUTHORITY_CALLS_CSV,
    CONCORDANCE_CSV,
    VALID_CALL_SHIFT_WITHHELD,
    answered_call_notes,
    answered_call_sentences,
    read_recorded_calls,
    shifted_authority_calls,
    write_concordance_tables,
)
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.overrides import OVERRIDABLE_TABLES, OverrideRow

_KEY = "rs334"
_GENOTYPE = "A/T"


def _call(
    clin_sig: str | None,
    *,
    authority: str = "clinvar",
    status: str = "recorded",
    raw: str | None = None,
    dataset: str = "clinvar_2026-08-01",
    variant_key: str = _KEY,
    genotype: str = _GENOTYPE,
) -> ClinSigAuthorityCallRow:
    return ClinSigAuthorityCallRow(
        variant_key=variant_key,
        genotype=genotype,
        authority=authority,
        status=status,
        clin_sig=clin_sig,
        clin_sig_raw=raw if raw is not None else (clin_sig and clin_sig.replace("_", " ")),
        dataset=dataset,
        checked_at="2026-08-31T00:00:00Z",
    )


def _answer(
    *,
    variant_key: str = _KEY,
    member: str | None = _GENOTYPE,
    operation: str = "update",
    field: str | None = "authored_clin_sig",
    value: str | None = "pathogenic",
) -> OverrideRow:
    return OverrideRow(
        table=CONCORDANCE_CSV,
        subject=variant_key,
        member=member,
        field=field,
        operation=operation,
        value=value,
        reason="two panels call this pathogenic; the archive's benign call predates them",
        decided_by="curator",
        decided_at="2026-08-31",
    )


def _spec(tmp_path: Path, answers: list[OverrideRow], baseline: list[ClinSigAuthorityCallRow]) -> Path:
    """A spec directory carrying an overlay and a previous run's record.

    The record is written through the real writer rather than by hand, so the baseline this reads is
    byte-for-byte the file a previous `enrich` would have left — the whole check turns on that file
    being the one the author read.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    parents = [
        ClinSigConcordanceRow(
            variant_key=row.variant_key,
            genotype=row.genotype,
            authored_clin_sig="pathogenic",
            authority_concordance="single",
            authored_position="matches_none",
            opposed=True,
        )
        for row in baseline
    ]
    write_concordance_tables(spec, parents, baseline)
    if answers:
        with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(OverrideRow.model_fields))
            writer.writeheader()
            for row in answers:
                writer.writerow({k: ("" if v is None else v) for k, v in row.model_dump().items()})
    return spec


# ── the control: an answer nothing has moved under says nothing ─────────────────────────────────


def test_an_answer_whose_call_still_reads_the_same_is_silent(tmp_path: Path) -> None:
    """Without this, every test below could pass against a check that fires on any overlay row."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    report = answered_call_shift(spec, [_call("benign")])

    assert report.answered == 1
    assert report.subjects == 1
    assert not report.shifts
    assert answered_call_sentences(report) == []
    assert answered_call_notes(report) == []


def test_a_module_with_no_answers_reports_nothing_at_all(tmp_path: Path) -> None:
    """`@tautology-zero` — a check that cannot fire must not announce a zero."""
    spec = _spec(tmp_path, [], [_call("benign")])
    report = answered_call_shift(spec, [_call("likely_pathogenic")])

    assert report.answered == 0
    assert answered_call_sentences(report) == []
    assert answered_call_notes(report) == []


def test_a_re_released_archive_saying_the_same_thing_has_not_moved(tmp_path: Path) -> None:
    """The `dataset` changed and the call did not. The answer is about the same disagreement."""
    spec = _spec(tmp_path, [_answer()], [_call("benign", dataset="clinvar_2026-08-01")])
    report = answered_call_shift(spec, [_call("benign", dataset="clinvar_2026-09-01")])

    assert not report.shifts
    assert answered_call_sentences(report) == []


# ── the signal ──────────────────────────────────────────────────────────────────────────────────


def test_a_call_that_moved_under_an_answer_is_reported(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [_answer()], [_call("benign", dataset="clinvar_2026-08-01")])
    report = answered_call_shift(
        spec, [_call("likely_pathogenic", dataset="clinvar_2026-09-01")]
    )

    assert report.moved_subjects == 1
    assert report.subjects == 1
    (line,) = answered_call_sentences(report)
    assert "1 of 1 answered subject(s)" in line
    # Both datasets in the message, because that pair is what separates a re-released archive from
    # one that revised in place — the check does not branch on it, the reader does.
    assert "benign (clinvar_2026-08-01) → likely_pathogenic (clinvar_2026-09-01)" in line
    assert CONCORDANCE_CSV in line


def test_an_authority_that_withdrew_its_record_is_a_move(tmp_path: Path) -> None:
    """`recorded → no_record` is an established change: it was asked both times."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    report = answered_call_shift(spec, [_call(None, status="no_record")])

    assert report.moved_subjects == 1
    assert "→ no record" in str(report.shifts[0])


def test_an_authority_that_gained_a_record_is_a_move(tmp_path: Path) -> None:
    """The mirror of the above, and the reading is the same: the record is not what it was."""
    spec = _spec(tmp_path, [_answer()], [_call(None, status="no_record")])
    report = answered_call_shift(spec, [_call("benign")])

    assert report.moved_subjects == 1
    assert str(report.shifts[0]).startswith("rs334 A/T clinvar: no record (")
    assert "→ benign (" in str(report.shifts[0])


def test_both_sides_holding_no_record_is_not_a_move(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [_answer()], [_call(None, status="no_record")])
    report = answered_call_shift(spec, [_call(None, status="no_record")])

    assert not report.shifts
    assert report.subjects == 1


# ── withholding: the half that could do real harm ───────────────────────────────────────────────


def test_an_authority_unreachable_this_run_is_withheld_never_read_as_unchanged(
    tmp_path: Path,
) -> None:
    """`unknown` is not `false`. Reading an unasked question as *nothing moved* would tell an author
    their reasoning still stands on evidence nobody looked at — the one way this check does harm."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    report = answered_call_shift(spec, [_call(None, status="unchecked")])

    assert not report.shifts
    assert report.subjects == 0
    assert [reason for *_key, reason in report.withheld] == ["unchecked_now"]
    assert answered_call_sentences(report) == []
    notes = " ".join(answered_call_notes(report))
    assert "could not be compared" in notes
    assert "unknown" in notes


def test_a_first_run_with_no_prior_record_withholds_rather_than_agreeing(tmp_path: Path) -> None:
    """No baseline is *nobody asked at record time*, which is not the same claim as unchanged."""
    spec = tmp_path / "spec"
    spec.mkdir()
    with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OverrideRow.model_fields))
        writer.writeheader()
        row = _answer()
        writer.writerow({k: ("" if v is None else v) for k, v in row.model_dump().items()})

    assert read_recorded_calls(spec) is None
    report = answered_call_shift(spec, [_call("benign")])

    assert not report.shifts
    assert report.subjects == 0
    assert report.answered == 1
    notes = " ".join(answered_call_notes(report))
    assert "no prior" in notes and AUTHORITY_CALLS_CSV in notes
    assert [reason for *_key, reason in report.withheld] == ["no_prior_record"]


def test_an_authority_unchecked_at_record_time_is_no_baseline(tmp_path: Path) -> None:
    """A row recorded as `unchecked` is a row that said nothing, so there is nothing to move from."""
    spec = _spec(tmp_path, [_answer()], [_call(None, status="unchecked")])
    report = answered_call_shift(spec, [_call("benign")])

    assert not report.shifts
    assert [reason for *_key, reason in report.withheld] == ["no_prior_record"]


def test_a_run_that_consulted_nobody_still_says_the_answers_went_unexamined(tmp_path: Path) -> None:
    """`clin_sig_concordance` returns `None` when no authority could be consulted. Silence there
    would read as a clean bill over answers nothing checked."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    report = answered_call_shift(spec, None)

    assert report.answered == 1
    assert report.subjects == 0
    assert "could not be compared" in " ".join(answered_call_notes(report))


def test_an_unreadable_baseline_reads_as_unknown_rather_than_as_a_move(tmp_path: Path) -> None:
    """Guessing at a half-read baseline manufactures a movement out of our own failure to read."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    (spec / AUTHORITY_CALLS_CSV).write_text("variant_key,genotype\nrs334\n", encoding="utf-8")

    assert read_recorded_calls(spec) is None
    report = answered_call_shift(spec, [_call("likely_pathogenic")])
    assert not report.shifts
    assert report.subjects == 0


# ── the boundary with RM117 ─────────────────────────────────────────────────────────────────────


def test_a_subject_that_left_the_record_is_rm117s_finding_and_not_this_one(tmp_path: Path) -> None:
    """The authorities stopped contesting it — `overlay_answer_vindicated`, reported as good news by
    the compiler. Counting it here as a question nobody could put would hang a second, gloomier
    finding on the same overlay row."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    other = _call("benign", variant_key="rs1801133", genotype="C/T")
    report = answered_call_shift(spec, [other])

    assert report.answered == 0
    assert report.subjects == 0
    assert answered_call_sentences(report) == []
    assert answered_call_notes(report) == []


# ── the normalizer's own movement is not the archive's ──────────────────────────────────────────


def test_a_move_our_own_normalizer_made_is_reported_apart_from_the_archives(tmp_path: Path) -> None:
    """Same verbatim wording, different normalized member: this tier changed, not ClinVar. Reporting
    it as an archive revision would accuse a source of a change we made."""
    spec = _spec(tmp_path, [_answer()], [_call("uncertain_significance", raw="Conflicting data")])
    report = answered_call_shift(spec, [_call("conflicting", raw="Conflicting data")])

    assert not report.shifts
    assert len(report.normalization) == 1
    (line,) = answered_call_sentences(report)
    assert "normalization" in line
    assert "nothing for an author to do" in line


# ── what counts as an answer ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "row",
    [
        _answer(operation="update", field="authored_clin_sig"),
        _answer(operation="update", field="authority_concordance", value="discordant"),
        _answer(operation="suppress", field=None, value=None, member=_GENOTYPE),
    ],
    ids=["update-the-call", "update-another-cell", "suppress"],
)
def test_any_overlay_row_naming_the_subject_is_an_answer(tmp_path: Path, row: OverrideRow) -> None:
    """What goes stale is the `reason`, and the model makes it mandatory on every row whatever the
    row does — so the rule consults neither `operation` nor `field`."""
    spec = _spec(tmp_path, [row], [_call("benign")])
    report = answered_call_shift(spec, [_call("likely_pathogenic")])

    assert report.moved_subjects == 1


def test_a_group_scoped_answer_covers_every_genotype_on_the_record(tmp_path: Path) -> None:
    """`member` is `genotype` here, and an empty one is group-scoped over the `variant_key`. The
    genotypes are known only from the record, which is why the expansion happens at the driver."""
    baseline = [_call("benign", genotype="A/T"), _call("benign", genotype="T/T")]
    spec = _spec(tmp_path, [_answer(member=None)], baseline)
    report = answered_call_shift(
        spec, [_call("likely_pathogenic", genotype="A/T"), _call("likely_pathogenic", genotype="T/T")]
    )

    assert report.answered == 2
    assert report.moved_subjects == 2


def test_an_answer_naming_one_genotype_leaves_the_other_alone(tmp_path: Path) -> None:
    baseline = [_call("benign", genotype="A/T"), _call("benign", genotype="T/T")]
    spec = _spec(tmp_path, [_answer(member="A/T")], baseline)
    report = answered_call_shift(
        spec, [_call("likely_pathogenic", genotype="A/T"), _call("likely_pathogenic", genotype="T/T")]
    )

    assert report.answered == 1
    assert [shift.subject for shift in report.shifts] == [(_KEY, "A/T")]


# ── the wording, and the scope it must state ────────────────────────────────────────────────────


#: Words that grade the author's judgement rather than describing the record. The finding is an
#: observation — *the disagreement you answered is not the one on record now* — and the moment it
#: says *your answer was wrong* it is a verdict passed by a check that cannot see the reasoning.
#: RM117's first draft said exactly that while claiming not to, which is why this is a test and not a
#: convention. Matched on a word boundary: "unchecked" contains no verdict, and neither does
#: "recorded".
_ADJUDICATING = (
    "correct", "incorrect", "right", "wrong", "mistaken", "invalid",
    "vindicated", "proved", "disproved", "confirmed", "refuted",
)


def _messages(tmp_path: Path) -> list[str]:
    spec = _spec(tmp_path, [_answer()], [_call("benign", raw="Benign")])
    moved = answered_call_shift(spec, [_call("likely_pathogenic", raw="Likely pathogenic")])
    normalized_spec = _spec(
        tmp_path / "b", [_answer()], [_call("uncertain_significance", raw="Conflicting data")]
    )
    normalized = answered_call_shift(normalized_spec, [_call("conflicting", raw="Conflicting data")])
    unreachable = answered_call_shift(
        _spec(tmp_path / "c", [_answer()], [_call("benign")]), [_call(None, status="unchecked")]
    )
    return [
        *answered_call_sentences(moved),
        *answered_call_sentences(normalized),
        *answered_call_notes(unreachable),
        *answered_call_notes(answered_call_shift(_spec(tmp_path / "d", [_answer()], []), None)),
    ]


def test_no_message_grades_the_authors_judgement(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    (tmp_path / "d").mkdir()
    messages = _messages(tmp_path)
    assert messages, "the probe must actually produce messages, or this asserts nothing"
    for message in messages:
        for word in _ADJUDICATING:
            assert not re.search(rf"\b{word}\b", message, re.IGNORECASE), (word, message)


def test_the_finding_names_the_one_table_it_is_answerable_for(tmp_path: Path) -> None:
    """`@probe-names-the-table`. An overlay row against `frequencies.csv` or `resolution.csv` has no
    recorded prior value at all, so a general "the value moved" check would be answerable for one
    table and silently absent for every other. An unscoped negative becomes a false constraint."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    (line,) = answered_call_sentences(answered_call_shift(spec, [_call("likely_pathogenic")]))
    assert CONCORDANCE_CSV in line


# ── the guards ──────────────────────────────────────────────────────────────────────────────────


def test_every_withheld_reason_is_reachable_and_the_registry_is_exactly_those(tmp_path: Path) -> None:
    """`@registry-completeness` — an equality over a walked set, never a floor. A third reason must
    arrive with a note attached rather than silently joining the states that say nothing."""
    (tmp_path / "b").mkdir()
    reached = set()
    for name, baseline, fresh in (
        ("b", [_call(None, status="unchecked")], [_call("benign")]),
        ("c", [_call("benign")], [_call(None, status="unchecked")]),
    ):
        directory = tmp_path / name
        if not directory.exists():
            directory.mkdir()
        report = answered_call_shift(_spec(directory, [_answer()], baseline), fresh)
        reached.update(reason for *_key, reason in report.withheld)
    assert reached == VALID_CALL_SHIFT_WITHHELD


def test_the_overlay_key_and_the_record_key_share_one_canonical_form() -> None:
    """The comparison matches an overlay's `subject`/`member` straight against the record's cells.

    That is only sound while both sides canonicalize a key the same way. `OverrideRow` strips its key
    columns and both concordance models strip theirs, so the canonical form is the stripped string on
    both sides and no per-column rule is needed (`@overlay-not-inside`). This asserts the *models'*
    own answers agree — the day either grows a normalizer, as `FrequencyRow.population` did, this
    fails and points at the canonicalization the driver would then owe.
    """
    target = OVERRIDABLE_TABLES[CONCORDANCE_CSV]
    for raw in (" rs334 ", "rs334", "A/T ", " 0/1"):
        overlay = OverrideRow(
            table=CONCORDANCE_CSV, subject=raw, member=raw, field="authored_clin_sig",
            operation="update", value="pathogenic", reason="probe",
        )
        record = ClinSigAuthorityCallRow(
            variant_key=raw, genotype=raw, authority="clinvar", status="unchecked"
        )
        assert overlay.subject == getattr(record, target.subject_field)
        assert overlay.member == getattr(record, target.member_field)


def test_the_baseline_is_read_before_the_commit_rewrites_it(tmp_path: Path) -> None:
    """The whole check rests on the previous run's file still being on disk when it is read. This
    pins the ordering the way `@enrich-is-a-transaction` pins the rest of the commit: it asserts on
    the bytes, by writing the new record and showing the comparison then reports nothing."""
    spec = _spec(tmp_path, [_answer()], [_call("benign")])
    fresh = [_call("likely_pathogenic")]

    before_commit = answered_call_shift(spec, fresh)
    write_concordance_tables(spec, [], fresh)
    after_commit = answered_call_shift(spec, fresh)

    assert before_commit.moved_subjects == 1
    assert after_commit.moved_subjects == 0


def test_the_pure_comparison_needs_no_files_at_all() -> None:
    """`shifted_authority_calls` is a pure function over two sequences, which is what lets it be
    exercised at shapes no producer reaches today."""
    report = shifted_authority_calls(
        [_call("benign"), _call("benign", authority="pubmind", dataset="pubmind_2026-07")],
        [_call("benign"), _call("pathogenic", authority="pubmind", dataset="pubmind_2026-09")],
        [(_KEY, _GENOTYPE)],
    )
    assert [shift.authority for shift in report.shifts] == ["pubmind"]
    assert report.subjects == 1
    assert report.moved_subjects == 1


# ── the wiring: where in the run this happens ───────────────────────────────────────────────────


_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_SPEC_VARIANTS = "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n"


def _enrich_spec(tmp_path: Path, *, with_answer: bool) -> Path:
    spec = tmp_path / "run"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_SPEC_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_SPEC_VARIANTS, encoding="utf-8")
    if with_answer:
        row = _answer(variant_key="rs1801133", member="A/G")
        with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(OverrideRow.model_fields))
            writer.writeheader()
            writer.writerow({k: ("" if v is None else v) for k, v in row.model_dump().items()})
    return spec


def _run(spec: Path, tmp_path: Path, **kwargs):
    """`enrich` with every network-touching pass off and no cache to find."""
    from just_dna_enricher.enrich import enrich

    defaults = {
        "ensembl_cache": tmp_path / "no-ensembl-cache",
        "clinvar_cache": tmp_path / "no-clinvar-cache",
        "download": False,
        "use_gnomad": False,
        "mint_vrs": False,
        "verify_ref": False,
        "verify_clinsig": True,
        "verify_rsids": False,
    }
    defaults.update(kwargs)
    return enrich(spec, **defaults)


def test_a_run_that_could_consult_nobody_still_counts_the_answers_it_did_not_examine(
    tmp_path: Path,
) -> None:
    """End to end with no snapshot to read: the record is `None`, and silence there would be a clean
    bill issued over an answer nothing checked."""
    result = _run(_enrich_spec(tmp_path, with_answer=True), tmp_path)

    assert result.answered_calls is not None
    assert result.answered_calls.answered == 1
    assert result.answered_calls.subjects == 0
    assert "could not be compared" in " ".join(answered_call_notes(result.answered_calls))


def test_a_run_with_no_answers_carries_an_empty_report_rather_than_a_finding(
    tmp_path: Path,
) -> None:
    result = _run(_enrich_spec(tmp_path, with_answer=False), tmp_path)

    assert result.answered_calls is not None
    assert result.answered_calls.answered == 0
    assert answered_call_notes(result.answered_calls) == []


def test_the_clin_sig_off_switch_turns_this_off_too(tmp_path: Path) -> None:
    """`@off-switch-needs-a-probe` — run the disabling value rather than reading it. An author who
    turned the clinical check off did not ask for a comparison of its answers, and `None` here is
    *not asked*, which is never *nothing moved*."""
    result = _run(_enrich_spec(tmp_path, with_answer=True), tmp_path, verify_clinsig=False)

    assert result.answered_calls is None


def test_the_run_reads_the_baseline_before_the_commit_overwrites_it() -> None:
    """The one ordering the whole check rests on, guarded where a refactor would break it.

    `enrich()` computes everything above its commit and writes below it, so the previous run's record
    is still on disk when the comparison reads it. That is a property of statement order inside one
    function, which no assertion over a return value can see — so it is walked, the way the exception
    contract's shape guard is (`@client-exception-contract`). Moving the read below
    `write_concordance_tables` would leave every test above green and the check permanently silent.
    """
    import ast
    import inspect

    from just_dna_enricher import enrich as enrich_module

    tree = ast.parse(inspect.getsource(enrich_module))
    # Found by the call it must precede rather than by the enclosing function's name: the pipeline
    # has been a private helper behind the public `enrich` since before this check existed, and a
    # test naming that helper would go green by finding nothing the day it is renamed.
    lines = {"answered_call_shift": [], "write_concordance_tables": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in lines:
            lines[node.func.id].append(node.lineno)
    assert lines["answered_call_shift"], "the comparison is not called from the run at all"
    assert lines["write_concordance_tables"], "the commit no longer writes the record"
    assert max(lines["answered_call_shift"]) < min(lines["write_concordance_tables"])

    enclosing = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.lineno <= lines["answered_call_shift"][0] <= (node.end_lineno or 0)
        and any(
            node.lineno <= line <= (node.end_lineno or 0)
            for line in lines["write_concordance_tables"]
        )
    ]
    assert enclosing, "the read and the write are in different functions, so their order is not fixed"

"""An answered conflict the archive has since resolved is good news, and used to read as a typo (RM117).

S52 asked for a check that reads the record an author writes when their value deliberately beats a
source's. The severity half of that was closed — putting a checked verdict under authored control is
something nothing else in this format does — and what stayed was the observability half: two signals
the compiler can compute without asking anyone's permission. **This is the first of them**, recast
onto `overrides.csv` rather than `provenance.json`'s `outranks`, because 0.7 settled that overlap as a
dated succession and `outranks` is filed for removal at the major (RM135). The second signal needs a
fresh archive call and is filed as RM151.

**The signal was already firing, with the wrong words on it.** `clin_sig_concordance.csv` holds
*contested* subjects only and is rewritten whole by the enricher — `concordance.py` says outright that
a subject leaving the record is how an author learns the archive caught up with them. So an overlay row
answering a conflict that has since resolved reaches nothing, and before this it drew the generic
finding: *the subject may be mistyped, or the correction may be aimed at a row the compiler drops*.
That sentence was put to an author in the one case where their judgement had just been confirmed.

**It is an observation, not a verdict.** The authorities agreed; the overlay row is now unnecessary.
Whether the author was right about the biology is not something a compiler can say, and this does not
say it.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.overrides import VINDICATING_OVERLAY_TABLE
from just_dna_format.vocab import ACTIONABLE_WARNING_CODES, VALID_WARNING_CODES

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_CONCORDANCE_HEADER = (
    "variant_key,genotype,authored_clin_sig,authority_concordance,authored_position,opposed,"
    "checked_at\n"
)
_CALLS_HEADER = (
    "variant_key,genotype,authority,status,clin_sig,clin_sig_raw,confidence,confidence_unit,"
    "dataset,checked_at\n"
)
_OVERLAY_HEADER = [
    "table", "subject", "member", "field", "operation", "value", "reason", "decided_by",
    "decided_at",
]
_VINDICATED = "no longer contested"
_GENERIC = "may be mistyped"


def _example(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / name, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    return spec


def _subjects(spec: Path, limit: int = 2) -> list[tuple[str, str]]:
    with (spec / "variants.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen: list[tuple[str, str]] = []
    for row in rows:
        key = (row.get("variant_key") or row.get("rsid") or "").strip()
        genotype = (row.get("genotype") or "").strip()
        if key and genotype and (key, genotype) not in seen:
            seen.append((key, genotype))
        if len(seen) == limit:
            break
    assert len(seen) == limit, "the fixture example must carry enough authored subjects"
    return seen


def _write_record(spec: Path, subjects: list[tuple[str, str]]) -> None:
    """One contested subject per pair — the shape the enricher writes."""
    concordance = [_CONCORDANCE_HEADER]
    calls = [_CALLS_HEADER]
    for key, genotype in subjects:
        concordance.append(
            f"{key},{genotype},pathogenic,single,matches_none,true,2026-08-28T00:00:00Z\n"
        )
        calls.append(
            f"{key},{genotype},clinvar,recorded,benign,Benign,3,review_stars,"
            f"clinvar_2026-08-01,2026-08-28T00:00:00Z\n"
        )
    (spec / "clin_sig_concordance.csv").write_text("".join(concordance), encoding="utf-8")
    (spec / "clin_sig_authority_calls.csv").write_text("".join(calls), encoding="utf-8")


def _write_overlay(spec: Path, rows: list[list[str]]) -> None:
    with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_OVERLAY_HEADER)
        writer.writerows(rows)


def _answer(key: str, genotype: str) -> list[str]:
    return [
        "clin_sig_concordance.csv", key, genotype, "authored_clin_sig", "update", "pathogenic",
        "two panels call this pathogenic; the archive's benign call predates them",
        "curator", "2026-08-31",
    ]


# ── the control: an answer to a live conflict says nothing ──────────────────────────────────────


def test_an_answer_to_a_conflict_that_still_exists_is_silent(tmp_path: Path) -> None:
    """The subject is in the record, the overlay matches it, and there is nothing to report.

    Without this the test below could pass against a check that fires on every overlay row.
    """
    spec = _example(tmp_path)
    subjects = _subjects(spec)
    _write_record(spec, subjects)
    _write_overlay(spec, [_answer(*subjects[0])])

    result = compile_module(spec, tmp_path / "art")

    assert result.success, result.errors
    assert not any(_VINDICATED in w for w in result.warnings)


# ── the signal ──────────────────────────────────────────────────────────────────────────────────


def test_an_answer_the_archive_caught_up_with_is_reported_as_such(tmp_path: Path) -> None:
    """The record no longer contests the subject, so the author's judgement was confirmed.

    Built by writing the record for the *other* subject only — which is exactly what a later
    enrichment run does when the authorities stop disagreeing, since the record is rewritten whole
    and carries contested subjects alone.
    """
    spec = _example(tmp_path)
    answered, still_contested = _subjects(spec)
    _write_record(spec, [still_contested])
    _write_overlay(spec, [_answer(*answered)])

    result = compile_module(spec, tmp_path / "art")

    assert result.success, result.errors
    assert any(_VINDICATED in w for w in result.warnings), result.warnings
    assert result.manifest.compilation.warnings_summary.get("overlay_answer_vindicated") == 1


def test_it_replaces_the_message_that_was_actively_misleading(tmp_path: Path) -> None:
    """**The reason this earns a code rather than a rewording of the generic one.**

    The finding that used to fire offers *the subject may be mistyped* — put to an author whose
    judgement the archive has just confirmed. Both halves are asserted: the good sentence appears and
    the misleading one does not.
    """
    spec = _example(tmp_path)
    answered, still_contested = _subjects(spec)
    _write_record(spec, [still_contested])
    _write_overlay(spec, [_answer(*answered)])

    result = compile_module(spec, tmp_path / "art")

    assert any(_VINDICATED in w for w in result.warnings)
    assert not any(_GENERIC in w for w in result.warnings)
    summary = result.manifest.compilation.warnings_summary
    assert summary.get("overlay_update_unmatched") is None
    assert summary.get("overlay_update_target_unreachable") is None


def test_it_claims_nothing_about_who_was_right(tmp_path: Path) -> None:
    """The wording is the decision here, so it is pinned: an observation about the record.

    A compiler cannot say an author was right about the biology, and this does not — it says the
    authorities now agree and the overlay row can be retired.
    """
    spec = _example(tmp_path)
    answered, still_contested = _subjects(spec)
    _write_record(spec, [still_contested])
    _write_overlay(spec, [_answer(*answered)])

    line = next(w for w in compile_module(spec, tmp_path / "art").warnings if _VINDICATED in w)

    assert "authorities now agree" in line
    assert "can be retired" in line
    # Word-boundary matching, not substring: "correct" is inside "correction", which the message says
    # legitimately — it is naming the author's overlay row, not grading it.
    words = set(re.findall(r"[a-z]+", line.lower()))
    for verdict in ("correct", "right", "wrong", "vindicated", "proved", "confirmed"):
        assert verdict not in words, f"the message must not adjudicate: {verdict!r}"
    # And the subject renders as a subject rather than as a Python tuple.
    assert "('" not in line and '("' not in line


def test_the_pre_flight_reports_what_the_compile_reports(tmp_path: Path) -> None:
    """`@parity-by-check`, and once — the compile runs the pre-flight and dedupes on the message."""
    spec = _example(tmp_path)
    answered, still_contested = _subjects(spec)
    _write_record(spec, [still_contested])
    _write_overlay(spec, [_answer(*answered)])

    checked = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "art")

    from_validate = [w for w in checked.warnings if _VINDICATED in w]
    assert from_validate, checked.warnings
    assert from_validate[0] in compiled.manifest.compilation.warnings
    assert len([w for w in compiled.manifest.compilation.warnings if _VINDICATED in w]) == 1


# ── scope and registry ──────────────────────────────────────────────────────────────────────────


def test_it_is_scoped_to_the_one_table_whose_absence_has_a_single_reading() -> None:
    """Every other table's unmatched update is ambiguous; this one's is not, because the record holds
    contested subjects only and is rewritten whole rather than merged."""
    assert VINDICATING_OVERLAY_TABLE == "clin_sig_concordance.csv"


def test_the_code_is_published_and_actionable() -> None:
    """Actionable rather than carried: the author can retire the overlay row, and nobody else can.

    It is also the one finding in the catalogue that reports good news, which is not a reason to
    classify it differently — carried-ness is about remediation, and this has one.
    """
    assert "overlay_answer_vindicated" in VALID_WARNING_CODES
    assert "overlay_answer_vindicated" in ACTIONABLE_WARNING_CODES


def test_a_module_with_no_overlay_reports_nothing(tmp_path: Path) -> None:
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))

    result = compile_module(spec, tmp_path / "art")

    assert result.success, result.errors
    assert not any(_VINDICATED in w for w in result.warnings)

"""Turning a clinical-significance comparison into a record an author can act on (0.7, RM130).

The ClinVar cross-check has always known which rows disagree and has always thrown them away: it
reports *twenty of 141,616* and the twenty reach a logger. This module is the other half — the two
verdicts, the per-authority calls behind them, and the writer that puts both beside the spec.

**Two functions, and the split is the design.** `classify_concordance` is a pure function over an
authored call and N authority outcomes; `concordance_tables` turns a run's findings into rows. The
classifier knows nothing about ClinVar, PubMind or any other source, which is what lets it be
exercised at three and five authorities today rather than at whatever N the current producer happens
to reach — and the arity of the vocabularies is the property the whole two-field split exists to
hold.

**Nothing here resolves a split.** With five authorities in a two-against-three disagreement,
precedence and majority pick different winners and choosing between them needs a weighting model.
This workspace has declined to invent one three times, so `authored_position` is a relation to the
*set*: computable with no weights, true at any topology, and leaving a consumer free to apply its own
model to the detail rows.

**What contests a subject, stated once because it is the contract with the shipped check.** A row is
written when a disagreement is *established*:

* the module's own call and an authority's call sit in opposite camps — a pathogenic-class call
  against a benign-class one; or
* two authorities that spoke disagree with each other.

At one authority the second clause cannot fire, so the emitted set is exactly the conflicts the
shipped check already reports — which is what keeps the three-way check a superset of the two-way
rather than a second opinion beside it, and keeps an author from meeting one disagreement twice.

**An authority that could not be consulted never contests anything on its own.** `unknown AND false`
is `false` under Kleene, so an unreachable archive does not un-see a disagreement already witnessed;
but on its own it produces no row, because a question nobody could put is not a finding.
"""

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.layout import atomic_writer, resolve_sidecar, sidecar_write_path

logger = logging.getLogger(__name__)

#: The CSV names, public because four parties agree on them — the enricher writes, the compiler
#: reads and hashes, a publisher uploads and a registry re-splits.
CONCORDANCE_CSV: str = "clin_sig_concordance.csv"
AUTHORITY_CALLS_CSV: str = "clin_sig_authority_calls.csv"

#: Column order, derived from the models rather than restated — a hand-kept parallel list is how
#: `SOURCES_FIELDNAMES` lost a column.
_CONCORDANCE_FIELDNAMES: list[str] = list(ClinSigConcordanceRow.model_fields)
_AUTHORITY_CALL_FIELDNAMES: list[str] = list(ClinSigAuthorityCallRow.model_fields)

#: The camps a clinical significance falls into, for deciding whether two calls actually *disagree*.
#:
#: Coarser than `VALID_CLIN_SIG` on purpose: `pathogenic` against `likely_pathogenic` is a difference
#: of confidence within one conclusion, not a conflict, and reporting it would bury the real finding.
#: Only `pathogenic` and `benign` are *opinionated* — an `undecided` or `orthogonal` call has no
#: opposing claim to conflict with, which is why neither ever makes a subject contested on its own.
#:
#: This lives here rather than in `clinical.py`, where it was first written, because the concordance
#: record and the two-way check must draw the line in the same place: two maps for one distinction is
#: the defect that would make a drift in our own code read as a disagreement between two archives.
CLIN_SIG_CAMP: dict[str, str] = {
    "pathogenic": "pathogenic",
    "likely_pathogenic": "pathogenic",
    "risk_factor": "pathogenic",
    "benign": "benign",
    "likely_benign": "benign",
    "protective": "benign",
    # Opinions that are not a pathogenic/benign call at all.
    "uncertain_significance": "undecided",
    "conflicting": "undecided",
    "not_provided": "undecided",
    "other": "undecided",
    # Orthogonal axes: a drug-response or expression call is about something else entirely.
    "drug_response": "orthogonal",
    "association": "orthogonal",
    "affects": "orthogonal",
}

#: The two camps that can contradict each other. A subject is *opposed* when both are in play.
OPINIONATED_CAMPS: frozenset[str] = frozenset({"pathogenic", "benign"})


def camp_of(clin_sig: str | None) -> str | None:
    """The camp a classification falls in, or `None` when there is no classification to place.

    `None` rather than `undecided` for an absent value, because the two are different statements: a
    source that said nothing has not landed in the undecided camp, it has not spoken at all. A
    classification this release does not model reads as `undecided` — it was stated, and it opposes
    nothing.
    """
    if clin_sig is None:
        return None
    return CLIN_SIG_CAMP.get(clin_sig, "undecided")


@dataclass(frozen=True)
class AuthorityCall:
    """What one annotation authority had to say about one subject.

    The classifier's input unit, and deliberately not tied to any source: it carries a normalized
    `clin_sig`, the raw token behind it, and a confidence **in the authority's own units** with the
    name of the instrument beside it. Nothing converts one authority's confidence into another's —
    a gold-star count and an evidence-depth count are not the same quantity, and folding them into
    one number would put three axes in one field.
    """

    authority: str
    #: `recorded` / `no_record` / `unchecked`. The third is nobody-asked, and it is the one the
    #: whole tri-state exists for: an archive that could not be reached has not agreed with anybody.
    status: str
    clin_sig: str | None = None
    clin_sig_raw: str | None = None
    confidence: str | None = None
    confidence_unit: str | None = None
    dataset: str | None = None

    @property
    def spoke(self) -> bool:
        """Whether this authority actually stated a classification."""
        return self.status == "recorded" and self.clin_sig is not None

    @property
    def unreachable(self) -> bool:
        """Whether this authority could not be consulted at all — never an absence of a record."""
        return self.status == "unchecked"


@dataclass(frozen=True)
class ConcordanceVerdict:
    """The two orthogonal verdicts, plus what follows from them.

    `contested` is on the verdict rather than recomputed by the caller because it depends on facts
    only the classifier holds — whether any authority actually spoke, and whether the camps in play
    are opinionated. A caller re-deriving it from the two vocabulary members alone would call a
    subject contested where nobody has a record, which is the vacuous-truth trap in the ∀ over an
    empty set.
    """

    authority_concordance: str
    authored_position: str
    #: `None` is not `False`: a subject with an unreachable authority and no established opposition
    #: has not been shown to be uncontroversial, it has been half-checked.
    opposed: bool | None
    contested: bool


def classify_concordance(
    authored_clin_sig: str | None, calls: Sequence[AuthorityCall]
) -> ConcordanceVerdict:
    """The two verdicts for one subject, at any number of authorities.

    **`authority_concordance` — do the authorities agree with each other?**

    A disagreement already witnessed is not un-witnessed by an authority that could not be asked
    (`unknown AND false` is `false`), so `discordant` wins over `unchecked`. Otherwise an unreachable
    authority leaves the question open, and the answer is `unchecked` rather than an agreement nobody
    established. With everyone reachable it is `concordant` for two or more agreeing, `single` for
    exactly one opinion — one voice is not corroboration — and `none` when every archive was asked
    and none has a record.

    **`authored_position` — where does the module's own call sit relative to them?**

    `matches_some` is establishable under an unreachable sibling, because both halves of it are
    witnessed by authorities that did speak. `matches_all` and `matches_none` are ∀ claims and need
    the set closed, so an unreachable authority sends them to `unchecked`. `absent` is the module
    stating no clinical call at all, which is a different thing from disagreeing with everyone.

    Both are at **camp** granularity, the same coarseness the two-way check uses: `pathogenic` and
    `likely_pathogenic` are one position, not two.
    """
    spoke = [call for call in calls if call.spoke]
    unreachable = [call for call in calls if call.unreachable]
    spoken_camps = [camp_of(call.clin_sig) for call in spoke]
    distinct_camps = set(spoken_camps)

    if len(distinct_camps) > 1:
        concordance = "discordant"
    elif unreachable:
        concordance = "unchecked"
    elif len(spoke) >= 2:
        concordance = "concordant"
    elif len(spoke) == 1:
        concordance = "single"
    else:
        concordance = "none"

    authored_camp = camp_of(authored_clin_sig)
    if authored_camp is None:
        position = "absent"
    else:
        matched = [camp for camp in spoken_camps if camp == authored_camp]
        missed = [camp for camp in spoken_camps if camp != authored_camp]
        if matched and missed:
            position = "matches_some"
        elif unreachable:
            position = "unchecked"
        elif not spoke:
            # Nobody has a record, so the ∀ is vacuous both ways. `matches_none` rather than
            # `matches_all`, because "every authority agrees" must not be sayable about no authority
            # at all — and this pairs with `none`, where the archives were asked and had nothing.
            position = "matches_none"
        elif not missed:
            position = "matches_all"
        else:
            position = "matches_none"

    # Opposed is a statement about the camps in play, the module's own included: two of them sit on
    # opposite sides of the pathogenic/benign line. Establishable regardless of an unreachable
    # authority — one more opinion cannot unmake an opposition already present.
    camps_in_play = {camp for camp in spoken_camps if camp is not None}
    if authored_camp is not None:
        camps_in_play.add(authored_camp)
    opposed_established = camps_in_play >= OPINIONATED_CAMPS
    opposed: bool | None = True if opposed_established else (None if unreachable else False)

    # An established disagreement, and only that, contests a subject. Two clauses: the module against
    # an authority, which needs both sides opinionated because an uncertain call opposes nothing; and
    # one authority against another, which cannot fire below two speakers. At one authority the
    # second is unreachable, so this reduces exactly to what the shipped two-way check reports.
    authored_contested = (
        authored_camp in OPINIONATED_CAMPS
        and any(camp in OPINIONATED_CAMPS and camp != authored_camp for camp in spoken_camps)
    )
    contested = authored_contested or concordance == "discordant"

    return ConcordanceVerdict(
        authority_concordance=concordance,
        authored_position=position,
        opposed=opposed,
        contested=contested,
    )


@dataclass(frozen=True)
class ConcordanceSubject:
    """One `(variant_key, genotype)` the check put a question about, and every answer it got."""

    variant_key: str
    genotype: str
    authored_clin_sig: str | None
    calls: tuple[AuthorityCall, ...]


def concordance_tables(
    subjects: Sequence[ConcordanceSubject], *, checked_at: str | None = None
) -> tuple[list[ClinSigConcordanceRow], list[ClinSigAuthorityCallRow]]:
    """The two tables for a run: contested subjects, and the calls behind each one.

    **Only contested subjects reach the record**, and the detail rows follow the parent rather than
    being written for every subject asked. A record of every agreement would be a copy of the
    module's own `clin_sig` column with a second opinion attached, and the count of subjects
    compared is already published as the check's denominator — recording it a second time as rows
    would be the same number in two places.

    Order is the subject order the caller supplied, and within a subject the call order it supplied,
    both preserved rather than sorted: parquet bytes depend on row order, and a sort over values
    would let a corrected classification move a row.
    """
    parents: list[ClinSigConcordanceRow] = []
    calls: list[ClinSigAuthorityCallRow] = []
    for subject in subjects:
        verdict = classify_concordance(subject.authored_clin_sig, subject.calls)
        if not verdict.contested:
            continue
        parents.append(
            ClinSigConcordanceRow(
                variant_key=subject.variant_key,
                genotype=subject.genotype,
                authored_clin_sig=subject.authored_clin_sig,
                authority_concordance=verdict.authority_concordance,
                authored_position=verdict.authored_position,
                opposed=verdict.opposed,
                checked_at=checked_at,
            )
        )
        calls.extend(
            ClinSigAuthorityCallRow(
                variant_key=subject.variant_key,
                genotype=subject.genotype,
                authority=call.authority,
                status=call.status,
                clin_sig=call.clin_sig,
                clin_sig_raw=call.clin_sig_raw,
                confidence=call.confidence,
                confidence_unit=call.confidence_unit,
                dataset=call.dataset,
                checked_at=checked_at,
            )
            for call in subject.calls
        )
    return parents, calls


def _cell(value: object) -> str:
    """Render one value to a canonical CSV cell, matching the compiler's `_scalar_cell` exactly.

    Its own function rather than inlined, because a column added later must be rendered the way the
    reverse writer renders it or the two spellings differ after a round trip.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_table(rows: Sequence[object], fieldnames: list[str], path: Path) -> None:
    """Write one table atomically, with a fixed column order and canonical cells.

    Atomic because every sidecar here is read back by the next run: a process killed mid-write leaves
    a file that is syntactically valid and simply short, which is the one failure mode a table cannot
    report about itself.
    """
    with atomic_writer(path, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()  # type: ignore[attr-defined]
            writer.writerow({name: _cell(dumped.get(name)) for name in fieldnames})


def write_concordance_tables(
    spec_dir: Path,
    parents: Sequence[ClinSigConcordanceRow],
    calls: Sequence[ClinSigAuthorityCallRow],
) -> tuple[Path, Path]:
    """Replace both tables beside the spec, and return where they were written.

    **These are pure build products, and they are rewritten whole rather than merged.** Every other
    derived sidecar gap-fills because a recorded row might carry a curator's judgement; this one
    cannot, because the judgement about a contested subject goes in `overrides.csv` and never into
    this file. Merging would be actively wrong: a subject the archive stopped contesting has to
    *leave* the record, since a conflict that stops being reported is exactly how an author learns
    the archive caught up with them.

    A run that found nothing contested therefore writes two empty tables rather than leaving the
    previous run's rows in place — an empty record is a claim (*nothing is contested*), and it is a
    different claim from no record at all, which is what a run that could not put the question leaves
    behind by writing nothing.

    Resolved through `layout` so a module carrying its sidecars under `derived/` gets them written
    where it keeps the rest, rather than growing a second copy at the root.
    """
    parent_path = sidecar_write_path(spec_dir, CONCORDANCE_CSV)
    calls_path = sidecar_write_path(spec_dir, AUTHORITY_CALLS_CSV)
    _write_table(parents, _CONCORDANCE_FIELDNAMES, parent_path)
    _write_table(calls, _AUTHORITY_CALL_FIELDNAMES, calls_path)
    logger.info(
        "Wrote the clinical-significance concordance record: %d contested subject(s), %d authority "
        "call(s). Answer one with an overrides.csv row against %s.",
        len(parents), len(calls), CONCORDANCE_CSV,
    )
    return parent_path, calls_path


def read_recorded_calls(spec_dir: Path) -> list[ClinSigAuthorityCallRow] | None:
    """The authority calls this module already has on file, or `None` when it has none (RM151).

    **The baseline half of the staleness comparison, and it must be read before the commit rewrites
    it.** `write_concordance_tables` replaces this table whole, so the previous run's rows are the
    record as it stood when an author read it and wrote their answer — available for exactly as long
    as this run has not yet committed. `enrich()` computes everything before its commit already, for
    the unrelated reason that a refused `strict` run must change nothing, and that ordering is what
    makes this readable at all.

    `None` rather than `[]` for a module that has never had a record written, because the two are
    different claims and the whole check turns on the difference: no file is *nobody asked at record
    time*, an empty file is a run that asked and found nothing contested.

    A file that will not parse is `None` too, and says so. Guessing at a half-read baseline would
    manufacture a movement out of our own inability to read, which is the one wrong answer available.

    Resolved through `layout` so a module keeping its sidecars under `derived/` is read where it
    keeps them (`@sidecar-name-and-place`).
    """
    path = resolve_sidecar(spec_dir, AUTHORITY_CALLS_CSV)
    if path is None:
        return None
    rows, errors, _ = load_csv_rows(path, ClinSigAuthorityCallRow, path.name)
    if errors:
        logger.warning(
            "%s is present but unreadable (%s); no answered call can be compared against it this "
            "run, which is reported as unknown rather than as unchanged.", path.name, errors[0],
        )
        return None
    return rows


# ── RM151: the disagreement an answer was written about, against the one on record now ───────────


#: Why one answered subject's call could not be compared. **Neither member ever reads as
#: `unchanged`** — that is the whole tri-state, and it is the reason this is a registry rather than
#: two string literals in a branch: a third state must arrive with a note attached, not silently join
#: the ones that say nothing (`@unreachable-not-absent`, `@registry-completeness`).
VALID_CALL_SHIFT_WITHHELD: frozenset[str] = frozenset({
    #: No usable prior row for this `(subject, authority)` — the previous record has none, or it has
    #: one whose status was `unchecked`. Nobody-asked at record time, so there is no baseline to move
    #: away from. The first run to write the record puts every answered subject here.
    "no_prior_record",
    #: The authority could not be consulted *this* run, so its call today is unknown. An unknown is
    #: withheld and never negated: a leg nobody could ask has not agreed with what was recorded.
    "unchecked_now",
})


@dataclass(frozen=True)
class CallShift:
    """One authority's call about one answered subject, as it was recorded and as it reads now.

    Both sides are whole `ClinSigAuthorityCallRow`s rather than the two classifications, because the
    `dataset` pair is what separates the two readings a reader actually needs: a **re-released**
    archive that revised its call, and an archive that revised **in place** within one release. The
    check does not branch on that difference — it has no rule for a `dataset` neither side recorded —
    it just puts both in the message and lets the reader see which happened.
    """

    before: ClinSigAuthorityCallRow
    after: ClinSigAuthorityCallRow

    @property
    def subject(self) -> tuple[str, str]:
        """The `(variant_key, genotype)` the answer was written about."""
        return (self.after.variant_key, self.after.genotype)

    @property
    def authority(self) -> str:
        return self.after.authority

    @property
    def wording_held(self) -> bool:
        """Whether the authority's own words are unchanged while our reading of them moved.

        True only when both sides recorded a verbatim token and the two are equal. That is *this
        release's normalizer* having moved, not the archive — a different finding wearing the same
        shape, and reporting it as an archive revision would accuse a source of a change we made.
        """
        return (
            self.before.status == "recorded"
            and self.after.status == "recorded"
            and self.before.clin_sig_raw is not None
            and self.before.clin_sig_raw == self.after.clin_sig_raw
        )

    def _side(self, row: ClinSigAuthorityCallRow) -> str:
        call = row.clin_sig if row.status == "recorded" and row.clin_sig else "no record"
        return f"{call} ({row.dataset})" if row.dataset else call

    def __str__(self) -> str:
        variant_key, genotype = self.subject
        return (
            f"{variant_key} {genotype} {self.authority}: "
            f"{self._side(self.before)} → {self._side(self.after)}"
        )


@dataclass(frozen=True)
class AnsweredCallReport:
    """What a run can say about the answers this module already carries.

    **Nothing here is computed and discarded** (`@dont-discard-computed`): `answered` and `subjects`
    are the two denominators, and a caller that recomputed either would be re-implementing the
    answered-subject rule — the drift the overlay's own design refuses.
    """

    #: Calls whose recorded value moved, and where the move is the authority's own.
    shifts: tuple[CallShift, ...]
    #: Calls that differ only after this release's normalization, the verbatim token unchanged.
    #: Kept apart because it is a statement about this tier, not about the archive.
    normalization: tuple[CallShift, ...]
    #: `(variant_key, genotype, authority, reason)` for every comparison that could not be made,
    #: `reason` from `VALID_CALL_SHIFT_WITHHELD`.
    withheld: tuple[tuple[str, str, str, str], ...]
    #: Answered subjects at least one authority could be compared for — the denominator the moved
    #: count is read against.
    subjects: int
    #: Answered subjects the overlay carries at all. Larger than `subjects` whenever the question
    #: could not be put, which is the gap the notes exist to say out loud.
    answered: int

    @property
    def moved_subjects(self) -> int:
        """Answered subjects carrying at least one moved call. The numerator."""
        return len({shift.subject for shift in self.shifts})


def shifted_authority_calls(
    baseline: Sequence[ClinSigAuthorityCallRow] | None,
    fresh: Sequence[ClinSigAuthorityCallRow] | None,
    answered: Sequence[tuple[str, str]],
) -> AnsweredCallReport:
    """The answered subjects whose authority calls have moved since the answer was written (RM151).

    **An `overrides.csv` row against the concordance record is a judgement about a particular
    disagreement** — the archive said X, the author says Y, and the `reason` column explains why. If
    the archive later says Z, that reason was written about a value that is no longer there. Nothing
    in the record distinguishes a justification that still describes the disagreement on file from
    one that describes a disagreement since replaced by a different one, and this is the check that
    notices.

    **The comparison is recorded-call against fresh-call, per `(variant_key, genotype, authority)`,
    and the previous `clin_sig_authority_calls.csv` is the only baseline this format has.** That
    table is what each authority actually said, with `clin_sig`, the verbatim `clin_sig_raw` and the
    `dataset` it came from — so the comparison is available here and nowhere else. **Do not promise
    this for a table that records no prior value** (`@probe-names-the-table`): an overlay row against
    `frequencies.csv` or `resolution.csv` has no recorded baseline at all, so a general "the value
    moved" check would be answerable for one table and silently absent for the rest.

    **It observes, it does not adjudicate.** *The disagreement you answered is not the disagreement
    that exists now* is a statement about the record. *Your answer may be wrong* is a verdict, and
    this format does not put a verdict under a check that cannot see the reasoning — the same
    restraint the concordance tables keep everywhere else.

    **A subject that left the record entirely is not this finding.** It is not in `fresh`, so it
    never enters the loop: the authorities stopped contesting it, which is RM117's
    `overlay_answer_vindicated` and is reported by the compiler as good news. Two findings about one
    overlay row would be one of them firing with the wrong words on it.

    Order is `fresh` row order, preserved rather than sorted: the message is read by a human and a
    sort over values would let a corrected classification move a line.
    """
    answered_keys = set(answered)
    if fresh is None:
        # No run to compare against — nobody could be consulted, so there is not even a set of
        # authorities to name. Zero comparable subjects, which is not the claim that nothing moved;
        # `answered` carries the gap and the notes are what say it out loud.
        return AnsweredCallReport((), (), (), 0, len(answered_keys))

    # **A missing baseline is an empty one, not a short circuit.** `None` here means the module has
    # never had a record written, or the one it has will not parse; either way every lookup below
    # misses and every answered call is withheld as `no_prior_record` — which is the reading, and it
    # is worth saying per authority rather than collapsing into "the question could not be put". The
    # first run to write a record takes this path, and its note is the useful one: run once more.
    before = {
        (row.variant_key, row.genotype, row.authority): row for row in (baseline or ())
    }
    shifts: list[CallShift] = []
    normalization: list[CallShift] = []
    withheld: list[tuple[str, str, str, str]] = []
    comparable: set[tuple[str, str]] = set()

    for now in fresh:
        subject = (now.variant_key, now.genotype)
        if subject not in answered_keys:
            continue
        key = (now.variant_key, now.genotype, now.authority)
        then = before.get(key)
        if then is None or then.status == "unchecked":
            withheld.append((*key, "no_prior_record"))
            continue
        if now.status == "unchecked":
            withheld.append((*key, "unchecked_now"))
            continue
        comparable.add(subject)
        if then.status == now.status and then.clin_sig == now.clin_sig:
            # Unchanged, `dataset` included or not: a re-released archive that says the same thing
            # has not moved the disagreement the answer was written about.
            continue
        shift = CallShift(before=then, after=now)
        (normalization if shift.wording_held else shifts).append(shift)

    return AnsweredCallReport(
        shifts=tuple(shifts),
        normalization=tuple(normalization),
        withheld=tuple(withheld),
        subjects=len(comparable),
        answered=len(answered_keys),
    )


def _render_shifts(shifts: Sequence[CallShift]) -> str:
    """A bounded, ordered rendering — a log line a person reads must not grow with the corpus."""
    shown = "; ".join(str(shift) for shift in shifts[:5])
    return shown + ("" if len(shifts) <= 5 else f" (+{len(shifts) - 5} more)")


def answered_call_sentences(report: AnsweredCallReport) -> list[str]:
    """The findings a run reports about its answered subjects, warning-tier, in both modes (RM151).

    **Never escalated under `strict`** (`@clinsig-never-escalates`), and with more force than for the
    concordance record itself: nothing here is even a disagreement, it is a note that the record an
    author reasoned over has been rewritten underneath their reasoning. Refusing a build over it
    would gate an artifact on an archive's release schedule.

    Two sentences, kept apart because they are about different parties. The first is the archive
    revising; the second is **this release's own normalizer** reading unchanged wording differently,
    which is a fact about our code and is not the author's to act on.

    Empty when nothing moved and empty when nothing could be compared — a check that cannot fail
    reports no zero (`@tautology-zero`), and the gap belongs in the notes rather than dressed up as a
    clean bill.
    """
    lines: list[str] = []
    if report.shifts:
        lines.append(
            f"{report.moved_subjects} of {report.subjects} answered subject(s) rest on an authority "
            f"call that has moved since the answer was recorded: {_render_shifts(report.shifts)}. "
            f"The overrides.csv reason for each was written about the earlier call, so it describes "
            f"a disagreement that is no longer the one on record. Nothing here grades the answer — "
            f"re-read the reason and decide whether it still says what you mean. Asked for "
            f"{CONCORDANCE_CSV} alone: it is the one table this format keeps a prior value in."
        )
    if report.normalization:
        lines.append(
            f"{len(report.normalization)} answered call(s) differ only after this release's own "
            f"normalization — the authority's verbatim wording is unchanged: "
            f"{_render_shifts(report.normalization)}. What moved is how this tier reads the token, "
            f"not what the archive published, so the answer is about the same disagreement it "
            f"always was and there is nothing for an author to do."
        )
    return lines


def answered_call_notes(report: AnsweredCallReport) -> list[str]:
    """What a run should say about answers it could **not** put the question for. Info-tier.

    Said out loud rather than left silent, because a comparison that quietly did not run reads as one
    that found nothing — the failure the whole tri-state exists to prevent
    (`@unreachable-not-absent`). Grouped by reason rather than by row, like every repeated finding
    here.

    Silent for a module with no answers at all, which is every module today: a check that cannot fire
    must not announce a zero.
    """
    if not report.answered:
        return []
    notes: list[str] = []
    uncomparable = report.answered - report.subjects
    if uncomparable:
        notes.append(
            f"{uncomparable} of {report.answered} answered subject(s) could not be compared against "
            f"what the authorities said when the answer was written. That is not agreement and not "
            f"an absence of movement: it is a question nobody could put."
        )
    reasons: dict[str, int] = {}
    for *_key, reason in report.withheld:
        reasons[reason] = reasons.get(reason, 0) + 1
    if reasons.get("no_prior_record"):
        notes.append(
            f"{reasons['no_prior_record']} answered call(s) have no prior {AUTHORITY_CALLS_CSV} row "
            f"to compare against — this run is writing the first record, the previous one would not "
            f"parse, or the authority was unchecked when the answer was written. Once a record is on "
            f"file the comparison becomes available on the next run."
        )
    if reasons.get("unchecked_now"):
        notes.append(
            f"{reasons['unchecked_now']} answered call(s) come from an authority this run could not "
            f"consult, so what it says today is unknown. Nothing is claimed about them either way."
        )
    return notes

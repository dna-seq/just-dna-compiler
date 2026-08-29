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

from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.layout import atomic_writer, sidecar_write_path

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

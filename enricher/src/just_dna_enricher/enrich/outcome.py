"""What a run returns and raises: `EnrichmentError`, `EnrichmentResult`, and the `rederive` drift
report (RM260 split this out of the former single-file `enrich.py`).
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from just_dna_format.base import merge_key
from just_dna_format.resolution import RESOLUTION_FACT_FIELDS, ResolutionRow

from just_dna_enricher.civic_citations import EvidenceStatusCheck
from just_dna_enricher.civic_refutation import RefutationFinding
from just_dna_enricher.clinical import ClinSigComparison, ClinSigConflict, ConcordanceRecord
from just_dna_enricher.concordance import AnsweredCallReport
from just_dna_enricher.currency import CurrencyCheck
from just_dna_enricher.grch37 import BuildDiagnosis
from just_dna_enricher.identifiers import RsidStatus
from just_dna_enricher.resolver import AlleleMismatch, PairCheck
from just_dna_enricher.sequences import RefMismatch
from just_dna_enricher.vrs import MintResult


class EnrichmentError(RuntimeError):
    """Raised in strict mode when the chain cannot fully resolve the module."""


@dataclass(frozen=True)
class SubjectDrift:
    """One subject whose recorded facts and freshly derived facts disagree, under `rederive=True`.

    The canary MODULE_LIFECYCLE describes, finally performed. Merge-not-clobber means an ordinary
    re-run never re-asks about a recorded row, so a source that silently *revised* an answer moves no
    `fetched_at`, no fact signature and no digest — and the only way to notice was to delete the table
    and re-derive, which used to discard the curator's rows with it. With corrections living in the
    overlay a full re-derivation costs nothing, and because the fresh table is staged beside the
    current one both sides exist at the commit boundary, so the comparison is free.

    `before`/`after` render the **fact** columns only (`RESOLUTION_FACT_FIELDS`), read off the
    registry rather than restated here: the provenance columns move on every run by design, and a
    report that called a new `fetched_at` a drift would cry wolf on every subject.
    """

    variant_key: str
    before: str
    after: str

    def __str__(self) -> str:
        return f"{self.variant_key}: {self.before} → {self.after}"


def _render_facts(rows: Sequence[ResolutionRow]) -> str:
    """A subject's resolved facts as one comparable string, in `locus_index` order."""
    return " + ".join(
        "|".join(
            "" if getattr(row, name) is None else str(getattr(row, name)) for name in RESOLUTION_FACT_FIELDS
        )
        for row in sorted(rows, key=lambda r: r.locus_index)
    )


def _rederived_drift(
    before: Mapping[tuple, Sequence[ResolutionRow]],
    after: Sequence[ResolutionRow],
    *,
    skip: Collection[tuple] = (),
) -> tuple[list[SubjectDrift], int]:
    """`(what moved, how many subjects were re-asked)` between a recorded table and a fresh one.

    Compared **only** over subjects present on both sides and not in `skip`. A recorded subject the run
    could not ask about this time produces no fresh row at all — the three branches that deliberately
    write nothing for an unanswerable subject — and calling that a drift would report the run's own
    reach as a change in the source.

    `skip` is what the carry-forward put back, and it is not optional bookkeeping: the carried rows are
    in `after` by the time this runs, so without it every un-asked subject would still land in the
    denominator and the warning would publish "N of M **re-asked**" over an M that includes subjects
    nothing asked. A count that travels with a finding has to be the count the sentence names.
    """
    skipped = set(skip)
    fresh: dict[tuple, list[ResolutionRow]] = {}
    for row in after:
        fresh.setdefault(merge_key(row), []).append(row)
    drift: list[SubjectDrift] = []
    compared = 0
    for key, old_rows in before.items():
        new_rows = fresh.get(key)
        if new_rows is None or key in skipped:
            continue
        compared += 1
        was, now = _render_facts(old_rows), _render_facts(new_rows)
        if was != now:
            drift.append(SubjectDrift(old_rows[0].variant_key, was, now))
    return sorted(drift, key=lambda d: d.variant_key), compared


@dataclass
class EnrichmentResult:
    rows: list[ResolutionRow]
    unresolved: list[str] = field(default_factory=list)  # variant_keys with no resolved position
    sources: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    # Authored data that disagrees with the reference genome. Reported, never repaired — see
    # `sequences.verify_reference_alleles`. Empty when the check could not run (offline).
    ref_mismatches: list[RefMismatch] = field(default_factory=list)
    # Which of those mismatched rows read as GRCh37 coordinates in a GRCh38 module (RM48). Computed
    # only over `ref_mismatches`, so a module whose refs agree costs no request at all, and grouped by
    # evidence class rather than by row.
    build_diagnoses: list[BuildDiagnosis] = field(default_factory=list)
    # Why the diagnosis above did not run, or `None` when it did. Same rule as `clin_sig_not_checked`:
    # an empty list otherwise means both "asked, and nothing points at another build" and "never
    # asked", and only one of those is a clean bill. `no_ref_mismatches` (nothing to diagnose) and
    # `skipped_offline` are the two ways it does not run.
    build_not_diagnosed: str | None = None
    # Authored `clin_sig` values ClinVar's own records do not support. Warnings in BOTH modes on
    # purpose — see `clinical.verify_clin_sig`. Empty when no snapshot was provisioned.
    clin_sig_conflicts: list[ClinSigConflict] = field(default_factory=list)
    # Why the cross-check above did not run, or `None` when it did. An empty `clin_sig_conflicts` says
    # two opposite things on its own — "compared everything, nothing disagreed" and "never compared" —
    # and a consumer reading the first when the second happened is being told a check passed that was
    # never put. So the skip carries its reason (S4): `not_requested`, `no_snapshot`, or the
    # drafted-from-this-release tautology, which is the one that used to report a confident zero, and
    # `unusable_snapshot` for a reference that is present but not queryable.
    clin_sig_not_checked: str | None = None
    # RM170. Authored `direction` values a CIViC snapshot publishes a refutation of — the source
    # asserting and rebutting one claim, or having only ever rebutted what the module asserts. Warnings
    # in BOTH modes and escalated in neither (`@a-source-recuring-is-not-a-strict-matter`): a source
    # disagreeing with itself is a fact about the field, not an authoring error. Empty when no CIViC
    # snapshot was provisioned, which is what `refutation_not_checked` says.
    refutation_findings: list[RefutationFinding] = field(default_factory=list)
    # Why the check above did not run, or `None` when it did. An empty `refutation_findings` says
    # nothing on its own, exactly as an empty `clin_sig_conflicts` does not.
    refutation_not_checked: str | None = None
    # RM160. The canary over citations `civic citations` recovered from CIViC's API: what the module
    # recorded as CIViC's curation status, re-asked. Warnings in BOTH modes and escalated in neither,
    # for the reason above it — and a **different** question from `dataset_currency`, which asks which
    # release a table came from rather than whether one judgement has moved. `None` when this run put
    # no such question, which its own `skip` names.
    evidence_status: EvidenceStatusCheck | None = None
    # The per-row split behind that tautology, and **only** there: `strict` over a module whose licence
    # row says it was drafted from this very snapshot looks every value up and reports how many are
    # still copies, how many a human wrote, and how many conflict (RM4). `None` — never an audit of
    # zeros — on every other run: `best_effort` deliberately does not pay for it (the reason is in
    # `clin_sig_not_checked`), and for a module that never claimed a draft the copied/authored split
    # would assert a provenance nobody established.
    clin_sig_comparison: ClinSigComparison | None = None
    # The N-authority concordance record this run built, or `None` when no authority could be
    # consulted at all — which is never "nothing was contested". Carried rather than recomputed: the
    # counts on it are the run's own, and a caller re-deriving them would be a second implementation
    # of the selection rule.
    clin_sig_record: ConcordanceRecord | None = None
    # What this run could say about the answers the module's overlay already carries (RM151): which
    # of them rest on an authority call that has moved since the answer was written. `None` when the
    # comparison was not made at all — the clin_sig check is off — which is never "nothing moved".
    answered_calls: AnsweredCallReport | None = None
    # Authored rsIDs dbSNP has merged away or has no record of. Recorded onto the rows' provenance
    # columns and reported; never substituted — see `identifiers.check_rsids`.
    stale_rsids: list[RsidStatus] = field(default_factory=list)
    # `(rsid, chrom, start)` of each Y pseudoautosomal locus left out in favour of its X spelling.
    # Surfaced rather than only logged: the table is half the size an author might expect, and a
    # selection nobody can see is indistinguishable from a silent repair. See
    # `select_par_representative`. Empty with `keep_par_twin`, and on every non-PAR module.
    par_twins_dropped: list[tuple[str, str, int]] = field(default_factory=list)
    # What the VRS minting pass did (RM40) — the same `MintResult` whose two counters `compile_module`
    # later stamps into `manifest.compilation.vrs_alleles` / `vrs_alleles_identified`, plus
    # `unmintable_reasons`, the grouped breakdown that is the actionable half.
    #
    # It was computed here and thrown away, so a consumer wanting to read coverage **before** a compile
    # — which is what a publish dry run is — had to re-implement the counting, and had to get two
    # non-obvious rules right to agree with the manifest a publish would produce: count per **ALT slot**
    # (`vrs_id` is a parallel array of `alts`), and treat an *absent* cell as `len(alts)` unnamed slots
    # rather than zero, or a table where nothing minted reports flawless coverage out of a denominator
    # of nothing. A number this workspace computed and discarded gets recomputed by every consumer, and
    # a recomputation is a place to drift.
    #
    # `None` — never a coverage of zero — when the pass did not run (`mint_vrs=False`). The house rule.
    vrs: MintResult | None = None
    # rsIDs the live Ensembl link could not be asked about — a failed request, never an empty answer
    # (S20). Separate from `unresolved`, which says a key has no position and is silent about why: a
    # row that failed to resolve because egress broke and one with genuinely no locus to find are the
    # same entry there, and only one of them is worth re-running. Same reason `clin_sig_not_checked`
    # exists beside an empty conflict list. Empty offline, since nothing was asked in the first place.
    unreachable_rsids: list[str] = field(default_factory=list)
    # rsIDs **no link was consulted about at all** — the `--offline` run on a machine with no Ensembl
    # and no ClinVar cache, where every link is gated off and there is nothing to ask (RM98). A third
    # state, deliberately not folded into either neighbour: `unreachable_rsids` means the request was
    # made and failed, and `unresolved` says a key has no position while staying silent about why.
    # This one says nobody looked, which is the only one of the three a `not_found` row would be a
    # plain fabrication of — the row used to be written, naming a cache that was never opened.
    unconsulted_rsids: list[str] = field(default_factory=list)
    # rsIDs the source HAS, whose every locus the allele-aware filter rejected (S85). The fourth state
    # in this family and the only one whose row is written anyway: `unreachable_rsids` means the
    # request failed, `unconsulted_rsids` that nobody looked, `unresolved` that a key has no position
    # and stays silent about why — and this one that the asking *succeeded* and the answer did not
    # match. The row is honestly unresolved, so it stays; what was wrong was the reason it gave.
    # Empty is a clean bill only because every branch that writes one appends here.
    allele_mismatches: list[AlleleMismatch] = field(default_factory=list)
    # What the rsid↔coordinate pass did (`resolver.check_rsid_coordinates`): the pairs it compared,
    # the ones the reference could not place, and the disagreements. Surfaced for the RM40/RM41 reason
    # — the run computes it and a consumer would otherwise recompute it from the log — and because the
    # denominator is the half a bare list of disagreements cannot state. `None` only for a caller that
    # built the result by hand; `enrich()` always sets it, carrying `not_checked` when the pass could
    # not run rather than an empty finding list that reads as a clean bill.
    rsid_coordinates: PairCheck | None = None
    # What a full re-derivation found had moved since the recorded table was written — `rederive=True`
    # only. **`None` is not `[]`**: `None` says nobody re-derived, and an empty list says every
    # recorded subject was re-asked and every one still answers the same. Only the second of those is
    # a clean bill, and only the second is worth printing (an empty one prints nothing at all — a
    # comparison that found nothing must not report a zero as though it were a finding).
    rederived: list[SubjectDrift] | None = None
    # Whether each release this module records having been drafted from is still the one its source
    # publishes (RM85). `--rederive`'s cheap neighbour: that one re-asks every source about every
    # subject and reports the rows that moved, this one asks about the release **label** alone, so it
    # is what tells an author whether the expensive question is worth putting. `None` only for a
    # caller that built the result by hand; `enrich()` always sets it, carrying `not_checked` when the
    # pass could not run rather than an empty finding list that would read as a clean bill.
    dataset_currency: CurrencyCheck | None = None

    @property
    def fully_resolved(self) -> bool:
        return not self.unresolved


def _subject_key(subject: object) -> tuple:
    """The `existing` key for a subject awaiting resolution, over the columns `ResolutionRow` declares.

    The dict is built with `base.merge_key` over real rows; a subject is a different type and cannot go
    through it, so the columns are read off the same `_KEY_FIELDS` rather than restated as
    `(v.variant_key,)`. A test asserts the two sides agree on a row built from a subject, which is what
    keeps a future member added to the key from silently splitting the two halves of this lookup (S51).
    """
    return tuple(getattr(subject, name) for name in ResolutionRow._KEY_FIELDS)

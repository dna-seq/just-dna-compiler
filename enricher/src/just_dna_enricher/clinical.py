"""The clinical cross-check: a module's authored `clin_sig` against ClinVar's own.

The cheapest bite out of the compiler's largest blind spot — *"is the annotation right?"* It cannot
answer that, and does not try: ClinVar is not truth either, and two curators reading the same evidence
may legitimately land in different places. What it *can* do is make sure an author who calls a variant
benign knows that ClinVar calls it pathogenic, and with how much review behind it.

**Why this lives in the enricher even though it never touches the network.** The tier boundary is not
"online vs offline", it is *does the check need a reference*. The compiler is inject-only by charter
(Principle 2) and holds no ClinVar; this check needs one, so it belongs here — beside
`sequences.verify_reference_alleles`, which needs the genome for the same structural reason. Reading
that boundary as "offline ⇒ compiler" would put it in the tier that cannot host it.

**It reports; it never repairs**, like every check in this tier, and:

**`strict` does not escalate it.** This is the one deliberate exception to severity-follows-the-mode,
and the reason is charter-level rather than pragmatic. Failing a compile on a ClinVar disagreement
would make the format arbitrate a clinical dispute — deciding that ClinVar is right and the curator is
wrong — which is precisely what the data-agnostic north star forbids: the format supplies annotation
tables and never a gene–disease inference. A curator who has read the primary literature and disagrees
with a one-star ClinVar submission is doing their job, not corrupting their module. So both modes warn,
and `review_stars` is carried into the message so a reader can weigh the disagreement themselves.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.clinvar import clinvar_dataset_label, lookup_clin_sig
from just_dna_enricher.concordance import (
    CLIN_SIG_CAMP,
    AuthorityCall,
    ConcordanceSubject,
    concordance_tables,
)
from just_dna_enricher.provenance import drafted_unchanged

logger = logging.getLogger(__name__)

#: Which annotation authority this module's comparison is against. One string, named once, because
#: RM130 took the authority out of the finding's field names and a literal in three places would put
#: it straight back.
CLINVAR_AUTHORITY: str = "clinvar"

#: The instrument ClinVar measures its own confidence on. Recorded beside the number rather than
#: converted into anybody else's scale: a gold-star count and a literature miner's evidence-depth
#: count are not the same quantity.
CLINVAR_CONFIDENCE_UNIT: str = "review_stars"


@dataclass
class ClinSigConflict:
    """One authored clinical significance an annotation authority's records do not support.

    **The authority is a field, not a field name** (RM130). This carried `clinvar: str` until 0.7,
    which read fine while there was one archive and would have cost a rename — major-only work under
    the additive rule — the moment a second one arrived. `clinvar` survives as a read-only alias so
    an existing caller keeps working; new code reads `authority_clin_sig` and `authority`.
    """

    variant_key: str
    genotype: str
    chrom: str
    start: int
    ref: str
    alt: str
    authored: str
    authority_clin_sig: str
    review_stars: int | None
    review_status: str | None
    condition: str | None
    #: True when the two are opposed calls (pathogenic-class vs benign-class) rather than merely
    #: different. An opposed pair is the finding worth acting on; the rest is worth knowing.
    #:
    #: **At one authority this is true of every conflict that is reported at all**, and that is a
    #: property of the comparison rather than a bug in the flag: the check only reports where both
    #: sides are opinionated and their camps differ, and `pathogenic` and `benign` are the only two
    #: opinionated camps. The distinction becomes live in the concordance record, where two
    #: authorities can differ without either of them opposing the module.
    opposed: bool = False
    authority: str = CLINVAR_AUTHORITY

    @property
    def clinvar(self) -> str:
        """The authority's own call. Superseded spelling of `authority_clin_sig`, kept for callers."""
        return self.authority_clin_sig

    @property
    def confidence(self) -> str:
        """How much review sits behind the authority's side, in the terms it itself uses."""
        if self.review_stars is None:
            return "unrated"
        return f"{self.review_stars}-star"

    def __str__(self) -> str:
        kind = "contradicts" if self.opposed else "differs from"
        detail = f" for {self.condition!r}" if self.condition else ""
        return (
            f"{self.variant_key} genotype {self.genotype}: authored clin_sig {self.authored!r} "
            f"{kind} {self.authority}'s {self.authority_clin_sig!r}{detail} at "
            f"{self.chrom}:{self.start} {self.ref}>{self.alt} ({self.confidence}, "
            f"{self.review_status!r}) — reported, never overwritten; a curator may legitimately "
            f"disagree with a low-reviewed submission"
        )


def _effect_allele(variant: VariantRow, ref: str, alts: list[str]) -> str | None:
    """The ALT the annotation is *about*, or `None` when it cannot be determined without guessing.

    `effect_allele` when the author stated it; otherwise the single genotype allele that is not the
    reference. A homozygous-reference genotype names no alt, and a genotype carrying two different
    alts names more than one — both are cases where picking would be inventing the author's intent,
    so both return `None` and the caller falls back to a locus-wide comparison.
    """
    if variant.effect_allele:
        return variant.effect_allele.upper()
    alleles = {
        allele.upper()
        for allele in variant.genotype.replace("|", "/").split("/")
        if allele
    }
    non_reference = sorted(alleles - {ref.upper()})
    if len(non_reference) == 1 and non_reference[0] in {a.upper() for a in alts}:
        return non_reference[0]
    return None


def tautology_reason(
    sources: Sequence[SourceRow], reference: Path | None, spec_dir: Path | None = None
) -> str | None:
    """Why this check cannot fail on this module, or `None` when it genuinely can (S4, re-keyed by RM4).

    A module drafted by `clinvar_draft` copied its `clin_sig` **out of the snapshot this check reads**,
    so the comparison is a value against itself: on a 7,818-row panel a consumer measured 27.1 s with
    the check on and 2.6 s with it off, byte-identical output, and 0 conflicts either way — necessarily
    0. Reporting "0 conflicts" there is mild misinformation, since it looks like evidence and is not,
    and the cost is real: 90% of the resolve time on a panel, ~83 s per batch on a genome-wide one.

    The check itself is one of the best things in this tier wherever a **human** typed the value, so
    the default does not change; what is needed is a way for a provider-drafted module to say "this
    came from you".

    **That marker is the licence row's `dataset`, not an authored `panel:` block (RM4).** The claim
    being established is *provenance* — these rows came from this snapshot — and the tool that copied
    them is the authority on it, so the enricher records it itself: `clinvar_draft` stamps the release
    into the `dataset` column of the `clinvar`/`annotation` row it already had to write, and this
    recomputes the same label from the snapshot in hand (`clinvar_dataset_label`, shared by both
    sides). The alternative was asking every author to maintain a declaration whose only reader is this
    one skip, which is bureaucracy the enricher exists to remove. The `panel:` block is deprecated in
    0.6 and keys nothing here any more.

    The row is matched at the **`annotation`** layer specifically: `enrich()` writes a second
    `clinvar` row at the `resolution` layer for the coordinates it looked up, and a coordinate is not
    a copied clinical call.

    Three-valued in the usual way: a module with no licence table, one whose ClinVar row records no
    dataset, an unreadable `release.json`, or a **different** release all return `None` and the check
    runs. Only an *established* match skips it — an unknown is never a permission to skip.

    **The release is half the question, and RM73 supplied the other half.** A matching release says
    the rows *were* copied out of this snapshot; it says nothing about whether they still are, which
    is the hole this function shipped with and named in its own message. `spec_dir` lets it recompute
    the drafter's digest over the `clin_sig` column and answer that too, so the skip is now a
    conjunction: same release **and** no checked value moved since. Either half failing runs the
    check, which is why the expensive per-row `strict` audit this used to defer to is gone — the
    digest answers the same question without a lookup, in both modes.

    `spec_dir` is optional so an existing caller keeps working, and omitting it is not treated as a
    pass: with no directory there is nothing to recompute, nothing is established, and the check
    runs.
    """
    label = clinvar_dataset_label(reference)
    if label is None:
        return None
    recorded = [
        (row.dataset or "").strip()
        for row in sources
        if row.source == "clinvar" and row.layer == "annotation" and (row.dataset or "").strip()
    ]
    if not recorded or any(dataset != label for dataset in recorded):
        return None
    if spec_dir is None or not drafted_unchanged(spec_dir, "clinvar", list(sources)):
        # Includes the `None` case on purpose — a module drafted before the digest existed has
        # established nothing about its cells, so it is checked in full rather than trusted.
        return None
    return (
        f"this module's licence row records that its ClinVar annotations were drafted from {label}, "
        f"the very snapshot this check reads, and every authored clin_sig still hashes to what the "
        f"drafter wrote — so each one is a copy of the value it would be compared against. What this "
        f"does not cover: a row hand-authored *before* a later re-draft, which the drafter's stamp "
        f"then covers along with its own. Edit any clin_sig and this check runs again in full"
    )


@dataclass
class ClinSigComparison:
    """What the cross-check actually put, and what it found (RM4, simplified by RM73).

    Two numbers and the findings. It carried a *provenance* breakdown until 0.6 — copied / authored /
    conflicting / no_record — which existed for one reason: the module-level release marker could not
    see a cell edited after the draft, so `strict` paid for a per-row look-up to recover the split the
    marker was blind to. `provenance.draft_digest` answers that question directly and offline, so the
    breakdown had no remaining consumer and the mode ladder under it collapsed: this check now behaves
    identically in both modes, which is what RM4 wanted and could not have.

    Removing it changed no verdict. The `copied` bucket was an early exit taken *before* the camp
    logic, and an exact match agrees with itself, so every row it caught already reached "no conflict"
    by the path below it.

    * `compared` — comparisons the snapshot could answer. One per resolved locus, which is one per row
      in the ordinary case, and the denominator `verification.json` publishes beside the findings.
    * `no_record` — resolved, but nothing at those coordinates to compare (or no ALT to ask about).
      Counted rather than folded into `compared`, which would claim a comparison nobody made.
    * `conflicts` — the disagreements, exactly as before.
    * `subjects` — every `(variant_key, genotype)` the comparison put a question about, with the
      authority's answer attached (RM130). The input to the concordance record, kept here rather
      than rebuilt by a second pass over the snapshot: re-asking would cost the whole comparison
      again, and a second implementation of the record-selection rule is a second place for it to
      drift from the one that decided the conflicts.
    """

    compared: int = 0
    no_record: int = 0
    conflicts: list[ClinSigConflict] = field(default_factory=list)
    subjects: list[ConcordanceSubject] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"{self.compared} authored clin_sig value(s) compared against ClinVar, "
            f"{len(self.conflicts)} in conflict; {self.no_record} had no ClinVar record to compare"
        )


def verify_clin_sig(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
) -> list[ClinSigConflict]:
    """Compare each authored `clin_sig` against the ClinVar snapshot. Returns the disagreements.

    The conflicts half of `compare_clin_sig`, which is where the comparison itself lives — one
    implementation, so the buckets and the findings can never disagree about a row. Empty when the
    snapshot could not be read at all; a caller that needs to tell that apart from "nothing
    disagreed" calls `compare_clin_sig` and branches on its `None`.
    """
    audit = compare_clin_sig(variants, resolution_rows, reference=reference)
    return audit.conflicts if audit is not None else []


def compare_clin_sig(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
) -> ClinSigComparison | None:
    """Compare each authored `clin_sig` against the ClinVar snapshot, and classify every comparison.

    `None` — never an audit of zeros — when the comparison could not be performed at all: no snapshot
    provisioned, or one that is present but not queryable. A check that could not run is not a check
    that passed, and an all-zero audit would read as the latter.

    Matching is on `(chrom, start, ref, alt)`, never on rsID, for the reason `lookup_clin_sig`
    documents. When the alt the annotation refers to cannot be determined, the comparison falls back to
    the *whole locus* and reports only if **no** ClinVar record there matches the authored call —
    conservative by construction, because the alternative is guessing which allele the author meant.

    Variants with no `clin_sig` are skipped: the module makes no clinical claim, so there is nothing to
    disagree with. `effective_clin_sig` is used rather than the raw column so a legacy row that set
    only the `pathogenic`/`benign` booleans is covered too.
    """
    if reference is None:
        logger.info("ClinVar clin_sig cross-check skipped: no snapshot provisioned this run.")
        return None

    resolved: dict[str, list[ResolutionRow]] = {}
    for row in resolution_rows:
        if row.chrom is not None and row.start is not None and row.ref and row.alts:
            resolved.setdefault(row.variant_key, []).append(row)

    # Collect every (allele, variant) pair worth asking about, in first-occurrence order so the query
    # and the emitted findings are deterministic (Principle 7).
    wanted: list[tuple[str, int, str, str]] = []
    seen: set[tuple[str, int, str, str]] = set()
    plan: list[tuple[VariantRow, str, list[tuple[str, int, str, str]], bool]] = []
    no_record = 0
    for variant in variants:
        authored = variant.effective_clin_sig
        if not authored or variant.variant_key not in resolved:
            continue
        for row in resolved[variant.variant_key]:
            alts = [a.strip() for a in (row.alts or "").split(",") if a.strip()]
            chosen = _effect_allele(variant, row.ref or "", alts)
            targets = [
                (row.chrom, row.start, row.ref, alt)
                for alt in ([chosen] if chosen else alts)
            ]
            for target in targets:
                if target not in seen:
                    seen.add(target)
                    wanted.append(target)
            if targets:
                plan.append((variant, authored, targets, chosen is None))
            else:
                # Resolved, but nothing to ask: the row names no ALT at this locus. Counted, not
                # dropped — an unasked question is not an answered one.
                no_record += 1

    if not wanted:
        return ClinSigComparison(no_record=no_record)
    try:
        records = lookup_clin_sig(reference, wanted)
    except Exception as exc:
        # Same degradation the resolver link uses: a located-but-unusable snapshot must not sink an
        # enrichment the rest of the chain can still complete. `None`, not an empty audit: nothing was
        # compared, and a zeroed breakdown would say the opposite.
        logger.warning(
            "ClinVar reference at %s is present but not queryable (%s); the clin_sig cross-check is "
            "skipped this run. Rebuild it with `just-dna-enricher clinvar build`.", reference, exc,
        )
        return None

    conflicts: list[ClinSigConflict] = []
    compared = 0
    # Per `(variant_key, genotype)` rather than per plan entry, because that is the concordance
    # record's key and one authored subject legitimately spans several loci when its rsID expands.
    # Insertion-ordered, so the record comes out in the module's own row order (Principle 7).
    pooled: dict[tuple[str, str], list[dict]] = {}
    conflicted: dict[tuple[str, str], ClinSigConflict] = {}
    authored_by_subject: dict[tuple[str, str], str] = {}
    for variant, authored, targets, locus_wide in plan:
        authored_camp = CLIN_SIG_CAMP.get(authored, "undecided")
        candidates = [
            (target, record)
            for target in targets
            for record in records.get(target, [])
            if record.get("clin_sig")
        ]
        subject = (variant.variant_key or "", variant.genotype)
        authored_by_subject[subject] = authored
        pooled.setdefault(subject, []).extend(record for _t, record in candidates)
        if not candidates:
            no_record += 1
            continue
        compared += 1
        if authored_camp in {"undecided", "orthogonal"}:
            continue
        # Agreement anywhere at the locus settles it — especially in the locus-wide fallback, where
        # several alts are in play and only one of them is the author's subject.
        if any(CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") == authored_camp for _t, r in candidates):
            continue
        opinionated = [
            (t, r) for t, r in candidates
            if CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") not in {"undecided", "orthogonal"}
        ]
        if not opinionated:
            continue
        # Report the best-reviewed disagreement: it is the one an author most needs to answer, and
        # `lookup_clin_sig` already ordered the records so the first is the best-reviewed.
        (chrom, start, ref, alt), record = opinionated[0]
        conflict = ClinSigConflict(
            variant_key=variant.variant_key or "",
            genotype=variant.genotype,
            chrom=chrom, start=start, ref=ref, alt=alt,
            authored=authored,
            authority_clin_sig=record["clin_sig"],
            review_stars=record.get("review_stars"),
            review_status=record.get("review_status"),
            condition=record.get("condition"),
            opposed=CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") != authored_camp
            and CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") in {"pathogenic", "benign"},
        )
        conflicts.append(conflict)
        conflicted.setdefault(subject, conflict)
        if locus_wide:
            logger.debug(
                "%s: compared against the whole locus (the annotation's ALT could not be determined "
                "from genotype %s)", variant.variant_key, variant.genotype,
            )
    return ClinSigComparison(
        compared=compared,
        no_record=no_record,
        conflicts=conflicts,
        subjects=_concordance_subjects(pooled, conflicted, authored_by_subject, reference),
    )


def _representative(records: list[dict], authored: str) -> dict | None:
    """The one ClinVar record that stands for this subject in the concordance record.

    Not "the first one", because a subject can pool several genuine records — different submissions,
    different conditions, and every alt at a locus when the annotation's own ALT could not be
    determined. The precedence is the two-way check's own, so the record and the finding cannot
    disagree about a subject: **an agreeing record wins**, because agreement anywhere settles the
    comparison and reporting a sibling allele's opposing call would manufacture a conflict out of
    ClinVar agreeing with the module; failing that the best-reviewed opinionated record, which is the
    one an author most needs to answer; failing that whatever was recorded, so an archive that spoke
    is never rendered as an archive that did not.
    """
    if not records:
        return None
    authored_camp = CLIN_SIG_CAMP.get(authored, "undecided")
    for record in records:
        if CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") == authored_camp:
            return record
    for record in records:
        if CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") in {"pathogenic", "benign"}:
            return record
    return records[0]


def _concordance_subjects(
    pooled: dict[tuple[str, str], list[dict]],
    conflicted: dict[tuple[str, str], ClinSigConflict],
    authored_by_subject: dict[tuple[str, str], str],
    reference: Path | None,
) -> list[ConcordanceSubject]:
    """Every subject the comparison asked about, with ClinVar's answer attached (RM130).

    **Derived from the comparison that already ran, never from a second pass.** A subject that
    produced a conflict is rendered from that conflict's own record, so the concordance verdict and
    the finding are the same fact told twice rather than two computations that could drift — which
    is the whole reason this is built here instead of by a caller re-reading the snapshot.

    A subject nothing was found for gets a `no_record` call, not an absent one: the archive was
    consulted and has nothing at those coordinates, which is an established absence. `unchecked` is
    reserved for an archive that could not be consulted at all, and that case never reaches here —
    `compare_clin_sig` returns `None` for it, because a check that could not run is not a check that
    found nothing.
    """
    dataset = clinvar_dataset_label(reference)
    subjects: list[ConcordanceSubject] = []
    for subject, records in pooled.items():
        variant_key, genotype = subject
        authored = authored_by_subject[subject]
        conflict = conflicted.get(subject)
        if conflict is not None:
            call = AuthorityCall(
                authority=CLINVAR_AUTHORITY,
                status="recorded",
                clin_sig=conflict.authority_clin_sig,
                clin_sig_raw=None,
                confidence=None if conflict.review_stars is None else str(conflict.review_stars),
                confidence_unit=None if conflict.review_stars is None else CLINVAR_CONFIDENCE_UNIT,
                dataset=dataset,
            )
        else:
            record = _representative(records, authored)
            stars = None if record is None else record.get("review_stars")
            call = AuthorityCall(
                authority=CLINVAR_AUTHORITY,
                status="no_record" if record is None else "recorded",
                clin_sig=None if record is None else record["clin_sig"],
                clin_sig_raw=None if record is None else record.get("clin_sig_raw"),
                confidence=None if stars is None else str(stars),
                confidence_unit=None if stars is None else CLINVAR_CONFIDENCE_UNIT,
                dataset=dataset,
            )
        subjects.append(
            ConcordanceSubject(
                variant_key=variant_key,
                genotype=genotype,
                authored_clin_sig=authored,
                calls=(call,),
            )
        )
    return subjects


def clin_sig_concordance(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
    checked_at: str | None = None,
) -> tuple[list[ClinSigConcordanceRow], list[ClinSigAuthorityCallRow]] | None:
    """The concordance record for a module, or `None` when the comparison could not be made at all.

    The record RM130 exists for: the contested subjects, named, in a form something can join to —
    against the counts the check has always published and the log lines nothing kept.

    `None` rather than two empty tables when there is no snapshot or an unusable one, and the
    distinction is the whole tri-state. Two empty tables are a claim (*nothing here is contested*);
    `None` says the question was never put, and the caller must not write a file that says the
    former when the latter happened.

    **One authority today, and the shape does not change when there are five.** The subject rows
    carry the agreement state and the call rows carry each authority's own words, so a second archive
    adds rows to the detail table and changes no key and no column.
    """
    comparison = compare_clin_sig(variants, resolution_rows, reference=reference)
    if comparison is None:
        return None
    return concordance_tables(comparison.subjects, checked_at=checked_at)

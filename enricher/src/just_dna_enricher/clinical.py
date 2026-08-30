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

from just_dna_enricher.clin_sig import CLIN_SIG_SEVERITY
from just_dna_enricher.clinvar import clinvar_dataset_label, lookup_clin_sig
from just_dna_enricher.concordance import (
    AUTHORITY_CALLS_CSV,
    CLIN_SIG_CAMP,
    CONCORDANCE_CSV,
    OPINIONATED_CAMPS,
    AuthorityCall,
    ConcordanceSubject,
    camp_of,
    concordance_tables,
)
from just_dna_enricher.provenance import DRAFT_PROJECTIONS, drafted_unchanged
from just_dna_enricher.pubmind import (
    PUBMIND_CONFIDENCE_UNIT,
    lookup_pubmind_calls,
    pubmind_dataset_label,
)

logger = logging.getLogger(__name__)

#: Which annotation authority this module's comparison is against. One string, named once, because
#: RM130 took the authority out of the finding's field names and a literal in three places would put
#: it straight back.
CLINVAR_AUTHORITY: str = "clinvar"

#: The instrument ClinVar measures its own confidence on. Recorded beside the number rather than
#: converted into anybody else's scale: a gold-star count and a literature miner's evidence-depth
#: count are not the same quantity.
CLINVAR_CONFIDENCE_UNIT: str = "review_stars"

#: The second annotation authority, added by RM134 § B. An authoritative *annotation* source in the
#: sense ClinVar is one, and never a resolver link: PubMind's coordinates are back-mappings of
#: extracted text, so nothing it says may enter `resolution.csv` (`@source-vs-authority`).
PUBMIND_AUTHORITY: str = "pubmind"

#: The order the authorities are consulted and their detail rows emitted in, fixed rather than derived
#: from a set: `clin_sig_authority_calls.csv` becomes a parquet whose bytes depend on row order, so a
#: run must not be able to emit the same two calls the other way round (Principle 7).
#:
#: A tuple rather than a list because it is a registry: the legs the check runs are built by walking
#: it, so an authority added to the check without a place here has nowhere to be consulted from.
AUTHORITY_ORDER: tuple[str, ...] = (CLINVAR_AUTHORITY, PUBMIND_AUTHORITY)


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


def is_tautological_leg(
    sources: Sequence[SourceRow],
    authority: str,
    dataset: str | None,
    spec_dir: Path | None,
) -> bool:
    """Would consulting this authority compare its own values against themselves? (RM134 § B)

    The conjunction RM4 established and RM73 completed, stated **once** and applied per authority:
    the module's licence row must name *this* release of *this* source — so the values really were
    copied out of what is about to be read — **and** the drafter's digest over the checked column
    must still match, so no cell has moved since. Either half missing runs the leg, which is the
    conservative direction: an unknown is never a permission to skip.

    Per **leg**, never per module, and that is the whole reason it is a predicate rather than the
    module-level `tautology_reason` generalized in place. A module drafted from ClinVar still gets a
    real comparison out of a second authority that copied nothing, so skipping the whole check would
    throw away a genuine finding to suppress a hollow one — the shape `enrich_pgx` already found the
    hard way when its CPIC leg went unmarked for two releases.

    Returns a plain `bool` rather than a tri-state on purpose: the two unknowns it can meet — no
    recorded digest, no `spec_dir` — both mean *nothing was established*, and nothing established is
    exactly the state in which a check runs. There is no third answer for a caller to act on.
    """
    if not dataset:
        return False
    recorded = [
        (row.dataset or "").strip()
        for row in sources
        if row.source == authority and row.layer == "annotation" and (row.dataset or "").strip()
    ]
    if not recorded or any(value != dataset for value in recorded):
        return False
    if spec_dir is None:
        return False
    # `drafted_unchanged` is tri-state and only `True` counts. `None` — a module drafted before the
    # digest existed — has established nothing about its cells, so it is checked in full rather than
    # trusted.
    return drafted_unchanged(spec_dir, authority, list(sources)) is True


def leg_tautology_note(
    sources: Sequence[SourceRow],
    authority: str,
    dataset: str | None,
    spec_dir: Path | None,
) -> str | None:
    """Why this authority's leg cannot fail on this module, or `None` when it genuinely can.

    The sentence an author reads for any authority but ClinVar, which keeps its own shipped wording
    in `tautology_reason`. The checked column is **derived** from `DRAFT_PROJECTIONS` rather than
    named here, so a drafting provider added later says which cell it copied without this function
    learning about it — and a source that drafts nothing at all can never reach this branch, because
    it records no digest for the predicate above to match.
    """
    if not is_tautological_leg(sources, authority, dataset, spec_dir):
        return None
    projection = DRAFT_PROJECTIONS.get(authority)
    column = projection.checked[0] if projection else "the checked column"
    return (
        f"{authority}: this module's licence row records that these rows were drafted from "
        f"{dataset}, the very snapshot this leg reads, and every authored {column} still hashes to "
        f"what the drafter wrote — so each is a copy of the value it would be compared against. This "
        f"authority is therefore not consulted at all: it states no call here, rather than one that "
        f"would agree with the module by construction. Edit any {column} and the leg runs again."
    )


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

    **The rule is shared with every other authority's leg and the prose is not** (RM134 § B). The
    conjunction lives in `is_tautological_leg`, which the PubMind leg calls with its own label, so
    two authorities cannot come to disagree about what "drafted from this very snapshot" means. This
    sentence stays here, verbatim, because a warning's text is an API and this one has shipped.
    """
    label = clinvar_dataset_label(reference)
    if not is_tautological_leg(sources, CLINVAR_AUTHORITY, label, spec_dir):
        return None
    return (
        f"this module's licence row records that its ClinVar annotations were drafted from {label}, "
        f"the very snapshot this check reads, and every authored clin_sig still hashes to what the "
        f"drafter wrote — so each one is a copy of the value it would be compared against. What this "
        f"does not cover: a row hand-authored *before* a later re-draft, which the drafter's stamp "
        f"then covers along with its own. Edit any clin_sig and this check runs again in full"
    )


@dataclass(frozen=True)
class PlannedComparison:
    """One authored clinical call and the alleles an authority will be asked about for it.

    The unit of the *reference-independent* half of the comparison: which subjects have a claim to
    check and which coordinates that claim lives at. Extracted from `compare_clin_sig` by RM134 § B
    because a second authority has to be asked about exactly the same alleles — building the plan
    twice, once per snapshot, is how the two legs would come to disagree about what was asked.
    """

    variant: VariantRow
    authored: str
    targets: tuple[tuple[str, int, str, str], ...]
    #: True when the annotation's own ALT could not be determined, so the whole locus is in play.
    locus_wide: bool

    @property
    def subject(self) -> tuple[str, str]:
        """The `(variant_key, genotype)` this comparison is about — the concordance record's key."""
        return (self.variant.variant_key or "", self.variant.genotype)


def comparison_plan(
    variants: list[VariantRow], resolution_rows: list[ResolutionRow]
) -> tuple[list[PlannedComparison], list[tuple[str, int, str, str]], int]:
    """`(plan, alleles to ask about, rows resolved with no ALT to ask about)`.

    Needs no snapshot and consults nothing, which is the point: every authority's leg is asked about
    the same alleles, and a leg that could not run does not change what a leg that did run was asked.

    The allele list is in first-occurrence order and deduplicated, so a batch look-up and the findings
    that come out of it are deterministic (Principle 7). The third element is a count rather than a
    silence: a resolved row naming no ALT is a question nobody could put, not a question answered
    with nothing.
    """
    resolved: dict[str, list[ResolutionRow]] = {}
    for row in resolution_rows:
        if row.chrom is not None and row.start is not None and row.ref and row.alts:
            resolved.setdefault(row.variant_key, []).append(row)

    wanted: list[tuple[str, int, str, str]] = []
    seen: set[tuple[str, int, str, str]] = set()
    plan: list[PlannedComparison] = []
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
                plan.append(
                    PlannedComparison(
                        variant=variant,
                        authored=authored,
                        targets=tuple(targets),
                        locus_wide=chosen is None,
                    )
                )
            else:
                # Resolved, but nothing to ask: the row names no ALT at this locus. Counted, not
                # dropped — an unasked question is not an answered one.
                no_record += 1
    return plan, wanted, no_record


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

    plan, wanted, no_record = comparison_plan(variants, resolution_rows)
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
    for entry in plan:
        variant, authored = entry.variant, entry.authored
        authored_camp = CLIN_SIG_CAMP.get(authored, "undecided")
        candidates = [
            (target, record)
            for target in entry.targets
            for record in records.get(target, [])
            if record.get("clin_sig")
        ]
        subject = entry.subject
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
        if entry.locus_wide:
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


@dataclass(frozen=True)
class AuthorityLegOutcome:
    """What happened when one annotation authority was approached, before any subject was asked.

    Three states, and the third is the one this release exists to keep honest:

    * `consulted` — a snapshot was open and answered. The only state that produces evidence.
    * `unchecked` — nobody asked. No snapshot was provisioned, or one was present and would not
      answer. Never an absence of records and never agreement (`@unreachable-not-absent`).
    * `tautological` — asking would compare the authority's own values against themselves, because
      this module's rows were drafted out of this very snapshot and have not moved since. The
      authority is left unconsulted and **states nothing**: a call recorded here would agree with the
      module by construction, and the record would publish that agreement as though somebody had
      checked it.
    """

    authority: str
    state: str
    dataset: str | None = None
    reason: str | None = None

    @property
    def consulted(self) -> bool:
        """Whether this leg produced evidence — the only state that lets a record be written."""
        return self.state == "consulted"


#: The three states above as a registry rather than literals scattered through the branches. Walked
#: by the test that asserts every member is reachable, so a fourth cannot arrive unexercised.
AUTHORITY_LEG_STATES: frozenset[str] = frozenset({"consulted", "unchecked", "tautological"})


@dataclass(frozen=True)
class ConcordanceRecord:
    """A run's concordance record: the two tables, plus everything the run measured making them.

    **Nothing here is computed and discarded** (`@dont-discard-computed`). The counts below are what
    a caller would otherwise recompute, and recomputing them means a second implementation of the
    selection rule — the drift RM130 built this record to avoid.
    """

    parents: list[ClinSigConcordanceRow]
    calls: list[ClinSigAuthorityCallRow]
    #: One per authority, in `AUTHORITY_ORDER`. Walked rather than restated, so an authority added to
    #: the check but not to the order has no leg to be consulted from.
    legs: tuple[AuthorityLegOutcome, ...]
    #: `(variant_key, genotype)` pairs the comparison put a question about — the denominator the
    #: contested count is read against.
    subjects: int
    #: Subjects for which an authority returned more than one record. PubMind's consolidation is on
    #: extracted *text*, so one allele legitimately carries several PVIDs; the multiplicity is a
    #: finding rather than tidy-up work (`@multiplicity-is-a-finding`).
    multi_record_subjects: int
    #: Subjects where one authority's own records straddle the pathogenic/benign line, so no single
    #: call represents it and the fold withholds by answering `conflicting`.
    internally_contested: int

    @property
    def consulted(self) -> tuple[str, ...]:
        """The authorities that actually answered, in consultation order."""
        return tuple(leg.authority for leg in self.legs if leg.consulted)

    @property
    def contested(self) -> int:
        """How many subjects reached the record. The numerator; `subjects` is the denominator."""
        return len(self.parents)


def concordance_sentences(record: ConcordanceRecord | None) -> list[str]:
    """The findings a run reports about its concordance record, warning-tier, in both modes.

    Empty for a run that could not put the question (`record is None`) and for one that found nothing
    contested. **A check that cannot fail reports no zero** (`@tautology-zero`), and neither does one
    that did run and found nothing — the denominator is on the record for a caller that wants it.

    Every sentence carries its denominator, because "9 contested" is unreadable without the number
    compared, and names the authorities that actually answered: the same nine subjects mean something
    different when one archive spoke and when three did.

    **Never escalated under `strict`** (`@clinsig-never-escalates`), and with more force here than
    for ClinVar alone. A disagreement with a literature miner's aggregate over the field is a
    statement about that extraction's limits at least as often as about the module, the corpus join
    measured 62 % agreement, and `discordant` is a fact about the field rather than a defect in the
    module. Reporting it as one would have the format arbitrate a clinical dispute.
    """
    if record is None or not record.parents:
        return []
    consulted = ", ".join(record.consulted)
    opposed = sum(1 for row in record.parents if row.opposed)
    discordant = sum(1 for row in record.parents if row.authority_concordance == "discordant")
    lines = [
        f"{record.contested} of {record.subjects} compared subject(s) are contested, "
        f"{opposed} of them on opposed calls — a pathogenic-class call against a benign-class one, "
        f"rather than a difference of confidence within one conclusion. Authorities consulted: "
        f"{consulted}. Reported and never escalated: a curator who has read the primary literature "
        f"may legitimately disagree. Answer one with an overrides.csv row naming "
        f"'{CONCORDANCE_CSV}', the subject's variant_key and its genotype, with your reason."
    ]
    if discordant:
        lines.append(
            f"{discordant} of {record.contested} contested subject(s) are a disagreement between "
            f"the authorities themselves rather than with the module. Nothing here resolves it: "
            f"picking a winner between two archives needs a weighting model this format does not "
            f"have, so each authority's own call is in {AUTHORITY_CALLS_CSV} for you to weigh."
        )
    return lines


def concordance_notes(record: ConcordanceRecord | None) -> list[str]:
    """What a run should say about its concordance record that is *not* a finding about the module.

    Info-tier, and said out loud rather than left silent: a leg that quietly did not run reads as a
    leg that found nothing, which is the failure this whole tri-state exists to prevent
    (`@unreachable-not-absent`). Three kinds of note:

    * an authority nobody could ask — unchecked is not absent, and it is never agreement;
    * an authority this module's own rows were drafted from, which is left unconsulted because its
      call would agree with the module by construction; and
    * the multiplicity, where one authority holds several records for one allele. Counted rather than
      collapsed, and the subset of those that straddle the pathogenic/benign line is counted
      separately because those are the ones no single call can represent.
    """
    if record is None:
        return []
    notes = []
    for leg in record.legs:
        if leg.state == "unchecked":
            notes.append(
                f"{leg.authority} was not consulted ({leg.reason}). Its call reads unchecked on "
                f"every subject: nobody asked is not an absence of records, and it is never "
                f"agreement."
            )
        elif leg.state == "tautological":
            notes.append(str(leg.reason))
    if record.multi_record_subjects:
        notes.append(
            f"{record.multi_record_subjects} of {record.subjects} subject(s) drew more than one "
            f"record from a single authority, and {record.internally_contested} of those straddle "
            f"the pathogenic/benign line. The straddling ones are recorded as 'conflicting' rather "
            f"than resolved to a winner, because picking one is an ordering nobody defined."
        )
    return notes


def fold_authority_records(records: Sequence[dict]) -> tuple[str | None, str | None, bool]:
    """`(clin_sig, clin_sig_raw, internally_contested)` for one authority's records about a subject.

    One authority can hold several records for one allele — ClinVar's several submissions, PubMind's
    several PVIDs over one coordinate — and the detail table is keyed
    `(variant_key, genotype, authority)`, so a subject carries **one** row per authority. Something
    has to stand for the set, and the two ways of getting that wrong are the interesting part.

    **The camp guard runs first, and it is the whole safety property.** When the records straddle the
    pathogenic/benign line there is no representative call, and folding by severity would silently
    answer `pathogenic` — severity ranks it above `benign`, so the more consequential verdict would
    win a vote nobody held. That is choosing a winner by an ordering nobody defined, which this item
    rejected outright. The answer is `conflicting`, the vocabulary's own word for exactly this, and
    it sits in the `undecided` camp so it opposes nothing and manufactures no disagreement.

    **Within one camp the fold is the shared normalizer's own rule.** `CLIN_SIG_SEVERITY` is what
    resolves a composite token — `Benign/Likely benign` becomes `likely_benign` — so resolving two
    records that say `Benign` and `Likely benign` the same way is one rule applied twice rather than
    a second rule invented here.

    `clin_sig_raw` keeps every distinct wording behind the fold, sorted and pipe-joined, so the
    answer stays auditable and a token this release does not model is still visible.
    """
    stated = [r for r in records if r.get("clin_sig")]
    if not stated:
        return None, None, False
    distinct = sorted({str(r["clin_sig"]) for r in stated})
    raw_tokens = sorted({str(r["clin_sig_raw"]) for r in stated if r.get("clin_sig_raw")})
    raw = "|".join(raw_tokens) or None
    opinionated = {camp_of(sig) for sig in distinct} & OPINIONATED_CAMPS
    if len(opinionated) > 1:
        return "conflicting", raw, True
    for sig in CLIN_SIG_SEVERITY:
        if sig in distinct:
            return sig, raw, False
    # Unreachable while `CLIN_SIG_SEVERITY` covers `VALID_CLIN_SIG` — an equality the shared
    # normalizer asserts at import — so reaching it is the shape of a registry that grew without its
    # walker, and it says so rather than returning a value nobody derived.
    raise ValueError(f"no severity rank for any of {distinct!r}")


def _pubmind_calls_by_subject(
    reference: Path,
    plan: Sequence[PlannedComparison],
    wanted: list[tuple[str, int, str, str]],
    dataset: str | None,
) -> tuple[dict[tuple[str, str], AuthorityCall], int, int] | None:
    """PubMind's call per subject, plus the two multiplicity counts. `None` if it will not answer.

    `None` rather than a dict of `no_record` calls when the snapshot is unusable, for the reason
    `compare_clin_sig` returns `None`: a leg that could not run has not found nothing, and rendering
    it as an archive with no records would turn a failure to ask into an established absence.

    Confidence is recorded **only where exactly one record stands behind the call**. PubMind's 0–3
    count is per record, so two records each reporting 2 do not make 2 the subject's evidence depth,
    and any function of the two would be an arithmetic nobody defined. Withheld, never averaged.
    """
    try:
        found = lookup_pubmind_calls(reference, wanted)
    except Exception as exc:
        # The same degradation the ClinVar leg uses: a located-but-unusable snapshot must not sink an
        # enrichment the rest of the chain can still complete. Broad because duckdb publishes no
        # exception base this tier may depend on, and because the alternative — letting it out — ends
        # the run over a snapshot nothing else needed.
        logger.warning(
            "PubMind reference at %s is present but not queryable (%s); its leg of the clin_sig "
            "concordance check reads unchecked this run. Rebuild it with "
            "`just-dna-enricher pubmind build`.", reference, exc,
        )
        return None

    pooled: dict[tuple[str, str], list[dict]] = {}
    for entry in plan:
        pooled.setdefault(entry.subject, []).extend(
            record for target in entry.targets for record in found.get(target, [])
        )
    calls: dict[tuple[str, str], AuthorityCall] = {}
    multi_record = 0
    contested = 0
    for subject, records in pooled.items():
        if len(records) > 1:
            multi_record += 1
        clin_sig, raw, internally_contested = fold_authority_records(records)
        contested += int(internally_contested)
        confidence = (
            str(records[0]["confidence"])
            if len(records) == 1 and records[0].get("confidence") is not None
            else None
        )
        calls[subject] = AuthorityCall(
            authority=PUBMIND_AUTHORITY,
            status="recorded" if clin_sig is not None else "no_record",
            clin_sig=clin_sig,
            clin_sig_raw=raw,
            confidence=confidence,
            confidence_unit=None if confidence is None else PUBMIND_CONFIDENCE_UNIT,
            dataset=dataset,
        )
    return calls, multi_record, contested


def clin_sig_concordance(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
    pubmind_reference: Path | None = None,
    sources: Sequence[SourceRow] | None = None,
    spec_dir: Path | None = None,
    checked_at: str | None = None,
    clinvar_comparison: ClinSigComparison | None = None,
) -> ConcordanceRecord | None:
    """The N-authority concordance record for a module, or `None` when nobody could be consulted.

    The record RM130 exists for and RM134 § B widened: the contested subjects, named, in a form
    something can join to — against the counts the check has always published and the log lines
    nothing kept.

    **The three-way check subsumes the two-way rather than running beside it.** With no PubMind
    snapshot that authority's calls read `unchecked`, which is what the tri-state is for, and the
    degenerate case is exactly the finding the ClinVar-only check reported: the same subjects are
    contested, the same conflicts are logged in the same words, and no author meets one disagreement
    twice. What changes is only what the record *withholds* — `authority_concordance` reads
    `unchecked` rather than `single`, because one authority speaking while another was never asked is
    not corroboration and must not be recorded as any.

    **`None` rather than empty tables when nobody could be consulted**, and the distinction is the
    whole tri-state. Two empty tables are a claim — *nothing here is contested* — and writing them
    after a comparison that never happened publishes that claim on no evidence. That is this
    release's most-repeated defect, a check agreeing with its own derivation, and this check is its
    likeliest home: it compares two normalizations, and a module drafted out of a snapshot it is then
    compared against agrees with itself by construction. So a record is written **iff at least one
    authority was actually consulted**, where consulted excludes:

    * an authority with no snapshot, or one that is present and will not answer; and
    * an authority whose values this module was drafted from and has not edited since — the
      tautology, decided **per leg** by `is_tautological_leg`, so a module drafted from ClinVar still
      gets a real comparison out of PubMind rather than losing the whole check to suppress half of it.

    Nothing resolves a split. At five authorities in a two-against-three disagreement, precedence and
    majority pick different winners and choosing needs a weighting model this workspace has declined
    to invent three times, so `authored_position` stays a relation to the *set* and a consumer with
    its own model computes what it likes from the detail rows.

    `clinvar_comparison` is the comparison a caller has **already run this run**, reused rather than
    repeated: `enrich()` performs it for the two-way findings, and asking the snapshot twice costs a
    consumer the whole look-up again (25 s on a 7,818-row panel) for an answer already in hand. It is
    ignored where the leg is tautological, which is the one case a caller holds no comparison for.
    """
    recorded_sources = list(sources) if sources is not None else []
    plan, wanted, _no_alt = comparison_plan(variants, resolution_rows)

    # ── the legs, walked from AUTHORITY_ORDER so the record cannot silently lose one ──────────────
    clinvar_dataset = clinvar_dataset_label(reference)
    pubmind_dataset = pubmind_dataset_label(pubmind_reference)
    clinvar_taut = (
        tautology_reason(recorded_sources, reference, spec_dir) if sources is not None else None
    )
    pubmind_taut = (
        leg_tautology_note(recorded_sources, PUBMIND_AUTHORITY, pubmind_dataset, spec_dir)
        if sources is not None
        else None
    )

    by_authority: dict[str, dict[tuple[str, str], AuthorityCall]] = {}
    outcomes: dict[str, AuthorityLegOutcome] = {}
    multi_record_subjects = 0
    internally_contested = 0

    if clinvar_taut is not None:
        outcomes[CLINVAR_AUTHORITY] = AuthorityLegOutcome(
            CLINVAR_AUTHORITY, "tautological", clinvar_dataset, clinvar_taut
        )
    else:
        comparison = clinvar_comparison
        if comparison is None:
            comparison = compare_clin_sig(variants, resolution_rows, reference=reference)
        if comparison is None:
            outcomes[CLINVAR_AUTHORITY] = AuthorityLegOutcome(
                CLINVAR_AUTHORITY, "unchecked", clinvar_dataset,
                "no ClinVar snapshot was provisioned, or the one present would not answer",
            )
        else:
            outcomes[CLINVAR_AUTHORITY] = AuthorityLegOutcome(
                CLINVAR_AUTHORITY, "consulted", clinvar_dataset
            )
            by_authority[CLINVAR_AUTHORITY] = {
                (subject.variant_key, subject.genotype): subject.calls[0]
                for subject in comparison.subjects
            }

    if pubmind_taut is not None:
        outcomes[PUBMIND_AUTHORITY] = AuthorityLegOutcome(
            PUBMIND_AUTHORITY, "tautological", pubmind_dataset, pubmind_taut
        )
    elif pubmind_reference is None:
        outcomes[PUBMIND_AUTHORITY] = AuthorityLegOutcome(
            PUBMIND_AUTHORITY, "unchecked", pubmind_dataset,
            "no PubMind snapshot was provisioned; it is operator-built and nothing provisions it "
            "for you (`just-dna-enricher pubmind build`)",
        )
    else:
        answered = _pubmind_calls_by_subject(pubmind_reference, plan, wanted, pubmind_dataset)
        if answered is None:
            outcomes[PUBMIND_AUTHORITY] = AuthorityLegOutcome(
                PUBMIND_AUTHORITY, "unchecked", pubmind_dataset,
                "the PubMind snapshot is present and would not answer",
            )
        else:
            pubmind_calls, multi_record_subjects, internally_contested = answered
            outcomes[PUBMIND_AUTHORITY] = AuthorityLegOutcome(
                PUBMIND_AUTHORITY, "consulted", pubmind_dataset
            )
            by_authority[PUBMIND_AUTHORITY] = pubmind_calls

    legs = tuple(outcomes[authority] for authority in AUTHORITY_ORDER)
    if not any(leg.consulted for leg in legs):
        logger.info(
            "The clinical-significance concordance record was not written: no authority could be "
            "consulted. %s",
            " ".join(f"{leg.authority}: {leg.reason}." for leg in legs),
        )
        # Every authority was either unasked or unaskable. A check that could not run reports no
        # zero: returning `None` leaves whatever record a previous run wrote exactly where it is,
        # rather than replacing it with two empty tables that claim nothing is contested.
        return None

    # Subject order is the module's own row order, taken from the plan rather than from whichever leg
    # answered — otherwise the emitted rows would depend on which snapshots a deployment happens to
    # hold (Principle 7).
    authored_by_subject: dict[tuple[str, str], str] = {}
    for entry in plan:
        authored_by_subject.setdefault(entry.subject, entry.authored)
    subjects: list[ConcordanceSubject] = []
    for subject, authored in authored_by_subject.items():
        calls_for_subject: list[AuthorityCall] = []
        for authority in AUTHORITY_ORDER:
            answers = by_authority.get(authority)
            if answers is not None:
                calls_for_subject.append(
                    answers.get(
                        subject,
                        AuthorityCall(
                            authority=authority,
                            status="no_record",
                            dataset=outcomes[authority].dataset,
                        ),
                    )
                )
            elif outcomes[authority].state == "unchecked":
                # An authority nobody could ask still gets a row, and it says so. Omitting it would
                # leave a reader unable to tell a two-authority agreement from a one-authority one,
                # and `classify_concordance` would read the silence as a closed set and answer
                # `matches_all` over a question that was never put.
                calls_for_subject.append(
                    AuthorityCall(
                        authority=authority,
                        status="unchecked",
                        dataset=outcomes[authority].dataset,
                    )
                )
            # A tautological authority contributes nothing at all: it was deliberately not consulted,
            # so it has neither a record nor an unasked question to report (`@unreachable-not-absent`
            # — write no row, and name it separately, which the leg's `reason` does).
        subjects.append(
            ConcordanceSubject(
                variant_key=subject[0],
                genotype=subject[1],
                authored_clin_sig=authored,
                calls=tuple(calls_for_subject),
            )
        )

    parents, calls = concordance_tables(subjects, checked_at=checked_at)
    return ConcordanceRecord(
        parents=parents,
        calls=calls,
        legs=legs,
        subjects=len(subjects),
        multi_record_subjects=multi_record_subjects,
        internally_contested=internally_contested,
    )

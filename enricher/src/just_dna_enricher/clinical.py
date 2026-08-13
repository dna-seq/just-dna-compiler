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

from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.clinvar import clinvar_dataset_label, lookup_clin_sig

logger = logging.getLogger(__name__)

# The four camps a clinical significance can fall into, for the purpose of deciding whether two values
# actually *disagree*. This is coarser than `VALID_CLIN_SIG` on purpose: `pathogenic` vs
# `likely_pathogenic` is a difference of confidence within one conclusion, not a conflict, and warning
# on it would bury the real finding under noise.
_CLIN_SIG_CAMP: dict[str, str] = {
    "pathogenic": "pathogenic",
    "likely_pathogenic": "pathogenic",
    "risk_factor": "pathogenic",
    "benign": "benign",
    "likely_benign": "benign",
    "protective": "benign",
    # Opinions that are not a pathogenic/benign call at all. Anything paired with one of these is not
    # a conflict — there is no opposing claim to conflict with.
    "uncertain_significance": "undecided",
    "conflicting": "undecided",
    "not_provided": "undecided",
    "other": "undecided",
    # Orthogonal axes: a drug-response or expression call is about something else entirely.
    "drug_response": "orthogonal",
    "association": "orthogonal",
    "affects": "orthogonal",
}


@dataclass
class ClinSigConflict:
    """One authored clinical significance that ClinVar's records do not support."""

    variant_key: str
    genotype: str
    chrom: str
    start: int
    ref: str
    alt: str
    authored: str
    clinvar: str
    review_stars: int | None
    review_status: str | None
    condition: str | None
    #: True when the two are opposed calls (pathogenic-class vs benign-class) rather than merely
    #: different. An opposed pair is the finding worth acting on; the rest is worth knowing.
    opposed: bool = False

    @property
    def confidence(self) -> str:
        """How much review sits behind ClinVar's side, in the terms ClinVar itself uses."""
        if self.review_stars is None:
            return "unrated"
        return f"{self.review_stars}-star"

    def __str__(self) -> str:
        kind = "contradicts" if self.opposed else "differs from"
        detail = f" for {self.condition!r}" if self.condition else ""
        return (
            f"{self.variant_key} genotype {self.genotype}: authored clin_sig {self.authored!r} "
            f"{kind} ClinVar's {self.clinvar!r}{detail} at {self.chrom}:{self.start} {self.ref}>"
            f"{self.alt} ({self.confidence}, {self.review_status!r}) — reported, never overwritten; "
            f"a curator may legitimately disagree with a low-reviewed submission"
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


def tautology_reason(sources: Sequence[SourceRow], reference: Path | None) -> str | None:
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
    return (
        f"this module's licence row records that its ClinVar annotations were drafted from {label}, "
        f"the very snapshot this check reads, so every authored clin_sig is a copy of the value it "
        f"would be compared against. Two things that leaves unseen: a cell edited by hand since the "
        f"draft, and rows added from another release. Re-run with --strict to look every row up and "
        f"report which values are still copies, which a human wrote, and which conflict"
    )


@dataclass
class ClinSigAudit:
    """What a full look-up found on a module that says it was drafted from this snapshot (RM4).

    The `strict` arm of the drafted-module ladder. `best_effort` keeps the module-level skip above,
    because deciding *per row* whether a value is still a copy requires exactly the look-up the skip
    exists to avoid; `strict` pays that cost and reports the split instead of a meaningless zero.

    Three disjoint outcomes, plus what could not be compared:

    * **copied** — the snapshot records this very value at this very allele. Nothing was learned, and
      nothing could have been: this is the tautology, now counted rather than assumed of the whole
      module. A row whose ALT could not be pinned down is never counted here, because a match against
      the locus may be a sibling allele's call; it lands in `authored` instead.
    * **authored** — the snapshot records something else that does not oppose it (a confidence
      refinement, an undecided call, an orthogonal one). A human wrote or edited this cell.
    * **conflicts** — the camps oppose. Exactly `verify_clin_sig`'s finding, unchanged, and the whole
      reason the hand-edit hole matters: a cell edited after the draft is the one thing the
      module-level skip cannot see.
    * **no_record** — resolved, but the snapshot has nothing to compare at those coordinates (or the
      row named no ALT to ask about). Counted rather than folded into `authored`, which would claim a
      human wrote something the check never looked up.

    Counts are per **comparison** — one per resolved locus a variant has, which is one per row in the
    ordinary case. Variants with no resolved locus are outside this entirely and are already named by
    `EnrichmentResult.unresolved`; recounting them here would publish the same number twice.
    """

    copied: int = 0
    authored: int = 0
    no_record: int = 0
    conflicts: list[ClinSigConflict] = field(default_factory=list)

    @property
    def compared(self) -> int:
        """Comparisons the snapshot could actually answer."""
        return self.copied + self.authored + len(self.conflicts)

    def __str__(self) -> str:
        return (
            f"{self.compared} authored clin_sig value(s) looked up: {self.copied} still a copy of "
            f"ClinVar's own, {self.authored} written or edited by hand and consistent with it, "
            f"{len(self.conflicts)} in conflict; {self.no_record} had no ClinVar record to compare"
        )


def verify_clin_sig(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
) -> list[ClinSigConflict]:
    """Compare each authored `clin_sig` against the ClinVar snapshot. Returns the disagreements.

    The conflicts half of `audit_clin_sig`, which is where the comparison itself lives — one
    implementation, so the buckets and the findings can never disagree about a row. Empty when the
    snapshot could not be read at all; a caller that needs to tell that apart from "nothing
    disagreed" calls `audit_clin_sig` and branches on its `None`.
    """
    audit = audit_clin_sig(variants, resolution_rows, reference=reference)
    return audit.conflicts if audit is not None else []


def audit_clin_sig(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
) -> ClinSigAudit | None:
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
        return ClinSigAudit(no_record=no_record)
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
    copied = authored_by_hand = 0
    for variant, authored, targets, locus_wide in plan:
        authored_camp = _CLIN_SIG_CAMP.get(authored, "undecided")
        candidates = [
            (target, record)
            for target in targets
            for record in records.get(target, [])
            if record.get("clin_sig")
        ]
        if not candidates:
            no_record += 1
            continue
        # Classified before any judgement about agreement, because "is this value a copy of the one it
        # is compared against" is a question about the *word*, not about the camps: `pathogenic` beside
        # `likely_pathogenic` agree and are not the same claim, and only one of them was copied. An
        # exact match also always agrees, so this never hides a conflict the old order would have found.
        #
        # Never in the locus-wide fallback: there `candidates` spans every ALT at the locus, so an exact
        # match may be a *sibling* allele's call rather than this row's, and "copied" would then say a
        # human did not write a cell a human wrote. Such a row falls through to the camp logic and lands
        # in `authored`, which understates rather than misattributes — the safe direction, since the
        # comparison really did run.
        if not locus_wide and any(record["clin_sig"] == authored for _t, record in candidates):
            copied += 1
            continue
        if authored_camp in {"undecided", "orthogonal"}:
            authored_by_hand += 1
            continue
        # Agreement anywhere at the locus settles it — especially in the locus-wide fallback, where
        # several alts are in play and only one of them is the author's subject.
        if any(_CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") == authored_camp for _t, r in candidates):
            authored_by_hand += 1
            continue
        opinionated = [
            (t, r) for t, r in candidates
            if _CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") not in {"undecided", "orthogonal"}
        ]
        if not opinionated:
            authored_by_hand += 1
            continue
        # Report the best-reviewed disagreement: it is the one an author most needs to answer, and
        # `lookup_clin_sig` already ordered the records so the first is the best-reviewed.
        (chrom, start, ref, alt), record = opinionated[0]
        conflicts.append(
            ClinSigConflict(
                variant_key=variant.variant_key or "",
                genotype=variant.genotype,
                chrom=chrom, start=start, ref=ref, alt=alt,
                authored=authored,
                clinvar=record["clin_sig"],
                review_stars=record.get("review_stars"),
                review_status=record.get("review_status"),
                condition=record.get("condition"),
                opposed=_CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") != authored_camp
                and _CLIN_SIG_CAMP.get(record["clin_sig"], "undecided") in {"pathogenic", "benign"},
            )
        )
        if locus_wide:
            logger.debug(
                "%s: compared against the whole locus (the annotation's ALT could not be determined "
                "from genotype %s)", variant.variant_key, variant.genotype,
            )
    return ClinSigAudit(
        copied=copied, authored=authored_by_hand, no_record=no_record, conflicts=conflicts
    )

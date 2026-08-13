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
from dataclasses import dataclass
from pathlib import Path

from just_dna_format.manifest import GenePanelSpec
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.clinvar import lookup_clin_sig
from just_dna_enricher.locations import read_release

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


def tautology_reason(panel: GenePanelSpec | None, reference: Path | None) -> str | None:
    """Why this check cannot fail on this module, or `None` when it genuinely can (S4).

    A module drafted by `clinvar_draft` copied its `clin_sig` **out of the snapshot this check reads**,
    so the comparison is a value against itself: on a 7,818-row panel a consumer measured 27.1 s with
    the check on and 2.6 s with it off, byte-identical output, and 0 conflicts either way — necessarily
    0. Reporting "0 conflicts" there is mild misinformation, since it looks like evidence and is not,
    and the cost is real: 90% of the resolve time on a panel, ~83 s per batch on a genome-wide one.

    The check itself is one of the best things in this tier wherever a **human** typed the value, so
    the default does not change; what was missing was any way for a provider-drafted module to say
    "this came from you". `GenePanelSpec.reference` / `reference_sha256` (RM4) is exactly that
    declaration, and `release.json` is the snapshot's own answer to the same question, so the two are
    compared and nothing is inferred.

    Three-valued in the usual way: a module with no `panel:` block, a panel over another source, an
    unstated pin, an unreadable `release.json`, or a **different** release all return `None` and the
    check runs. Only an *established* match skips it — an unknown is never a permission to skip.
    """
    if panel is None or reference is None or (panel.source or "").strip().lower() != "clinvar":
        return None
    release = read_release(reference)
    if not release:
        return None
    # Both halves must be declared and both must agree. The digest is the strong half — a release date
    # is a label, a sha256 is the bytes — but a panel that pins only the date still says something the
    # snapshot can confirm, so either pin alone is accepted when the other is unstated on both sides.
    pins = (
        ("release", (panel.reference or "").strip(), str(release.get("clinvar_file_date") or "")),
        ("sha256", _bare_digest(panel.reference_sha256), str(release.get("source_sha256") or "")),
    )
    stated = [(name, authored, actual) for name, authored, actual in pins if authored and actual]
    if not stated or any(authored != actual for _, authored, actual in stated):
        return None
    matched = ", ".join(f"{name} {authored}" for name, authored, _ in stated)
    return (
        f"this module declares it was drafted from the very snapshot the check reads ({matched}), so "
        f"every authored clin_sig is a copy of the value it would be compared against"
    )


def _bare_digest(value: str | None) -> str:
    """`sha256:abc…` and `abc…` are the same pin; `release.json` records the bare form."""
    return (value or "").strip().removeprefix("sha256:")


@dataclass(frozen=True)
class ClinSigCheck:
    """What the clinical cross-check did, not just what it found (RM45).

    `conflicts` alone is the same two-readings-one-value problem S4 fixed one layer up: an empty list
    means *nothing disagreed*, *no snapshot was provisioned*, *no authored call had a resolved locus*,
    and *the snapshot was present but would not answer*. `subjects` is the number of authored clinical
    claims actually compared, and `not_checked` carries a `VALID_VERIFICATION_SKIPS` key for the whole
    pass.

    The present-but-unqueryable branch is why this is a dataclass rather than a count bolted on beside
    the call: it is an internal degradation the caller could not see, so it used to leave
    `EnrichmentResult.clin_sig_not_checked` at `None` — the run reporting a clean cross-check it never
    completed, which is exactly the misinformation the other three skips were given reasons to avoid.
    """

    conflicts: list[ClinSigConflict]
    subjects: int = 0
    not_checked: str | None = None


def verify_clin_sig(
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
    *,
    reference: Path | None,
) -> ClinSigCheck:
    """Compare each authored `clin_sig` against the ClinVar snapshot. Returns the disagreements.

    Skipped (an empty `ClinSigCheck` carrying its reason) when no snapshot is provisioned — a check
    that could not run is not a check that passed, and the run says so rather than implying success.

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
        return ClinSigCheck([], 0, "no_reference")

    resolved: dict[str, list[ResolutionRow]] = {}
    for row in resolution_rows:
        if row.chrom is not None and row.start is not None and row.ref and row.alts:
            resolved.setdefault(row.variant_key, []).append(row)

    # Collect every (allele, variant) pair worth asking about, in first-occurrence order so the query
    # and the emitted findings are deterministic (Principle 7).
    wanted: list[tuple[str, int, str, str]] = []
    seen: set[tuple[str, int, str, str]] = set()
    plan: list[tuple[VariantRow, str, list[tuple[str, int, str, str]], bool]] = []
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

    if not wanted:
        # The check RAN and had nothing in scope, which is not a skip: the module authored no clinical
        # call that resolved to a locus. `subjects=0` with no reason is precisely that statement.
        return ClinSigCheck([], 0)
    try:
        records = lookup_clin_sig(reference, wanted)
    except Exception as exc:
        # Same degradation the resolver link uses: a located-but-unusable snapshot must not sink an
        # enrichment the rest of the chain can still complete.
        logger.warning(
            "ClinVar reference at %s is present but not queryable (%s); the clin_sig cross-check is "
            "skipped this run. Rebuild it with `just-dna-enricher clinvar build`.", reference, exc,
        )
        return ClinSigCheck([], 0, "no_reference")

    conflicts: list[ClinSigConflict] = []
    for variant, authored, targets, locus_wide in plan:
        authored_camp = _CLIN_SIG_CAMP.get(authored, "undecided")
        if authored_camp in {"undecided", "orthogonal"}:
            continue
        candidates = [
            (target, record)
            for target in targets
            for record in records.get(target, [])
            if record.get("clin_sig")
        ]
        if not candidates:
            continue
        # Agreement anywhere at the locus settles it — especially in the locus-wide fallback, where
        # several alts are in play and only one of them is the author's subject.
        if any(_CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") == authored_camp for _t, r in candidates):
            continue
        opinionated = [
            (t, r) for t, r in candidates
            if _CLIN_SIG_CAMP.get(r["clin_sig"], "undecided") not in {"undecided", "orthogonal"}
        ]
        if not opinionated:
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
    # The denominator is DISTINCT variants planned, not plan entries: a one-to-many rsID contributes
    # one entry per locus and the module made one clinical claim. Counting entries would report more
    # claims than the module holds.
    return ClinSigCheck(conflicts, len({v.variant_key for v, _a, _t, _l in plan}))

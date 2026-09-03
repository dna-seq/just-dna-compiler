"""RM170 — an authored direction over a variant CIViC has published a refutation of.

The defect this closes is not a missing value. It is that an author can write `direction=risk` over a
variant the same snapshot also rebuts, and every gate stays green. `contested_variants` cannot see the
pair: it counts a variant whose camps hold **both** `risk` and `protective`, and a `Does Not Support`
row enters no camp at all — `CIVIC_DIRECTION_MAP` sends it to `None`, because a refutation removes a
claim without establishing the opposite one (`@refutation-withholds`). So that counter is correctly 0
on every basis, and the muddy variants are invisible to it.

**The withhold is a slot beside the camps, never a member of them.** A snapshot variant carries three
independent things: the camps its `Supports` rows fill, a withhold any `Does Not Support` row raises,
and — once a module exists — the authored direction. Nothing here sums them into a point. Combining
signs would answer *what should the cell become?*, and RM170 asked for a **finding**: an enricher check
reports and never repairs (`@enrichment-is-validation`), and RM152 already refused filling `direction`
from a source's disagreement with itself. The house three-valued algebra is Kleene over *answers*, not
a metric over signs, so `risk` beside a withhold does not become `unknown` — it stays `risk` with a
warning next to it.

Two findings, deliberately two codes, because they are different sentences with different subjects and
one count over both would silently mix them:

* `refutation_beside_claim` — the source asserts **and** refutes. The RM170 case, e.g. VHL G104V:
  accepted supporting item 7134 against submitted refutation 10949.
* `refutation_without_claim` — the source has only ever refuted, and the module asserts a sign anyway.
  Author-versus-refutation rather than source-versus-itself. CHEK2 788 and TP53 4968 are the corpus.

**A finding keys on the refuting evidence item, then fans out to the authored rows it touches.** CIViC
evidence item 8721 is one statement about the two-variant genotype `VHL S183L AND VHL D126N`
(molecular profile 5278), and the snapshot writes it as two single-variant rows (RM174). Keying on the
evidence id means it is reported as **one** refutation over two subjects rather than as two
independent ones, which is true today and stays true whichever way RM174 is repaired.

**The status basis is part of the finding, not a weight.** Every assert-and-refute pair in CIViC rests
on a submitted refutation — measured in `docs/probes/CONTRADICTION_CORPORA.md`, where the two accepted
refutations in the whole database turn out to stand against nothing at all. A snapshot built on the
`accepted` basis therefore has an empty subject class *by construction*, so a run that finds nothing
must publish the basis it looked on; silence that does not name its basis reads as clear water.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.civic_build import CIVIC_PARQUET
from just_dna_enricher.clinical import comparison_plan
from just_dna_enricher.locations import RELEASE_FILENAME

logger = logging.getLogger(__name__)

#: The raw CIViC word for a refutation. Matched on the raw column rather than on a null `direction`:
#: a null direction means "Does Not Support" only because `CIVIC_DIRECTION_MAP` has no other
#: `None`-valued key, and that is an invariant of the map rather than something the row states about
#: itself. Reading the word the source wrote survives a fifth key being added to the map.
CIVIC_REFUTES: str = "Does Not Support"

#: One code per sentence. A permanent key names the **finding**, never the emission site
#: (`@warning-code-names-the-finding`), and these two have different subjects: one is a source
#: contradicting itself, the other an author asserting what the source only ever denied.
#:
#: **Deliberately not members of `VALID_WARNING_CODES`.** That vocabulary is the *compiler's*, and its
#: guard asserts every member is a code some compiler check actually builds — an enricher finding
#: reaches a compile through the attestation and is restated there as
#: `verification_findings_recorded`, so publishing these two beside the compiler's own would declare
#: codes nothing in that tier can emit. They key this pass's own findings and travel in the
#: verification record's `detail`.
REFUTATION_BESIDE_CLAIM: str = "refutation_beside_claim"
REFUTATION_WITHOUT_CLAIM: str = "refutation_without_claim"


@dataclass(frozen=True)
class EvidenceRef:
    """One CIViC evidence item as this finding needs to quote it."""

    evidence_id: str
    status: str | None
    direction_raw: str | None
    pmid: str | None = None

    def restate(self) -> str:
        """`EID 10949 (submitted)` — what a warning line puts in front of an author."""
        return f"EID {self.evidence_id}" + (f" ({self.status})" if self.status else "")


@dataclass(frozen=True)
class RefutedSubject:
    """One authored row a refutation touches."""

    variant_key: str
    genotype: str
    authored_direction: str
    civic_variant_id: str | None
    civic_variant_name: str | None
    gene: str | None


@dataclass(frozen=True)
class RefutationFinding:
    """One published refutation, and every authored row it lands on.

    Keyed by the refuting evidence item rather than by the variant, so a combination-genotype
    refutation is one finding with two subjects instead of two findings that look independent.
    """

    code: str
    refuting: tuple[EvidenceRef, ...]
    supporting: tuple[EvidenceRef, ...]
    subjects: tuple[RefutedSubject, ...]
    status_basis: str | None

    @property
    def combination(self) -> bool:
        """True when one evidence item refutes a genotype spanning more than one authored subject."""
        return len(self.subjects) > 1

    def restate(self) -> str:
        """The paragraph an author reads. Names both sides, their statuses, and the basis."""
        rows = ", ".join(
            f"{subject.variant_key} (`direction={subject.authored_direction}`"
            + (f", CIViC {subject.civic_variant_name}" if subject.civic_variant_name else "")
            + ")"
            for subject in self.subjects
        )
        refuting = ", ".join(ref.restate() for ref in self.refuting)
        basis = f" Snapshot basis `{self.status_basis}`." if self.status_basis else ""
        if self.code == REFUTATION_WITHOUT_CLAIM:
            return (
                f"{rows}: CIViC publishes {refuting} refuting a predisposition claim here and no "
                f"supporting item on this basis, so the module asserts a direction the source has "
                f"only ever denied. The row was not changed — a refutation withholds a claim, it "
                f"does not establish the opposite one.{basis}"
            )
        supporting = ", ".join(ref.restate() for ref in self.supporting)
        combination = (
            " That refutation is one statement about a combination genotype, so it lands on every "
            "row above rather than on each independently."
            if self.combination
            else ""
        )
        return (
            f"{rows}: CIViC has supporting {supporting} and Does-Not-Support {refuting}. A "
            f"refutation does not establish the opposite sign, so the row was not changed — but the "
            f"source both asserts and rebuts this claim, and only a reader of both can weigh it."
            f"{combination}{basis}"
        )


@dataclass
class RefutationComparison:
    """What was compared, and what was found. Never a stand-in for a check that could not run."""

    #: Authored rows carrying a `direction` that resolved onto a CIViC snapshot variant.
    subjects: int = 0
    #: Authored rows carrying a `direction` that no snapshot variant matched — asked, not answered.
    unmatched: int = 0
    findings: list[RefutationFinding] = field(default_factory=list)
    #: The basis the snapshot was built on, from its own `release.json`. `None` when unreadable —
    #: which is worth saying, because a finding count means nothing without it.
    status_basis: str | None = None


def _snapshot_release_basis(reference: Path) -> str | None:
    """`status_basis` out of the snapshot's own `release.json`, or `None` when it cannot be read."""
    release = reference / RELEASE_FILENAME if reference.is_dir() else reference.parent.parent / RELEASE_FILENAME
    if not release.exists():
        return None
    try:
        return json.loads(release.read_text(encoding="utf-8")).get("status_basis")
    except (OSError, ValueError):
        return None


def civic_snapshot_rows(reference: Path) -> list[dict]:
    """Every row of the CIViC snapshot parquet as plain dicts, or `[]` when there is none.

    Public and shared, because a second reading pass wanted exactly this and a private name is how a
    second caller stops finding the first (`@roster-is-as-wide-as-the-tables-it-reads`) — RM160's
    citation lane maps a module onto CIViC variant ids off the same rows. `civic_draft` keeps its own
    copy on purpose: that one **raises** on a missing snapshot because a draft with no source is a
    failed command, while a *check* with no snapshot is a skip, and one function cannot be both.

    Neither reader is imported at module scope for the reason `civic_draft._snapshot_rows` gives: a
    *reader* of a built snapshot must not drag the builder's dev extra in behind it.
    """
    parquet = reference / "data" / CIVIC_PARQUET if reference.is_dir() else reference
    if not parquet.exists():
        return []
    try:
        import polars as pl

        return pl.read_parquet(parquet).to_dicts()
    except ImportError:  # pragma: no cover - polars is present in this workspace's dev extra
        import pyarrow.parquet as pq

        return pq.read_table(parquet).to_pylist()


def _evidence(row: dict) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=str(row.get("evidence_id") or ""),
        status=row.get("evidence_status"),
        direction_raw=row.get("evidence_direction_raw"),
        pmid=row.get("pmid"),
    )


def compare_refutations(
    variants: Sequence[VariantRow],
    resolution_rows: Sequence[ResolutionRow],
    *,
    reference: Path | None,
) -> RefutationComparison | None:
    """Authored directions against the refutations CIViC publishes. `None` when nothing was compared.

    `None` — never a comparison of zeros — when no snapshot was provisioned or the one that was is
    unreadable. A check that could not run is not a check that passed, and the caller writes a
    `skipped` verification record from it rather than `ran, findings=0`.

    Matching goes through `comparison_plan`, the same resolved-coordinate route the ClinVar
    cross-check uses, so both authorities are asked about the same alleles. Rows with no authored
    `direction` are not subjects: the module makes no claim on this axis, so there is nothing for a
    refutation to sit beside.
    """
    if reference is None:
        logger.info("CIViC refutation check skipped: no snapshot provisioned this run.")
        return None
    rows = civic_snapshot_rows(reference)
    if not rows:
        logger.warning(
            "CIViC snapshot at %s is missing or unreadable; the refutation check is skipped this "
            "run. Build one with `just-dna-enricher civic build --release <date>`.", reference,
        )
        return None

    basis = _snapshot_release_basis(reference)
    # Every snapshot row that names a locus, grouped by the coordinate the plan asks about. A row with
    # no coordinate is unreachable from an authored one and is not counted as an absence here — the
    # snapshot's own `release.json` already accounts for those.
    by_target: dict[tuple[str, int, str, str], list[dict]] = {}
    for row in rows:
        chrom, start, ref, alt = row.get("chrom"), row.get("start"), row.get("ref"), row.get("alt")
        if chrom and start is not None and ref and alt:
            by_target.setdefault((str(chrom), int(start), str(ref), str(alt)), []).append(row)

    plan, _wanted, _no_alt = comparison_plan(
        list(variants), list(resolution_rows), authored=lambda variant: variant.direction
    )
    comparison = RefutationComparison(status_basis=basis)
    # Keyed by the refuting evidence ids so one statement about a combination genotype stays one
    # finding. Insertion-ordered, so findings come out in the module's own row order (Principle 7).
    grouped: dict[tuple[str, tuple[str, ...]], list[tuple[RefutedSubject, list[dict]]]] = {}
    for entry in plan:
        matched = [row for target in entry.targets for row in by_target.get(target, [])]
        if not matched:
            comparison.unmatched += 1
            continue
        comparison.subjects += 1
        refuting = [row for row in matched if row.get("evidence_direction_raw") == CIVIC_REFUTES]
        if not refuting:
            continue
        supporting = [row for row in matched if row.get("direction")]
        code = REFUTATION_BESIDE_CLAIM if supporting else REFUTATION_WITHOUT_CLAIM
        first = matched[0]
        subject = RefutedSubject(
            variant_key=entry.variant.variant_key or "",
            genotype=entry.variant.genotype,
            authored_direction=entry.authored,
            civic_variant_id=str(first.get("variant_id")) if first.get("variant_id") else None,
            civic_variant_name=first.get("variant_name"),
            gene=first.get("gene"),
        )
        key = (code, tuple(sorted({str(row.get("evidence_id") or "") for row in refuting})))
        grouped.setdefault(key, []).append((subject, matched))

    for (code, _ids), members in grouped.items():
        refuting_rows = {
            str(row.get("evidence_id")): row
            for _subject, matched in members
            for row in matched
            if row.get("evidence_direction_raw") == CIVIC_REFUTES
        }
        supporting_rows = {
            str(row.get("evidence_id")): row
            for _subject, matched in members
            for row in matched
            if row.get("direction")
        }
        comparison.findings.append(
            RefutationFinding(
                code=code,
                refuting=tuple(_evidence(row) for row in refuting_rows.values()),
                supporting=tuple(_evidence(row) for row in supporting_rows.values()),
                subjects=tuple(subject for subject, _matched in members),
                status_basis=basis,
            )
        )
    return comparison

"""Reference-sequence access, and the reference-allele check it makes possible.

This is the one place in the workspace that reads **actual bases**. Two callers need it: VRS indel
normalization (`vrs.py`), which must justify an allele against its surroundings, and the
reference-allele check below, which is the reason this module is more than plumbing.

**Enrichment is partly validation.** The enricher is the only tier that *can* compare authored data
against reality — the format and compiler tiers are inject-only by charter (Principle 2) and have no
reference to check anything against. So surfacing a discrepancy between what a module *claims* and what
the genome *says* is a goal of this tier, not a side effect of it. `verify_reference_alleles` is the
first check of that kind; `alts`-level and cross-source checks are the natural next ones.

**It reports; it never repairs.** A mismatch is surfaced with both values and left in place. Silently
rewriting an authored `ref` would destroy the evidence that something upstream is wrong — a liftover
run against the wrong assembly, an off-by-one, a hand-edited row — and would turn a loud data problem
into a quiet one. The author (or their pipeline) decides what the correct value is; the enricher's job
is to make sure they know there is a decision to make.

**Why this check has to exist at all.** A GA4GH VRS allele id is built from *which sequence*, *which
interval*, and *what replaces it* — the reference allele is not one of its components, because the
refget accession plus the interval already determine it (`sequence[start:end]` has exactly one answer).
That is correct and deliberate: a content-addressed identity must be a function of the allele, not of
the claim about it. But it means an authored `ref` is *unchecked* by minting. Two consequences, both
real:

- a wrong ref **base** is absorbed silently — `11:5227002 C>A` and the true `T>A` mint the same id;
- a wrong ref **length** is worse — it changes the interval, so it mints a well-formed id for a
  *different allele*, with nothing downstream able to notice.

VCF gets this check for free, because its `CHROM` is a name rather than a digest and `REF` is therefore
load-bearing. VRS trades that redundancy away for canonicality. This module buys the check back on the
one tier that has the sequence to do it with.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from ga4gh.vrs.dataproxy import create_dataproxy
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import UnsupportedBuildError, refget_accession

logger = logging.getLogger(__name__)

# The public seqrepo REST instance sequences are read from. A deployment with its own seqrepo points at
# it instead (`create_dataproxy` also accepts `seqrepo+file:///path/to/seqrepo/latest`), which is why
# this is a setting rather than a constant baked into the call sites.
DEFAULT_SEQREPO_URI = "seqrepo+https://services.genomicmedlab.org/seqrepo"

_ACGT = frozenset("ACGT")


@dataclass
class SequenceProxy:
    """Lazy, cached access to reference bases. `offline` makes every read return `None`.

    Two properties earn the wrapper over `create_dataproxy` directly: the proxy is built **at most
    once and only if actually needed** (a module of pure substitutions never touches the network for
    minting), and reads are **memoized** by `(accession, start, end)` — a module commonly asks about
    the same locus several times, and each miss is an HTTP round trip.
    """

    uri: str = DEFAULT_SEQREPO_URI
    offline: bool = False
    _proxy: object = None
    _tried: bool = False
    _cache: dict[tuple[str, int, int], str | None] = field(default_factory=dict)

    def proxy(self):
        """The underlying `ga4gh.vrs` data proxy, or `None` when offline or unreachable.

        `None` is a normal outcome, not an error: an offline run legitimately has no sequence access,
        and callers degrade (leave an id unminted, skip a check) rather than fail.
        """
        if self.offline or self._tried and self._proxy is None:
            return None
        if self._proxy is None:
            self._tried = True
            try:
                self._proxy = create_dataproxy(self.uri)
            except Exception as exc:
                logger.warning(
                    "Could not reach the sequence service at %s (%s); sequence-dependent work "
                    "(indel VRS ids, the reference-allele check) is skipped this run.", self.uri, exc,
                )
                return None
        return self._proxy

    def subsequence(self, accession: str, start: int, end: int) -> str | None:
        """Uppercased reference bases over the interbase interval `[start, end)`, or `None`."""
        key = (accession, start, end)
        if key in self._cache:
            return self._cache[key]
        proxy = self.proxy()
        result: str | None = None
        if proxy is not None:
            try:
                fetched = proxy.get_sequence(f"ga4gh:{accession}", start, end)
                result = fetched.upper() if fetched else None
            except Exception as exc:
                logger.warning("Sequence read failed for %s:[%d,%d) (%s)", accession, start, end, exc)
        self._cache[key] = result
        return result


@dataclass
class RefMismatch:
    """One row whose authored reference allele disagrees with the reference sequence.

    A mismatch has two quite different causes, and the finding names which one it found. Either the
    `ref` cell is wrong at a position that is right, or — the case that actually shows up in the wild
    — the *position* is wrong and `ref` was correct all along for the variant the author meant. The
    second is what a `pos - 1` conversion produces, and reporting it as a bad `ref` sends the author
    to the wrong column while leaving them to wonder why their coordinate "validated" against dbSNP.
    """

    variant_key: str
    chrom: str
    start: int
    claimed: str
    actual: str
    genome_build: str = "GRCh38"
    #: Offset, in bases, at which the authored `ref` *is* the reference sequence — `+1` means the
    #: variant sits one base to the right of the authored `start`, which is what subtracting one from
    #: a VCF position produces. `None` when no neighbour explains it: unknown, so nothing is claimed.
    shift: int | None = None

    @property
    def distorts_the_allele_id(self) -> bool:
        """Whether the mismatch also makes the minted VRS id describe a **different allele**.

        Three cases, and the middle one is why this is not simply a length test:

        - **A single-base claim at a position that is right: no.** The interval is one base wide
          whichever base the author thought was there, so the minted id is the true allele at that
          position — correct, despite the row being wrong. Only this check can surface it.
        - **A shifted coordinate: yes, whatever the length.** The id is minted at the authored
          position, so a shift means it addresses a base the author never meant. The id is still a
          correct digest of what it was given, which is exactly why nothing downstream can catch it:
          the compiler's VRS pass recomputes the same wrong id and reports it *verified*.
        - **A longer claim: yes.** The claimed length *sets the interval*, so a wrong `ref` means the
          allele spans the wrong bases and names an event the author did not intend.
        """
        return self.shift is not None or len(self.claimed) != 1

    @property
    def diagnosis(self) -> str:
        """The cause, as far as it was established — the grouping key for a run's summary."""
        if self.shift is not None:
            direction = "right" if self.shift > 0 else "left"
            return (
                f"coordinate shifted {abs(self.shift)} base to the {direction}: `start` is the "
                f"1-based VCF position and must not be converted"
            )
        if len(self.claimed) != 1:
            return "multi-base ref disagrees, so the allele spans the wrong bases"
        return "single-base ref disagrees at a position nothing else contradicts"

    def __str__(self) -> str:
        if self.shift is not None:
            return (
                f"{self.variant_key}: {self.genome_build} {self.chrom}:{self.start} is "
                f"{self.actual!r}, but the authored ref {self.claimed!r} is the base at "
                f"{self.chrom}:{self.start + self.shift} — the coordinate is off by {self.shift}, "
                f"not the ref. Any allele id minted for this row names the wrong position"
            )
        consequence = (
            "the minted allele id therefore describes a DIFFERENT allele"
            if self.distorts_the_allele_id
            else "the minted allele id is still the true allele at this position"
        )
        return (
            f"{self.variant_key}: authored ref {self.claimed!r} disagrees with {self.genome_build} "
            f"{self.chrom}:{self.start}, which is {self.actual!r} — {consequence}"
        )


def summarize_ref_mismatches(mismatches: Sequence[RefMismatch], *, examples: int = 3) -> list[str]:
    """Group findings by cause: one line per diagnosis with a count and a few named rows.

    A systematic mistake produces one finding per row — 56 lines for a 69-variant module, ~2,400 for a
    large panel — and a wall that long buries every other thing the run reported. Grouping by *reason*
    rather than by row is what makes the shared cause visible, which is the whole point: 2,400 rows
    disagreeing on `ref` reads as hopeless, while "2,400 rows are shifted one base right" is a
    one-line fix.
    """
    grouped: dict[str, list[RefMismatch]] = {}
    for mismatch in mismatches:
        grouped.setdefault(mismatch.diagnosis, []).append(mismatch)
    lines: list[str] = []
    for diagnosis, found in grouped.items():
        named = ", ".join(m.variant_key for m in found[:examples])
        more = f", and {len(found) - examples} more" if len(found) > examples else ""
        lines.append(f"{len(found)} row(s) — {diagnosis} ({named}{more})")
    return lines


@dataclass(frozen=True)
class RefCheck:
    """What the reference-allele check did, not just what it found (RM45).

    The mismatches alone answer one of the two questions a reader has, and the run used to discard the
    other: this function returns `[]` for *no row disagreed*, for *there was no sequence access*, and
    for *every row was a symbolic allele nothing could be compared*, and those are three different
    statements about a module. `subjects` is what was actually read and compared, and `not_checked`
    carries a `VALID_VERIFICATION_SKIPS` key when the whole pass could not run. Same shape, same
    argument, as `EnrichmentResult.clin_sig_not_checked` — extended here because `verification.json`
    publishes it, and publishing an empty finding list with no denominator is what RM45 exists to stop.
    """

    mismatches: list[RefMismatch]
    subjects: int = 0
    not_checked: str | None = None


def verify_reference_alleles(
    rows: list[ResolutionRow],
    *,
    sequences: SequenceProxy | None = None,
    offline: bool = False,
) -> RefCheck:
    """Compare each row's authored `ref` against the reference sequence. Returns the disagreements.

    Skipped (an empty `RefCheck` carrying its reason) when there is no sequence access — offline, or
    an unreachable service. A check that cannot run is not a check that passed, but it is also not a
    failure: the rest of the enrichment is unaffected, and the run says it was skipped.

    Rows without a coordinate, and rows whose `ref` is not plain ACGT (a symbolic or structural allele,
    RM5), are not checked — there is nothing to compare, and inventing a verdict would be worse than
    abstaining. Nor is a row whose read came back empty: the service answered nothing about that
    locus, so it is outside `subjects` rather than inside it with a clean bill. Reads are deduplicated
    through `SequenceProxy`'s cache, so a module asking about one locus repeatedly costs one round trip.
    """
    sequences = sequences or SequenceProxy(offline=offline)
    if sequences.proxy() is None:
        logger.info("Reference-allele check skipped: no sequence access this run.")
        # `offline` is a choice and `unreachable` is a failure, and only the second is worth a re-run.
        # Read off the proxy rather than the argument, so an injected offline proxy is described by
        # what it is instead of by what this call happened to be passed.
        return RefCheck([], 0, "offline" if (sequences.offline or offline) else "unreachable")

    mismatches: list[RefMismatch] = []
    subjects = 0
    for row in rows:
        if row.chrom is None or row.start is None or not row.ref:
            continue
        claimed = row.ref.strip().upper()
        if not claimed or not set(claimed) <= _ACGT:
            continue
        try:
            accession = refget_accession(row.chrom, row.genome_build)
        except UnsupportedBuildError:
            continue
        if accession is None:
            continue
        actual, shift = _read_with_neighbours(sequences, accession, row.start, len(claimed), claimed)
        if actual is None:
            continue
        subjects += 1
        if actual == claimed:
            continue
        mismatches.append(
            RefMismatch(
                variant_key=row.variant_key, chrom=row.chrom, start=row.start,
                claimed=claimed, actual=actual, genome_build=row.genome_build, shift=shift,
            )
        )
    return RefCheck(mismatches, subjects)


def _read_with_neighbours(
    sequences: SequenceProxy, accession: str, start: int, width: int, claimed: str
) -> tuple[str | None, int | None]:
    """The bases at `start`, plus which neighbouring offset (if any) carries `claimed` instead.

    One read, not three. The window spans one base either side of the claimed span, so establishing
    the shift costs the same round trip as not establishing it — which matters, because the rows that
    need the diagnosis are exactly the ones that come in thousands.

    The shift is returned only when **exactly one** neighbour matches. A homopolymer matches on both
    sides and settles nothing, so it reports `None` and the finding says only that the ref disagrees:
    an ambiguous direction is an unknown, and this codebase withholds rather than picks.
    """
    left_edge = start - 2  # interbase index of the base one to the LEFT of the claimed span
    if left_edge < 0:
        # At the very start of a contig there is no left neighbour; ask the plain question.
        actual = sequences.subsequence(accession, start - 1, start - 1 + width)
        after = sequences.subsequence(accession, start, start + width)
        return actual, (1 if after == claimed and actual != claimed else None)

    window = sequences.subsequence(accession, left_edge, start + width)
    if window is None or len(window) < width + 2:
        # A short window means a contig edge on the right; fall back to the unadorned comparison
        # rather than slicing a string that does not hold what the offsets assume.
        return sequences.subsequence(accession, start - 1, start - 1 + width), None

    actual = window[1 : 1 + width]
    before, after = window[0:width], window[2 : 2 + width]
    if actual == claimed:
        return actual, None
    candidates = [offset for offset, bases in ((-1, before), (1, after)) if bases == claimed]
    return actual, candidates[0] if len(candidates) == 1 else None

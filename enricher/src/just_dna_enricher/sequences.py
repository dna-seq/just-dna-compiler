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
from dataclasses import dataclass, field
from typing import Optional

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
    _cache: dict[tuple[str, int, int], Optional[str]] = field(default_factory=dict)

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

    def subsequence(self, accession: str, start: int, end: int) -> Optional[str]:
        """Uppercased reference bases over the interbase interval `[start, end)`, or `None`."""
        key = (accession, start, end)
        if key in self._cache:
            return self._cache[key]
        proxy = self.proxy()
        result: Optional[str] = None
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
    """One row whose authored reference allele disagrees with the reference sequence."""

    variant_key: str
    chrom: str
    start: int
    claimed: str
    actual: str
    genome_build: str = "GRCh38"

    @property
    def distorts_the_allele_id(self) -> bool:
        """Whether the wrong `ref` also makes the minted VRS id describe a **different allele**.

        The two failure modes differ in severity, and the difference is decided by the *claimed*
        length, not by comparing lengths (the actual bases are always read at the claimed length, so
        they cannot differ in length except at a contig edge):

        - **A single-base claim: no.** The interval is one base wide whichever base the author thought
          was there, so the minted id is the true allele at that position — correct, despite the row
          being wrong. Only this check can surface it.
        - **A longer claim: yes.** The claimed length *sets the interval*, so a wrong `ref` means the
          allele spans the wrong bases and names an event the author did not intend. This is the
          silent-corruption case, and nothing downstream can detect it.
        """
        return len(self.claimed) != 1

    def __str__(self) -> str:
        consequence = (
            "the minted allele id therefore describes a DIFFERENT allele"
            if self.distorts_the_allele_id
            else "the minted allele id is still the true allele at this position"
        )
        return (
            f"{self.variant_key}: authored ref {self.claimed!r} disagrees with {self.genome_build} "
            f"{self.chrom}:{self.start}, which is {self.actual!r} — {consequence}"
        )


def verify_reference_alleles(
    rows: list[ResolutionRow],
    *,
    sequences: Optional[SequenceProxy] = None,
    offline: bool = False,
) -> list[RefMismatch]:
    """Compare each row's authored `ref` against the reference sequence. Returns the disagreements.

    Skipped silently (empty list) when there is no sequence access — offline, or an unreachable
    service. A check that cannot run is not a check that passed, but it is also not a failure: the rest
    of the enrichment is unaffected, and the run logs that it was skipped.

    Rows without a coordinate, and rows whose `ref` is not plain ACGT (a symbolic or structural allele,
    RM5), are not checked — there is nothing to compare, and inventing a verdict would be worse than
    abstaining. Reads are deduplicated through `SequenceProxy`'s cache, so a module asking about one
    locus repeatedly costs one round trip.
    """
    sequences = sequences or SequenceProxy(offline=offline)
    if sequences.proxy() is None:
        logger.info("Reference-allele check skipped: no sequence access this run.")
        return []

    mismatches: list[RefMismatch] = []
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
        actual = sequences.subsequence(accession, row.start - 1, row.start - 1 + len(claimed))
        if actual is None or actual == claimed:
            continue
        mismatches.append(
            RefMismatch(
                variant_key=row.variant_key, chrom=row.chrom, start=row.start,
                claimed=claimed, actual=actual, genome_build=row.genome_build,
            )
        )
    return mismatches

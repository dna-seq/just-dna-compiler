"""The ClinGen Allele Registry — a CAID resolved to an identity this format can carry (RM153).

A ClinGen `allele_registry_id` (`CA341482`) is a **build-independent** name for an allele. CIViC
publishes one for most of the variants whose coordinates it only has on GRCh37, so the registry is the
route that places those rows without lifting anything over — which is the whole reason this module
exists rather than a liftover.

**It returns an rs-number where it can, and a GRCh38 coordinate only otherwise.** Both are usable, and
the preference is not stylistic. An rsID is build-independent, so a drafted row carrying one is placed
by the ordinary resolution chain rather than by us — and the value resolution then verifies came from
**dbSNP via ClinGen**, while the chain that verifies it is Ensembl. Two authorities, so the check is
real. That is the property RM48 refused a liftover for lacking: a lifted coordinate is the row's sole
identity with nothing independent to check it against, and an rs-number *recovered from the same
service that will later be asked* is the same defect wearing a different hat.

**Three outcomes, never two.** `resolved` / `no_identity` / `unchecked`. A registry that answers and
holds no placeable identity for a CAID (an indel whose alleles it cannot express as a substitution) is
a *fact* about the registry; a request that failed is not. Collapsing them is the S20 defect —
`([], None)` reading a failed request as an established absence — and it is the reason the outcome is a
dataclass rather than an optional tuple.

**Terms could not be established, and that is recorded rather than assumed.** The registry is run on
Baylor's Genboree infrastructure and its own `/site/terms` answers HTTP 200 with a generic
"broken link" page rather than a licence — the same shape as HPO's 404-behind-a-200, established by
probe on 2026-08-31. ClinGen's *gene-curation* surface is CC0, and this is a different surface, so that
grant is not evidence about these bytes. Unknown is not permissive: nothing here is redistributed, and
reading a public endpoint to place a row is a read rather than an acquisition anyone has gated
(`@acquisition-gate-is-not-a-read-gate`).
"""

import json
import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.net import PacingGate, attempt_floor

logger = logging.getLogger(__name__)

#: The registry's allele endpoint. No key, no authentication; probed 2026-08-31 over 102 CAIDs with
#: zero request failures.
CLINGEN_ALLELE_ENDPOINT = "https://reg.clinicalgenome.org/allele"

#: The build this module will accept a coordinate on. Named rather than spelled inline, for the reason
#: every sibling names its own: each build confusion in this package began as a bare literal.
CLINGEN_TARGET_BUILD = "GRCh38"

#: The registry publishes no rate limit. A tenth of a second is the pace the Ensembl client uses and it
#: kept a 102-CAID sweep comfortably inside whatever the server tolerates.
_REQUEST_INTERVAL = 0.1

#: What one lookup concluded. **Three, and the third is not padding** — the same rule
#: `VALID_RECOVERY_OUTCOME` states one module over: a registry that answered and has no placeable
#: identity is an established absence, while a request that failed is nobody-asked, and a pass that
#: reports the second as the first turns a network blip into a permanent negative about a variant.
VALID_CAID_OUTCOME: frozenset[str] = frozenset(
    {"resolved", "needs_anchor", "no_identity", "unchecked", "skipped_offline"}
)


class ClingenAlleleError(RuntimeError):
    """The registry could not be consulted in a way the caller must handle."""


@dataclass(frozen=True)
class AlleleIdentity:
    """What the registry holds for one CAID.

    `rsid` and `coordinate` are both optional and at least one is set when `outcome == "resolved"`;
    `coordinate` is `(chrom, start, ref, alt)` with `start` the **1-based** position this format's
    `start` column means (`@start-1based`), converted from the registry's interbase `start`/`end` pair.
    """

    caid: str
    outcome: str
    rsid: str | None = None
    coordinate: tuple[str, int, str, str] | None = None
    #: A one-sided indel the registry states in interbase terms, before an anchor base is read:
    #: `(chrom, interbase_start, reference_allele, allele)` with exactly one of the two alleles empty.
    #: Kept separate from `coordinate` because it is **not yet placeable** — it needs one reference
    #: base to become a VCF row, and a caller with no sequence access must not mistake it for one.
    #:
    #: **Set under `resolved` as well as under `needs_anchor`.** The registry serves an rs-number for
    #: most such alleles, which makes the outcome `resolved` on the rsID alone; the allele itself is
    #: still the only thing that says *which* allele, so it is carried rather than discarded.
    unanchored: tuple[str, int, str, str] | None = None

    @property
    def placeable(self) -> bool:
        """True when this carries something a `VariantRow` can be identified by.

        `unanchored` is deliberately **not** placeable: a half-stated allele is not a position
        (`@identity-whole-or-none`), and it becomes one only once `anchor_indel` has read the base.
        """
        return self.rsid is not None or self.coordinate is not None


def _parse(caid: str, payload: dict) -> AlleleIdentity:
    """The registry's JSON reduced to an identity, or `no_identity` when it holds none.

    The coordinate is taken **only** from the `GRCh38` genomic allele, never from whichever entry
    happens to come first: the payload lists NCBI36, GRCh37 and GRCh38 side by side plus a
    build-less transcript-relative one, and reading position 0 would silently place a row on hg18
    (`@assembly-first-wins`).

    A coordinate is accepted only where both alleles are stated. The registry expresses an insertion
    with an empty `referenceAllele`, which is a well-formed record and not a substitution this column
    can hold; withholding it is the `identity-whole-or-none` rule, and the rsID leg usually covers
    those rows anyway.
    """
    rsid = None
    for record in payload.get("externalRecords", {}).get("dbSNP", []) or []:
        rs = record.get("rs")
        if rs:
            rsid = f"rs{rs}"
            break

    coordinate = None
    unanchored = None
    for allele in payload.get("genomicAlleles", []) or []:
        if allele.get("referenceGenome") != CLINGEN_TARGET_BUILD:
            continue
        chrom = allele.get("chromosome")
        for c in allele.get("coordinates", []) or []:
            ref, alt = c.get("referenceAllele"), c.get("allele")
            start = c.get("start")
            if chrom and ref and alt and isinstance(start, int):
                # The registry is interbase: `start` is the 0-based position BEFORE the first
                # affected base, so the VCF POS this format's `start` column means is `start + 1`
                # (`@start-1based`). Read from `start`, never from `end`: the payload satisfies
                # `end == start + len(referenceAllele)`, so `end` is the POS only when `ref` is a
                # single base — and it silently runs `len(ref) - 1` bases too far right on every MNV
                # and two-sided delins, pairing a right-shifted position with a `ref` string
                # anchored at the left one. Measured on the registry: CA2499307077
                # (`c.272_273delinsAA`) is `start=10142118, end=10142120, ref='TC'`, whose POS is
                # 10142119 — the value `civic_identities` states by hand for the same allele, and
                # one base left of what reading `end` returns.
                coordinate = (str(chrom), int(start) + 1, str(ref), str(alt))
                break
            if chrom and isinstance(start, int) and (bool(ref) != bool(alt)):
                # A pure insertion (`ref` empty) or a pure deletion (`alt` empty). Neither is a VCF
                # row on its own — both need the preceding reference base as an anchor, which is the
                # left-aligned representation VCF and Picard/GATK use. The interbase `start` IS the
                # 1-based position of that anchor base, for both shapes.
                unanchored = (str(chrom), int(start), str(ref or ""), str(alt or ""))
                break
        break

    if rsid is None and coordinate is None and unanchored is None:
        return AlleleIdentity(caid=caid, outcome="no_identity")
    if rsid is None and coordinate is None:
        # Only a one-sided indel: real, and not yet a row. `no_identity` would be wrong (the registry
        # holds a perfectly good allele) and `resolved` would be wrong too, so the outcome waits.
        return AlleleIdentity(caid=caid, outcome="needs_anchor", unanchored=unanchored)
    # **`unanchored` travels on a `resolved` result too, and dropping it was a real loss.** The
    # registry answers with an rs-number for most one-sided indels, so `rsid` alone made the outcome
    # `resolved` while the one-sided allele this function had just parsed was discarded — leaving a
    # caller that wants the allele (rather than an identity to place a row by) with `coordinate=None`
    # and nothing to anchor, and no way to tell that from a registry record holding no allele at all.
    # The two consumers are unaffected either way: `civic_draft` reads `unanchored` only under
    # `outcome == "needs_anchor"`, and `placeable` is about `rsid`/`coordinate`. `@dont-discard-computed`.
    return AlleleIdentity(
        caid=caid, outcome="resolved", rsid=rsid, coordinate=coordinate, unanchored=unanchored
    )


def anchor_indel(
    unanchored: tuple[str, int, str, str], read_base
) -> tuple[str, int, str, str] | None:
    """A one-sided indel plus one reference base → a VCF-style row, or `None` if the base is unknown.

    **This is the left-aligned representation VCF requires and Picard/GATK produce.** An insertion and
    a deletion each state one side of the change and leave the other empty, which no `ref`/`alts` pair
    can hold; anchoring prefixes both sides with the single reference base immediately before the
    event, so `ref` and `alts` are both non-empty and the row means exactly what the registry said:

        deletion of `A` after base P   →  POS=P, REF=<base P> + "A", ALT=<base P>
        insertion of `G` after base P  →  POS=P, REF=<base P>,       ALT=<base P> + "G"

    The registry's interbase `start` is already that P, for both shapes, which is why one rule covers
    them and no per-shape arithmetic appears here.

    `read_base` is injected — `(chrom, one_based_pos) -> str | None` — so this stays a pure function
    with the network on the outside, and so a test can exercise both shapes without a sequence
    service. `None` when the base cannot be read: an unknown anchor is withheld, never guessed, and a
    guessed anchor would put a wrong `ref` on a right position, which is the mismatch class
    `sequences.RefMismatch` exists to report.
    """
    chrom, pos, ref, alt = unanchored
    if pos < 1:
        # An event at the very start of a contig has no preceding base to anchor on. Rare enough to be
        # theoretical and cheap enough to refuse outright rather than special-case.
        return None
    base = read_base(chrom, pos)
    if not base:
        return None
    base = base.upper()
    return (chrom, pos, base + ref, base + alt)


class ClingenAlleleClient:
    """Resolve CAIDs, one at a time, paced, with a per-run cache.

    A class rather than a function because the pacing gate and the cache are per-run state, and a
    module-level one would make two callers in one process share a clock they did not agree on.
    """

    def __init__(self, *, offline: bool = False, client: httpx.Client | None = None) -> None:
        self._offline = offline
        self._client = client
        self._gate = PacingGate(_REQUEST_INTERVAL)
        self._cache: dict[str, AlleleIdentity] = {}

    def resolve(self, caid: str) -> AlleleIdentity:
        """One CAID → an identity, an established absence, or nobody-asked."""
        caid = (caid or "").strip()
        if not caid:
            return AlleleIdentity(caid=caid, outcome="no_identity")
        if self._offline:
            return AlleleIdentity(caid=caid, outcome="skipped_offline")
        if caid in self._cache:
            return self._cache[caid]
        try:
            payload = self._fetch(caid)
        except httpx.HTTPStatusError as exc:
            # A 404 is the registry answering: it has no such allele. Any other status is a failure to
            # ask, and the two must not collapse.
            if exc.response.status_code == 404:
                result = AlleleIdentity(caid=caid, outcome="no_identity")
            else:
                logger.warning("ClinGen Allele Registry returned %s for %s", exc.response.status_code, caid)
                result = AlleleIdentity(caid=caid, outcome="unchecked")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ClinGen Allele Registry could not be consulted for %s (%s)", caid, exc)
            result = AlleleIdentity(caid=caid, outcome="unchecked")
        else:
            result = _parse(caid, payload)
        self._cache[caid] = result
        return result

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential_jitter(initial=0.5, max=8),
        stop=attempt_floor(3),
        reraise=True,
    )
    def _fetch(self, caid: str) -> dict:
        self._gate.wait()
        client = self._client or httpx
        response = client.get(f"{CLINGEN_ALLELE_ENDPOINT}/{caid}", timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return json.loads(response.text)

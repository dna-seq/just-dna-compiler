"""VRS allele-id minting for the resolution table — the enricher half of the identity story.

The format tier mints a `ga4gh:VA.…` for a **substitution** with pure stdlib and no sequence access
(`just_dna_format.vrs.derive_vrs_allele_id`). That covers most rows and costs nothing, online or off.
What it cannot do is an **indel**: a VRS allele id is defined over the *fully justified* allele, and
justifying an indel means reading the reference sequence around it to see how far the event can slide.
Sequence access is network access, and network access belongs here (Principle 2) — so the indel half
of minting lives in this module and nowhere else.

**Complete allele identity is the default, not an extra.** The plan budgeted for `ga4gh.vrs[extras]`
— `seqrepo` + `pysam` + `hgvs`, a compiled extension and a multi-gigabyte local sequence store — on
the belief that normalization needs a *local* seqrepo. Probing showed it does not: core `ga4gh.vrs`
plus the seqrepo **REST** data proxy normalizes indels over HTTP, at a cost of 14 pure-Python packages
with no compiled dependencies. Reading a remote sequence is exactly what a network tier is for, so at
that price there is no reason to make complete identity opt-in. `ga4gh.vrs` is therefore a **core**
dependency, indels are minted by default, and `--offline` is the only thing that turns it off.

(`AlleleTranslator` is deliberately unused despite being the obvious entry point: it imports `hgvs` at
module scope, which drags the heavy tree back in for a convenience wrapper we do not need.
`normalize()` + `ga4gh_identify()` are the two functions that matter.)

Three ways a row can get an id, in precedence order:

1. **Minted locally, stdlib** — a substitution. Zero egress, and verified against the library itself
   to be byte-identical (see `enricher/tests/test_vrs_mint.py`), so the offline answer and the online
   answer for a substitution are the same answer.
2. **Minted, normalized** — an indel/MNV, justified against the reference over the REST proxy. Needs
   the network, so `--offline` skips it.
3. **Left null** — an indel in an offline run, an unreachable sequence service, or an off-assembly
   contig. A missing id is the honest outcome; an unjustified one would be a `ga4gh:VA.…` string that
   *looks* interoperable and silently is not.

A source's own id (gnomAD serves one) is never written over a locally-minted value. It is compared
against it, and a disagreement is logged loudly — that cross-check is free provenance, and it is how a
bug in either implementation would surface.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ga4gh.core.identifiers import ga4gh_identify
from ga4gh.vrs import models, normalize
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import (
    VRS_SPEC_VERSION,
    UnsupportedBuildError,
    derive_vrs_allele_id,
    is_substitution,
    refget_accession,
)

from just_dna_enricher.sequences import DEFAULT_SEQREPO_URI, SequenceProxy

logger = logging.getLogger(__name__)


@dataclass
class MintResult:
    """What a minting pass did — counted by *how*, because the routes have different costs and
    different verifiability (the compiler can recompute a stdlib id and cannot recompute a
    normalized one)."""

    minted_stdlib: int = 0
    minted_normalized: int = 0
    skipped_unmintable: int = 0
    already_present: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def minted(self) -> int:
        return self.minted_stdlib + self.minted_normalized


@dataclass
class VrsMinter:
    """Mints allele ids: substitutions always, indels whenever the run is allowed to reach the network.

    Sequence access comes from a shared `SequenceProxy`, so a run that both mints indels and checks
    reference alleles builds one proxy and shares one read cache between them.
    """

    seqrepo_uri: str = DEFAULT_SEQREPO_URI
    offline: bool = False
    sequences: Optional[SequenceProxy] = None

    def __post_init__(self) -> None:
        if self.sequences is None:
            self.sequences = SequenceProxy(uri=self.seqrepo_uri, offline=self.offline)

    def _data_proxy(self):
        """The underlying data proxy, or `None` when offline or unreachable (a normal outcome —
        the caller leaves the indel's id unset, exactly as it leaves an unresolved position unset)."""
        assert self.sequences is not None
        return self.sequences.proxy()

    def mint(
        self,
        chrom: Optional[str],
        start: Optional[int],
        ref: Optional[str],
        alt: Optional[str],
        *,
        build: str = "GRCh38",
    ) -> tuple[Optional[str], Optional[str]]:
        """Return `(vrs_id, how)` where `how` is `"stdlib"`, `"normalized"`, or `None`.

        Reporting *how* rather than only *what* is deliberate: a normalized id depended on a live
        sequence service and a substitution's did not, and the compiler's verify pass — which can
        recompute one class and not the other — needs to be able to tell them apart.
        """
        if chrom is None or start is None or ref is None or not alt:
            return None, None
        if is_substitution(ref, alt):
            return derive_vrs_allele_id(chrom, start, ref, alt, build=build), "stdlib"
        minted = self._mint_normalized(chrom, start, ref, alt, build)
        return minted, ("normalized" if minted is not None else None)

    def _mint_normalized(
        self, chrom: str, start: int, ref: str, alt: str, build: str
    ) -> Optional[str]:
        """Justify an indel/MNV against the reference and mint its id, or return `None`."""
        proxy = self._data_proxy()
        if proxy is None:
            return None
        try:
            accession = refget_accession(chrom, build)
        except UnsupportedBuildError:
            return None
        if accession is None:
            return None
        allele = models.Allele(
            location=models.SequenceLocation(
                sequenceReference=models.SequenceReference(refgetAccession=accession),
                start=start - 1,
                end=start - 1 + len(ref),
            ),
            state=models.LiteralSequenceExpression(sequence=alt.upper()),
        )
        # A failure here is a live-service problem (unreachable, a contig it does not know), never a
        # reason to fail the enrichment — a null id degrades exactly like an unresolved position does.
        try:
            return ga4gh_identify(normalize(allele, data_proxy=proxy))
        except Exception as exc:
            logger.warning(
                "VRS normalization failed for %s:%s %s>%s (%s); leaving vrs_id unset",
                chrom, start, ref, alt, exc,
            )
            return None


def _single_alt(alts: Optional[str]) -> Optional[str]:
    """The one ALT of a row, or `None` when absent or multi-allelic.

    A VA names exactly one allele, so a comma-joined cell has no single id — picking one would be a
    data error wearing an identifier.
    """
    if alts and "," not in alts:
        return alts.strip() or None
    return None


def mint_resolution_rows(
    rows: list[ResolutionRow],
    *,
    minter: Optional[VrsMinter] = None,
    offline: bool = False,
    source_ids: Optional[dict[str, str]] = None,
) -> MintResult:
    """Stamp `vrs_id`/`vrs_spec` onto every mintable row, in place. Returns what it did.

    An **existing** `vrs_id` is never overwritten — the same "already there is authoritative" rule
    `enrich()` applies to the rest of the table, so a hand-corrected id survives a re-run.

    `source_ids` maps `variant_key` to an id a *source* reported (gnomAD serves one per variant). It is
    used only as a cross-check against what we minted, never as the value: trusting it would make our
    identity depend on which sources happened to answer, and the whole point of a content-addressed id
    is that it does not.
    """
    minter = minter or VrsMinter(offline=offline)
    result = MintResult()
    for row in rows:
        alt = _single_alt(row.alts)
        if row.vrs_id is not None:
            result.already_present += 1
        else:
            vrs_id, how = minter.mint(row.chrom, row.start, row.ref, alt, build=row.genome_build)
            if vrs_id is None:
                result.skipped_unmintable += 1
            else:
                row.vrs_id = vrs_id
                row.vrs_spec = VRS_SPEC_VERSION
                if how == "stdlib":
                    result.minted_stdlib += 1
                else:
                    result.minted_normalized += 1
        reported = (source_ids or {}).get(row.variant_key)
        if reported and row.vrs_id and reported != row.vrs_id:
            message = (
                f"{row.variant_key}: source reported vrs_id {reported} but we minted {row.vrs_id}"
            )
            logger.warning("%s — keeping the minted value", message)
            result.mismatches.append(message)
    return result

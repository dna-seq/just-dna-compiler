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

All three are decided **per ALT, not per row**: `vrs_id` is a comma-joined parallel array of `alts`
(`just_dna_format.vrs.split_vrs_ids`), so a multi-allelic site names each of its alleles and a hole
marks the one that could not be minted. Deciding it per row is what left 909 of 1,613 rows in a real
module with no id at all while every input needed to mint them sat in the same row.

A source's own id (gnomAD serves one) is never written over a locally-minted value. It is compared
against it, and a disagreement is logged loudly — that cross-check is free provenance, and it is how a
bug in either implementation would surface.
"""

import logging
from dataclasses import dataclass, field

from ga4gh.core.identifiers import ga4gh_identify
from ga4gh.vrs import models, normalize
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import (
    VRS_SPEC_VERSION,
    UnsupportedBuildError,
    derive_vrs_allele_id,
    is_substitution,
    join_vrs_ids,
    refget_accession,
    split_vrs_ids,
)

from just_dna_enricher.sequences import DEFAULT_SEQREPO_URI, SequenceProxy

logger = logging.getLogger(__name__)


@dataclass
class MintResult:
    """What a minting pass did — counted by *how*, because the routes have different costs and
    different verifiability (the compiler can recompute a stdlib id and cannot recompute a
    normalized one).

    The three minting counters are **per allele**, not per row: a multi-allelic site mints one id per
    ALT, so a row can contribute to `minted_stdlib` and `skipped_unmintable` at once. `already_present`
    is **per row**, because an existing `vrs_id` is left alone whole — the pass does not reach inside a
    cell it did not write. For the single-alt rows that are most of any table the two granularities
    coincide, which is why the counters kept their names.
    """

    minted_stdlib: int = 0
    minted_normalized: int = 0
    skipped_unmintable: int = 0
    already_present: int = 0
    mismatches: list[str] = field(default_factory=list)
    #: `reason -> allele count` for every allele left without an id. Grouped by reason rather than
    #: listed per row: this pass runs over whole tables, and a per-row line buries every other finding
    #: a run produces (the same collapse the CPIC provider needed four times).
    unmintable_reasons: dict[str, int] = field(default_factory=dict)
    #: Allele slots seen across the table, and how many came out named. The denominator is what makes
    #: the shortfall legible — "185 unmintable" says nothing without it.
    alleles: int = 0
    identified: int = 0

    @property
    def minted(self) -> int:
        return self.minted_stdlib + self.minted_normalized

    @property
    def complete(self) -> bool:
        """Whether every allele in the table now carries an id.

        The question a caller actually has, and the reason this pass reports more than counts: a VA is
        becoming the identity these tables are keyed on, and an identity scheme covering an unstated
        fraction of the table is not one anything can key on. `alleles == 0` (an empty table) is
        vacuously complete — there is no shortfall to report about nothing.
        """
        return self.identified >= self.alleles

    def coverage_warnings(self) -> list[str]:
        """The shortfall as text, one line plus one per reason — or nothing when coverage is complete.

        Returned rather than logged so the CLI, `enrich()` and a library caller all say the same thing.
        """
        if self.complete:
            return []
        share = f" ({self.identified / self.alleles:.0%})" if self.alleles else ""
        lines = [
            f"VRS allele identity covers {self.identified}/{self.alleles} allele(s){share} — "
            f"{self.alleles - self.identified} still carry no ga4gh:VA. id"
        ]
        lines.extend(
            f"  {count} allele(s): {reason}"
            for reason, count in sorted(
                self.unmintable_reasons.items(), key=lambda kv: (-kv[1], kv[0])
            )
        )
        return lines


@dataclass
class VrsMinter:
    """Mints allele ids: substitutions always, indels whenever the run is allowed to reach the network.

    Sequence access comes from a shared `SequenceProxy`, so a run that both mints indels and checks
    reference alleles builds one proxy and shares one read cache between them.
    """

    seqrepo_uri: str = DEFAULT_SEQREPO_URI
    offline: bool = False
    sequences: SequenceProxy | None = None

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
        chrom: str | None,
        start: int | None,
        ref: str | None,
        alt: str | None,
        *,
        build: str = "GRCh38",
    ) -> tuple[str | None, str | None]:
        """Return `(vrs_id, how)` where `how` is `"stdlib"`, `"normalized"`, or `None`.

        Reporting *how* rather than only *what* is deliberate: a normalized id depended on a live
        sequence service and a substitution's did not, and the compiler's verify pass — which can
        recompute one class and not the other — needs to be able to tell them apart.
        """
        if chrom is None or start is None or ref is None or not alt:
            return None, None
        if is_substitution(ref, alt):
            # `refget_accession` RAISES for a build with no table, deliberately — a caller asking for
            # GRCh37 must hear "not built", never get a GRCh38-flavoured id. So every call site has to
            # catch it, and this one did not: a single `genome_build: GRCh37` row in an otherwise fine
            # `resolution.csv` aborted the whole enrich run with an unhandled exception. The indel
            # branch below already caught it; the substitution branch is the cheap path that skipped
            # the guard. Same severity as any other unmintable row — no id, and the run carries on.
            try:
                return derive_vrs_allele_id(chrom, start, ref, alt, build=build), "stdlib"
            except UnsupportedBuildError:
                return None, None
        minted = self._mint_normalized(chrom, start, ref, alt, build)
        return minted, ("normalized" if minted is not None else None)

    def why_not(
        self,
        chrom: str | None,
        start: int | None,
        ref: str | None,
        alt: str | None,
        *,
        build: str = "GRCh38",
    ) -> str:
        """Why `mint` returned nothing for this allele — for grouping, not for a per-row line.

        Deliberately **not** shared with the compiler's `_recompute_vrs_id`, which answers a different
        question with different answers: an indel is permanently unrecomputable there (P2 keeps the
        reference sequence out of that tier) and merely *offline* here. Sharing the wording would make
        one of the two lie about what a re-run could fix, which is the whole point of reporting a
        reason at all.
        """
        if chrom is None or start is None:
            return "no coordinate to mint from (an unresolved row)"
        if not alt:
            return "no ALT recorded, and a VRS allele id names exactly one allele"
        try:
            accession = refget_accession(chrom, build)
        except UnsupportedBuildError as exc:
            return str(exc)
        if accession is None:
            return f"{chrom} is outside the primary assembly, so there is no refget accession for it"
        if is_substitution(ref, alt):
            return f"{chrom}:{start} is past the end of the contig"
        if self.offline or self._data_proxy() is None:
            return (
                "an indel/MNV, which must be justified against the reference sequence — re-run "
                "without --offline to mint it"
            )
        return "an indel/MNV whose normalization failed (see the warning logged for it)"

    def _mint_normalized(
        self, chrom: str, start: int, ref: str, alt: str, build: str
    ) -> str | None:
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


def _alt_list(alts: str | None) -> list[str | None]:
    """The ALTs of a row in authored order — the frame `vrs_id` is positionally aligned to.

    This function used to be `_single_alt`, returning `None` for a multi-allelic cell on the grounds
    that "a VA names exactly one allele, so a comma-joined cell has no single id — picking one would be
    a data error wearing an identifier". That argument is `derive_variant_key`'s and it is right *there*:
    `variant_key` is one column naming one thing, so a plural cell must fall through to the coordinate
    key. It is wrong here. `ResolutionRow.vrs_id` is a cross-reference the schema keeps **outside**
    `RESOLUTION_FACT_FIELDS`, nobody's identity rests on it, and nothing is being picked when every
    allele gets its own id. The enricher's own frequency pass already reasoned it out correctly —
    `frequencies._alleles_from_resolution` expands a multi-allelic cell into one entry per ALT — so the
    tier was giving two opposite answers about the same cell.

    An empty member is preserved as `None`, so a hand-written `A,,T` keeps its middle allele's position
    rather than silently becoming a 2-allele row.
    """
    if not alts:
        return []
    return [alt.strip() or None for alt in alts.split(",")]


def mint_resolution_rows(
    rows: list[ResolutionRow],
    *,
    minter: VrsMinter | None = None,
    offline: bool = False,
    source_ids: dict[str, str] | None = None,
) -> MintResult:
    """Stamp `vrs_id`/`vrs_spec` onto every mintable row, in place. Returns what it did.

    An **existing** `vrs_id` is never overwritten — the same "already there is authoritative" rule
    `enrich()` applies to the rest of the table, so a hand-corrected id survives a re-run.

    `source_ids` maps `variant_key` to an id a *source* reported (gnomAD serves one per variant). It is
    used only as a cross-check against what we minted, never as the value: trusting it would make our
    identity depend on which sources happened to answer, and the whole point of a content-addressed id
    is that it does not.

    The result also reports **coverage** — allele slots seen, how many are named, and what the rest are
    blocked on (`MintResult.coverage_warnings`). Callers are expected to surface a shortfall rather than
    only the success count: a VA is on its way to being the key these tables are joined on, and a pass
    that says "minted 237" while leaving 185 alleles anonymous has reported its own success and hidden
    the number that decides whether anything can key on the result.
    """
    minter = minter or VrsMinter(offline=offline)
    result = MintResult()
    for row in rows:
        alts = _alt_list(row.alts) or [None]
        result.alleles += len(alts)
        if row.vrs_id is not None:
            result.already_present += 1
            # Counted against coverage member by member: a pre-existing cell may itself carry holes,
            # and calling the row "already present" would report those as covered.
            for vrs_id in split_vrs_ids(row.vrs_id):
                if vrs_id is not None:
                    result.identified += 1
                else:
                    result.unmintable_reasons["already recorded with a hole, left as authored"] = (
                        result.unmintable_reasons.get(
                            "already recorded with a hole, left as authored", 0
                        )
                        + 1
                    )
        else:
            minted: list[str | None] = []
            for alt in alts:
                vrs_id, how = minter.mint(row.chrom, row.start, row.ref, alt, build=row.genome_build)
                minted.append(vrs_id)
                if vrs_id is None:
                    result.skipped_unmintable += 1
                    reason = minter.why_not(
                        row.chrom, row.start, row.ref, alt, build=row.genome_build
                    )
                    result.unmintable_reasons[reason] = result.unmintable_reasons.get(reason, 0) + 1
                    continue
                result.identified += 1
                if how == "stdlib":
                    result.minted_stdlib += 1
                else:
                    result.minted_normalized += 1
            # A row where only some alleles minted keeps the ones that did — the hole is what the
            # parallel-array shape is for. Refusing the whole row over the indel beside a substitution
            # would be the same abstention this function was just fixed for, one level down.
            row.vrs_id = join_vrs_ids(minted)
            if row.vrs_id is not None:
                row.vrs_spec = VRS_SPEC_VERSION
        reported = (source_ids or {}).get(row.variant_key)
        # A source serves one id per allele, so it is compared against the member for *its* allele,
        # never against the whole cell — on a multi-allelic row the joined value could not match any
        # single-allele id a source has, and the check would fire on every such row forever.
        if reported and row.vrs_id and reported not in split_vrs_ids(row.vrs_id):
            message = (
                f"{row.variant_key}: source reported vrs_id {reported} but we minted {row.vrs_id}"
            )
            logger.warning("%s — keeping the minted value", message)
            result.mismatches.append(message)
    return result

"""Pure, source-independent variant resolution from an injected `resolution.csv` (0.5).

The compiler's preferred resolution path. It consumes a table of already-resolved facts
(`just_dna_format.resolution.ResolutionRow`) keyed by the frozen `variant_key`, and reproduces the
DuckDB resolver's fill / expand / verify semantics **without any `duckdb` import, SQL, or Ensembl
convention**. All source knowledge (where facts come from) lives in the separate `just-dna-enricher`
tier; this module knows only "read the facts I was handed" — the strict inject-only end state
(CONSTITUTION Principle 2).

Digest parity with the DuckDB path is deliberate and load-bearing: given the same facts, this
produces byte-identical `weights.parquet` (hence `artifact.digest`) as `resolver.resolve_variants`.
The one place row order could drift — a one-to-many expansion — is pinned by sorting the expanded
rows on `(locus_index, chrom, start, ref)`, matching the resolver's `ORDER BY id, chrom, start, ref`.
"""

import logging
import re
from dataclasses import dataclass, field

from just_dna_format.alleles import (
    is_symbolic_allele,
    non_nucleotide_alleles,
    parsimony_reduce,
)
from just_dna_format.base import derive_variant_key
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import par_partner

logger = logging.getLogger(__name__)


@dataclass
class ResolutionOutcome:
    """What resolution produced, split by how badly each finding bites.

    Three channels rather than the usual two, because resolution has three distinct severities and
    collapsing any pair of them loses a real distinction:

    * `warnings` — reported in both modes, never fatal.
    * `strict_errors` — the **round-trip contract**: conditions under which `compile → reverse →
      compile` cannot reproduce the injected table, plus `ambiguous`, which is reproducible but rests
      on a guessed label. `best_effort` carries them; `strict`, whose contract is a reproducible
      artifact, refuses.
    * `errors` — fatal in **both** modes. Only `withdrawn` lands here: every other finding leaves the
      annotation intact, while a retracted variant may leave it describing nothing.
    """

    variants: list[VariantRow]
    warnings: list[str] = field(default_factory=list)
    strict_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def resolve_from_table(
    variants: list[VariantRow],
    resolution: dict[str, list[ResolutionRow]],
    genome_build: str = "GRCh38",
) -> ResolutionOutcome:
    """Fill/expand missing rsid or position from an injected resolution table (no network, no DuckDB).

    Mirrors `resolver.resolve_variants`:
      - **fill (1:1):** a `variant_key` with exactly one usable row fills the missing coord or rsid,
        keeping the frozen key.
      - **expand (1:N):** a `variant_key` (an rsid) with N usable rows expands to N coord-keyed rows,
        ordered by `(locus_index, chrom, start, ref)` so the parquet byte order matches the DuckDB
        path (digest parity). A locus whose alleles cannot host the authored genotype is **not**
        expanded onto — see `_hostable_loci`.
      - **verify:** a row carrying both an rsid and a coordinate is checked against the table; a
        disagreement warns in `best_effort` and refuses in `strict`.

    GRCh38-bound, like the DuckDB resolver (RM15): a non-GRCh38 module is skipped with a warning, and a
    resolution row whose `genome_build` differs from the module's is ignored.

    Returns a `ResolutionOutcome` — see its docstring for the three severity channels, and
    COMPILER.md § Resolution for the full matrix.
    """
    if genome_build != "GRCh38":
        msg = (
            f"Resolution-table fill skipped: compiler is GRCh38-bound, module genome_build is "
            f"{genome_build!r} — positions are not re-resolved cross-build (RM15)."
        )
        logger.warning(msg)
        return ResolutionOutcome(variants=variants, warnings=[msg])

    warnings: list[str] = []
    strict_errors: list[str] = []
    errors: list[str] = []
    patched: list[VariantRow] = []
    # Coordinate-authored rows the table knows no rsID for. Collected rather than reported per row:
    # `reference_examples/pathogenic_clinvar/` produced 26 of these, which buried the nine expansion
    # warnings and the duplicate-citation finding in the same run. It is also the *expected* state for a
    # coordinate-authored module — the row already has its identity, and an rsID is a convenience label
    # — so it earns one counted line, not a line each.
    no_rsid: list[str] = []
    for v in variants:
        rows = resolution.get(v.variant_key or "")
        loci = _usable_loci(rows, genome_build)

        if v.rsid is not None and v.chrom is None:
            # need position: fill from the table, or expand a one-to-many rsid
            if not loci:
                warnings.append(
                    f"{v.rsid}: not found in resolution table, position remains unset"
                )
                patched.append(v)
            elif len(loci) == 1:
                patched.append(v.model_copy(update=_coord_update(loci[0])))
            else:
                usable, rejected, undecided = _hostable_loci(loci, v.genotype)
                for locus in undecided:
                    # Kept, and said out loud. This tier cannot re-anchor an indel (that needs the
                    # reference sequence, which P2 keeps out of the compiler), so the row is carried and
                    # the reader is told the comparison did not reach a verdict — never that the locus is
                    # a different variant, which is what the old message asserted.
                    warnings.append(
                        f"{v.rsid}: whether {locus.chrom}:{locus.start} {locus.ref}>{locus.alts} can "
                        f"host the authored genotype {v.genotype} could not be decided here — the two "
                        f"spellings describe events of the same size but different content, which is "
                        f"either one indel re-anchored inside a repeat or two different variants, and "
                        f"telling those apart needs the reference sequence (run the enricher). The locus "
                        f"is kept."
                    )
                for locus in rejected:
                    # Dropping a locus makes the emitted table smaller than the injected one, so the
                    # round-trip cannot reproduce it — strict must refuse rather than silently prune.
                    caveat = spelling_caveat(locus.ref, locus.alts)
                    strict_errors.append(
                        f"{v.rsid}: locus {locus.chrom}:{locus.start} {locus.ref}>{locus.alts} "
                        f"cannot host the authored genotype {v.genotype}. Dropping it makes the "
                        f"compile non-reproducible from the injected table; fix the genotype or the "
                        f"table, or compile without strict.{caveat}"
                    )
                    warnings.append(
                        f"{v.rsid} maps to {locus.chrom}:{locus.start} {locus.ref}>{locus.alts}, "
                        f"which cannot host the authored genotype {v.genotype} — that locus is "
                        f"dropped from the expansion rather than emitted as a row asserting an "
                        f"allele it does not have.{caveat}"
                    )
                if not usable:
                    # Every candidate contradicts the genotype: the rsid and the genotype cannot both
                    # be right. Leave the row unresolved rather than pick one — `_cross_validate` and
                    # the strict gate then treat it as the unresolved variant it is.
                    warnings.append(
                        f"{v.rsid}: none of its {len(loci)} loci can host the authored genotype "
                        f"{v.genotype}; position remains unset"
                    )
                    patched.append(v)
                elif len(usable) == 1:
                    patched.append(v.model_copy(update=_coord_update(usable[0])))
                else:
                    warnings.append(_expansion_warning(v.rsid, usable, genome_build))
                    for locus in _sorted_loci(usable):
                        update = _coord_update(locus)
                        # `build=` is redundant *today* — the function returns early for any other
                        # build 70 lines up — and is passed anyway: correct-by-construction beats
                        # correct-by-a-distant-guard, and every instance of this bug so far was a
                        # guard that existed somewhere else.
                        update["variant_key"] = derive_variant_key(
                            None, locus.chrom, locus.start, locus.ref, locus.alts,
                            build=genome_build,
                        )
                        patched.append(v.model_copy(update=update))

        elif v.rsid is None and v.chrom is not None:
            # need rsid: fill from the single usable row (keeps the frozen coord key). `alts` is
            # filled too when the author left it out — the table knows the allele and the row would
            # otherwise reach the artifact without it, so reverse could not re-emit the resolved fact
            # and `resolution_signature` moved across the round-trip.
            row = next((lo for lo in loci if lo.rsid is not None), None)
            update: dict[str, object] = {}
            if row is not None:
                update["rsid"] = row.rsid
            if v.alts is None:
                supplier = row or next((lo for lo in loci if lo.alts), None)
                if supplier is not None and supplier.alts:
                    update["alts"] = supplier.alts
            if update:
                patched.append(v.model_copy(update=update))
            else:
                # Name the *place*, not the key. `variant_key` for a resolved substitution is a
                # `ga4gh:VA.…` allele id, so the old message read "Position
                # ga4gh:VA.aseiElOGc6FKVcLTpib-L1y4s1dwiYE2" — calling a content-addressed identity a
                # position, and giving the author nothing to look up. The row holds the coordinate.
                no_rsid.append(_locus_label(v))
                patched.append(v)

        else:
            # both authored (verify) or nothing to do
            if v.rsid is not None and v.chrom is not None and loci:
                _verify(v, loci, warnings, strict_errors)
            patched.append(v)

    if no_rsid:
        warnings.append(
            f"{len(no_rsid)} coordinate-authored row(s) have no rsid in the resolution table, so they "
            f"stay coordinate-keyed: {_examples(no_rsid)}. Not an error — a coordinate is a complete "
            f"identity and an rsID is a label on top of it; re-run the enricher if you want the labels "
            f"back-filled."
        )

    for variant in patched:
        for locus in resolution.get(variant.variant_key or "", []):
            if locus.rsid_status == "withdrawn":
                # The one resolution finding that is fatal in BOTH modes. A merged or absent rsID
                # leaves the annotation intact — the module is dated, or the label is unserved. A
                # *withdrawn* one is dbSNP repudiating the variant, so the annotation may be describing
                # something that does not exist; carrying it under `best_effort` would be publishing a
                # claim its own source has retracted. Never produced by the automated check (a
                # retraction is indistinguishable from a never-assigned id through the live API), so
                # this fires only where a curator recorded it deliberately.
                errors.append(
                    f"{variant.variant_key}: dbSNP has WITHDRAWN {locus.rsid} — the variant itself was "
                    f"retracted, so the annotation resting on it may be describing nothing. Remove the "
                    f"row or re-key it onto a coordinate; this refuses in best_effort too, unlike a "
                    f"merged or absent rsid."
                )
                break
            if locus.status == "ambiguous":
                strict_errors.append(
                    f"{variant.variant_key}: the resolution table marks this rsid ambiguous"
                    + (f" (candidates: {locus.rsid_alternates})" if locus.rsid_alternates else "")
                    + ". The label is a deterministic pick among equals, not a fact; an "
                    "all-or-nothing artifact should not rest on it. Resolve it by hand in "
                    "resolution.csv, or compile without strict."
                )
                warnings.append(
                    f"{variant.variant_key}: rsid resolved as AMBIGUOUS"
                    + (f" among {locus.rsid_alternates}" if locus.rsid_alternates else "")
                    + " — the deterministic pick is carried, and it is a pick, not a finding."
                )
                break

    return ResolutionOutcome(
        variants=patched, warnings=warnings, strict_errors=strict_errors, errors=errors
    )


def _locus_label(v: VariantRow) -> str:
    """`chrom:start ref>alts` for a message about a place, falling back to the key if it has none.

    Deliberately not `variant_key`: since 0.5 that is a `ga4gh:VA.…` digest for a resolved
    substitution, which names the variant precisely and tells a human nothing they can find in their
    own CSV.
    """
    if v.chrom is None or v.start is None:
        return str(v.variant_key)
    alleles = f" {v.ref}>{v.alts}" if v.ref and v.alts else f" {v.ref}" if v.ref else ""
    return f"{v.chrom}:{v.start}{alleles}"


def _examples(labels: list[str], limit: int = 3) -> str:
    """The first few labels, with a count of the rest — so one line stays one line."""
    shown = ", ".join(labels[:limit])
    return shown if len(labels) <= limit else f"{shown} … and {len(labels) - limit} more"


def _usable_loci(
    rows: list[ResolutionRow] | None, genome_build: str
) -> list[ResolutionRow]:
    """Rows that are for this build and record an actual locus (not a `not_found` sentinel)."""
    if not rows:
        return []
    return [
        r
        for r in rows
        if r.genome_build == genome_build and r.status != "not_found" and r.chrom is not None
    ]


def _coord_update(row: ResolutionRow) -> dict[str, object]:
    """The coordinate fields a fill copies onto a VariantRow (matches the DuckDB path's locus dict)."""
    return {"chrom": row.chrom, "start": row.start, "ref": row.ref, "alts": row.alts}


_GENOTYPE_SEP = re.compile(r"[/|]")


def hosting_verdict(genotype: str, ref: str | None, alts: str | None) -> bool | None:
    """Can a locus spelling `{ref} ∪ alts` host `genotype`? **Three-valued** (RM31).

    `True` it can, `False` it positively cannot, `None` this tier cannot tell — the house algebra, and
    the third value is the whole point: an indel has several valid spellings, so a string comparison
    reporting "does not fit" was asserting a verdict it had not reached.

    The ladder, in order, and the order is load-bearing:

    1. **No `ref`/`alts` recorded → `True`.** Nothing is known about the locus's alleles and rejecting
       for lack of evidence is worse than accepting. Unchanged.
    2. **The raw strings match → `True`.** Checked *before* any normalization so this function can only
       ever gain acceptances: whatever passed before still passes, byte for byte, which is what keeps the
       expansion (and every module's digest) stable except where a genuine reconciliation happens.
    3. **Either side names a symbolic allele → `None`.** A `<DEL:1500>` has no sequence, so it has no
       flank for `parsimony_reduce` and nothing to compare character by character — and a symbolic
       allele exists *because* the exact sequence is not known, so even two stated lengths that differ
       are summary information rather than grounds for a contradiction. Undecided, never "no match"
       (RM5). Below the raw comparison, so `<DEL:1500>` against a locus spelling `<DEL:1500>` still
       matches exactly.
    4. **The reduced allele sets match → `True`.** `alleles.parsimony_reduce` strips the flank each
       collection shares, leaving the event; ClinVar's `C/CAG` and Ensembl's `AGAG>AG` both reduce to
       `{'', 'AG'}`, the SHOX 2 bp deletion that used to resolve to `not_found`.
    5. **The locus is a substitution or MNV → `False`.** No flank, so no spelling freedom: an `A/G`
       genotype at a `C>T` locus is a real contradiction, and must stay one (a strand flip is exactly
       what that check catches).
    6. **The genotype names fewer than two distinct alleles → `None`.** A homozygous `C/C` carries no
       frame — one string has nothing to be relative to — so against an indel locus there is genuinely
       nothing to compare. Reported as undecided, never as a contradiction.
    7. **An event length the locus does not offer → `False`.** The confident negative:
       left-alignment moves an indel, it never changes how many bases the event adds or removes, so a
       1 bp insertion cannot be a 2 bp deletion however it is spelled.
    8. **Otherwise → `None`.** Same lengths, different content: one variant rotated inside a repeat, or
       two different variants, and only the reference sequence can say which. The enricher can settle
       it (seqrepo); the compiler holds no reference by charter (P2), so it withholds.

    Public because **both** resolvers must agree on it: this module's injected-table path and the
    deprecated DuckDB path in `just-dna-enricher`. Digest parity between the two is a documented
    guarantee, so a filter applied on one side only would silently break it.
    """
    if not ref or not alts:
        return True
    locus = {ref.strip().upper()} | {a.strip().upper() for a in alts.split(",") if a.strip()}
    called = {a.upper() for a in _GENOTYPE_SEP.split(genotype) if a}
    if called <= locus:
        return True

    # RM5. A symbolic allele names a variant whose sequence is deliberately unspelled, so from here on
    # every step is a comparison of *characters* and there are none to compare: `parsimony_reduce`
    # would treat `<DEL:1500>` as a nine-character sequence, `_indel_shaped` would read its bracket
    # count as an event length, and step 7 would then return a confident `False` on arithmetic over a
    # token. Undecided is the honest answer, and it only ever *adds* acceptances (`genotype_fits`
    # keeps an undecided locus), so no expansion and no digest moves for a module spelling in bases.
    if any(is_symbolic_allele(a) for a in locus | called):
        return None

    called_events = parsimony_reduce(called)
    locus_events = parsimony_reduce(locus)
    if len(called_events) > 1 and called_events <= locus_events:
        return True
    if not _indel_shaped(locus_events):
        return False
    if len(called) < 2:
        return None
    if not _indel_shaped(called_events):
        return False
    lengths = {len(event) for event in locus_events}
    if any(len(event) not in lengths for event in called_events - locus_events):
        return False
    return None


def _indel_shaped(events: frozenset[str]) -> bool:
    """Whether a reduced allele set describes an indel — i.e. its members differ in length.

    A substitution or MNV reduces to same-length members, and same-length members cannot be re-anchored:
    there is no shared flank to move. That is what separates "this is a different variant" from "this
    might be the same variant spelled differently", and it is why a strand-flipped SNV genotype stays a
    hard contradiction rather than becoming undecidable.
    """
    return len({len(event) for event in events}) > 1


def genotype_fits(genotype: str, ref: str | None, alts: str | None) -> bool:
    """Whether a locus can host `genotype`, collapsing "cannot tell" into "keep it".

    The boolean face of `hosting_verdict`, kept because both resolvers and three call sites read it, and
    because the collapse it performs is the module's existing doctrine: **only a positive contradiction
    rejects.** An undecidable spelling is therefore kept, exactly as a locus with no recorded alleles is.
    A caller that needs to *report* the difference asks `hosting_verdict` instead.
    """
    return hosting_verdict(genotype, ref, alts) is not False


def _hostable_loci(
    loci: list[ResolutionRow], genotype: str
) -> tuple[list[ResolutionRow], list[ResolutionRow], list[ResolutionRow]]:
    """Split candidate loci into those that can host `genotype`, those that cannot, and the undecidable.

    A one-to-many rsid carries **one** authored genotype onto **N** loci, and those loci need not be
    interchangeable: dbSNP tags several records at one position with a single rsid — in
    `reference_examples/pathogenic_clinvar/`, `rs281864532` is `G>GT`, `GT>G` *and* `GTT>G` — and a
    genotype written for one of them can name an allele another does not have. Emitting every locus
    produced rows asserting an allele that is not there, and reverse then wrote those fabrications out as
    authored data.

    Three channels, because `hosting_verdict` has three answers. A locus with no `ref`/`alts` recorded
    and one whose spelling cannot be reconciled without the reference are both **kept** — the doctrine is
    that only a positive contradiction rejects — but the undecided ones are returned separately so the
    caller can say which it is. Silently keeping them under the same label as a clean match is how the
    original message came to assert "a different variant sharing the rsID" about a SHOX deletion that was
    simply spelled two ways.
    """
    usable: list[ResolutionRow] = []
    rejected: list[ResolutionRow] = []
    undecided: list[ResolutionRow] = []
    for locus in loci:
        verdict = hosting_verdict(genotype, locus.ref, locus.alts)
        if verdict is False:
            rejected.append(locus)
            continue
        usable.append(locus)
        if verdict is None:
            undecided.append(locus)
    return usable, rejected, undecided


def _par_pairs(loci: list[ResolutionRow], genome_build: str) -> list[tuple[str, str]]:
    """Which of these loci are the same pseudoautosomal place spelled on the other contig.

    Returns `[(x_spelling, y_spelling)]` as `chrom:start` labels, in the loci's own order. Empty when
    the expansion is a genuine multi-locus one — paralogs, patch scaffolds — which is what the
    expansion was built for and what the generic message is right about.
    """
    places = {
        (lo.chrom, lo.start, lo.ref or "", lo.alts or ""): lo
        for lo in loci
        if lo.chrom is not None and lo.start is not None
    }
    pairs: list[tuple[str, str]] = []
    for lo in loci:
        if lo.chrom != "X" or lo.start is None:
            continue
        partner = par_partner(lo.chrom, lo.start, build=genome_build)
        if partner is not None and (partner[0], partner[1], lo.ref or "", lo.alts or "") in places:
            pairs.append((f"{lo.chrom}:{lo.start}", f"{partner[0]}:{partner[1]}"))
    return pairs


def _expansion_warning(rsid: str, usable: list[ResolutionRow], genome_build: str) -> str:
    """Describe a one-to-many expansion — and say which KIND of many it is.

    A paralogous rsID and a pseudoautosomal one produce the same row count for opposite reasons: the
    first is several distinct places, the second is **one place spelled on two contigs**. Reporting both
    with "a consumer can count them" told a SHOX author to count ten findings as twenty. The compiler
    can tell them apart offline — `chrom`, `start` and the PAR intervals are all it needs — so it says
    which.

    The compiler only *describes* this; it never drops the locus. Which loci reach the table is the
    enricher's decision (`enrich.select_par_representative`, which keeps the X spelling by default),
    because that choice has to be recorded in injected data to survive
    `compile → reverse → compile` — a compiler-side prune would fail Principle 7.
    """
    pairs = _par_pairs(usable, genome_build)
    if len(pairs) * 2 == len(usable):
        spellings = "; ".join(f"{x} and {y}" for x, y in pairs)
        return (
            f"{rsid} is pseudoautosomal: it maps to {len(usable)} loci ({spellings}) that are "
            f"{len(pairs)} place(s), because PAR1/PAR2 are shared between X and Y. Expanded to "
            f"{len(usable)} rows, so count distinct findings by rsid rather than by row — and note "
            f"that a standard GRCh38 analysis set hard-masks the Y PAR, so the Y row matches nothing "
            f"there. Re-run the enricher without --keep-par-twin to record the X spelling alone."
        )
    return (
        f"{rsid} maps to {len(usable)} loci in the resolution table; expanded to "
        f"{len(usable)} rows (one per locus, each keyed by its coordinate — a consumer "
        f"can count them)."
    )


def spelling_caveat(ref: str | None, alts: str | None) -> str:
    """The clause to append when a "cannot host" verdict is really about allele *spelling*.

    Empty for a locus spelled in nucleotides, which is nearly all of them, so a caller can append it
    unconditionally.

    `hosting_verdict` reaches `False` for a substitution locus by set difference, and it is right to: a
    substitution has no shared flank, so no spelling freedom, so `A/G` at a `C>T` locus is a real
    contradiction and must stay one — that is what makes the strand-flip check sharp. But it reaches the
    same `False` when the locus is spelled `T>Y`, and there the mismatch is between the *cell* and the
    nucleotide alphabet, not between the genotype and the variant. Reporting the generic message there
    sends the author to re-examine a genotype that was correct all along.

    Three reasons, kept apart, because what the author does next differs: an ambiguity code is an
    uncertainty that can never be expanded into definite alleles (expanding `N` to `A,C,G,T` asserts four
    alleles nobody stated), a well-formed symbolic allele is *held* by the grammar since RM5 and so is
    never a spelling defect at all, and everything else non-nucleotide is a grammar gap. None is
    repaired here — this tier reports.
    """
    offenders = non_nucleotide_alleles(ref, alts)
    if not offenders:
        return ""
    return (
        " Read that as a spelling problem rather than a variant one: the locus records "
        + _spelling_clauses(offenders)
        + "."
    )


def _spelling_clauses(offenders: dict[str, str]) -> str:
    """One clause per reason present, each carrying **its own** consequence.

    Shared with `compiler._spelling_because` in spirit and deliberately not in code: the two sit in
    different call sites of the same finding and read differently around it. What must not diverge is
    the *classification*, and that is `alleles.non_nucleotide_reason`, imported by both.
    """
    ambiguity = sorted(a for a, reason in offenders.items() if reason == "ambiguity")
    symbolic = sorted(a for a, reason in offenders.items() if reason == "symbolic")
    notation = sorted(a for a, reason in offenders.items() if reason == "notation")
    parts: list[str] = []
    if ambiguity:
        parts.append(
            f"{', '.join(repr(a) for a in ambiguity)} is an IUPAC ambiguity code rather than a "
            f"definite nucleotide (`Y` is C-or-T) — an uncertainty, so it is never expanded into the "
            f"alleles it could stand for and can match no genotype"
        )
    if symbolic:
        parts.append(
            f"{', '.join(repr(a) for a in symbolic)} is a symbolic/structural allele, which the "
            f"grammar holds (RM5) — it names a variant whose sequence is deliberately unspelled, so "
            f"comparing it against a spelled allele is undecided rather than a mismatch"
        )
    if notation:
        parts.append(
            f"{', '.join(repr(a) for a in notation)} is neither a nucleotide string nor a symbolic "
            f"allele the format holds (a repeat notation like `AAAGGGGCG(2)`, a deletion spelling "
            f"like `DELTCT`, or a typo) — a grammar gap rather than a genotype error"
        )
    return "; and ".join(parts)


def _sorted_loci(loci: list[ResolutionRow]) -> list[ResolutionRow]:
    """Deterministic expansion order, matching the resolver's `ORDER BY id, chrom, start, ref`."""
    return sorted(
        loci, key=lambda r: (r.locus_index, r.chrom or "", r.start or 0, r.ref or "")
    )


def _verify(
    v: VariantRow, loci: list[ResolutionRow], warnings: list[str], strict_errors: list[str]
) -> None:
    """Report when an authored rsid↔coordinate pair disagrees with the table.

    Warning in `best_effort`, refusal in `strict`. The authored value wins either way — the row keeps
    what its author wrote — which is precisely why the round-trip cannot reproduce the injected table:
    the artifact carries the authored coordinate and the table's is lost. Contradiction is therefore an
    instability, not merely a difference of opinion.
    """
    coordkey = derive_variant_key(None, v.chrom, v.start, v.ref)
    keys = {
        derive_variant_key(None, lo.chrom, lo.start, lo.ref) for lo in loci
    }
    if keys and coordkey not in keys:
        message = (
            f"{v.rsid} authored at {coordkey}, but the resolution table maps it to "
            f"{sorted(keys)} (reference disagreement)."
        )
        warnings.append(message)
        strict_errors.append(
            message + " The authored value is kept, so the table's position does not survive a "
            "reverse — the compile is not reproducible from it. Fix one of the two, or compile "
            "without strict."
        )

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
from dataclasses import dataclass, field

from just_dna_format.alleles import (
    is_symbolic_allele,
    is_unobservable_allele,
    non_nucleotide_alleles,
    parsimony_reduce,
    split_genotype,
)
from just_dna_format.base import derive_variant_key
from just_dna_format.findings import CodedWarning
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

    `expanded_keys` / `expanded_rows` are the one-to-many expansion's two counts, carried out for
    `manifest.compilation` (S33). Two numbers rather than one, and never a ratio, for RM44's reason:
    one authored key can expand to any number of rows, and a consumer told only "3 rows are expansion
    members" cannot tell three keys of one locus each from one key of three. Rows are counted in the
    artifact's own unit — a `weights.parquet` row — so the number is checkable against the file.

    They are `None` on the non-GRCh38 early return and nowhere else: that path resolves nothing, so
    `0` would say "looked, found no expansion" of a module nothing looked at. Same tri-state as every
    other unknown here — withhold rather than negate.
    """

    variants: list[VariantRow]
    warnings: list[str] = field(default_factory=list)
    strict_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    expanded_keys: int | None = None
    expanded_rows: int | None = None


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
        return ResolutionOutcome(
            variants=variants,
            warnings=[CodedWarning("resolution_skipped_cross_build", msg)],
        )

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
    # rsID → the usable loci found for each authored row carrying it, one entry per authored row. So
    # `len(entry)` is how many rows the author wrote at that key and `sum(map(len, entry))` is how
    # many artifact rows they became. Collected rather than reported in place — see the expansion
    # branch below.
    expansions: dict[str, list[list[ResolutionRow]]] = {}
    for v in variants:
        rows = resolution.get(v.variant_key or "")
        loci = _usable_loci(rows, genome_build)

        if v.rsid is not None and v.chrom is None:
            # need position: fill from the table, or expand a one-to-many rsid
            if not loci:
                warnings.append(CodedWarning(
                    "rsid_unresolved",
                    f"{v.rsid}: not found in resolution table, position remains unset",
                ))
                patched.append(v)
            elif len(loci) == 1:
                patched.append(v.model_copy(update=_coord_update(loci[0])))
            else:
                usable, rejected, undecided = _hostable_loci(loci, v.genotype)
                for locus in undecided:
                    # Kept, and said out loud. This tier cannot re-anchor an indel (that needs the
                    # reference sequence, which P2 keeps out of the compiler), so the row is carried and
                    # the reader is told the comparison did not reach a verdict — never that the locus is
                    # a different variant, which is what the old message asserted. `undecided_reason`
                    # supplies *which* of the four ways it withheld, rather than naming one of them for
                    # all four.
                    warnings.append(CodedWarning(
                        "locus_hosting_undecidable",
                        f"{v.rsid}: whether {locus.chrom}:{locus.start} {locus.ref}>{locus.alts} can "
                        f"host the authored genotype {v.genotype} could not be decided here — "
                        f"{undecided_reason(v.genotype, locus.ref, locus.alts)}. The locus is kept.",
                    ))
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
                    warnings.append(CodedWarning(
                        "locus_cannot_host_genotype",
                        f"{v.rsid} maps to {locus.chrom}:{locus.start} {locus.ref}>{locus.alts}, "
                        f"which cannot host the authored genotype {v.genotype} — that locus is "
                        f"dropped from the expansion rather than emitted as a row asserting an "
                        f"allele it does not have.{caveat}",
                    ))
                if not usable:
                    # Every candidate contradicts the genotype: the rsid and the genotype cannot both
                    # be right. Leave the row unresolved rather than pick one — `_cross_validate` and
                    # the strict gate then treat it as the unresolved variant it is.
                    warnings.append(CodedWarning(
                        "rsid_no_hosting_locus",
                        f"{v.rsid}: none of its {len(loci)} loci can host the authored genotype "
                        f"{v.genotype}; position remains unset",
                    ))
                    patched.append(v)
                elif len(usable) == 1:
                    patched.append(v.model_copy(update=_coord_update(usable[0])))
                else:
                    # Accumulated per rsID, reported once after the loop. Emitting here put the same
                    # sentence in `manifest.compilation.warnings` once per *authored row* — a site with
                    # two authored genotypes published it twice — and each copy said "expanded to 2
                    # rows" while the artifact gained four. Same rule as the counted line below: a
                    # message that embeds a count is owed the whole denominator, and the whole
                    # denominator is not known until every authored row at this key has been judged
                    # (which loci are usable depends on the genotype, so two rows at one key can
                    # legitimately expand onto different loci).
                    expansions.setdefault(v.rsid, []).append(usable)
                    for index, locus in enumerate(_sorted_loci(usable)):
                        update = _coord_update(locus)
                        # `build=` is redundant *today* — the function returns early for any other
                        # build 70 lines up — and is passed anyway: correct-by-construction beats
                        # correct-by-a-distant-guard, and every instance of this bug so far was a
                        # guard that existed somewhere else.
                        update["variant_key"] = derive_variant_key(
                            None, locus.chrom, locus.start, locus.ref, locus.alts,
                            build=genome_build,
                        )
                        # The expansion marker (RM87). This is the only site that knows a row is a
                        # member of anything — after here it is an ordinary well-formed row with a
                        # real coordinate, and nothing on it said so. Both numbers were already in
                        # scope: the ordinal is the `enumerate`, the total is `len(usable)`.
                        #
                        # The ordinal counts within `usable`, i.e. after `_hostable_loci` dropped any
                        # locus that positively contradicts the genotype — not within the injected
                        # table's own `locus_index`, which `_sorted_loci` only *orders* by. The two
                        # coincide under `strict`, where a dropped locus is a refusal, and that is
                        # also exactly what `reverse_module` recomputes by encounter order, so the
                        # round trip is a fixed point either way.
                        update["locus_index"] = index
                        update["locus_count"] = len(usable)
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
        warnings.append(CodedWarning(
            "rsid_without_resolution_label",
            f"{len(no_rsid)} coordinate-authored row(s) have no rsid in the resolution table, so they "
            f"stay coordinate-keyed: {_examples(no_rsid)}. Not an error — a coordinate is a complete "
            f"identity and an rsID is a label on top of it; re-run the enricher if you want the labels "
            f"back-filled.",
        ))

    expanded_rows = 0
    for rsid, per_row in expansions.items():
        expanded_rows += sum(len(u) for u in per_row)
        warnings.append(
            CodedWarning("rsid_expanded_to_multiple_loci", _expansion_warning(rsid, per_row, genome_build))
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
                warnings.append(CodedWarning(
                    "rsid_ambiguous",
                    f"{variant.variant_key}: rsid resolved as AMBIGUOUS"
                    + (f" among {locus.rsid_alternates}" if locus.rsid_alternates else "")
                    + " — the deterministic pick is carried, and it is a pick, not a finding.",
                ))
                break

    return ResolutionOutcome(
        variants=patched, warnings=warnings, strict_errors=strict_errors, errors=errors,
        expanded_keys=len(expansions), expanded_rows=expanded_rows,
    )


@dataclass
class PositionalFill:
    """What the positional fill did, per table. Counts, never a line per row.

    `unplaced_ambiguous` and `unplaced_absent` are separated for the reason every tri-state in this
    codebase is: "the table names this key at several loci and the compiler will not pick one" and
    "nothing has resolved this key" are different situations with different next moves, and one
    number reporting both says neither.
    """

    filled: int = 0
    unplaced_ambiguous: int = 0
    unplaced_absent: int = 0
    contradicted: list[str] = field(default_factory=list)


def resolve_positional_rows(
    rows: list[object],
    resolution: dict[str, list[ResolutionRow]],
    genome_build: str = "GRCh38",
) -> PositionalFill:
    """Fill the resolved coordinate into one 0.4-family positional table, **in place** (RM43).

    `pharm_variants.csv`, `haplotypes.csv` and `heteroplasmy.csv` may identify a row by rsID alone —
    their own models say so — and until 0.6 the compiler resolved `variants.csv` and materialized
    every other table verbatim. A consumer matching a patient VCF by position therefore matched
    nothing, silently, as an empty result rather than an error: the coordinates existed in the
    `resolution.csv` sitting beside the spec and reached the artifact by no path at all.

    Four rules, and the last two are what keep this from being the naive repair the roadmap rejected:

    * **Fill only what the author left empty.** A cell the author wrote is never overwritten; that is
      `enrich`'s inject-only doctrine (report, never repair) and it is also what makes the fill
      idempotent.
    * **Fill from exactly one locus, or from none.** One usable locus fills. Several are filtered by
      `hosting_verdict` against whatever allele the row states — a `genotype` on a pharm row, the
      defining `allele` on a haplotype junction, and nothing at all on a heteroplasmy band, which is a
      measurement over a locus rather than a claim about a genotype. If that leaves one, it fills;
      otherwise the row stays unplaced and is counted. There is deliberately **no expansion**: a
      one-to-many rsID expands `variants.csv` into N coord-keyed rows, and doing the same here would
      multiply a pharm annotation's `(variant_key, drug, genotype, …)` key across loci the author
      never named.
    * **A row whose own coordinate contradicts the table is left alone.** `haplotypes.csv` drafted
      from CPIC carries a `start` with no `chrom`, so the fill has to complete a half-coordinate — and
      completing it from a locus whose `start` disagrees would build a coordinate no source ever
      stated. Reported, never repaired, and never fatal: the same shape as `resolve_from_table`'s
      `_verify`, minus the strict escalation, because the row is left exactly as authored.
    * **The row is mutated, not copied, and its identity is frozen.** `variant_key`/`authored_ident`
      are stamped at load from the authored subset, so filling cannot re-key the row and
      `reverse_module` re-emits the shape the author wrote (`_write_table_csv`).

    GRCh38-bound for the same reason `resolve_from_table` is (RM15): the caller skips a non-GRCh38
    module rather than joining rows this tier cannot re-derive an identity for.
    """
    report = PositionalFill()
    for row in rows:
        loci = _usable_loci(resolution.get(getattr(row, "variant_key", None) or ""), genome_build)
        fillable = [
            name
            for name in ("rsid", "chrom", "start", "ref", "alts")
            if name in type(row).model_fields and getattr(row, name) is None
        ]
        # Deliberately **not** short-circuited on `not fillable`. A fully-populated row has nothing to
        # fill and can still contradict the table it is keyed into — reachable on `heteroplasmy.csv`,
        # the one positional model whose whole identity set is authorable — and the promise this
        # function makes is that such a disagreement is *reported*, never repaired. Skipping the
        # lookup there would have let a mistyped `start` sit beside a disagreeing `resolution.csv` row
        # in silence, which is the shape `resolve_from_table._verify` exists to catch on the SNP core.
        if not loci:
            if row.chrom is None or row.start is None:
                report.unplaced_absent += 1
            continue
        statement = _stated_allele(row)
        candidates = (
            loci if len(loci) == 1 or statement is None else _hostable_loci(loci, statement)[0]
        )
        if len(candidates) != 1:
            if row.chrom is None or row.start is None:
                report.unplaced_ambiguous += 1
            continue
        locus = candidates[0]
        conflict = _authored_conflict(row, locus)
        if conflict is not None:
            report.contradicted.append(conflict)
            continue
        if not fillable:
            continue
        for name in fillable:
            value = getattr(locus, name, None)
            if value is not None:
                setattr(row, name, value)
        report.filled += 1
    return report


def _stated_allele(row: object) -> str | None:
    """The allele statement a positional row makes, for the hosting filter — or `None` if it makes none.

    A `PharmVariantRow` states a `genotype` (optional, so it really can be absent), a `HaplotypeRow`
    states its defining `allele`, and a `HeteroplasmyRow` states neither. Reading the two field names
    rather than branching on the model keeps this agreeing with `enrich._collect_subjects`, which
    feeds the identical pair into the identical predicate.
    """
    return getattr(row, "genotype", None) or getattr(row, "allele", None)


def _authored_conflict(row: object, locus: ResolutionRow) -> str | None:
    """A sentence naming the authored identity cell the locus disagrees with, or `None`.

    Only cells the author actually wrote are compared — a filled cell is by construction the locus's
    own value. A half-coordinate (`start` with no `chrom`, the shape CPIC drafting produces) is the
    case this exists for: completing it from a locus that puts the variant somewhere else would
    fabricate a coordinate.

    **`alts` is left out of the comparison on purpose.** A locus legitimately lists every ALT recorded
    there while a row names the one it is about — `A,G` against `G` is agreement, not contradiction —
    so string equality would manufacture a finding about correct data. Whether the row's allele can
    sit at the locus is a different question with its own three-valued predicate, and
    `_hostable_loci`/`hosting_verdict` has already asked it by the time this runs.
    """
    for name in ("rsid", "chrom", "start", "ref"):
        authored = getattr(row, name, None)
        against = getattr(locus, name, None)
        if authored is not None and against is not None and str(authored) != str(against):
            return (
                f"{getattr(row, 'variant_key', None)}: authored {name}={authored!r} contradicts the "
                f"resolution table's {name}={against!r}, so the rest of that row's coordinate is left "
                f"unfilled rather than completed from a locus the row disagrees with"
            )
    return None


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


def hosting_verdict(genotype: str, ref: str | None, alts: str | None) -> bool | None:
    """Can a locus spelling `{ref} ∪ alts` host `genotype`? **Three-valued** (RM31).

    `True` it can, `False` it positively cannot, `None` this tier cannot tell — the house algebra, and
    the third value is the whole point: an indel has several valid spellings, so a string comparison
    reporting "does not fit" was asserting a verdict it had not reached.

    The ladder, in order, and the order is load-bearing:

    1. **No `ref`/`alts` recorded → `True`.** Nothing is known about the locus's alleles and rejecting
       for lack of evidence is worse than accepting. Unchanged.
    2. **`*` abstains — on both sides — and the rest is still judged (RM59).** `*` says *this sample's
       allele could not be observed here*; it names no allele, so a locus cannot fail to offer it and
       cannot contradict it, and it belongs in the allele algebra on neither side. Without this the
       widening that made `*/G` authorable would be self-defeating: no source spells `*` in an ALT list,
       so an rsid-authored `*/G` resolved against a `G>A` locus fell through to step 6 and came back a
       confident **`False`** — the locus dropped from the expansion, the row unresolved, and `strict`
       refusing over a finding no authored edit could clear. Dropping the member rather than the whole
       verdict is what keeps the *observable* half sharp: `*/T` at a `G>A` locus is still `False`,
       because the `T` really is a contradiction. Nothing observable on either side is `None`.

       **The locus side is not optional, and the first cut got this wrong** on the reasoning that a `*`
       in `ref`/`alts` is reachable today, so excluding it might move an existing verdict. It does move
       existing verdicts, and it is still right: `parsimony_reduce` cannot strip a shared flank past a
       member that has none, so a `*` left in the locus stops the set reducing and collapses RM31 —
       `hosting_verdict('C/CAG', 'AGAG', 'AG')` is `True` while `…('C/CAG', 'AGAG', 'AG,*')` was
       `False`, refusing a correctly transcribed indel under `--strict` and telling the author to
       "replace it with the alleles the locus actually has". `ALT=AG,*` is ordinary joint-caller output.

       **What that costs is measured, and it is not only acceptances.** Swept over every star-free
       genotype — i.e. everything authorable before RM59 — against loci with and without a `*`: for a
       locus spelled in nucleotides **nothing changes at all**, and for a locus spelling `*` verdicts
       move in *both* directions, `None → False` among them. Those are corrections. `*` was doing two
       things to the arithmetic at once, blocking the flank strip and lending its own single character
       to `_indel_shaped`'s length set, so `ref=AGAG alts=AG,*` stayed unreduced, read as indel-shaped,
       and withheld on calls that were decidable all along — a genotype naming an allele the locus does
       not have escaped the finding. Same bug class as the RM5 guard's stated reason: characters counted
       out of a token that spells no sequence. No reference example carries a `*`, so the corpus could
       not have shown any of this.
    3. **The raw strings match → `True`.** Checked *before* any normalization, so *this step* can only
       ever gain acceptances: whatever passed the raw comparison before still passes it, byte for byte.
       Step 2 sits above it and costs it nothing, *provably* rather than nearly — the called side is
       stripped first, so `*` is never on the left of the subset test, and dropping it from the right
       therefore cannot change the answer. **The guarantee stops here**: steps 5–8 are arithmetic over
       the *reduced* sets, and stripping the locus does change those, in both directions (see step 2).
    4. **Either side names a symbolic allele → `None`.** A `<DEL:1500>` has no sequence, so it has no
       flank for `parsimony_reduce` and nothing to compare character by character — and a symbolic
       allele exists *because* the exact sequence is not known, so even two stated lengths that differ
       are summary information rather than grounds for a contradiction. Undecided, never "no match"
       (RM5). Below the raw comparison, so `<DEL:1500>` against a locus spelling `<DEL:1500>` still
       matches exactly.
    5. **The reduced allele sets match → `True`.** `alleles.parsimony_reduce` strips the flank each
       collection shares, leaving the event; ClinVar's `C/CAG` and Ensembl's `AGAG>AG` both reduce to
       `{'', 'AG'}`, the SHOX 2 bp deletion that used to resolve to `not_found`.
    6. **The locus is a substitution or MNV → `False`.** No flank, so no spelling freedom: an `A/G`
       genotype at a `C>T` locus is a real contradiction, and must stay one (a strand flip is exactly
       what that check catches).
    7. **The genotype names fewer than two distinct alleles → `None`.** A homozygous `C/C` carries no
       frame — one string has nothing to be relative to — so against an indel locus there is genuinely
       nothing to compare. Reported as undecided, never as a contradiction. A `*/C` reaches this too
       once the `*` has abstained, and for the same reason: one string has nothing to be relative to.
    8. **An event length the locus does not offer → `False`.** The confident negative:
       left-alignment moves an indel, it never changes how many bases the event adds or removes, so a
       1 bp insertion cannot be a 2 bp deletion however it is spelled.
    9. **Otherwise → `None`.** Same lengths, different content: one variant rotated inside a repeat, or
       two different variants, and only the reference sequence can say which. The enricher can settle
       it (seqrepo); the compiler holds no reference by charter (P2), so it withholds.

    Public because **both** resolvers must agree on it: this module's injected-table path and the
    deprecated DuckDB path in `just-dna-enricher`. Digest parity between the two is a documented
    guarantee, so a filter applied on one side only would silently break it.
    """
    if not ref or not alts:
        return True
    locus = {ref.strip().upper()} | {a.strip().upper() for a in alts.split(",") if a.strip()}
    called = {a.upper() for a in split_genotype(genotype)}

    # RM59, and kept visibly separate from the RM5 guard below it because they are separate axes: this
    # one drops a *member* that makes no claim, that one withholds the whole *verdict* because a claim
    # cannot be compared. `*` is not an allele — it reports that the sample's allele could not be
    # observed here — so it is neither offered by a locus nor contradicted by one, and every step from
    # here on is a comparison of characters it has none of. Removing it leaves the observable half to be
    # judged normally; removing it and finding nothing left means nothing was seen at all.
    #
    # **Both sides, and the locus side is not optional.** A `*` in `alts` is what a joint-called VCF
    # writes, and left in the locus set it silently defeats `parsimony_reduce`: the shared flank cannot
    # be stripped past a member that has none, so `parsimony_reduce({'AGAG','AG','*'})` returns the set
    # unreduced and RM31's reconciliation collapses — `hosting_verdict('C/CAG', 'AGAG', 'AG')` is `True`
    # while `hosting_verdict('C/CAG', 'AGAG', 'AG,*')` was a confident `False`, refusing a correctly
    # transcribed indel under `--strict` and advising the author to "replace it with the alleles the
    # locus actually has". One rule on both sides is also the only consistent reading: an allele the
    # algebra must ignore cannot be one the algebra ignores in one direction.
    #
    # **Above the raw comparison, not below it**, which is the opposite of where the RM5 guard sits and
    # is forced rather than chosen: the whole point is that the *rest* of the call must still be matched
    # against the locus, and `*/G` at a `G>A` locus is exactly the case — `{'*','G'}` is not a subset,
    # so below the comparison it fell through to the substitution arm and came back a confident `False`.
    # It costs the raw comparison nothing, and provably rather than nearly: `called` is stripped first,
    # so `*` is not on the left of the subset test, and dropping it from the right therefore cannot
    # change the answer. Nothing reachable before RM59 could put one in a genotype at all.
    called = {a for a in called if not is_unobservable_allele(a)}
    locus = {a for a in locus if not is_unobservable_allele(a)}
    if not called or not locus:
        return None

    if called <= locus:
        return True

    # RM5. A symbolic allele names a variant whose sequence is deliberately unspelled, so from here on
    # every step is a comparison of *characters* and there are none to compare: `parsimony_reduce`
    # would treat `<DEL:1500>` as a nine-character sequence, `_indel_shaped` would read its bracket
    # count as an event length, and step 8 would then return a confident `False` on arithmetic over a
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


def undecided_reason(genotype: str, ref: str | None, alts: str | None) -> str:
    """Why `hosting_verdict` withheld — the clause a caller appends when the answer was `None`.

    **`None` has five causes and the message asserted one of them.** Both reporting sites — this
    module's expansion warning and the enricher's twin — said *"the two spellings describe events of
    the same size but different content, either one indel re-anchored inside a repeat or two different
    variants"*, which is step 9's cause and false for the other four: a symbolic allele was never
    compared at all (RM5), an all-`*` call observed nothing and an all-`*` locus offers nothing (RM59),
    and a homozygous call carries no frame. Stating a cause the tier did not establish is the same
    defect as the `([], None)` collapse S20 was filed for — two ways of returning nothing rendered as
    one sentence — and here it sends the reader to check a reference sequence for a row where no
    reference could help.

    Mirrors `hosting_verdict`'s withholding branches **in its order**, so the two answer the same
    question the same way; a test walks every `None`-producing shape and asserts the pairing, which is
    what keeps a sixth branch from quietly inheriting a fifth's explanation.

    The sets are built exactly as the predicate builds them — including dropping an empty `ref` rather
    than folding `""` in, which would put a member in `locus` that is neither observable nor an allele
    and quietly defeat the branch below it. Keeping the two constructions identical is the entire point
    of the pair.
    """
    locus = {a.strip().upper() for a in (ref or "", *(alts or "").split(",")) if a.strip()}
    called = {a.upper() for a in split_genotype(genotype)}
    observable_called = {a for a in called if not is_unobservable_allele(a)}
    observable_locus = {a for a in locus if not is_unobservable_allele(a)}

    if not observable_called:
        return (
            "the call observed no allele at this position at all — every member is VCF's `*`, so "
            "there is nothing to match against the locus and nothing a reference could settle"
        )
    if not observable_locus:
        return "the locus records no allele that is not VCF's `*`, so it offers nothing to match"
    if any(is_symbolic_allele(a) for a in observable_locus | observable_called):
        return (
            "a symbolic/structural allele names a variant whose sequence is deliberately unspelled, "
            "so the two were never compared character by character — undecided, not a mismatch"
        )
    if len(observable_called) < 2:
        return (
            "the genotype names one distinct allele, so it carries no flank to be relative to and "
            "the spelling cannot be reconciled against an indel locus"
        )
    return (
        "the two spellings describe events of the same size but different content, which is either "
        "one indel re-anchored inside a repeat or two different variants, and telling those apart "
        "needs the reference sequence (run the enricher)"
    )


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


def _expansion_warning(
    rsid: str, per_row: list[list[ResolutionRow]], genome_build: str
) -> str:
    """Describe a one-to-many expansion — and say which KIND of many it is.

    A paralogous rsID and a pseudoautosomal one produce the same row count for opposite reasons: the
    first is several distinct places, the second is **one place spelled on two contigs**. Reporting both
    with "a consumer can count them" told a SHOX author to count ten findings as twenty. The compiler
    can tell them apart offline — `chrom`, `start` and the PAR intervals are all it needs — so it says
    which.

    **One sentence per rsID, over every authored row at it** (S33). `per_row` carries the usable loci
    judged for each authored row separately, because `_hostable_loci` asks the question per genotype
    and two rows at one key can legitimately reach different loci. The union is what "maps to N loci"
    means; the sum is what "expanded to M rows" means, and the two come apart exactly when the author
    wrote more than one genotype — the shape that made the old per-row copy say "2 rows" of an
    artifact that gained four.

    **And it says what those rows are, because that is the half a reader gets wrong.** Only one member
    of an expansion can match a given genotype; the rest are well-formed rows asserting the authored
    conclusion beside a locus that cannot carry it. A reader doing anything but a position join —
    counting rows, classifying them, asking what the module says about a reference-homozygous subject
    — reads those as claims the module never made.

    The compiler only *describes* this; it never drops the locus. Which loci reach the table is the
    enricher's decision (`enrich.select_par_representative`, which keeps the X spelling by default),
    because that choice has to be recorded in injected data to survive
    `compile → reverse → compile` — a compiler-side prune would fail Principle 7.
    """
    seen: dict[tuple, ResolutionRow] = {}
    for usable in per_row:
        for lo in usable:
            seen.setdefault((lo.locus_index, lo.chrom, lo.start, lo.ref, lo.alts), lo)
    loci = _sorted_loci(list(seen.values()))
    rows = sum(len(u) for u in per_row)
    authored = len(per_row)
    # "N rows from M authored genotype(s)" only earns its place when M > 1; on the ordinary
    # single-genotype expansion the two numbers are the same and the clause is noise.
    from_clause = f" from {authored} authored genotype(s)" if authored > 1 else ""
    pairs = _par_pairs(loci, genome_build)
    if len(pairs) * 2 == len(loci):
        spellings = "; ".join(f"{x} and {y}" for x, y in pairs)
        return (
            f"{rsid} is pseudoautosomal: it maps to {len(loci)} loci ({spellings}) that are "
            f"{len(pairs)} place(s), because PAR1/PAR2 are shared between X and Y. Expanded to "
            f"{rows} rows{from_clause}, so count distinct findings by rsid rather than by row — and "
            f"note that a standard GRCh38 analysis set hard-masks the Y PAR, so the Y row matches "
            f"nothing there. Re-run the enricher without --keep-par-twin to record the X spelling "
            f"alone."
        )
    return (
        f"{rsid} maps to {len(loci)} loci in the resolution table; expanded to {rows} rows"
        f"{from_clause}, one per (authored genotype, locus) pair and each keyed by its coordinate. "
        f"Only the locus whose alleles can carry a given genotype can match it, so the rest are "
        f"well-formed rows that assert nothing about a subject — count findings by rsid, and do not "
        f"read a row as a standalone claim about its locus."
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

    Three reasons reach this caveat, kept apart because what the author does next differs: an ambiguity
    code is an uncertainty that can never be expanded into definite alleles (expanding `N` to `A,C,G,T`
    asserts four alleles nobody stated), a well-formed symbolic allele is *held* by the grammar since
    RM5 and so is never a spelling defect at all, and everything else non-nucleotide is a grammar gap.
    None is repaired here — this tier reports.

    **`*` is the fourth classification and is excluded here (RM59)**, because `hosting_verdict` strips
    it from both sides before comparing, so it can no longer contribute to the `False` this sentence
    explains. Left in, it inverted the caveat's whole point: `genotype=C/G` at `ref=A alts="T,*"` is a
    real genotype error, and the author was told to read it as a spelling problem instead.
    """
    offenders = {
        allele: reason
        for allele, reason in non_nucleotide_alleles(ref, alts).items()
        if not is_unobservable_allele(allele)
    }
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

    **Every reason the classifier can return needs an arm here, and the failure is silent.** The
    offenders are already non-empty when the caller builds its sentence, so a reason with no clause
    does not raise — it drops the allele from the explanation, and a locus whose *only* odd allele is
    unclassified yields "the locus records ." with nothing between. RM59 added the fourth reason and
    this is the second of the two builders; the first was updated in the same change, and the reason
    the pair is not one function is style at the call site, never the classification.
    """
    ambiguity = sorted(a for a, reason in offenders.items() if reason == "ambiguity")
    symbolic = sorted(a for a, reason in offenders.items() if reason == "symbolic")
    unobservable = sorted(a for a, reason in offenders.items() if reason == "unobservable")
    notation = sorted(a for a, reason in offenders.items() if reason == "notation")
    missing = sorted(a for a, reason in offenders.items() if reason == "missing")
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
    if unobservable:
        parts.append(
            f"{', '.join(repr(a) for a in unobservable)} is VCF's allele-missing-due-to-overlapping-"
            f"deletion marker (RM59) — it records what a call could not observe, so it names no allele "
            f"for a genotype to match, and it is a fact about a sample rather than a grammar gap a "
            f"release could close"
        )
    if notation:
        parts.append(
            f"{', '.join(repr(a) for a in notation)} is neither a nucleotide string nor a symbolic "
            f"allele the format holds (a repeat notation like `AAAGGGGCG(2)`, a deletion spelling "
            f"like `DELTCT`, or a typo) — a grammar gap rather than a genotype error"
        )
    if missing:
        # Third reason, third consequence (RM58). Unlike the other two this one is not a limit of the
        # schema at all: `.` is VCF's MISSING marker, so the cell asserts that the record has no
        # alternate allele. Nothing can be widened to hold it and nothing can match it.
        parts.append(
            f"{', '.join(repr(a) for a in missing)} is VCF's MISSING marker rather than an allele — it "
            f"states that the record has no alternate allele, so no genotype can name it; leave the "
            f"cell empty instead"
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
        warnings.append(CodedWarning("rsid_coordinate_disagrees", message))
        strict_errors.append(
            message + " The authored value is kept, so the table's position does not survive a "
            "reverse — the compile is not reproducible from it. Fix one of the two, or compile "
            "without strict."
        )

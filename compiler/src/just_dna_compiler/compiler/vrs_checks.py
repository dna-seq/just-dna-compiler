"""VRS identifiers: verifying the recorded `vrs_id`s, their coverage, and the reason a row carries none."""

from just_dna_format.alleles import is_symbolic_allele, is_unobservable_allele
from just_dna_format.findings import CodedWarning
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import UnsupportedBuildError, derive_vrs_allele_id, is_substitution, split_vrs_ids


def _verify_vrs_ids(resolution_rows: list[ResolutionRow]) -> tuple[list[str], list[str]]:
    """Recompute every stored `vrs_id` and report disagreements. Returns (errors, warnings).

    Takes no `mode`: every outcome below is the same in `best_effort` and `strict`, which is the point
    of the split. It was a mode ladder until the severity was rethought — see the *unverifiable* bullet.

    The integrity check the whole minting story earns: a `ga4gh:VA.…` is *content-addressed*, so it is
    the one column in the whole artifact that can be checked against itself with no reference, no
    network, and no dependency — `derive_vrs_allele_id` is stdlib, so the compiler tier gains nothing
    to run this (Goal 2). A mismatch means the row was tampered with, or the producer and this
    implementation disagree — either way the id is not usable as an identity.

    Every row lands in exactly one of **three** outcomes, and the distinction between the last two is
    the one that matters:

    - **verified** — recomputed and equal. Silent.
    - **mismatch** — recomputed and *different*. Always an **error**, in both modes: this computation
      is fully deterministic here, so a disagreement can only mean the stored id is corrupt.
    - **unverifiable** — could not be recomputed at all (see `_recompute_vrs_id` for the five reasons).
      Severity follows **whose limit it is**, not the mode alone: `_BLAME_ROW` is an **error** in both
      modes, `_BLAME_TIER` is a **warning** in both.

    The third case is emphatically *not* "an indel mismatch". This tier cannot recompute an indel's id,
    so it can never detect that one disagrees — it can only report that it did not check. Calling that
    a mismatch would claim a verdict that was never reached.

    **Why the tier's own limits do not escalate under `strict`, though they used to.** `strict` means
    *reproducible artifact*, and an enricher-minted indel VA is perfectly reproducible: the bytes are
    injected, the compile is deterministic, and recompiling yields the same digest. What is impossible
    here is the *verification*, not the reproduction — and escalating on that conflates "I could not
    check this" with "this cannot be rebuilt". The cost was not hypothetical: minting indel ids online
    is exactly what `just-dna-enricher` is for, so every ClinVar-derived module acquired ids that
    `compile --strict` then refused, and the two remedies the message offered were *lower your
    guarantee* or *delete a correct identity* — the second being the same abstention the per-ALT fix had
    just finished removing one file away. Two reference examples (`pathogenic_clinvar`, `shox_par1`)
    stopped compiling in the mode their own README documents. The rule this now follows is the one
    `_vrs_coverage_warnings` and `frequencies`' `not_covered` already followed: **a finding no authored
    edit could clear is not a `strict` matter.**

    `_BLAME_ROW` keeps the error, in *both* modes rather than only `strict`. A row asserting a `vrs_id`
    while carrying no coordinate or no ALT is not a limit of this tier — it is a table contradicting
    itself, catchable offline, and it is the same class as the "inconsistent reference allele" error.

    A row with no `vrs_id` is skipped entirely — there is nothing to check, which is not the same as
    something that could not be checked. The same goes for a **hole** in a multi-allelic cell: `vrs_id`
    is positionally aligned with `alts`, so each allele is verified on its own and an empty member is
    the same non-event as an empty cell. That alignment is the second thing this pass now guards —
    `ResolutionRow` refuses a pair of the wrong *length*, and recomputing member by member catches a
    pair of the right length in the wrong *order*, which is the failure mode a parallel array has and a
    scalar column does not.
    """
    errors: list[str] = []
    # `_BLAME_TIER` findings are collected and grouped at the end rather than appended as they are
    # found (S67). Which path an allele takes is decided by whether the enricher happened to mint an
    # id for it — `_vrs_coverage` aggregates the ones with **no** id, this pass reported one line per
    # id **present** — so noise ran inversely to how well-resolved a module was: a 101-row module with
    # every id minted produced 80 of its 85 warnings here, while a 57,595-row module with none minted
    # produced one aggregated line. The three findings its author could act on were items 83, 84 and
    # 85. Grouping by reason is what `_vrs_coverage_warnings` already does one function away, on the
    # argument its own docstring makes.
    carried: dict[str, list[str]] = {}
    for row in resolution_rows:
        if row.vrs_id is None:
            continue
        stored = split_vrs_ids(row.vrs_id)
        alts = [alt.strip() for alt in row.alts.split(",")] if row.alts else []
        for index, vrs_id in enumerate(stored):
            if vrs_id is None:
                # A hole: this allele has no id to check. Same non-event as a row with no `vrs_id`.
                continue
            alt = alts[index] if index < len(alts) else None
            where = f"{row.variant_key} allele {alt}" if len(stored) > 1 else str(row.variant_key)
            recomputed, reason, blame = _recompute_vrs_id(row, alt)
            if recomputed is None:
                message = f"{where}: vrs_id {vrs_id} could not be verified — {reason}"
                if blame == _BLAME_ROW:
                    errors.append(
                        f"{message}. An id recorded against nothing to check it with is a "
                        f"contradiction in the table, not a limit of this tier: resolve the row, or "
                        f"drop the vrs_id."
                    )
                else:
                    carried.setdefault(reason, []).append(where)
                continue
            if recomputed != vrs_id:
                errors.append(
                    f"{where}: stored vrs_id {vrs_id} does not match the id recomputed "
                    f"from {row.chrom}:{row.start} {row.ref}>{alt} ({recomputed}) — a substitution's "
                    f"id is deterministic here, so this is corruption, not a difference of opinion."
                )
    return errors, _carried_vrs_warnings(carried)


#: How many `variant_key`s a grouped finding names before it says "and N more". Three, matching
#: `sequences.summarize_ref_mismatches`, which is the shape this was asked for in: enough to go and
#: look at one, few enough that the line stays a line.
_VRS_CARRIED_EXAMPLES = 3


def _carried_vrs_warnings(carried: dict[str, list[str]]) -> list[str]:
    """One line per *reason* for the ids this tier cannot recompute, with a count and named examples.

    Not a cap and not suppression: the count stays truthful and every reason still appears, which is
    what the reporter asked for and what the coverage half already does. What goes away is the one
    line per allele, which carried no information the reason and the count do not — every allele in a
    group failed for the identical cause, and none of them is fixable by an authored edit at all.

    Sorted by descending count then by reason, the same order `_vrs_coverage_warnings` emits its
    groups in, so the two halves of the VRS story read the same way round. Deterministic because
    warning text is an API and a set-ordered one would differ between runs.
    """
    lines: list[str] = []
    for reason, wheres in sorted(carried.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        named = ", ".join(wheres[:_VRS_CARRIED_EXAMPLES])
        more = (
            f", and {len(wheres) - _VRS_CARRIED_EXAMPLES} more" if len(wheres) > _VRS_CARRIED_EXAMPLES else ""
        )
        lines.append(
            CodedWarning(
                "vrs_id_unverifiable",
                f"{len(wheres)} allele(s): vrs_id could not be verified — {reason}; carried unverified "
                f"({named}{more}).",
            )
        )
    return lines


def _vrs_coverage(resolution_rows: list[ResolutionRow]) -> tuple[int, int, dict[str, int]]:
    """`(alleles, identified, gaps_by_reason)` — how much of the table a VA actually names.

    The counterpart to `_verify_vrs_ids`, and the thing that pass structurally cannot see: it verifies
    ids that are *there*, and an absent id is "nothing to check". That was the right severity while a
    VA was a decorative cross-reference. It is the wrong one now that `variant_key` derives from a VA
    for a resolved substitution and the id is headed for primary-key status — an identity scheme
    covering an unstated fraction of the table is not one anything can key on, and *unstated* is the
    defect. So absence is counted and reported; a consumer can then decide.

    The denominator is **alleles, not rows** — one multi-allelic site is several identities — and a row
    with no ALT at all counts as one unnamed slot rather than vanishing from the ratio.

    Gaps are grouped by *why*, because the reasons have completely different remedies and a bare
    "N missing" hides which one you have. The sharpest is the first: an allele this tier could mint
    **right now, offline**, which means nothing minted it, not that anything is hard.
    """
    alleles = identified = 0
    gaps: dict[str, int] = {}
    for row in resolution_rows:
        stored = split_vrs_ids(row.vrs_id)
        alts = [alt.strip() for alt in row.alts.split(",")] if row.alts else [None]
        for index, alt in enumerate(alts):
            alleles += 1
            if index < len(stored) and stored[index] is not None:
                identified += 1
                continue
            reason = _vrs_gap_reason(row, alt)
            gaps[reason] = gaps.get(reason, 0) + 1
    return alleles, identified, gaps


#: The symbolic-allele gap class (RM5, 0.6), as ONE constant string — `_vrs_coverage` groups on it, so
#: interpolating the token would rebuild the per-row wall this bucketing exists to prevent, and a
#: structural module carries several spellings at once (`<DEL:4977>`, `<DUP:16000>`, `<CNV:TR:30>`).
#: It names no remedy, because there is none: this is not the indel class one enricher run away from an
#: id, it is an allele nothing anywhere can mint one for.
_SYMBOLIC_GAP_REASON: str = (
    "a symbolic allele (<DEL:…>, <CNV:TR:…>): it names a structural event rather than a sequence, so "
    "there is nothing for a content-addressed id to be a digest of — no tier can mint one, offline or "
    "online, and no authored edit clears it"
)


#: The unobservable-allele gap class (RM59, 0.6) — a *third* bucket, not a spelling of the one above
#: and emphatically not the indel one (R2-6).
#:
#: 0.6 gave the symbolic class its own permanent reason here and guarded `*` and `.` on the *enricher*
#: side, and these two compiler functions were never told: neither tested `is_unobservable_allele`, so
#: a `*` in `resolution.csv`'s `alts` would have been reported as *"an indel or MNV … re-run it
#: online"* — the same false class D1-2 had just fixed for symbolic alleles, one axis over, with a
#: remedy that could never work.
#:
#: **Filed as having no instantiation, and upgraded when it turned out to have one.** The reasoning
#: was that nothing writes a `*` into that column today; the unit fixing D1-1 then probed
#: `LiteralSequenceExpression`'s pattern — `^[A-Z*\\-]*$` — and found `*` **passes** it, so before the
#: enricher guard an unobservable allele reaching the minter would have been normalized and handed a
#: content-addressed id for a state that is not a sequence. *"Nothing produces it today"* is a fact
#: about the current wiring, never about the function: the same lesson RM38 and
#: `VALID_RSID_STATUS.withdrawn` already carry.
#:
#: Separate from the symbolic bucket because the two answer different questions and P5 keeps them
#: apart everywhere else: `parse_symbolic_allele` asks *which variant is this, unspelled*, while
#: `is_unobservable_allele` asks *whether this sample's call could see the allele at all* — the
#: callability axis. One is a variant with no sequence written down; the other is not a variant.
_UNOBSERVABLE_GAP_REASON: str = (
    "the unobservable-allele marker '*': it records that an overlapping deletion left this position "
    "uncallable in the sample, so it names no allele and there is nothing to digest — no tier mints "
    "one, and this is the callability axis rather than a gap in the identity scheme"
)


def _vrs_gap_reason(row: ResolutionRow, alt: str | None) -> str:
    """Which *class* of gap this is — a bucket, deliberately not `_recompute_vrs_id`'s prose.

    That function names the alleles (`AG>A is not a single-base substitution…`) because it is
    diagnosing one row, and it is right to. Grouping on it produced 40-odd lines that all said the same
    thing about a different indel — a per-row wall wearing an aggregate's clothes. One reason per arm,
    and a reader needs all of them — **not a number here** (RM218): this said "six" while the function
    had eight arms, because RM5's symbolic class and RM59's unobservable class were each added without
    moving it. `test_source_counted_prose.py` asserts the arms stay pairwise distinct instead, which is
    the property `@answered-is-not-absent` actually asks for.
    """
    if row.chrom is None or row.start is None:
        return "no coordinate to mint from (an unresolved row)"
    if not alt:
        return "no ALT recorded, and a VRS allele id names exactly one allele"
    # Ahead of both the mint attempt and the `is_substitution` fall-through, in this function and in
    # `_recompute_vrs_id` — the two order their other branches differently, and this one branch must be
    # in the same place in both. A symbolic allele is *also* not a substitution and *also* has no
    # accession on a non-GRCh38 build, and both of those reasons are answerable by someone: the indel
    # class by an online enricher run, the build class by RM15. This one never is, so it is the reason
    # to print. Lenient predicate on purpose (`is_symbolic_allele`, not `parse_symbolic_allele`): a
    # malformed `<FOO>` or an unterminated `<DEL` names no sequence either, so filing it under "indel"
    # would be the same false claim about a different mistake.
    if is_symbolic_allele(alt):
        return _SYMBOLIC_GAP_REASON
    # Beside it, and above the substitution fall-through for the identical reason (R2-6): `*` is also
    # not a substitution, and filing it under the indel class would print a remedy — re-run online —
    # that can never work. The two are disjoint predicates (`*` is one character, a symbolic token is
    # bracketed), so their order relative to each other decides nothing.
    if is_unobservable_allele(alt):
        return _UNOBSERVABLE_GAP_REASON
    try:
        recomputed = derive_vrs_allele_id(row.chrom, row.start, row.ref, alt, build=row.genome_build)
    except UnsupportedBuildError as exc:
        return str(exc)
    if recomputed is not None:
        # The sharp one: nothing was blocking this. Either the mint pass never ran, or it ran before
        # multi-allelic cells were minted per ALT.
        return "no id recorded, though one is computable offline — run `just-dna-enricher vrs mint`"
    if not is_substitution(row.ref, alt):
        return (
            "an indel or MNV: justification needs the reference sequence, so only the enricher can "
            "mint it (re-run it online)"
        )
    return "outside the primary assembly, or past the end of the contig — no refget accession"


def _vrs_coverage_warnings(resolution_rows: list[ResolutionRow]) -> list[str]:
    """One line for the shortfall, one per reason — never one per row.

    A **warning in both modes**, deliberately, and for the same reason `not_covered` sits outside the
    strict gate: the commonest gaps (an indel with no sequence proxy, a build with no refget table)
    are fixable by no authored edit, so refusing would make such a module uncompilable rather than
    telling its author anything. `strict` means "reproducible artifact", which an incomplete identity
    scheme still is. What strict *does* refuse is a stored id it cannot confirm — a claim, not an
    absence.
    """
    if not resolution_rows:
        return []
    alleles, identified, gaps = _vrs_coverage(resolution_rows)
    if not alleles or identified == alleles:
        return []
    findings = [
        CodedWarning(
            "vrs_coverage_incomplete",
            f"VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv "
            f"({identified / alleles:.0%}) — {alleles - identified} carry no ga4gh:VA. id. Anything "
            f"keying on the VA sees only the covered fraction.",
        )
    ]
    findings.extend(
        # The per-reason breakdown is the same finding continued, so it takes the same code: a
        # summary counting the headline and its own detail under two keys would double-count one
        # coverage gap.
        CodedWarning("vrs_coverage_incomplete", f"  {count} allele(s): {reason}")
        for reason, count in sorted(gaps.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    return findings


#: Whose limit made an allele unverifiable — the classification `_verify_vrs_ids` takes its severity
#: from. `TIER` is *this compiler cannot do it, and no edit to the module would change that*; `ROW` is
#: *the row does not carry what a check needs*, which a producer can fix. See `_recompute_vrs_id`.
#: Two values, not three: a symbolic allele is beyond *every* tier rather than this one, and that is a
#: sharper statement than `TIER` makes — but blame decides severity and nothing else, and a third
#: member mapping to the same severity would be a fourth outcome in all but name. It is said in the
#: reason instead, which is what a reader actually sees.
_BLAME_TIER = "tier"


_BLAME_ROW = "row"


def _recompute_vrs_id(row: ResolutionRow, alt: str | None) -> tuple[str | None, str | None, str | None]:
    """`(recomputed_id, reason, blame)` for ONE allele — either the id is set, or the other two are.

    The five reasons an allele is unverifiable here, split by **whose limit each one is**, because that
    is what decides severity upstream (`_BLAME_TIER` / `_BLAME_ROW`):

    1. **no coordinate** — nothing to recompute from (an unresolved rsid row carrying an external id).
       `_BLAME_ROW`: the row asserts an identity while withholding the coordinate that identity is a
       digest of, so nothing can ever check it — an internal contradiction, catchable offline;
    2. **no ALT** — a position-only row, so there is no allele to name. `_BLAME_ROW`, same shape: a VA
       names exactly one allele and the row names none. This used to also cover *multi-allelic*, on the
       reasoning that "picking one from a comma-joined cell would be inventing data". Nothing is picked
       now: `vrs_id` is positionally aligned with `alts`, so the caller walks the pair and asks about
       allele *i* — and a multi-allelic site of substitutions verifies as completely as a bi-allelic one;
    3. **a symbolic allele** (`<DEL:4977>`, `<CNV:TR:30>` — RM5, 0.6) — it names a structural *event*
       and no sequence, so nothing is being digested and no id exists to recompute. `_BLAME_TIER` by
       severity and by the only thing blame decides, though it understates the case: this is not a
       limit of *this* tier but of every tier, since the enricher cannot mint one either. Checked
       **before** reason 4, which it would otherwise fall into: both statements are true of the row,
       and the one to print is the one no release can answer. **Whether a *stored* id on such a row
       should instead be `_BLAME_ROW` is a real open question, deliberately not answered here.** The
       case for it: nothing mints a VA for a symbolic allele, so a present one names some other,
       sequence-spelled allele, and unlike an indel — which the enricher legitimately mints online —
       deleting the cell clears the finding, which is exactly what takes it out of the P5 class where
       no authored edit helps. The case against acting on that in this pass: it would refuse, in both
       modes, a module that compiles today, and the same judgement has to be made on the minting side
       first (whether the enricher may ever write a non-VA identity into that column). Surfaced, not
       half-mended;
    4. **not a single-base substitution** — an indel or MNV must be justified against the reference
       sequence, which this tier has no access to and will never fetch (Principle 2). `_BLAME_TIER`;
    5. **outside the primary assembly, or a build with no refget table** — no accession to address the
       sequence by. `_BLAME_TIER` for both. The build case is *raised* by `refget_accession` rather than
       returned, deliberately (a caller asking for GRCh37 should hear "not built" rather than get a
       GRCh38-flavoured answer), so it is caught here and turned into a reason. Letting it propagate
       would abort the whole compile over one unverifiable row, which is the wrong severity for
       `best_effort`.
    """
    if row.chrom is None or row.start is None:
        return None, "the row carries no coordinate to recompute from", _BLAME_ROW
    if not alt:
        return (
            None,
            "the row records an id against no ALT (a position-only row), and a VRS allele id "
            "names exactly one allele",
            _BLAME_ROW,
        )
    if is_symbolic_allele(alt):
        # Named per row here (unlike `_vrs_gap_reason`'s constant) for the same reason the indel branch
        # below names its alleles: this diagnoses one row, and the caller has already located it.
        #
        # **`_BLAME_ROW`, and it was `_BLAME_TIER` until R2-5 was settled.** Tier-blame is for a
        # finding **no authored edit could clear** (P5 — the rule that also keeps `not_covered` and the
        # coverage warnings out of the `strict` gate), and this one is cleared by deleting the cell. It
        # belongs with *inconsistent reference allele* and *an id recorded against no ALT*: the row
        # asserts a content-addressed identity for an allele that has no content to address, so the id
        # necessarily names some **other** allele. That is a false claim, catchable offline, and an
        # error in both modes.
        #
        # It was left at tier-blame when first found because escalating needed the minting side
        # answered first — *may a non-VA identity ever be written here?* — and that is now settled in
        # the grammar: `validate_vrs_allele_id` refuses anything but `ga4gh:VA.`, on a probe of 844 ids
        # across the corpus that found no other type. With the column VA-only, a present id on a
        # symbolic row can only be a VA minted for a different allele, and there is nothing left to be
        # unsure about. Note the asymmetry that stays: the *coverage* side (`_vrs_gap_reason`) still
        # reports the same allele as a permanent gap and warns, because an **absent** id there is
        # honest and no edit improves it. Absence is a limit; a claim is a claim.
        return (
            None,
            f"{alt} is a symbolic allele: it names a structural event rather than a sequence, so there "
            f"is nothing for a content-addressed id to be a digest of and no tier mints one — a "
            f"recorded id here names some other allele. Delete the vrs_id cell; the allele keeps its "
            f"identity through variant_key",
            _BLAME_ROW,
        )
    if is_unobservable_allele(alt):
        # The same branch `_vrs_gap_reason` gained in R2-6, in the same place: above the substitution
        # fall-through, because `*` is not one either and the indel message's remedy — re-run the
        # enricher online — is unreachable for a marker that names no allele. `_BLAME_TIER` matches
        # the symbolic branch above, and a *stored* id here raises the identical open question that
        # branch records: nothing mints one, so a present id names something else.
        return (
            None,
            f"{alt} is the unobservable-allele marker, not an allele: it records that an overlapping "
            f"deletion left this position uncallable in the sample, so there is no sequence for a "
            f"content-addressed id to name",
            _BLAME_TIER,
        )
    if not is_substitution(row.ref, alt):
        return (
            None,
            f"{row.ref}>{alt} is not a single-base substitution, so justifying it needs the reference "
            f"sequence — minted upstream by the enricher, not recomputable here",
            _BLAME_TIER,
        )
    try:
        recomputed = derive_vrs_allele_id(row.chrom, row.start, row.ref, alt, build=row.genome_build)
    except UnsupportedBuildError as exc:
        return None, str(exc), _BLAME_TIER
    if recomputed is None:
        return (
            None,
            f"{row.chrom}:{row.start} is outside the primary assembly (no refget accession for the "
            f"contig, or the position is past its end)",
            _BLAME_TIER,
        )
    return recomputed, None, None

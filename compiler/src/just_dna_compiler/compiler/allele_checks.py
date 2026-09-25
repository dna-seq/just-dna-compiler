"""Allele checks: membership against the resolved locus, study effect alleles, genotype coverage,
symbolic alleles and their drops, and `p_value_num`.
"""

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from just_dna_format.alleles import (
    RECOMMENDED_SYMBOLIC_SUBTYPES,
    SYMBOLIC_ALLELE_TYPES,
    is_symbolic_allele,
    is_unobservable_allele,
    non_nucleotide_reason,
    symbolic_allele_defect,
)
from just_dna_format.base import derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.normalize import parse_p_value
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import ALLELE_PATTERN

from just_dna_compiler.compiler.table_checks import _examples
from just_dna_compiler.compiler.tables import _split_genotype
from just_dna_compiler.ladder import LadderFinding, route
from just_dna_compiler.resolution import hosting_verdict


def _allowed_alleles(
    variant: VariantRow, resolution_table: dict[str, list[ResolutionRow]]
) -> tuple[set[str] | None, str]:
    """`(allele set, provenance)` for one variant — `(None, "unknown")` when nothing is comparable.

    The provenance shapes the diagnosis — it says where to go and look — but deliberately **not** the
    severity; `_check_allele_membership` explains why the obvious escalation is unsafe.

    - **authored** — the row itself carries `ref` *and* `alts`, so it contradicts itself. Note this
      does not mean a human wrote them: `reverse_module` emits both columns too.
    - **resolved** — the alleles come from `resolution.csv`, i.e. from whichever link won the variant.
      ClinVar carries only its *submitted* alleles while Ensembl carries every allele dbSNP knows, so a
      short alt list is a gap in the source at least as often as it is a defect in the module.

    `ref` without `alts` yields `None` deliberately: `{ref}` alone would flag every heterozygous
    genotype in the module, which is the normal shape of the data and not a finding.

    The resolved set is the **union over every locus** the key resolves to. A one-to-many rsid keeps one
    authored genotype while expanding to several loci, so exactly one locus can match and the others
    cannot; unioning is the only reading that does not manufacture a finding out of the expansion. (This
    is not hypothetical — `rs281864532`, `rs267607291` and `rs613985` in
    `reference_examples/pathogenic_clinvar/` are exactly that shape.)
    """
    if variant.ref and variant.alts:
        alleles = {variant.ref.upper()}
        alleles.update(a.strip().upper() for a in variant.alts.split(",") if a.strip())
        return alleles, "authored"
    resolved: set[str] = set()
    for row in resolution_table.get(variant.variant_key or "", []):
        if not row.ref or not row.alts:
            continue
        resolved.add(row.ref.upper())
        resolved.update(a.strip().upper() for a in row.alts.split(",") if a.strip())
    if resolved:
        return resolved, "resolved"
    return None, "unknown"


def _allele_verdict(
    call: str, variant: VariantRow, resolution_table: dict[str, list[ResolutionRow]]
) -> bool | None:
    """Can any locus this row is about host `call`? The shared tri-state predicate, Kleene-OR'd.

    **This must be the same question resolution asked, or the compiler contradicts itself.** The two
    checks are string comparisons of the same kind, and while membership did its own exact-set difference
    the halves disagreed the moment one indel was spelled two ways: `resolve_from_table` reconciled
    ClinVar's `C/CAG` with Ensembl's `AGAG>AG` and expanded onto the locus, and then membership refused
    the compile in `strict` because the literal strings `C` and `CAG` were not in the resolved set. Found
    by adding the case to `test_resolution_matrix.py`, which is what that file is for.

    Kleene semantics over the loci, matching `_allowed_alleles`' union reading: one locus that *can* host
    it settles the question (a one-to-many rsid carries one genotype onto N loci, and exactly one is
    expected to match), an undecidable spelling anywhere withholds, and only all-False is a finding.
    """
    if variant.ref and variant.alts:
        return hosting_verdict(call, variant.ref, variant.alts)
    return _resolved_allele_verdict(call, variant.variant_key, resolution_table)


def _resolved_allele_verdict(
    call: str, variant_key: str | None, resolution_table: dict[str, list[ResolutionRow]]
) -> bool | None:
    """The resolved half of `_allele_verdict`, keyed by identity rather than by row.

    Split out for `_check_study_effect_alleles` (RM91), which asks the identical question about a
    `StudyRow` — a model with no `alts` and no `variant_key` column, so it cannot be passed to the
    row-shaped predicate above. Factored rather than copied: two implementations of "can this locus
    host that call" is exactly the drift `_allele_verdict`'s own docstring records, where membership
    and resolution disagreed the moment one indel was spelled two ways.
    """
    verdicts = [
        hosting_verdict(call, row.ref, row.alts)
        for row in resolution_table.get(variant_key or "", [])
        if row.ref and row.alts
    ]
    if not verdicts:
        return None
    if any(verdict is True for verdict in verdicts):
        return True
    return None if any(verdict is None for verdict in verdicts) else False


def _spelling_because(allowed: set[str]) -> str | None:
    """The explanation to use when the locus's own alleles are not nucleotides, else `None`.

    Takes the allele *set* rather than a `ref`/`alts` pair because `_allowed_alleles` has already
    unioned across every locus the key resolves to, and the finding is stated against that union — a
    caveat derived from anything narrower could name an allele the message does not.

    **`*` is excluded, and this caveat is the one place that is unconditional (RM59).** The sentence
    exists to say *the genotype is not the problem, the locus is spelled oddly* — and since
    `hosting_verdict` now strips `*` from both sides before comparing, a `*` can no longer contribute to
    the `False` this explains. Leaving it in produced the exact inversion the caveat exists to prevent:
    `genotype=C/G` at `ref=A alts="T,*"` is a real genotype error, and the module was told the genotype
    was not the problem and to "replace it with the alleles the locus actually has".
    """
    offenders = {a: non_nucleotide_reason(a) for a in sorted(allowed)}
    offenders = {
        a: reason for a, reason in offenders.items() if reason is not None and not is_unobservable_allele(a)
    }
    if not offenders:
        return None
    return (
        "the genotype is not the problem: "
        + _spelling_clauses(offenders)
        + " — replace it with the alleles the locus actually has"
    )


def _spelling_clauses(offenders: dict[str, str]) -> str:
    """One clause per reason present, and **only** per reason present.

    The consequence sentence belongs *inside* the branch it is true of. The first cut appended "an
    ambiguity code is an uncertainty and is never expanded…" to every finding, so a `<DEL>` locus was
    told about ambiguity codes — the identical conflation `cpic.unusable_allele_reason` was repaired to
    stop making, reintroduced in the message that repair paid for. Four reasons, four consequences: an
    uncertainty is permanent, a symbolic allele is held by the grammar and simply not comparable here,
    a `*` is a fact about the sample's *coverage* and not about the variant at all, and a grammar gap is
    what is left.

    The fourth arm arrived with RM59 for the same reason the third did: `*` used to answer `"notation"`,
    so a locus whose ALT list carries one — which is what a joint-called VCF writes, and `alts` has no
    grammar to stop it — was told it had hit a gap a future release may widen. Nothing can widen to hold
    `*`, because there is no sequence there to hold.

    The `"notation"` clause used to say a `<DEL>` is "a grammar gap (RM5) … a future release may widen
    to hold it". RM5 shipped in 0.6, so that reading became false for the five structural types, and
    `alleles.non_nucleotide_reason` now separates them — which is why this clause list grew a third arm
    rather than reworded the second.
    """
    ambiguity = [a for a, reason in offenders.items() if reason == "ambiguity"]
    symbolic = [a for a, reason in offenders.items() if reason == "symbolic"]
    unobservable = [a for a, reason in offenders.items() if reason == "unobservable"]
    notation = [a for a, reason in offenders.items() if reason == "notation"]
    missing = [a for a, reason in offenders.items() if reason == "missing"]
    parts: list[str] = []
    if ambiguity:
        parts.append(
            f"{', '.join(repr(a) for a in ambiguity)} is an IUPAC ambiguity code rather than a definite "
            f"nucleotide (`Y` is C-or-T) — an uncertainty, so it is never expanded into the alleles it "
            f"could stand for and can match no genotype"
        )
    if symbolic:
        parts.append(
            f"{', '.join(repr(a) for a in symbolic)} is a symbolic/structural allele, which the grammar "
            f"holds (RM5) — it names a variant whose sequence is deliberately unspelled, so comparing it "
            f"against a spelled allele is undecided rather than a mismatch"
        )
    if unobservable:
        parts.append(
            f"{', '.join(repr(a) for a in unobservable)} is VCF's allele-missing-due-to-overlapping-"
            f"deletion marker (RM59) — it records that a call could not observe this position, so it "
            f"names no allele for anything to match, and it is a fact about a sample rather than a "
            f"grammar gap a release could close"
        )
    if notation:
        parts.append(
            f"{', '.join(repr(a) for a in notation)} is neither a nucleotide string nor a symbolic "
            f"allele the format holds (a repeat notation like `AAAGGGGCG(2)`, a deletion spelling like "
            f"`DELTCT`, or a typo) — a grammar gap rather than a genotype error"
        )
    if missing:
        # Third reason, third consequence (RM58), and the one that must NOT borrow either sentence
        # above: `.` is VCF's MISSING marker, so the locus is asserting that it has no alternate
        # allele. That is not an uncertainty and not a grammar gap — there is nothing to widen.
        parts.append(
            f"{', '.join(repr(a) for a in missing)} is VCF's MISSING marker rather than an allele — the "
            f"locus states that it has no alternate allele, so no genotype can match it; leave the cell "
            f"empty instead"
        )
    return "; and ".join(parts)


def _check_allele_membership(
    variants: list[VariantRow],
    resolution_table: dict[str, list[ResolutionRow]],
    *,
    strict: bool,
) -> tuple[list[str], list[str]]:
    """Every `genotype` allele and every `effect_allele` must be an allele the locus actually has.

    Validate-by-redundancy, and the cheapest high-value pair in the tier: a genotype `A/G` at a `C>T`
    locus, and an `effect_allele` naming an allele that is not there, both compile clean without this.
    The second is the more dangerous of the two — `direction`, `weight` and `effect_size` are all
    *relative to* `effect_allele`, so naming the wrong one silently inverts the module's conclusion
    rather than corrupting it visibly.

    **Run this on the authored rows, before resolution expands them.** After `resolve_from_table` a
    one-to-many rsid has become N rows that share the authored genotype and carry N *different* allele
    sets, so at most one of them can match and the rest would be reported as findings. See
    `_allowed_alleles` for the union semantics this relies on.

    **Severity is the mode ladder in every case — warning in `best_effort`, error in `strict`** — the
    same one the VRS *unverifiable* outcome uses. Provenance shapes the *message*, because it changes
    what the author should go and look at, but it cannot decide severity, and the reason is worth
    recording so it is not "simplified" back:

    - a **resolved** mismatch may be an incomplete source rather than a bad row (ClinVar carries only
      its submitted alleles), so failing by default would let a source's gap sink a correct module;
    - an **authored** mismatch looks decidable, and is not, because `ref`/`alts` in `variants.csv` are
      not necessarily *human*-authored. `reverse_module` writes them, and a one-to-many rsid reverses
      into N rows that each carry their own locus's alleles beside the *one* genotype the author wrote.
      Exactly one of those rows can match. Making that an unconditional error would mean any module
      with a one-to-many rsid stops recompiling after a round-trip — Principle 7's fixed point, broken
      by a lint. (Verified against `rs999`'s two loci in `test_resolution_table.py`, and the same shape
      occurs eleven times in `reference_examples/pathogenic_clinvar/`.)

    A row with neither allele set known is skipped: nothing to compare is not the same as nothing wrong.
    """
    ladders: list[LadderFinding] = []
    for variant in variants:
        allowed, provenance = _allowed_alleles(variant, resolution_table)
        if allowed is None:
            continue
        shown = "/".join(sorted(allowed))
        # A locus spelled with a non-nucleotide replaces the explanation rather than decorating it: both
        # stories below are *false* for that row. "The row contradicts itself" and "the source's allele
        # list is incomplete" each send the author to re-examine a genotype that was correct, when the
        # defect is one cell of the allele column. Checked against `allowed` (the union the verdict was
        # taken over), so it describes the same alleles the finding names.
        spelling = _spelling_because(allowed)
        if spelling is not None:
            because = spelling
        elif provenance == "authored":
            because = (
                "the row carries both `ref` and `alts`, so it contradicts itself — either the genotype "
                "or the alleles is wrong, or this row is one locus of a one-to-many rsid whose genotype "
                "belongs to a sibling locus (reverse writes the alleles per locus but copies the single "
                "authored genotype to all of them)"
            )
        else:
            because = (
                "these alleles come from resolution.csv, so either the genotype is wrong or the "
                "resolving source's allele list is incomplete (ClinVar carries only its submitted "
                "alleles, while Ensembl carries every allele dbSNP knows) — check which before editing"
            )
        findings: list[str] = []
        # The message must name exactly what `_allele_verdict` judged, and that predicate abstains on
        # a `*` (RM59): it records what the call could not observe, so it is never one of the alleles
        # "missing" from a locus. Listing it anyway pointed the author at a correct transcription — a
        # false accusation in the one sentence that is supposed to say which cell is wrong.
        missing = sorted(
            {a.upper() for a in _split_genotype(variant.genotype) if not is_unobservable_allele(a)} - allowed
        )
        if _allele_verdict(variant.genotype, variant, resolution_table) is False:
            findings.append(
                CodedWarning(
                    "genotype_allele_not_at_locus",
                    f"{variant.variant_key} genotype {variant.genotype}: allele(s) "
                    f"{', '.join(missing)} are not among the {provenance} alleles at this locus "
                    f"({shown}) — {because}",
                )
            )
        if (
            variant.effect_allele
            and _allele_verdict(variant.effect_allele, variant, resolution_table) is False
        ):
            findings.append(
                CodedWarning(
                    "effect_allele_not_at_locus",
                    f"{variant.variant_key} genotype {variant.genotype}: effect_allele "
                    f"{variant.effect_allele!r} is not among the {provenance} alleles at this locus "
                    f"({shown}) — direction/weight/effect_size are all stated relative to it, so a wrong "
                    f"effect allele inverts the conclusion rather than breaking it; {because}",
                )
            )
        if not findings:
            continue
        ladders.extend(LadderFinding(finding) for finding in findings)
    return route(ladders, strict=strict)


def _check_study_effect_alleles(
    studies: list[StudyRow],
    resolution_table: dict[str, list[ResolutionRow]],
    *,
    strict: bool,
) -> tuple[list[str], list[str]]:
    """`StudyRow.effect_allele` must be an allele the study's locus can host (RM91).

    The same question `_check_allele_membership` asks of `VariantRow.effect_allele`, and it exists for
    the same reason: `effect_size` is stated *relative to* this allele, so naming the wrong one inverts
    the study's finding instead of breaking it. Same mode ladder — warning in `best_effort`, error in
    `strict`.

    **Resolved evidence only, and it withholds on everything else.** A `StudyRow` has `ref` but no
    `alts` (`ref` is there so a position-only row keeps an identifier), so the authored branch of
    `_allowed_alleles` has nothing to compare and `{ref}` alone would flag every study of a
    non-reference allele — which is most of them. A row whose key reaches no `resolution.csv` entry is
    therefore skipped, not reported: unresolvable is unknown, and the house algebra withholds on
    unknown rather than negating it. That also means this check is silent on a module compiled with
    `--no-resolve`, which is correct and mirrors every other resolution-dependent check.

    Since 0.6 a study row need not name a variant at all (`REQUIRED_ANY_OF` is empty, RM47), so a row
    with no identity derives no key and is skipped by the same path.
    """
    ladders: list[LadderFinding] = []
    for study in studies:
        if not study.effect_allele:
            continue
        if study.rsid is None and study.chrom is None:
            continue
        key = derive_variant_key(study.rsid, study.chrom, study.start, study.ref)
        if _resolved_allele_verdict(study.effect_allele, key, resolution_table) is not False:
            continue
        resolved: set[str] = set()
        for row in resolution_table.get(key or "", []):
            if not row.ref or not row.alts:
                continue
            resolved.add(row.ref.upper())
            resolved.update(a.strip().upper() for a in row.alts.split(",") if a.strip())
        shown = "/".join(sorted(resolved))
        ladders.append(
            LadderFinding(
                CodedWarning(
                    "study_effect_allele_not_at_locus",
                    f"{key} (PMID {study.pmid}): effect_allele {study.effect_allele!r} is not among "
                    f"the resolved alleles at this locus ({shown}) — effect_size is stated relative to "
                    f"it, so a wrong effect allele inverts the study's finding rather than breaking "
                    f"it; the resolving source's allele list may also be incomplete, so check which "
                    f"before editing",
                )
            )
        )
    return route(ladders, strict=strict)


def _site_reference_allele(
    rows: list[VariantRow], site_key: str, resolution_table: dict[str, list[ResolutionRow]]
) -> str | None:
    """Which allele is the reference at this site, or `None` when nothing establishes it.

    Authored `ref` first, then the injected table — and the table half is what makes the check work at
    all on an rsid-authored module, where no row carries a coordinate and the site key *is* the rsID,
    which is exactly the key `resolution.csv` is written under. Withheld rather than guessed on a
    disagreement, because the classification below turns a missing genotype into a sentence naming
    which allele a subject would have to carry, and that is a claim about a row.
    """
    authored = {row.ref.upper() for row in rows if row.ref}
    if len(authored) == 1:
        return authored.pop()
    if authored:
        return None  # two rows disagree — `_cross_validate_variants` owns that finding, not this one
    resolved = {r.ref.upper() for r in resolution_table.get(site_key, []) if r.ref}
    return resolved.pop() if len(resolved) == 1 else None


def _check_genotype_coverage(
    variants: list[VariantRow], resolution_table: dict[str, list[ResolutionRow]]
) -> list[str]:
    """A site the module annotates for some of its genotypes and not the rest (S32).

    A consumer joins a module on `(variant, genotype)`, so a genotype with no row is a subject with no
    answer. `longevitymap` — a curated Gen-I module, 520 sites — authors **no** homozygous-alternate
    genotype at 208 of them, and the reporting consumer's subject was homozygous at 74; every one was
    silently unreported, and nothing in the toolchain said so. That is a curation gap the compiler can
    see, because it is entirely a property of the authored rows.

    **Scoped to sites authoring two or more genotypes, and that is the whole of the design.** A site
    with exactly one is the ordinary shape of a drafted-then-curated module — `pathogenic_clinvar`
    authors one genotype at 326 of its 327 sites — and it is a legitimate one: a rule that fires on the
    risk genotype and says nothing otherwise is a rule, not a gap. Reporting those would put a warning
    on almost every module in existence, which is the failure mode where warnings stop being read.
    Two or more genotypes is the author demonstrating that this site's genotype *space* is what they
    are describing, and then the missing member is a hole in something they started.

    **It says nothing about any callset, deliberately.** Whether a hom-ref row can ever match is a
    property of the *data* a consumer brings — a variant-only VCF emits no record where the sample
    matches the reference, a gVCF and an array both do — and that call belongs to the annotator, not
    here. So the finding is stated as what it is: a genotype this module has no row for. The presence
    of a hom-ref row is not reported at all; those rows are correct, and on array data they are the
    ones that carry the answer.

    Three things it will not do, each of which would make it wrong rather than noisier:

    * **never demand an alt/alt pair.** At a site with two alternates the expressible set includes
      `A/T`, and requiring it would make a complete table unreachable — the jointly-satisfiable lesson
      RM35 was filed for. The expected set is the reference homozygote, one heterozygote per alternate,
      and one homozygote per alternate.
    * **never guess the reference.** With no `ref` authored and none in the injected table, a
      two-allele site is still fully enumerable (three pairs over two alleles) and is reported by
      spelling; a site with three or more alleles is **skipped**, because without knowing which is the
      reference there is no way to enumerate without inventing alt/alt pairs.
    * **skip a site whose genotypes are not diploid nucleotide pairs.** Symbolic alleles (RM5), `*`
      (RM59) and single-allele hemizygous cells all land here, which is what keeps MT and non-PAR Y out
      without a contig list: those contigs are authored one allele per cell, so "incomplete" has no
      meaning there and a special case would only be a second thing to keep true.

    **Warning in both modes, never a `strict` error**, and it joins the small set of checks that
    arbitrate nothing — the ClinVar `clin_sig` cross-check, the declared-licence disagreement, the
    non-commercial quote. Which genotypes a module annotates is the curator's judgement; the compiler
    can say a member is absent, and must not say it is wrong to be absent.

    Runs in `validate_spec` **only**, and reaches `compile_module` through the warnings it returns. The
    message embeds counts, and by the time the compile has resolved, a one-to-many rsID has become one
    row per locus — so a second pass would report the same finding with a different number, and the
    message-dedup keys on the sentence, putting both into `manifest.compilation.warnings` (RM44's
    published surface). There is no severity for a re-run to recover here, so the single pass in front
    of resolution is the correct side.
    """
    sites: dict[str, list[VariantRow]] = defaultdict(list)
    for variant in variants:
        # Position-level, never allele-level: `derive_variant_key` mints a distinct VA id per ALT when
        # it is handed one, so keying with `alts` would split a two-alternate site into two
        # single-genotype sites and this check would go quiet on exactly the shape it is looking for.
        # This is the same call the study join and the reverse rsID back-fill make, for the same
        # reason — a genotype is written about a place.
        sites[derive_variant_key(variant.rsid, variant.chrom, variant.start, variant.ref)].append(variant)

    by_reason: dict[str, list[str]] = defaultdict(list)
    for site_key, rows in sites.items():
        pairs = [tuple(a.upper() for a in _split_genotype(row.genotype)) for row in rows]
        if any(len(p) != 2 or not all(ALLELE_PATTERN.match(a) for a in p) for p in pairs):
            continue
        authored = {tuple(sorted(p)) for p in pairs}
        if len(authored) < 2:
            continue
        alleles = {a for pair in authored for a in pair}
        ref = _site_reference_allele(rows, site_key, resolution_table)
        if ref is None and len(alleles) != 2:
            continue
        if ref:
            alts = sorted(alleles - {ref})
            expected = {(ref, ref)} | {tuple(sorted((ref, a))) for a in alts}
            expected |= {(a, a) for a in alts}
        else:
            # Two alleles and no reference: the three pairs over them are enumerable without knowing
            # which is which, and no alt/alt pair can be invented from two.
            first, second = sorted(alleles)
            expected = {(first, first), (first, second), (second, second)}
        for missing in sorted(expected - authored):
            spelled = "/".join(missing)
            if ref and missing == (ref, ref):
                reason = (
                    "the reference homozygote has no row, so a subject carrying neither alternate "
                    "matches nothing in this module"
                )
            elif ref and missing[0] == missing[1]:
                reason = (
                    "a homozygous alternate genotype has no row, so a subject carrying two copies "
                    "matches nothing in this module — the row that would describe them is the one "
                    "missing"
                )
            elif ref:
                reason = "a heterozygous genotype has no row, so a carrier matches nothing in this module"
            elif len({r.ref.upper() for r in resolution_table.get(site_key, []) if r.ref}) > 1:
                # A one-to-many rsID: the table resolves this key onto several loci and they disagree
                # about the reference, which is the *normal* shape of a ClinVar duplication/deletion
                # pair. `_site_reference_allele` withholds, correctly — but the generic wording below
                # then says "no ref is authored or resolved here" of a site with two of them, which
                # sends an author to fill in a cell that is already answered twice over (S33).
                reason = (
                    "a genotype expressible from the alleles this site already names has no row, and "
                    "this rsID resolves onto loci that disagree about the reference allele, so which "
                    "reading it is cannot be said here — a one-to-many expansion, not a missing fact"
                )
            else:
                reason = (
                    "a genotype expressible from the alleles this site already names has no row, and "
                    "no ref is authored or resolved here, so which reading it is cannot be said"
                )
            by_reason[reason].append((site_key, spelled))

    findings: list[str] = []
    for reason, found in sorted(by_reason.items()):
        # Both numbers, because they are different facts and one site can be missing several
        # genotypes: `hfe_hemochromatosis` is missing two heterozygotes at a **single** two-alternate
        # locus, which "2 sites" would have misreported. Same rule as every other counted warning here
        # — say what the denominator is rather than leaving a bare number to be read as either.
        sites_missing = len({site_key for site_key, _spelled in found})
        findings.append(
            CodedWarning(
                "genotype_coverage_gap",
                f"{len(found)} genotype(s) at {sites_missing} site(s) have no row: {reason}. The module "
                f"states two or more genotypes at each of those sites, so this is a gap in a set the "
                f"author started rather than a rule that fires once — "
                f"{_examples([f'{site_key} {spelled}' for site_key, spelled in found])}",
            )
        )
    return findings


# ── Symbolic / structural alleles (RM5) ─────────────────────────────────────────────────────────
#
# Which authored tables the symbolic-allele check may **drop a row from**, and which it must refuse on
# instead. The line is whether a row stands alone as a rule.
#
# `variants.csv` and `pharm_variants.csv` are one self-contained rule per row: dropping one removes a
# claim and removes nothing else, which is exactly the decided `best_effort` behaviour — a module is a
# declarative rulebook, and an unusable rule is worse than an absent one.
#
# `haplotypes.csv` and `heteroplasmy.csv` rows are *parts of a composite*. Dropping a haplotype's
# defining variant silently redefines the haplotype — the module would go on naming `*5` while
# describing something else — and dropping a bin punches a hole in a tiling `_validate_table_kind`
# just checked. Neither is a smaller module; both are a **different** one, asserted quietly. So the
# finding is fatal in both modes there, and the message says why the `best_effort` escape is not on
# offer. It is clearable by an authored edit (state the length), which is what separates it from the
# findings P5 keeps out of `strict`.
_SYMBOLIC_DROPPABLE_TABLES: frozenset[str] = frozenset({"variants.csv", "pharm_variants.csv"})


#: Splits a cell into the alleles it names: `/` and `|` for a genotype, `,` for a multi-allelic `alts`.
#: One splitter for every allele column — no allele column uses these characters within a token.
_ALLELE_CELL_SEP: re.Pattern[str] = re.compile(r"[,/|]")


@dataclass(frozen=True)
class _SymbolicFinding:
    """One unusable symbolic allele, located well enough for an author to go and fix it.

    **Located by the row's own identity, not by its position in the file.** A row index looks more
    precise and is not: `load_csv_rows` prints a *header-inclusive line number*, so a bare "row 2"
    would be a third coordinate convention beside that and `hints.Finding.row` (0-based); and it is
    computed over the rows that survived model validation, so any earlier load error silently shifts
    it. Every other row-level finding in this module names `variant_key`, and so does this one.
    """

    table: str
    index: int  # position among the loaded rows — for stable ordering only, never printed
    label: str  # the row's identity: variant_key, else haplotype_name
    column: str
    allele: str
    reason: str  # "no_length" | "unknown_type" | "reference_allele"


#: Reason → (what is wrong, what to do). Written out rather than composed, because the three are
#: different findings with different fixes and running them together is the conflation this codebase
#: has unwound twice (`cpic.unusable_allele_reason`, `_spelling_clauses`).
#:
#: **The prose names no allele type, and the reason is the aggregation** (D3-1). This dict is keyed by
#: reason because the messages are grouped by reason — one line per (table, reason), never one per row
#: — so a sentence that opened "A <DEL> that does not say how long it is" was a claim about *the*
#: offending allele made where several are being reported at once, and it read as a false one the
#: moment the author had written `<DUP:TANDEM>`. Interpolating the authored type would make each
#: sentence exactly right and turn one constant into N messages, which is the per-row prose that
#: printed forty lines each naming a different indel in the VRS pass. The example clause that
#: `_symbolic_allele_messages` appends already names the real cells, so the specific case is not lost.
#: `<DEL:1500>` survives below as the *spelling to use*, which is what an author actually needs.
_SYMBOLIC_REASONS: dict[str, str] = {
    "no_length": (
        "a symbolic allele with no usable length. An allele that names an event without saying how "
        "long it is cannot be sized, matched against a call, or told apart from any other event of "
        "the same type at that position, so the rule states nothing a consumer can apply. Spell the "
        "length into the allele — <DEL:1500>, <CNV:TR:30> — or, when the sequence is actually known, "
        "spell the bases out instead (VCF 4.4 says to: symbolic notation is for imprecision)"
    ),
    "unknown_type": (
        "an allele that is angle-bracketed but not one this format holds. The first level is the closed "
        f"five {'/'.join(sorted(SYMBOLIC_ALLELE_TYPES))} and subtypes are free-form — VCF recommends "
        f"{', '.join(f'<{s}>' for s in RECOMMENDED_SYMBOLIC_SUBTYPES)} — but there is no declaration "
        "mechanism for arbitrary names, deliberately. VCF's <*> is not one of them either: it makes a "
        "claim about what could be *observed*, which is a different axis from what the variant *is*"
    ),
    "reference_allele": (
        "a symbolic allele in a reference-allele column. REF is always a sequence — the padding base "
        "and whatever follows it — and a structural allele names an ALT; a locus whose own reference "
        "is unspelled anchors nothing"
    ),
}


def _symbolic_findings(rows_by_table: dict[str, list[Any]]) -> list[_SymbolicFinding]:
    """Every unusable symbolic allele in the authored rows, in a deterministic order.

    Which columns hold an allele comes from the **model** (`AuthoredModel.ALLELE_COLUMNS`), never from
    a list kept here: a compiler-side copy of a model's column names is the drift `SOURCES_FIELDNAMES`
    already demonstrated, and this check would go quietly blind the day a model gained a column.

    Sorted by `(table, reason, index, column)` so the messages built from it are byte-stable — findings
    reach `manifest.compilation.warnings`, so their order is artifact-visible.
    """
    found: list[_SymbolicFinding] = []
    for table, rows in rows_by_table.items():
        for index, row in enumerate(rows):
            label = getattr(row, "variant_key", None) or getattr(row, "haplotype_name", None)
            for column in getattr(type(row), "ALLELE_COLUMNS", ()):
                cell = getattr(row, column, None)
                if not isinstance(cell, str):
                    continue
                for token in _ALLELE_CELL_SEP.split(cell):
                    allele = token.strip()
                    if not is_symbolic_allele(allele):
                        continue
                    reason = "reference_allele" if column == "ref" else symbolic_allele_defect(allele)
                    if reason is not None:
                        found.append(
                            _SymbolicFinding(
                                table,
                                index,
                                str(label or f"the {_ordinal(index)} row"),
                                column,
                                allele,
                                reason,
                            )
                        )
    return sorted(found, key=lambda f: (f.table, f.reason, f.index, f.column))


def _ordinal(index: int) -> str:
    """`0` → `1st`. The last-resort label for a row carrying no identity of its own — no model in
    `ALLELE_COLUMNS` is in that state today, and a bare integer would read as a file line number."""
    n = index + 1
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _symbolic_allele_messages(findings: list[_SymbolicFinding]) -> list[str]:
    """One aggregated line per (table, reason) — never one per row.

    A structural panel drafted from a caller's VCF hits this per locus, and a line each buries every
    other finding in the run. The grouping is by **reason** rather than by row for the other half of
    the same rule: two reasons under one message is the mistake that took four rounds to stop making
    in the CPIC provider.

    The wording is identical in `validate_spec` and `compile_module` on purpose. `compile_module` runs
    `validate_spec` first, in `best_effort` whatever its own mode, so a check living in both places
    emits its sentence twice and the compile side de-duplicates **on the message**.
    """
    messages: list[str] = []
    grouped: dict[tuple[str, str], list[_SymbolicFinding]] = {}
    for finding in findings:  # already sorted, so insertion order is deterministic
        grouped.setdefault((finding.table, finding.reason), []).append(finding)
    for (table, reason), entries in grouped.items():
        # Rows, not findings. One row routinely carries the same unusable allele in three columns
        # (`alts`, `genotype`, `effect_allele`), and the sentence says "row(s)" — counting findings
        # there would report three rows dropped where one is.
        affected = len({e.index for e in entries})
        shown = ", ".join(f"{e.label} {e.column}={e.allele!r}" for e in entries[:3])
        rest = f" (+{len(entries) - 3} more)" if len(entries) > 3 else ""
        fate = (
            "Those row(s) are DROPPED from the compiled artifact — reverse will not re-emit them — "
            "and --strict refuses instead."
            if table in _SYMBOLIC_DROPPABLE_TABLES
            else (
                f"This is fatal in both modes: a {table} row is part of a composite (a haplotype's "
                f"definition, a bin tiling), so dropping it would not make a smaller module but a "
                f"quietly different one."
            )
        )
        # Coded even where the caller routes the line into `errors` — one builder, one sentence, and
        # the code costs nothing on the error path, where nothing reads it. **That is also why the
        # code names the unusable allele and not the drop**: `fate` says "dropped" for a droppable
        # table and "fatal in both modes" for a composite one, so a code naming the consequence would
        # be accurate on one path and a false claim on the other the day somebody routes the errors
        # here too. A code names the finding; the sentence carries which of its two consequences fired.
        messages.append(
            CodedWarning(
                "symbolic_allele_unusable",
                f"{table}: {affected} row(s) carry {_SYMBOLIC_REASONS[reason]}. {fate} e.g. {shown}{rest}.",
            )
        )
    return messages


def _check_symbolic_alleles(
    rows_by_table: dict[str, list[Any]], *, strict: bool
) -> tuple[list[str], list[str], dict[str, set[int]]]:
    """`(errors, warnings, rows to drop per table)` for unusable symbolic alleles (RM5).

    **The schema accepts what this refuses, and that split is forced rather than chosen.** A model-level
    rejection surfaces through `load_csv_rows` as a load error, which is fatal in *both* modes; the
    decided behaviour is warn-and-drop under `best_effort`. So the grammar says what the DSL can spell
    (`vocab.validate_allele`, `AuthoredModel._validate_genotype`) and this says what makes a usable
    rulebook. Do not "tighten" it back into the models.

    One asymmetry worth expecting: `<FOO>` fails at *load* in `genotype`/`effect_allele`/
    `HaplotypeRow.allele`, because those columns have a grammar, and reaches this check only through
    `ref`/`alts`, which deliberately have none (adding one would reject `N` and break P3). Same
    diagnosis either way; different point of arrival.

    Pure computation over authored bytes with no `output_dir`, so by the standing rule it runs in
    `validate_spec` too — where nothing is dropped and the message is a prediction of what a compile
    will do.
    """
    findings = _symbolic_findings(rows_by_table)
    if not findings:
        return [], [], {}
    fatal = [f for f in findings if f.table not in _SYMBOLIC_DROPPABLE_TABLES]
    droppable = [f for f in findings if f.table in _SYMBOLIC_DROPPABLE_TABLES]
    errors = _symbolic_allele_messages(fatal)
    # The droppable half is a ladder member with the same sentence in both channels (RM246) — which is
    # what `refusal=None` states, where the third spelling this used to carry (`if strict:` moving the
    # same list into `errors`) only implied it. The mode ALSO decides whether the rows are dropped, and
    # that half stays here: it is a behaviour the channel does not carry, and `route` deliberately
    # answers one question.
    ladders = [LadderFinding(message) for message in _symbolic_allele_messages(droppable)]
    ladder_errors, ladder_warnings = route(ladders, strict=strict)
    errors.extend(ladder_errors)
    if strict:
        return errors, [], {}
    drops: dict[str, set[int]] = {}
    for finding in droppable:
        drops.setdefault(finding.table, set()).add(finding.index)
    errors.extend(_emptied_table_errors(rows_by_table, drops))
    return errors, ladder_warnings, drops


def _emptied_table_errors(rows_by_table: dict[str, list[Any]], drops: dict[str, set[int]]) -> list[str]:
    """A table the drop would empty outright is an error in **both** modes.

    The drop exists so a module can lose one unusable rule and still say the rest; a table that loses
    *every* row says nothing at all, and says it silently — the surviving artifact is a module that
    annotates nothing, which is precisely the shape the DROPPED warning exists to keep an author from
    believing they still have.

    **Computed here rather than at the point of application, and that placement is the point.**
    `_check_symbolic_alleles` runs in `validate_spec` as well as `compile_module`, so the refusal is
    predicted by the pre-flight; the first cut refused inside the drop, which only `compile_module`
    performs, and produced exactly the green-`validate`-then-failing-`compile` sequence the standing
    parity rule exists to prevent. (An earlier version of this docstring justified the refusal as
    "`validate_spec` already refuses a present-but-empty table". That is true of the `_TABLE_KINDS`
    loop and **false of `variants.csv`**, which validates and compiles header-only — measured. The
    refusal stands on its own reason, above.)
    """
    return [
        f"{table}: every row would be dropped for carrying an unusable symbolic allele, leaving a "
        f"table that states nothing — so the compile would quietly produce a module that annotates "
        f"nothing at all. Refused in both modes. Give the alleles their lengths, or remove the table."
        for table, rows in sorted(rows_by_table.items())
        if rows and len(drops.get(table, ())) == len(rows)
    ]


def _apply_symbolic_drops(rows: list[Any], drop_rows: set[int]) -> list[Any]:
    """The surviving rows. Refusal is `_emptied_table_errors`' job — see there for why it is not here."""
    return [row for index, row in enumerate(rows) if index not in drop_rows]


def _check_p_value_num(studies: list[StudyRow], *, strict: bool) -> tuple[list[str], list[str]]:
    """Does the typed `p_value_num` agree with the free-form `p_value` string beside it?

    Validate-by-redundancy on two encodings of one number, so it is exactly the tier's own kind of
    check: pure computation over injected data, no reference required. A transcription slip between
    the verbatim cell and the queryable one is otherwise invisible — the module compiles, and a
    consumer thresholding on the number silently reads a different p-value than the row displays.

    **A string that does not denote one definite value is skipped in silence.** `"<0.001"`, `"NS"` and
    `"5e-8 (adjusted)"` are all legitimate things to have written in a free-form column, and none of
    them disagrees with anything — see `normalize.parse_p_value`, which is anchored on the whole cell
    rather than reading a leading number out of commentary.

    The comparison is relative, at 1%: the string is the record and the number is a transcription of
    it, so `p_value="5.23e-8"` beside `5.2e-8` is a rounding rather than a contradiction, while a
    wrong digit or a wrong power of ten is neither. Severity is the mode ladder — warning in
    `best_effort`, error in `strict`."""
    ladders: list[LadderFinding] = []
    for row in studies:
        if row.p_value_num is None:
            continue
        parsed = parse_p_value(row.p_value)
        if parsed is None or math.isclose(parsed, row.p_value_num, rel_tol=0.01):
            continue
        ladders.append(
            LadderFinding(
                CodedWarning(
                    "p_value_encodings_disagree",
                    f"{row.variant_key} pmid {row.pmid}: p_value {row.p_value!r} reads as {parsed:g}, "
                    f"but p_value_num says {row.p_value_num:g} — two encodings of one number disagree, "
                    f"so one of them is a transcription slip (the string is the record; the number is "
                    f"what a consumer filters on).",
                )
            )
        )
    return route(ladders, strict=strict)

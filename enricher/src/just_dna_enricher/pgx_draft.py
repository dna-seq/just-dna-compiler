"""Draft a PGx module's authored tables from CPIC (0.5) — the first drafting provider.

`cpic.py` already fetches the three things a star-allele module is made of (allele function, the
defining variants behind each allele, and diplotype → phenotype), and `just_dna_compiler.draft` owns
the append-without-clobbering mechanism. This module is the mapper between them.

**Why it exists.** The actionable layer of pharmacogenomics is the diplotype — `CYP2C19 *2/*17`, not
`rs4244285` heterozygous — and the format has carried `haplotypes.csv` / `allele_function.csv` /
`diplotypes.csv` since 0.4. Nothing populated them, so the tables were authorable in principle and
empty in practice, and the reference example went to the variant grain instead. Transcribing a
published table is machine work; deciding what a module says about a patient is not.

**What it will not do**, and each is a rule rather than a limitation:

* It **never rewrites an authored cell.** A row whose key already exists is reported, not replaced —
  see `just_dna_compiler.draft`. Drift against CPIC is `pgx.enrich_pgx`'s finding to report.
* It **stamps no `authorship`.** The generator transcribes a published table; the human owns the
  module and the record of who wrote it.
* It **skips what it cannot express rather than coercing it.** CPIC's IUPAC ambiguity codes (`R` at
  CYP2C19 `*2`) are not nucleotides, and its activity scores are inequality strings (`"≥3.0"`) that
  fit no numeric bound. Both are reported and left out.
* CYP2D6's structural alleles (`*5` whole-gene deletion, `*1x2` duplication) have no defining
  nucleotide event to write, so they are skipped with a warning. That is RM5, not a bug here.

Coordinates from CPIC are GRCh38 and **1-based**, which is what this pipeline already stores — the
instinctive `-1` introduces an off-by-one.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import DraftReport, append_rows
from just_dna_format.pgx import STAR_ALLELE_PATTERN, AlleleFunctionRow, DiplotypeRow, HaplotypeRow

from just_dna_enricher.cpic import (
    CpicClient,
    CpicDefiningVariant,
    CpicError,
    CpicRecommendation,
    CpicSnapshotClient,
)
from just_dna_enricher.enrich import source_build_mismatch
from just_dna_enricher.licensing import CPIC_TERMS, check_declared_use, merge_sources_file
from just_dna_enricher.locations import resolve_cpic_reference

#: The assembly CPIC's `sequence_location.position` is on — probed, not assumed: `rs1799853` is
#: `10:94942290` there, which is its GRCh38 position (GRCh37 is `10:96702047`). Named for the reason
#: `gnomad.FREQUENCY_GENOME_BUILD` and `pharmvar.PHARMVAR_GENOME_BUILD` are: this is the fourth build
#: confusion in this package and every one of them was a literal assumption at a call site.
CPIC_GENOME_BUILD = "GRCh38"

logger = logging.getLogger(__name__)

#: CPIC's spelling for "not scored" — an absence, never a value the module should carry.
_NOT_SCORED: frozenset[str] = frozenset({"n/a", "na", "none", "-"})

#: CPIC writes a diplotype as `*1/*2`; both halves must be star alleles the format can hold.
_DIPLOTYPE_SEP = "/"


@dataclass
class PgxDraftResult:
    """What a scaffold run did, per table."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def added(self) -> int:
        return sum(len(r.added) for r in self.reports)

    @property
    def differs(self) -> int:
        return sum(len(r.differs) for r in self.reports)


def _haplotype_rows(variants: list[CpicDefiningVariant]) -> tuple[list[HaplotypeRow], list[str]]:
    """CPIC's defining variants → `haplotypes.csv` rows, skipping what the grammar cannot hold."""
    rows: list[HaplotypeRow] = []
    warnings: list[str] = []
    # Aggregated for the third time in this file, and the same reason each time: a real CYP2D6 draft
    # emits ten of these for `*1` alone, one line apiece, which buries the licence row and the allele
    # skips underneath them.
    no_locus: list[str] = []
    for variant in variants:
        if variant.unusable or not variant.variant_allele:
            continue  # already reported by the client; nothing definite to write
        if not STAR_ALLELE_PATTERN.match(variant.allele or ""):
            warnings.append(
                f"{variant.gene}: {variant.allele!r} is not a star-allele string this format can "
                f"hold — skipped."
            )
            continue
        # Mirror `HaplotypeRow._validate_identification` exactly: rsid, or chrom AND start. The
        # guard used to accept a bare `start`, so `draft --gene CYP2C9` built a row with a position,
        # no chromosome and no rsID and died on an unhandled pydantic error. A guard that does not
        # match the model it builds is not a guard.
        #
        # Those 36 rows (18 CYP2C9, 14 TPMT, 4 NUDT15) are now *drafted* rather than skipped: the
        # chromosome they were missing is published on CPIC's `gene` table, and `defining_variants`
        # joins it (see `cpic.py`). What is left here is the genuine residue — a variant CPIC gives
        # neither an rsID nor a position for, or a gene whose `chr` cell is blank.
        if variant.rsid is None and (variant.chrom is None or variant.start is None):
            no_locus.append(f"{variant.allele}@{variant.start}")
            continue
        rows.append(
            HaplotypeRow(
                haplotype_name=variant.allele,
                rsid=variant.rsid,
                # `chrom` was dropped on the floor here: `CpicDefiningVariant` carries one and this
                # never passed it, so a coordinate-identified variant would have been built without
                # its chromosome and rejected by the very rule the guard above checks. Latent while
                # CPIC publishes no chromosome, and exactly the kind of gap that bites the day it does.
                chrom=variant.chrom,
                # CPIC positions are GRCh38 1-based; stored as-is (see the module docstring).
                start=variant.start,
                allele=variant.variant_allele,
                gene=variant.gene,
            )
        )
    if no_locus:
        gene = variants[0].gene if variants else "?"
        shown = ", ".join(no_locus[:3])
        rest = f" (+{len(no_locus) - 3} more)" if len(no_locus) > 3 else ""
        warnings.append(
            f"{gene}: {len(no_locus)} defining variant(s) skipped — CPIC gives no rsID and no usable "
            f"locus for them (no position, or no `chr` on the gene), and a haplotype row identified "
            f"by neither resolves to nothing. e.g. {shown}{rest}."
        )
    return rows, warnings


def _split_diplotype(diplotype: str) -> tuple[str, str] | None:
    parts = [p.strip() for p in diplotype.split(_DIPLOTYPE_SEP)]
    if len(parts) != 2 or not all(STAR_ALLELE_PATTERN.match(p) for p in parts):
        return None
    return parts[0], parts[1]


#: The reference allele, always kept by an `--allele` filter. It is *defined* by carrying no variants, so
#: including it costs no rows, and leaving it out would make `*1/*2` — the commonest real diplotype —
#: undraftable while the author was asking for `*2`.
_REFERENCE_ALLELE = "*1"


def _selected_alleles(
    requested: Sequence[str], published: Sequence[str], gene: str
) -> frozenset[str] | None:
    """The allele set to draft, or `None` for "everything CPIC publishes" (no filter).

    **Why a filter exists at all.** `draft --gene CYP2D6` produces 16,290 diplotype rows, 73% of them
    `Indeterminate` — every row a faithful transcription, and a module no human can read (RM34). The
    author's own bound is the allele set their caller can emit, and *n* alleles is *n(n+1)/2* pairs, so
    naming six collapses CYP2D6 to something authorable.

    **An unknown name refuses.** A typo silently yields a smaller module, which is the failure mode a
    filter must not introduce — and `--population` already set the precedent that a value the source does
    not have is reported rather than quietly drafting nothing.
    """
    if not requested:
        return None
    wanted = {a.strip() for a in requested if a.strip()}
    unknown = sorted(wanted - set(published))
    if unknown:
        raise CpicError(
            f"{gene}: CPIC publishes no allele(s) {unknown}. Available: "
            f"{', '.join(sorted(published)) or '(none)'}."
        )
    return frozenset(wanted | {_REFERENCE_ALLELE})


def _pair_in(diplotype: str, selected: frozenset[str]) -> bool:
    """Whether both halves of a diplotype are in the selected set (an unparsable pair is left alone).

    Unparsable means the copy-number/`≥` notation the provider already skips and reports; deciding it
    here too would report it twice and, worse, would hide it behind a filter message.
    """
    pair = _split_diplotype(diplotype)
    return pair is None or (pair[0] in selected and pair[1] in selected)


def _recommendation_rows(
    diplotypes: Sequence,
    recommendations: Sequence[CpicRecommendation],
    *,
    population: str | None,
) -> tuple[list[DiplotypeRow], list[str]]:
    """CPIC recommendations → drug-carrying `DiplotypeRow`s, joined on the phenotype.

    **Every clinical context is drafted, and `--population` filters rather than decides (0.5.1).**
    This used to refuse whenever CPIC scoped a gene/drug pair to more than one setting: clopidogrel
    has three (`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`) whose recommendations disagree, and with
    no column to hold the distinction, writing them all produced rows the compiler rejected as
    duplicates while writing one asserted a setting the author never chose. `DiplotypeRow.clinical_context`
    (RM29b) removes the dilemma rather than resolving it: the settings become distinct rows, keyed
    apart, and the *consumer* selects its own at query time. That is the right owner — which
    indication a patient is being treated for is knowable at query time and not at authoring time.

    `population` is kept as a filter for an author who genuinely wants one setting only, and an
    unknown value is still an error: silently drafting nothing because of a typo would look like
    "CPIC has no recommendations here".
    """
    populations = sorted({r.population for r in recommendations if r.population})
    warnings: list[str] = []
    if not recommendations:
        return [], warnings
    if population is not None and population not in populations:
        return [], [
            f"{recommendations[0].drug}: no CPIC recommendations for population {population!r}. "
            f"Available: {', '.join(populations) or '(none)'}."
        ]
    wanted = [r for r in recommendations if population is None or r.population == population]
    # `(phenotype, context)` — the pair a row is now keyed on. One phenotype legitimately carries
    # several rows, one per setting, which is the whole point of the column.
    by_key = {(r.phenotype, r.population): r for r in wanted}
    rows: list[DiplotypeRow] = []
    unmatched: set[str] = set()
    for entry in diplotypes:
        pair = _split_diplotype(entry.diplotype)
        if pair is None or entry.phenotype is None:
            continue
        matched = [rec for (phenotype, _), rec in by_key.items() if phenotype == entry.phenotype]
        if not matched:
            unmatched.add(entry.phenotype)
            continue
        for rec in matched:
            rows.append(
                DiplotypeRow(
                    gene=entry.gene,
                    haplotype_a=pair[0],
                    haplotype_b=pair[1],
                    phenotype=entry.phenotype,
                    drug=rec.drug,
                    recommendation_strength=rec.classification,
                    clinical_context=rec.population or None,
                    # CPIC's own words. The implication says what the genotype does, the recommendation
                    # says what to do about it; both are transcribed, neither is summarized.
                    conclusion=" ".join(
                        part for part in (rec.implication, rec.recommendation) if part
                    ) or f"{entry.gene} {entry.diplotype} and {rec.drug}: {entry.phenotype}",
                )
            )
    if unmatched:
        scope = f" in population {population!r}" if population else ""
        warnings.append(
            f"{recommendations[0].drug}: no CPIC recommendation for phenotype(s) "
            f"{sorted(unmatched)}{scope} — those diplotypes carry no drug row."
        )
    return rows, warnings


def draft_gene(
    spec_dir: Path,
    gene: str,
    *,
    drugs: Sequence[str] = (),
    alleles: Sequence[str] = (),
    population: str | None = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
    offline: bool = False,
    cpic_cache: Path | None = None,
    client: CpicClient | CpicSnapshotClient | None = None,
) -> PgxDraftResult:
    """Draft one gene's `haplotypes.csv`, `allele_function.csv` and `diplotypes.csv` rows.

    Re-runnable and additive: call it once per gene, in any order, as a module grows. Rows already in
    the files are left exactly as they are.

    `alleles` restricts the draft to a set of star alleles (RM34) and is applied to **all three** tables:
    the defining variants of those alleles, their function rows, and only the diplotypes whose *both*
    halves are in the set. Filtering one table and not the others would leave a module naming alleles it
    never defines, which is precisely what `_cross_validate_haplotype_definitions` warns about. `*1` is
    always kept; empty means everything CPIC publishes, exactly as before.

    `offline` (0.5.1, RM38) is the flag this provider simply did not have — every sibling pass took one,
    so a caller running the family under one switch had to know out of band that drafting ignored it,
    and forgetting meant silent egress from a run documented as making none. A built CPIC snapshot
    serves the draft; with none and `offline` set, nothing is drafted and the reason is returned.
    """
    skip_reason = check_declared_use(CPIC_TERMS, declared_use)
    if skip_reason:
        # Acquisition-time refusal: nothing is fetched, because the terms are accepted by taking it.
        return PgxDraftResult(warnings=[skip_reason], skipped=True)

    # **Asked before the client, not beside the rows it warns about** (R2-2). `source_build_mismatch`
    # raises `EnrichmentError` on a present-but-unreadable `module_spec.yaml`, which is right — a
    # module whose declaration cannot be read has no build to draft against — but asking it *after*
    # the CPIC queries meant the failure landed once the work was already paid for. It reads a file
    # beside the spec and costs nothing, so it belongs with the other precondition above. The warning
    # itself is still appended in its old place, so the reported order does not move.
    build_warning = source_build_mismatch(spec_dir, "CPIC", CPIC_GENOME_BUILD)

    owned = client is None
    if client is not None:
        cpic = client
    else:
        reference = resolve_cpic_reference(cpic_cache)
        if reference is not None:
            cpic = CpicSnapshotClient(reference)
        elif offline:
            return PgxDraftResult(
                warnings=[
                    "CPIC draft skipped: --offline and no built snapshot. Build one with "
                    "`just-dna-enricher cpic build --out <dir>`, or point at it with "
                    "$JUST_DNA_CPIC_CACHE."
                ],
                skipped=True,
            )
        else:
            cpic = CpicClient()
    try:
        published = cpic.alleles_for_gene(gene)
        diplotypes = cpic.diplotypes_for_gene(gene)
        defining, defining_warnings = cpic.defining_variants(gene)
        by_drug = {drug: cpic.recommendations(gene, drug) for drug in drugs}
        # Asked here, inside the `try`, because the client is closed in the `finally` below — and
        # asked only for the drugs that came back empty, since that is the only case whose message
        # needs it. See `CpicClient.knows_drug`.
        #
        # **Its failure is caught, and that is R2-4.** By this line every substantive query has
        # already returned: the alleles, the diplotypes, the defining variants and the
        # recommendations are all in hand, and a complete draft exists. `knows_drug` exists only to
        # sharpen the *sentence* explaining an empty result, so letting a transport failure here
        # propagate would discard finished work to improve a message about it — the gnomAD rule
        # (a per-item error must never sink a batch) arriving in a different tier.
        #
        # The tri-state it is typed with was designed and, from the live client, never delivered:
        # `CpicClient.knows_drug` could only return `True`/`False` or raise, so the `known is None`
        # branch below was reachable from the snapshot client alone. R2-13 is what makes this
        # catchable at all — before it, the escape was a raw `httpx.HTTPStatusError`.
        drug_known: dict[str, bool | None] = {}
        unaskable: dict[str, str] = {}
        for drug, found in by_drug.items():
            if found:
                continue
            try:
                drug_known[drug] = cpic.knows_drug(drug)
            except CpicError as exc:
                drug_known[drug] = None
                unaskable[drug] = str(exc)
    finally:
        if owned:
            cpic.close()

    warnings = list(defining_warnings)
    # CPIC's `sequence_location` is GRCh38 and `haplotypes.csv` gets a `chrom`/`start` from it, so a
    # module declaring another build is about to record a position from the wrong assembly. Computed
    # at the top of the function; reported here.
    if build_warning:
        warnings.append(f"{gene}: {build_warning}")
    selected = _selected_alleles(alleles, [a.allele for a in published], gene)
    if selected is not None:
        # Filtered once, here, so the three tables and the drug rows all see the same set — the drug rows
        # are joined onto these same diplotypes below.
        kept = [d for d in diplotypes if _pair_in(d.diplotype, selected)]
        # Counted over the **parsable** pairs only, which is what the filter actually decided. Counting
        # every row instead read "567 of 16836 drafted" for a set of six alleles, because the 546
        # copy-number rows `_pair_in` deliberately leaves alone were tallied as kept and then skipped by
        # the notation rule below — two different findings, and the reader could not see either.
        parsable = [d for d in diplotypes if _split_diplotype(d.diplotype) is not None]
        kept_parsable = [d for d in kept if _split_diplotype(d.diplotype) is not None]
        warnings.append(
            f"{gene}: --allele kept {len(selected)} allele(s) {sorted(selected)} (`*1` is always kept, "
            f"since it is defined by carrying no variants) — {len(kept_parsable)} of {len(parsable)} "
            f"diplotype(s) drafted; the rest name an allele outside the set."
        )
        diplotypes = kept
        published = [a for a in published if a.allele in selected]
        defining = [v for v in defining if v.allele in selected]

    haplotypes, haplotype_warnings = _haplotype_rows(defining)
    warnings.extend(haplotype_warnings)

    function_rows: list[AlleleFunctionRow] = []
    for allele in published:
        if not STAR_ALLELE_PATTERN.match(allele.allele or ""):
            warnings.append(f"{gene}: allele {allele.allele!r} is not a star-allele string — skipped.")
            continue
        function_rows.append(
            AlleleFunctionRow(
                gene=allele.gene,
                allele=allele.allele,
                activity_value=allele.activity_value,
                function_status=allele.function_status,
            )
        )

    diplotype_rows: list[DiplotypeRow] = []
    # Aggregated, not one line per row: CYP2C19 alone produced ~600 identical warnings, which buries
    # every other finding in the run. A cap with the total stated beats a wall with nothing stated.
    unscorable: dict[str, list[str]] = {}
    unparsable: list[str] = []
    for entry in diplotypes:
        pair = _split_diplotype(entry.diplotype)
        if pair is None:
            # Aggregated for the same reason the activity scores four lines below are, which this
            # loop had not learned: a real CYP2D6 draft skips 546 diplotypes whose copy-number
            # notation carries `≥` (`*4x≥3/*95`), and 546 identical-shaped lines bury every other
            # finding — including the three allele skips and the licence row. One line, examples,
            # and the count, so nothing is silently dropped.
            unparsable.append(entry.diplotype)
            continue
        if entry.phenotype is None:
            continue  # nothing to conclude; a row whose only content is the pair says nothing
        if entry.activity_score and not _is_numeric(entry.activity_score):
            # Two different things, and they were reported as one. `"≥3.0"` is a *bound*: real
            # information the numeric bin columns cannot hold. `"n/a"` is CPIC saying it did not
            # score this diplotype — an absence, which is an empty cell here and not a finding at
            # all. Calling that "an inequality rather than a number" was simply wrong.
            bucket = "unscored" if entry.activity_score.strip().lower() in _NOT_SCORED else "bounded"
            unscorable.setdefault(bucket, []).append(f"{entry.diplotype}={entry.activity_score}")
        diplotype_rows.append(
            DiplotypeRow(
                gene=entry.gene,
                haplotype_a=pair[0],
                haplotype_b=pair[1],
                phenotype=entry.phenotype,
                conclusion=f"{entry.gene} {entry.diplotype}: {entry.phenotype}",
            )
        )

    if unparsable:
        shown = ", ".join(unparsable[:3])
        rest = f" (+{len(unparsable) - 3} more)" if len(unparsable) > 3 else ""
        warnings.append(
            f"{gene}: {len(unparsable)} diplotype(s) are not a pair of star alleles and were "
            f"skipped — CPIC writes copy number as `x≥3`, and `≥` is not a nucleotide-allele or "
            f"star-string character. e.g. {shown}{rest}."
        )

    for bucket, entries in sorted(unscorable.items()):
        shown = ", ".join(entries[:3])
        rest = f" (+{len(entries) - 3} more)" if len(entries) > 3 else ""
        warnings.append(
            f"{gene}: {len(entries)} diplotype(s) carry no numeric activity score — "
            + (
                "CPIC records them as not scored, so the cell is simply empty"
                if bucket == "unscored"
                else "CPIC gives a bound rather than a value; add a bin by hand if you need one"
            )
            + f". e.g. {shown}{rest}."
        )

    # Drug rows are *added to* the phenotype table, not a replacement for it: the plain rows answer
    # "what phenotype is this pair", the drug rows answer "and what does CPIC say to do about it for
    # this drug". Different questions, and `_TABLE_DUPE_KEYS` keys on `drug`, so both coexist.
    for drug, recommendations in by_drug.items():
        if not recommendations:
            # Three outcomes, not one sentence. "CPIC has no recommendations for X" was emitted
            # identically for a typo and for a real drug CPIC scores in a shape this table does not
            # hold — warfarin being exactly that: the guideline exists, it is a dosing algorithm over
            # several genes rather than a per-phenotype recommendation, so nothing lands here and the
            # author was told CPIC has nothing. Same distinction the rsID vocabulary makes between a
            # mistyped id and a real one the source records differently.
            known = drug_known.get(drug)
            if known is False:
                detail = (
                    "CPIC does not list that drug at all — check the spelling (CPIC uses lowercase "
                    "generic names)"
                )
            elif drug in unaskable:
                # A third reading of "could not establish", kept apart from the snapshot one below
                # because the remedies differ: this one is re-runnable and that one is not. Folding
                # them would put the snapshot's sentence in front of an author who has no snapshot.
                detail = (
                    f"CPIC could not be asked whether it lists that drug ({unaskable[drug]}), so "
                    "whether the name is a typo or a real drug with no phenotype-keyed "
                    "recommendation is undetermined. The rest of the draft is unaffected and was "
                    "written; re-run to settle this line"
                )
            elif known is None:
                # Deliberately does NOT say "re-run without --offline": the route is snapshot-first,
                # so a provisioned cache is used whether or not --offline was passed, and advising a
                # flag that changes nothing is the same defect as the joinability warning telling a
                # GRCh37 author to re-run enrich.
                detail = (
                    "the CPIC snapshot's recommendation table has no row for it. That table only "
                    "names drugs that already have a phenotype-keyed recommendation, so this does "
                    "not establish whether CPIC knows the drug at all. Only the live API can answer "
                    "that, and it is consulted only when no snapshot is present"
                )
            else:
                detail = (
                    "CPIC lists the drug but records no single-gene, phenotype-keyed recommendation "
                    "for it — a guideline shaped as a dosing algorithm over several genes (warfarin) "
                    "has no row here"
                )
            warnings.append(f"{gene}: nothing drafted for {drug!r} — {detail}.")
            continue
        drug_rows, drug_warnings = _recommendation_rows(
            diplotypes, recommendations, population=population
        )
        warnings.extend(drug_warnings)
        diplotype_rows.extend(drug_rows)

    reports = [
        append_rows(spec_dir, csv_name, rows, dry_run=dry_run)
        for csv_name, rows in (
            ("haplotypes.csv", haplotypes),
            ("allele_function.csv", function_rows),
            ("diplotypes.csv", diplotype_rows),
        )
        if rows
    ]
    if not dry_run and reports:
        # A pass that consults a source must WRITE its `SourceRow`. This one did not, and of the three
        # providers it is the one where that matters most: CPIC is CC BY-SA **with a no-sale clause**,
        # so a module drafted from it and carrying no `sources.csv` leaves the compile gate nothing to
        # refuse on — the restriction simply disappears. Building the row and not writing it is the
        # exact `clingen.py` bug, and it was sitting in the newest provider.
        merge_sources_file(
            [CPIC_TERMS.row("annotation", declared_use=declared_use)],
            spec_dir,
            error=CpicError,
        )
    return PgxDraftResult(reports=reports, warnings=warnings)


def _is_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True

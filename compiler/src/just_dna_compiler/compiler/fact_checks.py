"""Checks over the derived fact tables: frequency and gene-metric arithmetic, literature, BA1, gene
validity currency, and the cross-checks against `variants.csv`.
"""

from collections.abc import Callable
from typing import Any

from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow, superseded_groups, undecidable_groups
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.overrides import (
    VINDICATING_OVERLAY_TABLE,
    classify_update_targets,
    classify_vindicated_answers,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import StudyRow, VariantRow, extract_pmids

from just_dna_compiler.compiler.load import table_citations
from just_dna_compiler.compiler.tables import BA1_ALLELE_FREQUENCY_THRESHOLD

# Relative tolerance for the float redundancy checks. These are published numbers rendered through a
# CSV, so exact equality is the wrong test; anything looser than this would stop catching real slips.
_REDUNDANCY_TOLERANCE: float = 1e-6


def _close(left: float, right: float, tolerance: float = _REDUNDANCY_TOLERANCE) -> bool:
    """Relative comparison that behaves at zero (where a relative test alone is meaningless)."""
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def _check_frequency_arithmetic(rows: list[FrequencyRow]) -> tuple[list[str], list[str]]:
    """Validate-by-redundancy over the frequency table's own numbers. Returns (errors, warnings).

    These columns are not independent — they constrain each other — so a violation is detectable with
    no reference at all, which is exactly the class of check a no-network tier can own. The compiler
    cannot know whether an allele count is *right*; it can know when a set of counts is *impossible*.

    Integer impossibilities are **errors** (exact arithmetic, so there is no tolerance argument to
    have, and a violation is corruption). Float relations are **warnings**: they hold on real data
    (verified against the recorded gnomAD payload), but they compare numbers a source computed on
    possibly-different denominators, and failing a good module over a rounding difference would be
    worse than the miss.
    """
    errors: list[str] = []
    warnings_out: list[str] = []
    for row in rows:
        where = f"frequencies.csv [{row.variant_key} / {row.population}]"
        ac, an, hom = row.allele_count, row.allele_number, row.homozygote_count
        if ac is not None and an is not None and ac > an:
            errors.append(
                f"{where}: allele_count {ac} exceeds allele_number {an} — a count cannot be larger "
                f"than its own denominator"
            )
        if ac is not None and hom is not None and 2 * hom > ac:
            errors.append(
                f"{where}: homozygote_count {hom} implies at least {2 * hom} alleles, but "
                f"allele_count is {ac} — each homozygote contributes two"
            )
        frequency = row.allele_frequency
        if row.faf95 is not None and frequency is not None and row.faf95 > frequency:  # noqa: SIM102
            # Separate layer on purpose: the outer asks whether it is above, this asks whether it is
            # above by more than float tolerance.
            if not _close(row.faf95, frequency):
                warnings_out.append(
                    CodedWarning(
                        "faf95_exceeds_frequency",
                        f"{where}: faf95 {row.faf95} exceeds the group's own allele frequency "
                        f"{frequency:.6g} — a 95% CI *lower bound* should sit at or below the point "
                        f"estimate, so these two numbers may not describe the same denominator",
                    )
                )
    return errors, warnings_out


def _check_gene_metrics_arithmetic(rows: list[GeneMetricsRow]) -> list[str]:
    """Validate-by-redundancy over the constraint table. Returns warnings.

    Two relations hold by definition and are therefore checkable without a reference: the observed/
    expected ratio must sit inside its own confidence interval, and it must equal `obs / exp` (on the
    recorded gnomAD payload it agrees to six decimal places for both BRCA1 and MYH7). Warnings rather
    than errors throughout: every value here is a float that has been through a CSV, and a constraint
    score is advisory to begin with.
    """
    warnings_out: list[str] = []
    for row in rows:
        where = f"gene_metrics.csv [{row.gene}]"
        lower, point, upper = row.oe_lof_lower, row.oe_lof, row.loeuf
        if None not in (lower, point, upper) and not lower <= point <= upper:
            warnings_out.append(
                CodedWarning(
                    "oe_lof_outside_interval",
                    f"{where}: oe_lof {point} lies outside its own interval [{lower}, {upper}] — the "
                    f"point estimate and the bounds may have come from different releases or columns",
                )
            )
        if row.obs_lof is not None and row.exp_lof and point is not None:
            derived = row.obs_lof / row.exp_lof
            if not _close(derived, point, 1e-4):
                warnings_out.append(
                    CodedWarning(
                        "oe_lof_disagrees_with_counts",
                        f"{where}: obs_lof/exp_lof is {derived:.6g} but oe_lof is {point} — these are the "
                        f"same quantity, so a disagreement means one of the three columns is mismapped",
                    )
                )
    return warnings_out


def _cross_check_frequencies(rows: list[FrequencyRow], variants: list[VariantRow]) -> list[str]:
    """Warn when a frequency row describes a coordinate no variant in the module sits at.

    Matched at *position* level (`chrom:start:ref`, no alt) rather than on `variant_key` equality: the
    sidecar is keyed per-allele while a module row may be position-only or multi-allelic, so key
    equality would false-alarm on rows that are in fact about the same locus. The same reasoning the
    study/variant orphan check already uses.
    """
    if not variants:
        return []
    positions = {derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None}
    if not positions:
        return []
    orphans = sorted(
        {
            f"{r.chrom}:{r.start}:{r.ref}"
            for r in rows
            if r.chrom is not None and derive_variant_key(None, r.chrom, r.start, r.ref) not in positions
        }
    )
    if not orphans:
        return []
    # One code across all five orphan checks. They are one finding — a fact row describing something
    # no variant in the module names — reached through five tables, and the fix is the same edit in
    # every one of them, so the sentence names the table and the code names the kind.
    return [
        CodedWarning(
            "derived_row_orphan",
            f"frequencies.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: "
            f"{orphans}",
        )
    ]


def _cross_check_literature(
    rows: list[LiteratureRow],
    studies: list[StudyRow],
    kind_rows: dict[str, list[Any]] | None = None,
) -> list[str]:
    """Two orphan directions, one finding that is not an orphan at all, and one licensing notice.

    * a literature row for a PMID **nothing in the module cites** — the sidecar is stale or over-broad
      (warning, the same reasoning as the frequency/gene-metrics orphan checks: an extra row is
      harmless);
    * a **nonexistent citation** (`exists is False`) — not an orphan but a defect in the module, and
      the compiler can surface it offline because the enricher already recorded the verdict as a fact;
    * a **quote lifted from an article whose licence forbids commercial reuse** (RM46).

    **Every citation site counts, and the set of them is derived rather than listed** (RM47, RM132).
    `studies.csv` was the only one until binning rows gained a `pmid`; `pharm_variants.csv` is the
    third. Reading fewer than all of them makes every citation from the site left out look like an
    orphan — shipping evidence the compiler then reports as stale, which is worse than the honest gap
    the column replaced. `table_citations` walks `_CITING_TABLE_KINDS`, so the *next* citing kind is
    read here by declaring the column and this docstring is the only thing that goes stale.

    Matched on digit-only PMIDs, since every `pmid` in the schema is free-form and may carry several
    ids or a `[PMID: N]` wrapper — `extract_pmids` is the same normalizer the enricher pass uses, so
    the sides cannot drift apart.

    **The non-commercial notice warns in both modes and gates nothing.** It is the third such
    exception, after the ClinVar `clin_sig` cross-check and `_check_declared_license_agrees`, and for
    the same reason: refusing would make the format arbitrate a copyright question. What it can
    honestly do is make the tension visible, because a `provenance_quote` is publisher text sitting in
    the module's own *annotation* layer — precisely where the licence gate bites — while the article's
    terms are recorded per article here and never as a `sources.csv` row. Grouped by licence rather
    than one line per citation, since a panel cites in the hundreds.
    """
    if not rows:
        return []
    findings: list[str] = []
    kept, dropped = split_cited_literature(rows, studies, kind_rows)

    missing = sorted({r.pmid for r in kept if r.exists is False})
    if missing:
        findings.append(
            CodedWarning(
                "citation_not_in_pubmed",
                f"literature.csv records {len(missing)} citation(s) PubMed has no record of: "
                f"{missing} — either the id is a typo or the article was retracted from the index; "
                f"the annotation resting on it should be re-examined either way",
            )
        )
    if dropped:
        findings.append(
            CodedWarning(
                "literature_row_uncited",
                f"literature.csv describes {len(dropped)} citation(s) no study, bin or pharm row in "
                f"this module cites: {sorted({r.pmid for r in dropped})} — left out of the artifact, "
                f"and left in the CSV, which is the pin that keeps a re-run cheap",
            )
        )
    findings.extend(_check_quoted_article_licenses(kept, studies))
    findings.extend(_check_quote_counter_is_current(kept, studies, kind_rows))
    return findings


def split_cited_literature(
    rows: list[LiteratureRow],
    studies: list[StudyRow],
    kind_rows: dict[str, list[Any]] | None = None,
) -> tuple[list[LiteratureRow], list[LiteratureRow]]:
    """`(kept, dropped)` — the literature rows this module actually cites, and the rest (RM79).

    **The compiler discards the rest; `literature.csv` keeps them.** A row describing a citation no
    study and no citing table row names is dead weight in the artifact: nothing joins to it, and it
    is only there
    because `literature.csv` is merge-not-clobber, so a citation the author has since deleted from
    `studies.csv` leaves its row behind. Keeping the row in the CSV is the point of that rule — it is
    the pin that makes a re-run cheap — and carrying it into the parquet and the manifest is a
    separate decision that nobody had taken deliberately.

    **What this settles.** `manifest.literature.missing_count` counted `exists is False` over *every*
    row in the table while the `citation_existence` verification record counted over the module's
    *current* citations, so the two disagreed in a published manifest with nothing wrong in the
    module. Both were honest about their own subject, which is what made it a decision rather than a
    bug. Filtering here makes them the same subject **by construction**, rather than documenting a
    discrepancy a reader would have to reconcile.

    **`cited` empty means discard nothing**, deliberately, and it is not the degenerate case it looks
    like: a module that cites nothing at all cannot distinguish "the sidecar is stale" from "the
    citations are not authored yet", and emptying its whole table on that reading would delete an
    enrichment pass's entire output. The `if cited` guard the orphan check already had is kept for the
    same reason it existed.

    **On the round trip.** `reverse_module` rebuilds `literature.csv` from the parquet, so a reversed
    copy carries the kept rows only. That is a deterministic narrowing rather than a P7 breach —
    `literature.csv` is a machine-written derived sidecar, not an authored value (the RM69 reading of
    Principle 7's letter) — and it **converges**: everything in the parquet is cited by construction,
    so lap two discards nothing and the signatures are a fixed point. The rows are recoverable the way
    every derived sidecar's are, by re-running the pass.
    """
    cited = cited_pmids(studies, kind_rows)
    if not cited:
        return list(rows), []
    kept = [r for r in rows if r.pmid in cited]
    return kept, [r for r in rows if r.pmid not in cited]


def cited_pmids(studies: list[StudyRow], kind_rows: dict[str, list[Any]] | None = None) -> set[str]:
    """Every PMID this module cites, from both citation sites, through the one normalizer.

    Extracted so RM137's reachability predicate asks the **same** question `split_cited_literature`
    answers, rather than a second statement of it. The two would drift silently and in the worst
    direction: the predicate would call a row unreachable that the drop had kept, so a healthy overlay
    would report a finding forever.

    **The empty case is the caller's to interpret, and it is not "nothing is cited".** A module citing
    nothing cannot distinguish a stale sidecar from citations not yet authored, so `split_cited_literature`
    discards nothing there — and the predicate must mirror that or every literature `update` on such a
    module reads as unreachable. `literature_target_survives` builds the mirror; nothing should test
    this set for emptiness on its own.
    """
    cited: set[str] = set()
    for study in studies:
        cited.update(extract_pmids(study.pmid))
    cited.update(table_citations(kind_rows or {}))
    return cited


def literature_target_survives(
    studies: list[StudyRow], kind_rows: dict[str, list[Any]] | None = None
) -> Callable[[str], bool]:
    """Can an artifact of this module carry a `literature.csv` row for this PMID? (RM137)

    True when the PMID is cited, because `split_cited_literature` keeps exactly the cited rows — and
    **True for everything when the module cites nothing at all**, which is that function's own guard
    reproduced rather than restated. Without the guard a module with no citations would mark every
    literature correction unreachable: a stable false positive, which is worse than the unstable true
    one RM137 is about.
    """
    cited = cited_pmids(studies, kind_rows)
    if not cited:
        return lambda pmid: True
    return lambda pmid: pmid in cited


def resolution_target_survives(
    variants: list[VariantRow], resolution_rows: list[ResolutionRow]
) -> Callable[[str], bool]:
    """Can an artifact of this module carry a `resolution.csv` row for this `variant_key`? (RM137)

    `resolution.csv` has no parquet, so `reverse_module` rebuilds it from the SNP core and
    `_write_resolution_csv` skips a row with no resolved position — *"rows without a resolved position
    carry no fact and are skipped"*. So the surviving set is the subjects this module can **place**.

    Computed from the authored coordinates and the injected table together, which is what makes it
    answer the same on both laps: on lap 1 the unpositioned row is present and its own cells say it is
    unpositioned; on lap 2 the row is gone and the authored side still says the same thing. Neither
    reading depends on the row being there to be matched.
    """
    placed: set[str] = {row.variant_key for row in resolution_rows if row.chrom and row.start is not None}
    placed.update(v.variant_key for v in variants if v.chrom and v.start is not None)
    return lambda subject: subject in placed


def _check_quote_counter_is_current(
    rows: list[LiteratureRow],
    studies: list[StudyRow],
    kind_rows: dict[str, list[Any]] | None = None,
) -> list[str]:
    """`literature.csv`'s `quotes_authored` against the quotes `studies.csv` actually carries (S56).

    **The sidecar can be stale in exactly the way that matters and nothing said so.** It is
    merge-not-clobber, so a literature pass that ran while `provenance_quote` was still empty wrote
    `quotes_authored=0` and every later run treated that row as authoritative. Four published modules
    are in that state — 3,668 authored quotes, every counter reading zero — and they compile green,
    because the two files sit in one spec directory and nothing compared them.

    Cheap and offline: the count is arithmetic over rows the compiler already holds open, and
    `LITERATURE_FACT_FIELDS` keeps `quotes_authored` out of the fact hash on the stated grounds that
    it *is derivable from `studies.csv`*. That is the argument for checking it here rather than
    trusting the stored copy.

    **A warning, not an error, and it names both numbers.** The sidecar being behind the table is a
    staleness signal rather than a malformed module, and a finding that says only "these disagree"
    leaves the author to work out which side to trust. Aggregated to one line, since a panel cites in
    the hundreds — the same rule the licence check above obeys.

    Reads every citation site and the same `extract_pmids` normalizer for the same reason
    `_cross_check_literature` does: a threshold-grounding `pmid` on a binning row and a claim-grounding
    one on a pharm row are both citations, and counting only `studies.csv` would report a current
    sidecar as stale on any module that grounds its rows where `studies.csv` cannot reach.
    """
    authored: dict[str, int] = {}
    for study in studies:
        if not (study.provenance_quote or study.provenance_regex):
            continue
        for pmid in extract_pmids(study.pmid):
            authored[pmid] = authored.get(pmid, 0) + 1
    # A bin or pharm row cites but carries no quote (`provenance_quote` deliberately did not follow
    # the column to either site), so it contributes a denominator of zero rather than being skipped: a
    # literature row reachable only from such a row must not read as "cited by nothing".
    # Through `table_citations`, which knows which kinds actually carry a `pmid` — walking
    # `kind_rows` directly reaches `DiplotypeRow`, which has no such column.
    for pmid in table_citations(kind_rows or {}):
        authored.setdefault(pmid, 0)

    stale = sorted(
        (row.pmid, row.quotes_authored or 0, authored.get(row.pmid, 0))
        for row in rows
        if (row.quotes_authored or 0) != authored.get(row.pmid, 0)
    )
    if not stale:
        return []
    return [
        CodedWarning(
            "quote_counter_stale",
            f"literature.csv's quotes_authored disagrees with studies.csv for {len(stale)} citation(s): "
            + ", ".join(
                f"pmid {pmid} records {recorded} but {counted} quote(s) cite it"
                for pmid, recorded, counted in stale
            )
            + " — the sidecar predates the quotes (it is merge-not-clobber, so a re-run keeps the old "
            "row); re-run the literature pass to bring the counters and quotes_found up to date",
        )
    ]


def _check_quoted_article_licenses(rows: list[LiteratureRow], studies: list[StudyRow]) -> list[str]:
    """Quotes taken from articles whose licence forbids commercial reuse (RM46). Warning-only.

    Keyed on the *quote*, not on the citation: naming a PMID costs nothing under any licence, while a
    `provenance_quote` / `provenance_regex` copies the publisher's own words into `studies.csv`, which
    is authored content the module ships. `commercial_use is False` is a recorded fact the enricher
    read off the article's licence; `None` is unknown and withholds, as everywhere else.

    Aggregated by licence string, one line per licence, because a repeated per-row warning buries
    every other finding a compile produces (the lesson CPIC taught four times).
    """
    quoted = {
        pmid
        for study in studies
        if study.provenance_quote or study.provenance_regex
        for pmid in extract_pmids(study.pmid)
    }
    if not quoted:
        return []
    by_license: dict[str, list[str]] = {}
    for row in rows:
        if row.commercial_use is False and row.pmid in quoted:
            by_license.setdefault(row.license or "an unnamed non-commercial licence", []).append(row.pmid)
    return [
        CodedWarning(
            "quoted_article_license_restrictive",
            f"{len(pmids)} study quote(s) come from article(s) licensed {license_name!r}, which "
            f"forbids commercial reuse: {sorted(pmids)}. Not adjudicated here — quoting for comment "
            f"or research is often fine and the format is not the tier that decides — but the "
            f"passage is publisher text in this module's annotation layer, so a commercial "
            f"distribution has to answer for it",
        )
        for license_name, pmids in sorted(by_license.items())
    ]


def _check_ba1_lint(
    rows: list[FrequencyRow],
    variants: list[VariantRow],
    *,
    threshold: float = BA1_ALLELE_FREQUENCY_THRESHOLD,
) -> list[str]:
    """Warn when a variant the module calls pathogenic is common in a general population.

    ACMG's **BA1** rule: an allele frequency above a threshold in a general population is *stand-alone*
    evidence that a variant is benign. Newly checkable only because `frequencies.csv` exists — before
    0.5 the compiler held no frequency to compare a `clin_sig` against.

    **Warning only, in both modes, and the threshold is overridable.** The 5% default is ACMG's, not a
    constant of nature: the right cutoff is disease-specific, and a common recessive carrier allele
    (sickle-cell's `rs334` sits around 4-5% in African-ancestry groups) legitimately lives near or above
    it. Failing a compile over that would be the format arbitrating a clinical judgement, which the
    data-agnostic charter forbids. What it *can* honestly do is make the tension visible.

    Which number: `faf95` when the sidecar carries one — that is the filtering allele frequency an ACMG
    filter actually uses, a 95% CI lower bound on the group with the highest frequency, and it is
    deliberately conservative. Otherwise the maximum per-group `allele_frequency`, which is the same
    quantity without the confidence discount. Matched at position level, like `_cross_check_frequencies`.
    """
    if not rows or not variants:
        return []
    pathogenic_at: dict[str, list[VariantRow]] = {}
    for variant in variants:
        if variant.chrom is None or not variant.effective_pathogenic:
            continue
        key = derive_variant_key(None, variant.chrom, variant.start, variant.ref)
        pathogenic_at.setdefault(key, []).append(variant)
    if not pathogenic_at:
        return []

    # Per allele, the strongest frequency evidence and where it came from.
    strongest: dict[tuple[str, str], tuple[float, str, str]] = {}
    for row in rows:
        if row.chrom is None or row.status == "not_found":
            continue
        key = derive_variant_key(None, row.chrom, row.start, row.ref)
        if key not in pathogenic_at:
            continue
        if row.faf95 is not None:
            candidate = (row.faf95, "faf95", row.population)
        elif row.allele_frequency is not None:
            candidate = (row.allele_frequency, "allele frequency", row.population)
        else:
            continue
        slot = (key, row.alt or "")
        # faf95 wins over a raw AF regardless of magnitude (it is the rule's own statistic); among
        # like measures the larger one is the one BA1 would be evaluated on.
        held = strongest.get(slot)
        if (
            held is None
            or (candidate[1] == "faf95" and held[1] != "faf95")
            or (candidate[1] == held[1] and candidate[0] > held[0])
        ):
            strongest[slot] = candidate

    findings: list[str] = []
    for (key, alt), (value, measure, population) in sorted(strongest.items()):
        if value <= threshold:
            continue
        for variant in pathogenic_at[key]:
            findings.append(
                CodedWarning(
                    "clin_sig_contradicts_frequency",
                    f"{variant.variant_key} genotype {variant.genotype}: clin_sig "
                    f"{variant.effective_clin_sig!r} but the {measure} of ALT {alt!r} in "
                    f"{population!r} is {value:.4g}, above the ACMG BA1 threshold of {threshold:.4g} — "
                    f"BA1 treats that as stand-alone evidence of benign impact. The threshold is "
                    f"disease-specific (a common recessive carrier allele sits above it legitimately), so "
                    f"this is a prompt to check, not a verdict.",
                )
            )
    return findings


def _cross_check_gene_metrics(rows: list[GeneMetricsRow], variants: list[VariantRow]) -> list[str]:
    """Warn when a gene-metrics row names a gene the module never mentions."""
    if not variants:
        return []
    genes = {v.gene for v in variants if v.gene}
    if not genes:
        return []
    orphans = sorted({r.gene for r in rows if r.gene not in genes})
    if not orphans:
        return []
    return [
        CodedWarning(
            "derived_row_orphan",
            f"gene_metrics.csv names {len(orphans)} gene(s) this module never mentions: {orphans}",
        )
    ]


def _classify_deferred_overlay_updates(
    deferred: dict[str, list[tuple[tuple[str, str], bool]]],
    studies: list[StudyRow],
    kind_rows: dict[str, list[Any]],
    variants: list[VariantRow],
    resolution_rows: list[ResolutionRow],
) -> list[str]:
    """Split each deferred unmatched set by whether the artifact could carry the row (RM137).

    One function so `validate_spec` and `compile_module` cannot classify differently — the predicates
    are the same objects, built from the same inputs, and the message text is the schema tier's.
    """
    findings: list[str] = []
    for table, targets in deferred.items():
        if not targets:
            continue
        if table == VINDICATING_OVERLAY_TABLE:
            # RM117. Not a reachability question: an unmatched answer here has ONE reading, and it is
            # the good one. Routed away from `classify_update_targets` entirely rather than given a
            # predicate, because the generic finding's "may be mistyped" is the wrong thing to put to
            # an author whose judgement the archive has just confirmed.
            findings.extend(classify_vindicated_answers(table, targets))
            continue
        if table == "literature.csv":
            survives = literature_target_survives(studies, kind_rows)
        elif table == "resolution.csv":
            survives = resolution_target_survives(variants, resolution_rows)
        else:  # pragma: no cover - only the deferred tables reach here
            survives = None
        findings.extend(classify_update_targets(table, targets, survives))
    return findings


def _check_gene_validity_currency(rows: list[GeneValidityRow]) -> list[str]:
    """Report a claim carrying several curations: which one is live, or that nothing says (RM108).

    ClinGen's `assertion_id` embeds the curation timestamp, so a re-curated assertion arrives under a
    different id, misses the merge key and is appended beside the row it replaces. The manifest then
    published `["definitive", "refuted"]` as a pair, and nothing anywhere said which was current.

    **Two findings, never one number**, because they ask a reader for different things: a superseded
    row is the archive having moved on, and an unorderable group is the archive not having said enough
    to tell. Both aggregate by kind with a count rather than printing per group, which is this
    workspace's standing rule for a repeated finding, and both name their groups in a bounded,
    deterministic list so the message is stable across recompiles.

    **A warning in BOTH modes, never a `strict` error.** `strict` means *reproducible artifact*, and a
    module carrying two curations of one claim is perfectly reproducible: the bytes are injected and
    the compile is deterministic. What the author can do about it is nothing — both rows are true
    records of what a curating body published, and deleting one would falsify the file rather than
    repair it. The rule this follows is the one `_vrs_coverage_warnings` and `frequencies`'
    `not_covered` already follow: **a finding no authored edit could clear is not a `strict` matter**,
    which is also why both codes are in `CARRIED_WARNING_CODES`.
    """
    findings: list[str] = []
    superseded = superseded_groups(rows)
    if superseded:
        findings.append(
            CodedWarning(
                "gene_validity_superseded",
                f"gene_validity.csv carries a later curation for {len(superseded)} gene-disease claim(s), "
                f"so an earlier row is superseded and kept: {_currency_group_names(superseded)}. Nothing is "
                f"deleted and nothing is wrong — the newest classification_date is read as current, both "
                f"rows stay so the drift is visible, and manifest.gene_validity.classifications publishes "
                f"the current one. A curating body re-curating is not an error in your module.",
            )
        )
    undecidable = undecidable_groups(rows)
    if undecidable:
        findings.append(
            CodedWarning(
                "gene_validity_currency_undecidable",
                f"gene_validity.csv carries several curations for {len(undecidable)} gene-disease claim(s) "
                f"and nothing orders them: {_currency_group_names(undecidable)}. Either two rows share a "
                f"classification_date or one states none, so no row is called current and none superseded "
                f"— every classification in those groups is published, which is the honest answer rather "
                f"than a winner picked from an identifier. Withheld deliberately, not skipped.",
            )
        )
    return findings


def _currency_group_names(groups: list[tuple]) -> str:
    """A bounded, ordered rendering of currency groups for a warning string.

    Capped at five with a count of the rest, the way every other aggregated finding here is: the
    message is a published field, so it must not grow with the table. `groups` already arrives in
    first-seen order, so this adds no ordering of its own.
    """
    shown = ", ".join("/".join(str(part) for part in group if part) for group in groups[:5])
    more = "" if len(groups) <= 5 else f" (+{len(groups) - 5} more)"
    return f"{shown}{more}"


def _cross_check_gene_validity(rows: list[GeneValidityRow], variants: list[VariantRow]) -> list[str]:
    """Warn when a gene-validity row names a gene the module never mentions (RM24).

    The gene-metrics orphan check with one table swapped, deliberately: the two sidecars answer
    different questions about the same key, so an over-broad table fails the same way and a reader
    should see the same sentence. Warning-only for the same reason — an extra row is harmless, and the
    compiler cannot tell a stale row from a curator's deliberate context.
    """
    if not variants:
        return []
    genes = {v.gene for v in variants if v.gene}
    if not genes:
        return []
    orphans = sorted({r.gene for r in rows if r.gene not in genes})
    if not orphans:
        return []
    return [
        CodedWarning(
            "derived_row_orphan",
            f"gene_validity.csv names {len(orphans)} gene(s) this module never mentions: {orphans}",
        )
    ]


def _cross_check_clinical_assertions(
    rows: list[ClinicalAssertionRow], variants: list[VariantRow]
) -> list[str]:
    """Warn when a clinical-assertion row describes a coordinate no variant in the module sits at.

    Matched at *position* level (`chrom:start:ref`, no alt), exactly as `_cross_check_frequencies`
    does and for its reason: the sidecar is per-allele while a module row may be position-only or
    multi-allelic, so comparing `variant_key` for equality would false-alarm on rows that are about
    the same locus.

    **It does not compare the calls.** Whether the module's own `clin_sig` agrees with the archive's
    is `enricher.clinical.verify_clin_sig`'s question, it needs a reference the compiler is barred
    from holding, and it warns in both modes on purpose because failing would make the format
    arbitrate a clinical dispute. Recording the archive's side in a table does not move that line, and
    a coherence check here must not quietly become the escalation that was parked.
    """
    if not variants:
        return []
    positions = {derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None}
    if not positions:
        return []
    orphans = sorted(
        {
            f"{r.chrom}:{r.start}:{r.ref}"
            for r in rows
            if r.chrom is not None and derive_variant_key(None, r.chrom, r.start, r.ref) not in positions
        }
    )
    if not orphans:
        return []
    return [
        CodedWarning(
            "derived_row_orphan",
            f"clinical_assertions.csv describes {len(orphans)} coordinate(s) no variant in this module "
            f"sits at: {orphans}",
        )
    ]


def _cross_check_clin_sig_concordance(rows: list, variants: list[VariantRow], *, table: str) -> list[str]:
    """Warn when a concordance row is about a subject no variant in the module carries.

    Matched on `variant_key` against the **authored** keys, which is `_cross_check_gwas_effects`'s
    rule and for its reason: comparing against expanded keys would let a one-to-many rsID report its
    own siblings.

    An orphan here means something narrower than it does on the sibling tables, and the difference is
    worth stating. This record is rewritten whole on every run rather than merged, so a row cannot
    survive a re-run of the check that produced it — an orphan can only mean `variants.csv` was
    narrowed since, and the remedy is to re-run rather than to edit anything. Warning-only in both
    modes, like every other over-broad sidecar.

    Serves both halves of the pair, which is why the table is a parameter: a detail row and a subject
    row go stale together and for the same reason, and two functions saying so differently is how the
    two spellings of one finding get reported as two findings.
    """
    if not variants or not rows:
        return []
    known = {v.variant_key for v in variants if v.variant_key}
    known |= {v.rsid for v in variants if v.rsid}
    if not known:
        return []
    orphans = sorted({r.variant_key for r in rows if r.variant_key not in known})
    if not orphans:
        return []
    return [
        CodedWarning(
            "derived_row_orphan",
            f"{table} records {len(orphans)} subject(s) no variant in this module carries: {orphans}. "
            f"The record is rebuilt whole on every run, so this means variants.csv was narrowed since "
            f"the comparison last ran — re-run it rather than editing the table.",
        )
    ]


def _cross_check_gwas_effects(rows: list[GwasEffectRow], variants: list[VariantRow]) -> list[str]:
    """Warn when a GWAS-effect row is about a locus no variant in the module carries.

    Matched on `variant_key`, not on position, and the difference from
    `_cross_check_clinical_assertions` is a property of the source rather than a preference: a
    `GwasEffectRow` carries no coordinates at all, because the Catalog's association payload has none
    (they sit on the SNP object behind a link). So the key the enricher wrote is the only thing to
    compare, and comparing it to the *authored* keys — before expansion — is what keeps a one-to-many
    rsID from reporting its own siblings.

    **Warning-only, in both modes.** An over-broad sidecar is the ordinary result of enriching a
    module and then narrowing its variant list, and it must not fail a compile that is otherwise fine.
    """
    if not variants or not rows:
        return []
    known = {v.variant_key for v in variants if v.variant_key}
    known |= {v.rsid for v in variants if v.rsid}
    if not known:
        return []
    orphans = sorted({r.variant_key for r in rows if r.variant_key not in known and r.rsid not in known})
    if not orphans:
        return []
    return [
        CodedWarning(
            "derived_row_orphan",
            f"gwas_effects.csv carries associations for {len(orphans)} identity(ies) no variant in this "
            f"module carries: {orphans}",
        )
    ]

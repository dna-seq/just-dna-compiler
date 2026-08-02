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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.draft import DraftReport, append_rows
from just_dna_format.pgx import STAR_ALLELE_PATTERN, AlleleFunctionRow, DiplotypeRow, HaplotypeRow

from just_dna_enricher.cpic import CpicClient, CpicDefiningVariant
from just_dna_enricher.licensing import CPIC_TERMS, check_declared_use

logger = logging.getLogger(__name__)

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
    for variant in variants:
        if variant.ambiguous or not variant.variant_allele:
            continue  # already reported by the client; nothing definite to write
        if not STAR_ALLELE_PATTERN.match(variant.allele or ""):
            warnings.append(
                f"{variant.gene}: {variant.allele!r} is not a star-allele string this format can "
                f"hold — skipped."
            )
            continue
        if variant.rsid is None and variant.start is None:
            warnings.append(
                f"{variant.gene} {variant.allele}: CPIC gives neither an rsID nor a position for a "
                f"defining variant — skipped, since a haplotype row with no locus resolves to nothing."
            )
            continue
        rows.append(
            HaplotypeRow(
                haplotype_name=variant.allele,
                rsid=variant.rsid,
                # CPIC positions are GRCh38 1-based; stored as-is (see the module docstring).
                start=variant.start,
                allele=variant.variant_allele,
                gene=variant.gene,
            )
        )
    return rows, warnings


def _split_diplotype(diplotype: str) -> Optional[tuple[str, str]]:
    parts = [p.strip() for p in diplotype.split(_DIPLOTYPE_SEP)]
    if len(parts) != 2 or not all(STAR_ALLELE_PATTERN.match(p) for p in parts):
        return None
    return parts[0], parts[1]


def draft_gene(
    spec_dir: Path,
    gene: str,
    *,
    declared_use: str = "unstated",
    dry_run: bool = False,
    client: Optional[CpicClient] = None,
) -> PgxDraftResult:
    """Draft one gene's `haplotypes.csv`, `allele_function.csv` and `diplotypes.csv` rows.

    Re-runnable and additive: call it once per gene, in any order, as a module grows. Rows already in
    the files are left exactly as they are.
    """
    skip_reason = check_declared_use(CPIC_TERMS, declared_use)
    if skip_reason:
        # Acquisition-time refusal: nothing is fetched, because the terms are accepted by taking it.
        return PgxDraftResult(warnings=[skip_reason], skipped=True)

    owned = client is None
    cpic = client or CpicClient()
    try:
        alleles = cpic.alleles_for_gene(gene)
        diplotypes = cpic.diplotypes_for_gene(gene)
        defining, defining_warnings = cpic.defining_variants(gene)
    finally:
        if owned:
            cpic.close()

    warnings = list(defining_warnings)
    haplotypes, haplotype_warnings = _haplotype_rows(defining)
    warnings.extend(haplotype_warnings)

    function_rows: list[AlleleFunctionRow] = []
    for allele in alleles:
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
    for entry in diplotypes:
        pair = _split_diplotype(entry.diplotype)
        if pair is None:
            warnings.append(
                f"{gene}: diplotype {entry.diplotype!r} is not a pair of star alleles — skipped."
            )
            continue
        if entry.phenotype is None:
            continue  # nothing to conclude; a row whose only content is the pair says nothing
        if entry.activity_score and not _is_numeric(entry.activity_score):
            # `"≥3.0"` is a bound, not a value. Reported so the author can bin it by hand rather than
            # having a fabricated number appear in their module.
            warnings.append(
                f"{gene} {entry.diplotype}: CPIC gives the activity score as {entry.activity_score!r}, "
                f"an inequality rather than a number — not carried; add a bin by hand if you need it."
            )
        diplotype_rows.append(
            DiplotypeRow(
                gene=entry.gene,
                haplotype_a=pair[0],
                haplotype_b=pair[1],
                phenotype=entry.phenotype,
                conclusion=f"{entry.gene} {entry.diplotype}: {entry.phenotype}",
            )
        )

    reports = [
        append_rows(spec_dir, csv_name, rows, dry_run=dry_run)
        for csv_name, rows in (
            ("haplotypes.csv", haplotypes),
            ("allele_function.csv", function_rows),
            ("diplotypes.csv", diplotype_rows),
        )
        if rows
    ]
    return PgxDraftResult(reports=reports, warnings=warnings)


def _is_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True
